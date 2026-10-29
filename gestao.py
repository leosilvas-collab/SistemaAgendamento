"""Acesso, planos e isolamento das agendas na demonstração acadêmica local."""
from datetime import datetime, time, timedelta
from functools import wraps
import hashlib
import math
import re
import secrets
import unicodedata

import bcrypt
from flask import g, jsonify, render_template, request
from sqlalchemy import func, or_, text
from sqlalchemy.exc import IntegrityError
from werkzeug.exceptions import HTTPException

from agenda import horario_local, limite_consulta

COOKIE = "marcia_sessao"
ESPERAS = (1, 2, 4, 8, 60)
HASH_FICTICIO = bcrypt.hashpw(b"000000", bcrypt.gensalt(rounds=12))


class ErroGestao(Exception):
    def __init__(self, mensagem, status=400):
        self.mensagem, self.status = mensagem, status


def email_normalizado(valor):
    if not isinstance(valor, str) or len(valor) > 254:
        raise ErroGestao("Informe um e-mail válido.")
    email = valor.strip().casefold()
    if not re.fullmatch(r"[^@\s]+@[^@\s]+\.[^@\s]+", email):
        raise ErroGestao("Informe um e-mail válido.")
    return email


def pode_agendar(usuario, agora):
    return usuario.plano == "pago" or (
        usuario.vence_em is not None and usuario.vence_em > horario_local(agora)
    )


def dados_usuario(usuario, agora, incluir_controle_interno=False):
    dados = {"id":usuario.id, "email":usuario.email, "papel":usuario.papel,
            "nome":usuario.nome, "telefone":usuario.telefone, "estabelecimento":usuario.estabelecimento,
            "slug":usuario.slug, "plano":usuario.plano, "ativado":usuario.ativado_em is not None,
            "redefinir":usuario.redefinir,
            "vence_em":usuario.vence_em.isoformat() if usuario.vence_em else None,
            "pode_agendar":pode_agendar(usuario, agora)}
    if incluir_controle_interno:
        dados["premium_concedidos"] = usuario.premium_concedidos
    return dados


