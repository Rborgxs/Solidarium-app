from flask import Flask, render_template, request, redirect, url_for, send_file, jsonify, send_from_directory
from collections import defaultdict
import csv
import io
import json
import os
import uuid
from werkzeug.utils import secure_filename
import shutil

app = Flask(__name__)
app.config.setdefault('MAX_CONTENT_LENGTH', 16 * 1024 * 1024)  # 16 MB
UPLOAD_FOLDER = os.path.join('data', 'uploads')
os.makedirs(UPLOAD_FOLDER, exist_ok=True)
ALLOWED_EXTENSIONS = {'.png', '.jpg', '.jpeg', '.gif', '.webp'}


def allowed_file(filename: str) -> bool:
    if not filename:
        return False
    _, ext = os.path.splitext(filename.lower())
    return ext in ALLOWED_EXTENSIONS

formularios = {}
respostas = defaultdict(list)

id_counter = {"formulario": 1}


FORMS_JSON = os.path.join('data', 'formularios.json')


def save_forms():
    os.makedirs('data', exist_ok=True)
    # JSON requires string keys
    serial = {str(k): v for k, v in formularios.items()}
    with open(FORMS_JSON, 'w', encoding='utf-8') as f:
        json.dump(serial, f, ensure_ascii=False, indent=2)


def load_forms():
    if not os.path.exists(FORMS_JSON):
        return
    try:
        with open(FORMS_JSON, 'r', encoding='utf-8') as f:
            data = json.load(f)
        formularios.clear()
        max_id = 0
        for k, v in data.items():
            try:
                ik = int(k)
            except Exception:
                continue
            formularios[ik] = v
            max_id = max(max_id, ik)
        if max_id >= id_counter.get('formulario', 1):
            id_counter['formulario'] = max_id + 1
    except Exception:
        pass


# load forms at startup
load_forms()



def load_responses_for_form(formulario_id):
    """Carrega respostas salvas em JSON (se existir) para o formulário na memória."""
    path = os.path.join('data', f'respostas_{formulario_id}.json')
    if not os.path.exists(path):
        return
    try:
        with open(path, 'r', encoding='utf-8') as f:
            entries = json.load(f)
        # entradas já possuem URL para imagens (quando salvos), mas mantemos a mesma estrutura
        respostas[formulario_id] = entries
    except Exception:
        # falha ao carregar -> ignorar
        return


# carregar respostas salvas para cada formulário presente
for fid in list(formularios.keys()):
    try:
        load_responses_for_form(fid)
    except Exception:
        pass

@app.route("/")
def index():
    return redirect(url_for("listar_formularios"))


@app.route("/formularios")
def listar_formularios():
    return render_template("generated_form.html", formularios=formularios)


@app.route("/formulario/criar", methods=["GET", "POST"])
def criar_formulario():
    titulo = ""
    qtd_perguntas = 0

    if request.method == "POST":
        if "confirm_qtd" in request.form:
            titulo = request.form.get("titulo", "")
            qtd_perguntas = int(request.form.get("qtd_perguntas", 0))
            return render_template(
                "formulario.html",
                titulo=titulo,
                qtd_perguntas=qtd_perguntas
            )

        elif "submit_form" in request.form:
            titulo = request.form.get("titulo", "")
            qtd_perguntas = int(request.form.get("qtd_perguntas", 0))
            perguntas = []

            for i in range(1, qtd_perguntas + 1):
                texto = request.form.get(f"pergunta_{i}", "")
                tipo = request.form.get(f"tipo_{i}", "subjetiva")
                opcoes_raw = request.form.get(f"opcoes_{i}", "")
                obrigatoria = bool(request.form.get(f"obrigatoria_{i}", False))
                opcoes = [o.strip() for o in opcoes_raw.splitlines() if o.strip()]

                pergunta = {
                    "texto": texto,
                    "tipo": tipo,
                    "modo": "multipla" if tipo == "objetiva" else None,
                    "opcoes": opcoes,
                    "obrigatoria": obrigatoria
                }
                perguntas.append(pergunta)

            formulario_id = id_counter["formulario"]
            id_counter["formulario"] += 1
            formularios[formulario_id] = {"titulo": titulo, "perguntas": perguntas}

            # persistir formulários em disco
            try:
                save_forms()
            except Exception:
                pass

            return redirect(url_for("listar_formularios"))

    return render_template("formulario.html", titulo=titulo, qtd_perguntas=qtd_perguntas)


