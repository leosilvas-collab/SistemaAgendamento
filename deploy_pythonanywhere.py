"""Configuração da demonstração pública no PythonAnywhere."""
import os
os.environ["MARCIA_OWNER_EMAIL"]="leocladison@leocladison.com"
from flask import jsonify, request
from app import app as application
application.config["TRUSTED_HOSTS"]=["leocladison.pythonanywhere.com"]
@application.before_request
def proteger_ativacao_publica():
    if request.path=="/api/acesso/ativar":
        return jsonify({"mensagem":"Nesta demonstração publicada, a definição de senha é realizada pelo proprietário no console."}),403
    if request.path=="/api/status-banco":
        return jsonify({"mensagem":"Use /health para verificar a disponibilidade."}),403
