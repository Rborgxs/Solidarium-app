from flask import Flask, render_template, request, redirect, url_for, send_file, jsonify
from collections import defaultdict
import csv
import io
import json

app = Flask(__name__)

# Estruturas de dados para armazenar os formulários e respostas
formularios = {}  # {id_formulario: {"titulo": str, "perguntas": [pergunta_dicts]}}
respostas = defaultdict(list)  # {id_formulario: [resposta_dicts]}

# Contador simples de IDs
id_counter = {"formulario": 1}


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

                # Se objetiva, forçar modo múltipla escolha
                pergunta = {
                    "texto": texto,
                    "tipo": tipo,
                    "modo": "multipla",  # sempre múltipla escolha
                    "opcoes": opcoes,
                    "obrigatoria": obrigatoria
                }
                perguntas.append(pergunta)

            formulario_id = id_counter["formulario"]
            id_counter["formulario"] += 1
            formularios[formulario_id] = {"titulo": titulo, "perguntas": perguntas}

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
    return redirect(url_for("listar_formularios"))


@app.route("/formulario/<int:formulario_id>/responder", methods=["GET", "POST"])
def responder_formulario(formulario_id):
    if formulario_id not in formularios:
        return "Formulário não encontrado", 404

    formulario = formularios[formulario_id]

    if request.method == "POST":
        resposta = {}
        for idx, q in enumerate(formulario["perguntas"], start=1):
            key = f"pergunta_{idx}"
            if q["tipo"] == "objetiva":
                resposta[key] = request.form.getlist(key)
            else:
                resposta[key] = request.form.get(key, "")
        respostas[formulario_id].append(resposta)
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

        # Cabeçalho
        header = [f"Pergunta {i+1}" for i in range(len(formulario["perguntas"]))]
        writer.writerow(header)

        # Respostas
        for r in respostas_form:
            row = [", ".join(r.get(f"pergunta_{i+1}", [])) if isinstance(r.get(f"pergunta_{i+1}"), list) else r.get(f"pergunta_{i+1}", "") for i in range(len(formulario["perguntas"]))]
            writer.writerow(row)

        output = io.BytesIO()
        output.write(si.getvalue().encode("utf-8"))
        output.seek(0)
        return send_file(output, mimetype="text/csv", as_attachment=True, download_name=f"{formulario['titulo']}.csv")

    elif formato == "json":
        return jsonify(respostas_form)

    else:
        return "Formato não suportado", 400


if __name__ == "__main__":
    app.run(debug=True)