@app.route("/formulario/<int:formulario_id>/editar", methods=["GET", "POST"])
def editar_formulario(formulario_id):
    if formulario_id not in formularios:
        return "Formulário não encontrado", 404

    formulario = formularios[formulario_id]

    if request.method == "POST":
        titulo = request.form.get("titulo", "")
        perguntas = []

        for idx, q in enumerate(formulario["perguntas"], start=1):
            texto = request.form.get(f"pergunta_{idx}", "")
            tipo = request.form.get(f"tipo_{idx}", "subjetiva")
            opcoes_raw = request.form.get(f"opcoes_{idx}", "")
            obrigatoria = bool(request.form.get(f"obrigatoria_{idx}", False))
            opcoes = [o.strip() for o in opcoes_raw.splitlines() if o.strip()]

            pergunta = {
                "texto": texto,
                "tipo": tipo,
                "modo": "multipla" if tipo == "objetiva" else None,
                "opcoes": opcoes,
                "obrigatoria": obrigatoria
            }
            perguntas.append(pergunta)

        formulario["titulo"] = titulo
        formulario["perguntas"] = perguntas

        # salvar alterações
        try:
            save_forms()
        except Exception:
            pass

        return redirect(url_for("listar_formularios"))

    return render_template(
        "editar_formulario.html",
        formulario_id=formulario_id,
        titulo=formulario["titulo"],
        perguntas=formulario["perguntas"]
    )


@app.route("/formulario/<int:formulario_id>/excluir", methods=["POST"])
def excluir_formulario(formulario_id):
    if formulario_id in formularios:
        formularios.pop(formulario_id)
        respostas.pop(formulario_id, None)
        # remover arquivos de respostas (.json, .csv) e pasta de uploads do formulário
        try:
            json_path = os.path.join('data', f'respostas_{formulario_id}.json')
            csv_path = os.path.join('data', f'respostas_{formulario_id}.csv')
            if os.path.exists(json_path):
                os.remove(json_path)
            if os.path.exists(csv_path):
                os.remove(csv_path)
            upload_dir = os.path.join(UPLOAD_FOLDER, f'form_{formulario_id}')
            if os.path.exists(upload_dir) and os.path.isdir(upload_dir):
                shutil.rmtree(upload_dir)
        except Exception:
            pass

        try:
            save_forms()
        except Exception:
            pass
    return redirect(url_for("listar_formularios"))


