from datetime import date, datetime, time, timedelta
from pathlib import Path

from flask import Flask, jsonify, render_template, request
from sqlalchemy import text
from sqlalchemy.exc import OperationalError
from werkzeug.exceptions import BadRequest

from reservas import validar_reserva, ReservaInvalida, LimiteDeTentativas

from agenda import (DURACAO_MINUTOS, horarios_disponiveis, agora_sao_paulo,
                    datas_disponiveis, limite_consulta)
from models import Session, Cliente, Agendamento
import models as modelos
from gestao import registrar_gestao, ErroGestao, pode_agendar

app = Flask(__name__, root_path=str(Path(__file__).resolve().parent))
app.config.update(MAX_CONTENT_LENGTH=8192, RESERVAS_POR_MINUTO=10)
limite_reservas = LimiteDeTentativas()

@app.route('/')
def home():
    with Session() as sessao:
        usuario=gestao_service.publico(sessao)
        return render_template("inicio.html",salao=usuario.slug,
            nome_estabelecimento=usuario.estabelecimento or "Agendamento Online")



@app.route('/manifest.webmanifest')
def manifesto():
    resposta = app.send_static_file("manifest.webmanifest")
    resposta.mimetype = "application/manifest+json"
    return resposta


@app.route('/sw.js')
def service_worker():
    resposta = app.send_static_file("sw.js")
    resposta.headers["Cache-Control"] = "no-cache"
    return resposta


@app.after_request
def impedir_cache_de_dados(resposta):
    if request.path.startswith("/api/"):
        resposta.headers["Cache-Control"] = "no-store"
    return resposta

@app.route('/api/status')
def status_aplicacao():
    return jsonify({
        "status": "online",
        "sistema": "Studio Marcia Nails",
        "mensagem": "Servidor da VPS rodando com sucesso!"
    })

@app.route('/api/status-banco')
def status_banco():
    try:
        with Session() as sessao:
            total_clientes = sessao.query(Cliente).count()
            total_agendamentos = sessao.query(Agendamento).count()
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
            usuario=gestao_service.publico(sessao)
            registros = gestao_service.filtrar_agenda(sessao.query(Agendamento.data_hora),usuario).filter(
                Agendamento.data_hora >= datetime.combine(dia, time.min),
                Agendamento.data_hora <= datetime.combine(dia, time.max),
            ).all()
        livres = horarios_disponiveis(dia, [registro[0] for registro in registros], agora_sao_paulo())
        return jsonify({
            "data": dia.isoformat(),
            "duracao_minutos": DURACAO_MINUTOS,
            "horarios": livres,
        })
    except ErroGestao:
        raise
    except Exception:
        app.logger.exception("Falha ao consultar os horários disponíveis.")
        return jsonify({"mensagem": "Não foi possível consultar os horários."}), 500


@app.route('/api/datas')
def consultar_datas():
    try:
        agora = agora_sao_paulo()
        hoje = agora.date()
        limite = limite_consulta(hoje)
        # Uma consulta para todo o período evita uma chamada ao banco por dia.
        with Session() as sessao:
            usuario=gestao_service.publico(sessao)
            registros = gestao_service.filtrar_agenda(sessao.query(Agendamento.data_hora),usuario).filter(
                Agendamento.data_hora >= datetime.combine(hoje, time.min),
                Agendamento.data_hora <= datetime.combine(limite, time.max),
            ).all()
        dados=datas_disponiveis(agora, [registro[0] for registro in registros])
        dados["reservas_liberadas"]=pode_agendar(usuario,agora)
        dados["estabelecimento"]=usuario.estabelecimento
        return jsonify(dados)
    except ErroGestao:
        raise
    except Exception:
        app.logger.exception("Falha ao consultar as datas disponíveis.")
        return jsonify({"mensagem": "Não foi possível consultar as datas."}), 500


@app.route('/api/agendamentos', methods=['POST'])
def criar_agendamento():
    return gravar_agendamento()


