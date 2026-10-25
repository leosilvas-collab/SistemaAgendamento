from datetime import date, datetime, time

from flask import Flask, jsonify, request

from agenda import DURACAO_MINUTOS, horarios_disponiveis
from models import session, Session, Cliente, Agendamento

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


@app.route('/api/horarios')
def consultar_horarios():
    datas = request.args.getlist("data")
    try:
        if len(datas) != 1:
            raise ValueError
        dia = date.fromisoformat(datas[0])
        if dia.isoformat() != datas[0]:
            raise ValueError
    except ValueError:
        return jsonify({
            "mensagem": "Informe uma data válida no formato AAAA-MM-DD.",
        }), 400

    try:
        # A consulta não compartilha sessão entre requisições e não expõe clientes.
        with Session() as sessao:
            registros = sessao.query(Agendamento.data_hora).filter(
                Agendamento.data_hora >= datetime.combine(dia, time.min),
                Agendamento.data_hora <= datetime.combine(dia, time.max),
            ).all()
        livres = horarios_disponiveis(dia, [registro[0] for registro in registros])
        return jsonify({
            "data": dia.isoformat(),
            "duracao_minutos": DURACAO_MINUTOS,
            "horarios": livres,
        })
    except Exception:
        app.logger.exception("Falha ao consultar os horários disponíveis.")
        return jsonify({"mensagem": "Não foi possível consultar os horários."}), 500

if __name__ == '__main__':
    app.run(host='0.0.0.0', port=5000)
