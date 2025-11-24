#!/usr/bin/env python3
"""Migra do esquema antigo (forms/questions/options/submissions/answers) para o esquema v2:
- clients (id, external_id, nome, cpf, created_at)
- questions (id, ord, texto, tipo, opcoes (JSON), modo, obrigatoria)
- answers (id, client_id, question_id, resposta, created_at)

Uso: python scripts/migrate_to_v2.py
"""
import os
import sys
import json
from datetime import datetime

ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), '..'))
if ROOT not in sys.path:
    sys.path.insert(0, ROOT)

from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker

# modelos antigos
from models.models import Base as BaseOld, Form as OldForm, Question as OldQuestion, Option as OldOption, Submission as OldSubmission, Answer as OldAnswer
# novos modelos
from models.models_v2 import Base as BaseV2, Client, Question, Answer

DB_PATH = os.path.join('data', 'forms.db')

def main():
    engine = create_engine(f"sqlite:///{DB_PATH}")
    Session = sessionmaker(bind=engine)

    # cria tabelas v2 se necessário
    BaseV2.metadata.create_all(engine)

    with Session() as s:
        # mapar perguntas existentes
        question_map = {}  # old_question_id -> new_question_id
        # Como o app suporta apenas um formulário, migramos todas as perguntas encontradas
        forms = s.query(OldForm).all()
        next_ord = 1
        for form in forms:
            for old_q in form.perguntas:
                texto = old_q.texto
                # parse tipo que pode ser JSON ou string
                modo = None
                obrigatoria = 0
                tipo_normal = old_q.tipo
                try:
                    if isinstance(old_q.tipo, str) and old_q.tipo.strip().startswith('{'):
                        parsed = json.loads(old_q.tipo)
                        tipo_normal = parsed.get('tipo', 'subjetiva')
                        modo = parsed.get('modo')
                        obrigatoria = 1 if parsed.get('obrigatoria') else 0
                except Exception:
                    tipo_normal = old_q.tipo

                # coletar opções
                opcoes = [o.texto for o in old_q.opcoes]
                opcoes_json = json.dumps(opcoes, ensure_ascii=False)

                new_q = Question(ord=next_ord, texto=texto, tipo=tipo_normal or 'subjetiva', opcoes=opcoes_json if opcoes else None, modo=modo, obrigatoria=obrigatoria)
                s.add(new_q)
                s.flush()
                question_map[old_q.id] = new_q.id
                next_ord += 1
        s.commit()

        # migrar submissions -> clients e answers
        submissions = s.query(OldSubmission).all()
        client_map = {}  # old_submission_id -> new_client_id
        for sub in submissions:
            # tenta extrair nome e cpf a partir das respostas ligadas
            answers = {a.question_id: a for a in sub.answers}
            nome = None
            cpf = None
            # procurar por perguntas com texto 'Nome' e 'CPF'
            for old_q_id, new_q_id in question_map.items():
                q = s.query(OldQuestion).get(old_q_id)
                if not q:
                    continue
                text = (q.texto or '').strip().lower()
                ans = answers.get(old_q_id)
                if not ans:
                    continue
                if 'nome' == text:
                    nome = ans.resposta
                if 'cpf' == text:
                    cpf = ans.resposta
            client = Client(external_id=sub.id, nome=nome, cpf=cpf, created_at=sub.created_at)
            s.add(client)
            s.flush()
            client_map[sub.id] = client.id
        s.commit()

        # migrar respostas
        old_answers = s.query(OldAnswer).all()
        migrated = 0
        for oa in old_answers:
            # localizar novo question id
            new_q_id = question_map.get(oa.question_id)
            if not new_q_id:
                # tentar achar por texto
                old_q = s.query(OldQuestion).get(oa.question_id)
                if old_q:
                    # procurar new question with same text
                    candidate = s.query(Question).filter(Question.texto == old_q.texto).first()
                    if candidate:
                        new_q_id = candidate.id
            if not new_q_id:
                # pular se não conseguimos mapear
                continue
            # mapear client via submission id
            client_id = client_map.get(oa.submission_id)
            if not client_id:
                # cria client genérico
                client = Client(external_id=oa.submission_id, nome=None, cpf=None)
                s.add(client)
                s.flush()
                client_id = client.id
                client_map[oa.submission_id] = client_id
            new_ans = Answer(client_id=client_id, question_id=new_q_id, resposta=oa.resposta, created_at=None)
            s.add(new_ans)
            migrated += 1
        s.commit()

        print(f'Migração concluída: {len(question_map)} perguntas, {len(client_map)} clientes criados, {migrated} respostas migradas.')


if __name__ == '__main__':
    main()