@app.route("/formulario/<int:formulario_id>/responder", methods=["GET", "POST"])
def responder_formulario(formulario_id):
    if formulario_id not in formularios:
        return "Formulário não encontrado", 404

    formulario = formularios[formulario_id]

    if request.method == "POST":
        nome = request.form.get("nome", "")
        cpf = request.form.get("cpf", "")

        # Validação: CPF obrigatório
        if not cpf or not str(cpf).strip():
            return render_template("respostas_formulario.html", formulario=formulario, error="CPF obrigatório")

        resposta = {}
        for idx, q in enumerate(formulario["perguntas"], start=1):
            key = f"pergunta_{idx}"
            if q["tipo"] == "objetiva":
                resposta[key] = request.form.getlist(key)
            elif q["tipo"] == "imagem":
                file_field = f"{key}_file"
                file = request.files.get(file_field)
                if file and file.filename:
                    if allowed_file(file.filename):
                        form_folder = os.path.join(UPLOAD_FOLDER, f"form_{formulario_id}")
                        os.makedirs(form_folder, exist_ok=True)
            
                        filename = secure_filename(file.filename)
                        unique_name = f"{uuid.uuid4().hex}_{filename}"
                        save_path = os.path.join(form_folder, unique_name)
                        file.save(save_path)

                        resposta[key] = {
                            "caminho": f"form_{formulario_id}/{unique_name}",
                            "tipo": "imagem"
                        }
                    else:
                        resposta[key] = ""
                else:
                    resposta[key] = ""
            else:
                resposta[key] = request.form.get(key, "")

        # armazenar como objeto com dados do cliente e respostas
        entry = {
            "cliente": {"nome": nome, "cpf": cpf},
            "respostas": resposta
        }
        respostas[formulario_id].append(entry)

        # Persistir em disco: JSON e CSV para este formulário
        try:
            save_responses_json(formulario_id)
        except Exception:
            pass
        try:
            save_responses_csv(formulario_id)
        except Exception:
            pass

        return render_template("confirmacao.html")

    return render_template(
        "respostas_formulario.html",
        formulario=formulario
    )


@app.route("/formulario/<int:formulario_id>/exportar/<string:formato>")
def exportar_respostas(formulario_id, formato):
    if formulario_id not in formularios:
        return "Formulário não encontrado", 404

    formulario = formularios[formulario_id]
    respostas_form = respostas.get(formulario_id, [])

    if formato == "csv":
        si = io.StringIO()
        writer = csv.writer(si)

        # incluir colunas de cliente e texto completo das perguntas
        header = ["Nome", "CPF"] + [q.get("texto", f"Pergunta {i+1}") for i, q in enumerate(formulario["perguntas"])]
        writer.writerow(header)

        for r in respostas_form:
            cliente = r.get("cliente", {}) if isinstance(r, dict) else {}
            nome = cliente.get("nome", "")
            cpf = cliente.get("cpf", "")
            row_resps = []
            for i in range(len(formulario["perguntas"])):
                val = r.get("respostas", {}).get(f"pergunta_{i+1}")
                if isinstance(val, dict) and "caminho" in val:
                    # É um upload com caminho e URL
                    cell = val.get("caminho", "")
                elif isinstance(val, list):
                    cell = ", ".join(val)
                elif isinstance(val, str) and val.startswith("form_"):
                    # caminho relativo salvo para o upload
                    cell = val
                else:
                    cell = val or ""
                row_resps.append(cell)
            row = [nome, cpf] + row_resps
            writer.writerow(row)

        output = io.BytesIO()
        output.write(si.getvalue().encode("utf-8"))
        output.seek(0)
        return send_file(output, mimetype="text/csv", as_attachment=True, download_name=f"{formulario['titulo']}.csv")

    elif formato == "json":
        # retornar JSON com URLs externas para uploads
        entries = []
        for entry in respostas_form:
            new_entry = {
                'cliente': dict(entry.get('cliente', {})) if isinstance(entry, dict) else {},
                'respostas': {}
            }
            for k, v in entry.get('respostas', {}).items():
                if isinstance(v, str) and v.startswith('form_'):
                    try:
                        new_entry['respostas'][k] = url_for('uploaded_file', filename=v, _external=True)
                    except Exception:
                        new_entry['respostas'][k] = v
                else:
                    new_entry['respostas'][k] = v
            entries.append(new_entry)
        return jsonify(entries)

    else:
        return "Formato não suportado", 400