class ServicoGestao:
    def __init__(self, app, modelos, relogio):
        self.app, self.m, self.relogio = app, modelos, relogio

    def agora(self):
        return horario_local(self.relogio())

    def publico(self, sessao):
        slug = request.args.get("salao", "marcia-nails")
        usuario = sessao.query(self.m.UsuarioGestao).filter_by(slug=slug, papel="gestor").first()
        if usuario is None:
            raise ErroGestao("Estabelecimento não encontrado.",404)
        return usuario

    def filtrar_agenda(self, consulta, usuario):
        v = self.m.VinculoAgenda
        consulta = consulta.outerjoin(v, v.agendamento_id == self.m.Agendamento.id).filter(self.m.Agendamento.status != "cancelado")
        if usuario.email == "marcia@marcia.com":
            return consulta.filter(or_(v.usuario_id == usuario.id, v.agendamento_id.is_(None)))
        return consulta.filter(v.usuario_id == usuario.id)

    def vincular(self, sessao, reserva, usuario, nome):
        sessao.add(self.m.VinculoAgenda(agendamento_id=reserva.id, usuario_id=usuario.id, nome_cliente=nome))

    def sessao_atual(self, sessao):
        token = request.cookies.get(COOKIE, "")
        if not token or len(token) > 128:
            raise ErroGestao("Entre na sua conta para continuar.",401)
        chave = hashlib.sha256(token.encode()).hexdigest()
        registro = sessao.get(self.m.SessaoGestao, chave)
        if registro is None or registro.expira_em <= self.agora():
            raise ErroGestao("Sua sessão expirou. Entre novamente.",401)
        usuario = sessao.get(self.m.UsuarioGestao, registro.usuario_id)
        if usuario is None or usuario.redefinir or not usuario.senha_hash:
            raise ErroGestao("Entre novamente na sua conta.",401)
        return usuario, registro

    def autorizado(self, papel=None):
        def decorar(funcao):
            @wraps(funcao)
            def executar(*args, **kwargs):
                with self.m.Session() as sessao:
                    usuario, registro = self.sessao_atual(sessao)
                    if papel and usuario.papel != papel:
                        raise ErroGestao("Acesso não permitido.",403)
                    if request.method == "POST" and not secrets.compare_digest(
                        request.headers.get("X-CSRF-Token", ""), registro.csrf
                    ):
                        raise ErroGestao("Atualize a página antes de continuar.",403)
                    g.usuario_gestao = usuario
                    g.token_gestao = registro.token_hash
                    g.csrf_gestao = registro.csrf
                return funcao(*args, **kwargs)
            return executar
        return decorar

    def iniciar_sessao(self, sessao, usuario):
        anterior=request.cookies.get(COOKIE, "")
        if anterior:
            sessao.query(self.m.SessaoGestao).filter_by(token_hash=hashlib.sha256(anterior.encode()).hexdigest()).delete()
        sessao.query(self.m.SessaoGestao).filter(self.m.SessaoGestao.expira_em <= self.agora()).delete()
        token = secrets.token_urlsafe(32)
        csrf = secrets.token_urlsafe(32)
        sessao.add(self.m.SessaoGestao(token_hash=hashlib.sha256(token.encode()).hexdigest(),
            usuario_id=usuario.id, csrf=csrf, expira_em=self.agora()+timedelta(hours=8)))
        dados = dados_usuario(usuario,self.relogio())
        sessao.commit()
        resposta = jsonify({"usuario":dados,"csrf":csrf})
        resposta.set_cookie(COOKIE,token,max_age=8*3600,httponly=True,
            secure=request.is_secure,samesite="Lax",path="/")
        return resposta

    def identidade(self, dados):
        if not isinstance(dados, dict):
            raise ErroGestao("Informe os dados de acesso.")
        email = email_normalizado(dados.get("email"))
        area = dados.get("area")
        if area not in ("gestor", "proprietario"):
            raise ErroGestao("Área de acesso inválida.")
        return email,area

    def verificar_espera(self,sessao,email,area):
        chave = hashlib.sha256((area+":"+email).encode()).hexdigest()
        falha = sessao.get(self.m.FalhaAcesso,chave)
        if falha and falha.tentar_apos > self.agora():
            espera = max(1,math.ceil((falha.tentar_apos-self.agora()).total_seconds()))
            resposta = jsonify({"mensagem":f"Aguarde {espera} segundos antes de tentar novamente.","espera":espera})
            resposta.headers["Retry-After"] = str(espera)
            return falha,resposta
        return falha,None

    def falhar_login(self,sessao,email,area,falha):
        agora = self.agora()
        if falha is None:
            falha = self.m.FalhaAcesso(chave=hashlib.sha256((area+":"+email).encode()).hexdigest(),
                quantidade=0,tentar_apos=agora,ultima_falha=agora)
            sessao.add(falha)
        if agora-falha.ultima_falha > timedelta(minutes=15):
            falha.quantidade=0
        falha.quantidade += 1
        espera=ESPERAS[min(falha.quantidade-1,4)]
        falha.tentar_apos=agora+timedelta(seconds=espera)
        falha.ultima_falha=agora
        sessao.commit()
        return jsonify({"mensagem":"E-mail ou senha inválidos.","espera":espera}),401


