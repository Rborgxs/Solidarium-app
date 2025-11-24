#!/usr/bin/env python3
"""Migra `data/formularios.json` e `data/respostas.csv` para o banco SQLite `data/forms.db`.

Uso:
  python scripts/migrate_to_db.py [--overwrite]

Por padrão não sobrescreve formulários já existentes no DB; use --overwrite para forçar.
"""
import os
import json
import csv
import argparse
import uuid
from datetime import datetime

from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
import sys

# Garante que o diretório raiz do projeto está no path para permitir imports relativos
ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), '..'))
if ROOT not in sys.path:
    sys.path.insert(0, ROOT)

# importa modelos
from models.models import Base, Form, Question, Option, Submission, Answer

DB_PATH = os.path.join('data', 'forms.db')
FORM_JSON = os.path.join('data', 'formularios.json')
RESPOSTAS_CSV = os.path.join('data', 'respostas.csv')


def parse_args():
    p = argparse.ArgumentParser()
    p.add_argument('--overwrite', action='store_true', help='Sobrescrever formulários existentes no DB')
    return p.parse_args()


def load_forms_json(path):
    if not os.path.exists(path):
        print(f'Arquivo {path} não encontrado — nenhum formulário para migrar.')
        return {}
    with open(path, 'r', encoding='utf-8') as f:
        try:
            data = json.load(f)
            if isinstance(data, dict):
                return data
            else:
                print('Formato inesperado em formularios.json — esperado um objeto/dicionário.')
                return {}
        except Exception as e:
            print('Erro ao ler formularios.json:', e)
            return {}


def migrate_forms(session, forms_data, overwrite=False):
    created = 0
    skipped = 0
    for fid, form in forms_data.items():
        try:
            fid_int = int(fid)
        except Exception:
            # gera um id novo
            fid_int = None
        existing = None
        if fid_int is not None:
            existing = session.get(Form, fid_int)
        if existing and not overwrite:
            skipped += 1
            print(f'Skipping existing form id={fid_int} (use --overwrite to replace)')
            continue
        if existing and overwrite:
            print(f'Overwriting form id={fid_int}')
            session.delete(existing)
            session.commit()
        titulo = form.get('titulo') or form.get('title') or f'Form {fid}'
        if fid_int is not None:
            f = Form(id=fid_int, titulo=titulo)
        else:
            f = Form(titulo=titulo)
        session.add(f)
        session.flush()
        perguntas = form.get('perguntas') or form.get('questions') or []
        for idx, p in enumerate(perguntas, start=1):
            texto = p.get('texto') or p.get('text') or ''
            tipo = p.get('tipo') or p.get('type') or 'subjetiva'
            q = Question(form_id=f.id, ord=idx, texto=texto, tipo=tipo)
            session.add(q)
            session.flush()
            opcoes = p.get('opcoes') or p.get('options') or []
            for op in opcoes:
                opt = Option(question_id=q.id, texto=op)
                session.add(opt)
        session.commit()
        created += 1
    return created, skipped


def migrate_answers(session, csv_path):
    if not os.path.exists(csv_path):
        print(f'Arquivo {csv_path} não encontrado — nada para migrar de CSV.')
        return 0, 0
    created = 0
    orphan_answers = 0
    with open(csv_path, 'r', newline='', encoding='utf-8') as f:
        reader = csv.DictReader(f)
        # detect possible headers if legacy
        headers = reader.fieldnames or []
        for row in reader:
            # normalize keys
            form_id = row.get('formulario_id') or row.get('form_id') or row.get('form')
            if not form_id:
                continue
            # find or create submission
            submission_id = row.get('submission_id') or row.get('sid') or ''
            if not submission_id:
                submission_id = uuid.uuid4().hex
            created_at_raw = row.get('created_at') or row.get('created') or ''
            created_at = None
            if created_at_raw:
                try:
                    created_at = datetime.fromisoformat(created_at_raw)
                except Exception:
                    try:
                        created_at = datetime.strptime(created_at_raw, '%Y-%m-%d %H:%M:%S')
                    except Exception:
                        created_at = None
            pergunta_text = row.get('pergunta') or row.get('question') or ''
            resposta_text = row.get('resposta') or row.get('answer') or ''

            # ensure form exists
            try:
                fid_int = int(form_id)
            except Exception:
                print('formulario_id invalido:', form_id)
                continue
            form = session.get(Form, fid_int)
            if not form:
                print(f'Form id={fid_int} not found in DB — skipping answer for pergunta="{pergunta_text}"')
                orphan_answers += 1
                continue
            # find or create submission
            sub = session.get(Submission, submission_id)
            if not sub:
                sub = Submission(id=submission_id, form_id=form.id)
                if created_at:
                    sub.created_at = created_at
                session.add(sub)
                session.flush()
            # find question by text
            q = None
            for question in form.perguntas:
                if (question.texto or '').strip() == (pergunta_text or '').strip():
                    q = question
                    break
            if not q:
                # cria uma pergunta nova como subjetiva
                max_ord = max([q.ord for q in form.perguntas] or [0])
                q = Question(form_id=form.id, ord=max_ord + 1, texto=pergunta_text or 'Pergunta migrada', tipo='subjetiva')
                session.add(q)
                session.flush()
                print(f'Criada pergunta nova id={q.id} para formulário {form.id} com texto="{pergunta_text}"')
            # cria resposta
            ans = Answer(submission_id=sub.id, question_id=q.id, resposta=resposta_text)
            session.add(ans)
            session.commit()
            created += 1
    return created, orphan_answers


def main():
    args = parse_args()
    os.makedirs('data', exist_ok=True)
    engine = create_engine(f"sqlite:///{DB_PATH}")
    Session = sessionmaker(bind=engine)
    # ensure tables exist
    Base.metadata.create_all(engine)

    forms = load_forms_json(FORM_JSON)
    with Session() as session:
        created, skipped = migrate_forms(session, forms, overwrite=args.overwrite)
        print(f'Formulários migrados: {created}, ignorados: {skipped}')
        ans_created, orphan = migrate_answers(session, RESPOSTAS_CSV)
        print(f'Respostas migradas: {ans_created}, respostas ignoradas por formulário ausente: {orphan}')


if __name__ == '__main__':
    main()