@app.route('/formulario/<int:formulario_id>/respostas')
def visualizar_respostas(formulario_id):
    """Página HTML que mostra todas as respostas com thumbnails (quando houver)."""
    if formulario_id not in formularios:
        return "Formulário não encontrado", 404

    formulario = formularios[formulario_id]
    respostas_form = respostas.get(formulario_id, [])

    # construir lista com URLs completas para imagens e caminhos
    entries = []
    for entry in respostas_form:
        cliente = entry.get('cliente', {}) if isinstance(entry, dict) else {}
        resp = {}
        for k, v in entry.get('respostas', {}).items():
            if isinstance(v, dict) and "caminho" in v:
                # É um upload com caminho relativo
                resp[k] = {
                    'caminho': v.get('caminho'),
                    'url': url_for('uploaded_file', filename=v.get('caminho'), _external=True)
                }
            elif isinstance(v, str) and v.startswith('form_'):
                # Caminho relativo como string (compatibilidade)
                resp[k] = {
                    'caminho': v,
                    'url': url_for('uploaded_file', filename=v, _external=True)
                }
            else:
                resp[k] = v
        entries.append({'cliente': cliente, 'respostas': resp})

    return render_template('visualizar_respostas.html', formulario=formulario, entries=entries)


def save_responses_json(formulario_id):
    os.makedirs('data', exist_ok=True)
    path = os.path.join('data', f'respostas_{formulario_id}.json')
    entries = []
    for entry in respostas.get(formulario_id, []):
        new_entry = {
            'cliente': dict(entry.get('cliente', {})) if isinstance(entry, dict) else {},
            'respostas': {}
        }
        for k, v in entry.get('respostas', {}).items():
            if isinstance(v, str) and v.startswith('form_'):
                new_entry['respostas'][k] = {
                    'caminho': v,
                    'tipo': 'imagem'
                }
            else:
                new_entry['respostas'][k] = v
        entries.append(new_entry)

    with open(path, 'w', encoding='utf-8') as f:
        json.dump(entries, f, ensure_ascii=False, indent=2)


def save_responses_csv(formulario_id):
    """Grava as respostas em CSV com colunas Nome, CPF, Pergunta 1, ..."""
    os.makedirs('data', exist_ok=True)
    formulario = formularios.get(formulario_id)
    if not formulario:
        return

    path = os.path.join('data', f'respostas_{formulario_id}.csv')

    with open(path, 'w', newline='', encoding='utf-8') as f:
        writer = csv.writer(f)
        header = ['Nome', 'CPF'] + [q.get("texto", f"Pergunta {i+1}") for i, q in enumerate(formulario['perguntas'])]
        writer.writerow(header)

        for r in respostas.get(formulario_id, []):
            cliente = r.get('cliente', {}) if isinstance(r, dict) else {}
            nome = cliente.get('nome', '')
            cpf = cliente.get('cpf', '')
            row_resps = []
            for i in range(len(formulario['perguntas'])):
                val = r.get('respostas', {}).get(f'pergunta_{i+1}')
                if isinstance(val, dict) and "caminho" in val:
                    # É um upload com caminho
                    cell = val.get("caminho", "")
                elif isinstance(val, list):
                    cell = ', '.join(val)
                elif isinstance(val, str) and val.startswith('form_'):
                    cell = val
                else:
                    cell = val or ''
                row_resps.append(cell)
            row = [nome, cpf] + row_resps
            writer.writerow(row)
            row = [nome, cpf] + row_resps
            writer.writerow(row)


@app.route('/uploads/<path:filename>')
def uploaded_file(filename):
    safe_path = os.path.normpath(filename)
    if safe_path.startswith('..') or os.path.isabs(safe_path) or '..' in safe_path.split(os.path.sep):
        return "Caminho inválido", 400
    return send_from_directory(UPLOAD_FOLDER, safe_path)


@app.route('/download/<path:filename>')
def download_file(filename):
    """Rota para baixar arquivos da pasta uploads."""
    safe_path = os.path.normpath(filename)
    if safe_path.startswith('..') or os.path.isabs(safe_path) or '..' in safe_path.split(os.path.sep):
        return "Caminho inválido", 400
    return send_from_directory(UPLOAD_FOLDER, safe_path, as_attachment=True)


if __name__ == "__main__":
    app.run(debug=True)
