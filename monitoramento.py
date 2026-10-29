"""Sonda de saúde e painel visual; nenhuma informação de clientes é exposta."""
from flask import jsonify, render_template
from sqlalchemy import text


def registrar_monitoramento(app, obter_sessao):
    @app.get("/health")
    def health():
        try:
            with obter_sessao() as sessao:
                sessao.execute(text("SELECT 1"))
            resposta = jsonify({"status":"ok","banco":"ok"})
        except Exception:
            resposta = jsonify({"status":"indisponivel","banco":"offline"})
            resposta.status_code = 503
        resposta.headers["Cache-Control"] = "no-store"
        return resposta

    @app.get("/monitoramento")
    def painel_monitoramento():
        return render_template("monitoramento.html"), 200, {"Cache-Control":"no-store"}