def registrar_gestao(app, modelos, relogio, gravar_reserva):
    servico = ServicoGestao(app,modelos,relogio)
    app.extensions["gestao"] = servico
    m = modelos

    @app.errorhandler(ErroGestao)
    def erro_gestao(erro):
        return jsonify({"mensagem":erro.mensagem}),erro.status

    @app.errorhandler(Exception)
    def erro_nao_previsto(erro):
        if isinstance(erro,HTTPException):
            return erro
        app.logger.error("Falha interna; tipo=%s.",type(erro).__name__)
        return jsonify({"mensagem":"Não foi possível concluir a operação. Tente novamente."}),500

    @app.before_request
    def proteger_post_gestao():
        if request.method == "POST" and request.path.startswith(("/api/acesso/","/api/proprietario/","/api/gestao/")):
            origem = request.headers.get("Origin")
            if request.headers.get("X-Requested-With") != "MarciaNails" or (origem is not None and origem != request.host_url.rstrip("/")):
                return jsonify({"mensagem":"Envio não autorizado."}),403
            if not request.is_json:
                return jsonify({"mensagem":"Envie JSON."}),415

    @app.after_request
    def proteger_telas(resposta):
        if request.path in ("/proprietario","/gestao"):
            resposta.headers["Cache-Control"]="no-store"
        resposta.headers["X-Content-Type-Options"]="nosniff"
        resposta.headers["X-Frame-Options"]="DENY"
        resposta.headers["Referrer-Policy"]="same-origin"
        return resposta

    @app.route('/proprietario')
    def pagina_proprietario():
        return render_template("gestao.html",area="proprietario")

    @app.route('/gestao')
    def pagina_gestor():
        return render_template("gestao.html",area="gestor")

    @app.post('/api/acesso/identificar')
    def identificar_acesso():
        email,area=servico.identidade(request.get_json())
        with m.Session() as s:
            _,bloqueio=servico.verificar_espera(s,email,area)
            if bloqueio is not None: return bloqueio,429
            usuario=s.query(m.UsuarioGestao).filter_by(email=email,papel=area).first()
            if usuario is None: return jsonify({"mensagem":"Acesso não disponível. Consulte o proprietário."}),401
            if area=="proprietario" and (not usuario.senha_hash or usuario.redefinir) and request.remote_addr not in ("127.0.0.1","::1"):
                raise ErroGestao("Defina a senha master no próprio computador do servidor.",403)
            return jsonify({"etapa":"cadastro" if not usuario.senha_hash or usuario.redefinir else "senha","email":email})

    @app.post('/api/acesso/ativar')
    def ativar_acesso():
        dados=request.get_json()
        email,area=servico.identidade(dados)
        senha=dados.get("senha")
        if not isinstance(senha,str) or not re.fullmatch(r"[0-9]{6}",senha) or dados.get("confirmacao")!=senha:
            raise ErroGestao("Digite e confirme uma senha de exatamente seis números.")
        if area=="proprietario" and request.remote_addr not in ("127.0.0.1","::1"):
            raise ErroGestao("O primeiro cadastro master deve ser feito localmente.",403)
        nome=telefone=estabelecimento=""
        if area=="gestor":
            for campo in ("nome","telefone","estabelecimento"):
                if not isinstance(dados.get(campo),str): raise ErroGestao("Preencha todos os dados do cadastro.")
            nome=" ".join(dados["nome"].split())
            estabelecimento=" ".join(dados["estabelecimento"].split())
            telefone=re.sub(r"[ ()+\-]","",dados["telefone"])
            if len(telefone) in (12,13) and telefone.startswith("55"): telefone=telefone[2:]
            if not 2<=len(nome)<=100 or not 2<=len(estabelecimento)<=100 or not re.fullmatch(r"[1-9][0-9]{9,10}",telefone):
                raise ErroGestao("Confira nome, estabelecimento e telefone com DDD.")
            if any(unicodedata.category(c).startswith("C") for c in nome+estabelecimento):
                raise ErroGestao("Os dados contêm caracteres inválidos.")
        with m.Session() as s:
            s.execute(text("BEGIN IMMEDIATE"))
            _,bloqueio=servico.verificar_espera(s,email,area)
            if bloqueio is not None: return bloqueio,429
            usuario=s.query(m.UsuarioGestao).filter_by(email=email,papel=area).first()
            if usuario is None: raise ErroGestao("Acesso não disponível.",401)
            if usuario.senha_hash and not usuario.redefinir: raise ErroGestao("Conta já ativada. Entre com sua senha.",409)
            usuario.senha_hash=bcrypt.hashpw(senha.encode(),bcrypt.gensalt(rounds=12)).decode()
            usuario.redefinir=False
            if area=="gestor":
                usuario.nome,usuario.telefone,usuario.estabelecimento=nome,telefone,estabelecimento
            if usuario.ativado_em is None:
                usuario.ativado_em=servico.agora()
                if usuario.plano=="teste": usuario.vence_em=servico.agora()+timedelta(days=30)
            s.query(m.SessaoGestao).filter_by(usuario_id=usuario.id).delete()
            s.query(m.FalhaAcesso).filter_by(chave=hashlib.sha256((area+":"+email).encode()).hexdigest()).delete()
            return servico.iniciar_sessao(s,usuario)

    @app.post('/api/acesso/entrar')
    def entrar_acesso():
        dados=request.get_json()
        email,area=servico.identidade(dados)
        senha=dados.get("senha", "")
        with m.Session() as s:
            s.execute(text("BEGIN IMMEDIATE"))
            falha,bloqueio=servico.verificar_espera(s,email,area)
            if bloqueio is not None: return bloqueio,429
            usuario=s.query(m.UsuarioGestao).filter_by(email=email,papel=area).first()
            hash_atual=usuario.senha_hash.encode() if usuario and usuario.senha_hash else HASH_FICTICIO
            formato=isinstance(senha,str) and re.fullmatch(r"[0-9]{6}",senha)
            confere=bcrypt.checkpw(senha.encode() if formato else b"invalido", hash_atual)
            if not usuario or usuario.redefinir or not usuario.senha_hash or not formato or not confere:
                return servico.falhar_login(s,email,area,falha)
            if falha: s.delete(falha)
            return servico.iniciar_sessao(s,usuario)

    @app.get('/api/acesso/sessao')
    @servico.autorizado()
    def obter_sessao():
        return jsonify({"usuario":dados_usuario(g.usuario_gestao,relogio()),"csrf":g.csrf_gestao})

    @app.post('/api/acesso/sair')
    @servico.autorizado()
    def sair_acesso():
        with m.Session() as s:
            s.query(m.SessaoGestao).filter_by(token_hash=g.token_gestao).delete()
            s.commit()
        resposta=jsonify({"mensagem":"Sessão encerrada."})
        resposta.delete_cookie(COOKIE,path="/",httponly=True,samesite="Lax")
        return resposta

    @app.get('/api/proprietario/usuarios')
    @servico.autorizado("proprietario")
    def listar_usuarios():
        with m.Session() as s:
            usuarios=s.query(m.UsuarioGestao).filter_by(papel="gestor").order_by(m.UsuarioGestao.email).all()
            return jsonify({"usuarios":[dados_usuario(u,relogio(),incluir_controle_interno=True) for u in usuarios]})

    @app.post('/api/proprietario/usuarios')
    @servico.autorizado("proprietario")
    def cadastrar_gestor():
        dados=request.get_json()
        email=email_normalizado(dados.get("email") if isinstance(dados,dict) else None)
        with m.Session() as s:
            if s.query(m.UsuarioGestao).filter_by(email=email).first(): raise ErroGestao("E-mail já cadastrado.",409)
            usuario=m.UsuarioGestao(email=email,papel="gestor",slug=secrets.token_urlsafe(12),plano="teste")
            s.add(usuario)
            try:
                s.flush()
                resposta=dados_usuario(usuario,relogio(),incluir_controle_interno=True)
                s.commit()
            except IntegrityError:
                s.rollback()
                raise ErroGestao("E-mail já cadastrado.",409) from None
        return jsonify({"usuario":resposta}),201

    @app.post('/api/proprietario/usuarios/<int:identificador>/plano')
    @servico.autorizado("proprietario")
    def alterar_plano(identificador):
        dados=request.get_json()
        acao=dados.get("acao") if isinstance(dados,dict) else None
        if acao not in ("premium","pago"): raise ErroGestao("Ação de plano inválida.")
        with m.Session() as s:
            s.execute(text("BEGIN IMMEDIATE"))
            usuario=s.get(m.UsuarioGestao,identificador)
            if not usuario or usuario.papel!="gestor": raise ErroGestao("Gestor não encontrado.",404)
            if acao=="pago": usuario.plano="pago"
            else:
                if usuario.plano=="pago": raise ErroGestao("Esta conta já está no plano pago.")
                if not usuario.ativado_em: raise ErroGestao("Aguarde a ativação do cadastro.")
                if usuario.premium_concedidos>=3: raise ErroGestao("As três concessões premium já foram utilizadas.",409)
                usuario.vence_em=max(usuario.vence_em or servico.agora(),servico.agora())+timedelta(days=30)
                usuario.premium_concedidos+=1
            resposta=dados_usuario(usuario,relogio(),incluir_controle_interno=True)
            s.commit()
            return jsonify({"usuario":resposta})

    @app.post('/api/proprietario/redefinir')
    @servico.autorizado("proprietario")
    def autorizar_redefinicao():
        dados=request.get_json()
        email=email_normalizado(dados.get("email") if isinstance(dados,dict) else None)
        with m.Session() as s:
            usuario=s.query(m.UsuarioGestao).filter_by(email=email,papel="gestor").first()
            if usuario is None: raise ErroGestao("Gestor não encontrado.",404)
            usuario.redefinir=True
            s.query(m.SessaoGestao).filter_by(usuario_id=usuario.id).delete()
            s.commit()
        return jsonify({"mensagem":"Redefinição autorizada. O gestor pode definir a senha na Área de Gestão. Nenhum e-mail foi enviado."})

    @app.get('/api/gestao/agenda')
    @servico.autorizado("gestor")
    def agenda_gestor():
        try:
            valor=request.args.get("data",servico.agora().date().isoformat())
            dia=datetime.strptime(valor,"%Y-%m-%d").date()
            if dia.isoformat()!=valor: raise ValueError
        except ValueError: raise ErroGestao("Informe a data no formato AAAA-MM-DD.") from None
        with m.Session() as s:
            a,c,v=m.Agendamento,m.Cliente,m.VinculoAgenda
            consulta=s.query(a, c.telefone, func.coalesce(v.nome_cliente,c.nome)).select_from(a).join(c,c.id==a.cliente_id)
            registros=servico.filtrar_agenda(consulta,g.usuario_gestao).filter(
                a.data_hora>=datetime.combine(dia,time.min),a.data_hora<=datetime.combine(dia,time.max)
            ).order_by(a.data_hora).all()
            itens=[{"id":a.id,"horario":a.data_hora.strftime("%H:%M"),"nome":nome,
                    "telefone":telefone,"servico":a.servico,"status":a.status} for a,telefone,nome in registros]
        primeiro_futuro = limite_consulta(servico.agora().date()) + timedelta(days=1)
        # O período público termina no sábado; a extensão começa no próximo dia de atendimento.
        while primeiro_futuro.weekday() == 6:
            primeiro_futuro += timedelta(days=1)
        return jsonify({"data":dia.isoformat(),"agendamentos":itens,
            "usuario":dados_usuario(g.usuario_gestao,relogio()),
            "futuro_a_partir_de":primeiro_futuro.isoformat()})

    @app.get('/api/gestao/clientes')
    @servico.autorizado("gestor")
    def buscar_clientes():
        termo=request.args.get("q", "").strip()
        if not 2<=len(termo)<=100: return jsonify({"clientes":[]})
        with m.Session() as s:
            a,c,v=m.Agendamento,m.Cliente,m.VinculoAgenda
            nome=func.coalesce(v.nome_cliente,c.nome)
            consulta=s.query(nome,c.telefone).select_from(a).join(c,c.id==a.cliente_id)
            registros=servico.filtrar_agenda(consulta,g.usuario_gestao).filter(
                or_(nome.icontains(termo,autoescape=True),c.telefone.contains(re.sub(r"\D","",termo) or termo,autoescape=True))
            ).order_by(a.id.desc()).limit(100).all()
            encontrados={}
            for nome,telefone in registros:
                encontrados.setdefault(telefone,{"nome":nome,"telefone":telefone})
        return jsonify({"clientes":list(encontrados.values())})

    @app.get('/api/gestao/horarios')
    @servico.autorizado("gestor")
    def horarios_gestor():
        from agenda import horarios_disponiveis
        try:
            valor=request.args.get("data", "")
            dia=datetime.strptime(valor,"%Y-%m-%d").date()
            if dia.isoformat()!=valor: raise ValueError
        except ValueError: raise ErroGestao("Informe uma data válida.") from None
        with m.Session() as s:
            a=m.Agendamento
            consulta=servico.filtrar_agenda(s.query(a.data_hora),g.usuario_gestao)
            edicao=request.args.get("agendamento")
            if edicao is not None:
                if not edicao.isascii() or not edicao.isdigit() or len(edicao)>10:
                    raise ErroGestao("Agendamento inválido.")
                reserva_do_gestor(s,int(edicao))
                consulta=consulta.filter(a.id != int(edicao))
            registros=consulta.filter(
                a.data_hora>=datetime.combine(dia,time.min),a.data_hora<=datetime.combine(dia,time.max)).all()
        return jsonify({"horarios":horarios_disponiveis(dia,[r[0] for r in registros],relogio())})

    @app.post('/api/gestao/agendamentos')
    @servico.autorizado("gestor")
    def reservar_como_gestor():
        return gravar_reserva(g.usuario_gestao)

    def reserva_do_gestor(sessao, identificador):
        reserva=servico.filtrar_agenda(sessao.query(m.Agendamento),g.usuario_gestao).filter(
            m.Agendamento.id==identificador).first()
        if reserva is None:
            raise ErroGestao("Agendamento não encontrado.",404)
        return reserva

    def verificar_plano_atual(sessao):
        usuario=sessao.get(m.UsuarioGestao,g.usuario_gestao.id)
        if not pode_agendar(usuario,relogio()):
            raise ErroGestao("O período de teste terminou. A agenda está disponível somente para consulta.",403)

    @app.post('/api/gestao/agendamentos/<int:identificador>/excluir')
    @servico.autorizado("gestor")
    def excluir_agendamento(identificador):
        with m.Session() as s:
            s.execute(text("BEGIN IMMEDIATE"))
            reserva=reserva_do_gestor(s,identificador)
            verificar_plano_atual(s)
            # Exclusão lógica: libera o horário e preserva o registro original no banco.
            reserva.status="cancelado"
            s.commit()
        return jsonify({"mensagem":"Agendamento excluído e horário liberado."})

    @app.post('/api/gestao/agendamentos/<int:identificador>/alterar')
    @servico.autorizado("gestor")
    def alterar_agendamento(identificador):
        from agenda import horarios_disponiveis
        from reservas import validar_reserva, ReservaInvalida
        with m.Session() as s:
            s.execute(text("BEGIN IMMEDIATE"))
            reserva=reserva_do_gestor(s,identificador)
            verificar_plano_atual(s)
            try:
                dados=validar_reserva(request.get_json(),relogio(),permitir_futuro=True)
            except ReservaInvalida as erro:
                raise ErroGestao(str(erro)) from None
            dia=dados["data_hora"].date()
            a=m.Agendamento
            registros=servico.filtrar_agenda(s.query(a.data_hora),g.usuario_gestao).filter(
                a.id!=identificador,a.data_hora>=datetime.combine(dia,time.min),
                a.data_hora<=datetime.combine(dia,time.max)).all()
            livres=horarios_disponiveis(dia,[r[0] for r in registros],relogio())
            if dados["data_hora"].strftime("%H:%M") not in livres:
                raise ErroGestao("Esse horário não está mais disponível. Escolha outro.",409)
            cliente=s.query(m.Cliente).filter_by(telefone=dados["telefone"]).first()
            if cliente is None:
                cliente=m.Cliente(nome=dados["nome"],telefone=dados["telefone"])
                s.add(cliente)
            reserva.cliente=cliente
            reserva.data_hora=dados["data_hora"]
            reserva.servico=dados["servico"]
            vinculo=s.get(m.VinculoAgenda,identificador)
            if vinculo is None:
                servico.vincular(s,reserva,g.usuario_gestao,dados["nome"])
            else:
                vinculo.nome_cliente=dados["nome"]
            resposta={"id":identificador,"nome":dados["nome"],"data":dia.isoformat(),
                      "horario":reserva.data_hora.strftime("%H:%M"),"servico":reserva.servico}
            s.commit()
        return jsonify({"agendamento":resposta})

    return servico
