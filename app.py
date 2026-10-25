from flask import Flask, jsonify
from models import session, Cliente, Agendamento

app = Flask(__name__)

@app.route('/')
def home():
    return jsonify({
        "status": "online",
        "sistema": "Studio Marcia Nails",
        "mensagem": "Servidor da VPS rodando com sucesso!"
    })

@app.route('/api/status-banco')
def status_banco():
    try:
        total_clientes = session.query(Cliente).count()
        total_agendamentos = session.query(Agendamento).count()
        return jsonify({
            "banco": "conectado",
            "total_clientes": total_clientes,
            "total_agendamentos": total_agendamentos
        })
    except Exception:
        app.logger.exception("Falha ao consultar o status do banco de dados.")
        return jsonify({
            "banco": "erro",
            "mensagem": "Não foi possível consultar o banco de dados.",
        }), 500

if __name__ == '__main__':
    app.run(host='0.0.0.0', port=5000)