def gravar_agendamento(gestor=None):
    origem = request.headers.get("Origin")
    if request.headers.get("X-Requested-With") != "MarciaNails" or (
        origem is not None and origem != request.host_url.rstrip("/")
    ):
        return jsonify({"mensagem": "Envio não autorizado. Abra o formulário pelo aplicativo."}), 403
    if not request.is_json:
        return jsonify({"mensagem": "Envie os dados no formato JSON."}), 415
    if not limite_reservas.permitir(request.remote_addr or "local", app.config["RESERVAS_POR_MINUTO"]):
        resposta = jsonify({"mensagem": "Muitas tentativas. Aguarde um minuto antes de tentar novamente."})
        resposta.headers["Retry-After"] = "60"
        return resposta, 429
    try:
        dados = validar_reserva(request.get_json(), agora_sao_paulo(), permitir_futuro=gestor is not None)
    except (ReservaInvalida, BadRequest) as erro:
        mensagem = str(erro) if isinstance(erro, ReservaInvalida) else "Os dados enviados são inválidos."
        return jsonify({"mensagem": mensagem}), 400
    try:
        with Session() as sessao:
            # O bloqueio é adquirido ANTES da consulta. Outra confirmação espera
            # o commit e reavalia a disponibilidade, sem mudar as tabelas existentes.
            sessao.execute(text("BEGIN IMMEDIATE"))
            agora = agora_sao_paulo()
            usuario = sessao.get(modelos.UsuarioGestao,gestor.id) if gestor is not None else gestao_service.publico(sessao)
            if not pode_agendar(usuario,agora):
                return jsonify({"mensagem":"O período de teste terminou. A agenda pode ser consultada, mas novas reservas estão bloqueadas."}),403
            data_hora = dados["data_hora"]
            registros = gestao_service.filtrar_agenda(sessao.query(Agendamento.data_hora),usuario).filter(
                Agendamento.data_hora >= datetime.combine(data_hora.date(), time.min),
                Agendamento.data_hora <= datetime.combine(data_hora.date(), time.max),
            ).all()
            livres = horarios_disponiveis(data_hora.date(), [r[0] for r in registros], agora)
            if data_hora.strftime("%H:%M") not in livres:
                return jsonify({"mensagem": "Esse horário não está mais disponível. Escolha outro."}), 409
            cliente = sessao.query(Cliente).filter_by(telefone=dados["telefone"]).first()
            if cliente is None:
                cliente = Cliente(nome=dados["nome"], telefone=dados["telefone"])
            # Sem autenticação, não sobrescrevemos nem revelamos o nome já cadastrado.
            reserva = Agendamento(cliente=cliente, data_hora=data_hora, servico=dados["servico"])
            sessao.add(reserva)
            sessao.flush()
            gestao_service.vincular(sessao,reserva,usuario,dados["nome"])
            comprovante = {"id": reserva.id, "nome": dados["nome"], "servico": dados["servico"],
                           "data": data_hora.date().isoformat(), "horario": data_hora.strftime("%H:%M"),
                           "fim": (data_hora + timedelta(minutes=DURACAO_MINUTOS)).strftime("%H:%M")}
            sessao.commit()
        return jsonify({"agendamento": comprovante}), 201
    except ErroGestao:
        raise
    except OperationalError:
        # Não registrar a exceção SQL: ela pode incluir nome e telefone nos parâmetros.
        app.logger.error("Banco temporariamente indisponível ao gravar reserva (OperationalError).")
        return jsonify({"mensagem": "Não foi possível confirmar agora. Tente novamente em instantes."}), 503
    except Exception as erro:
        app.logger.error("Falha ao gravar a reserva; tipo=%s.", type(erro).__name__)
        return jsonify({"mensagem": "Não foi possível salvar o agendamento."}), 500


@app.errorhandler(413)
def requisicao_grande(erro):
    return jsonify({"mensagem": "O formulário excedeu o tamanho permitido."}), 413

gestao_service = registrar_gestao(app,modelos,lambda: agora_sao_paulo(),gravar_agendamento)

if __name__ == '__main__':
    app.run(host='0.0.0.0', port=5000)
