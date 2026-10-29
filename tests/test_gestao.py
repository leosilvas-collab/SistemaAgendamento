"""Áreas autenticadas com SQLite temporário; nenhum cadastro real é alterado."""
from datetime import datetime, timedelta
import unittest
from unittest.mock import patch
import test_horarios_integracao as base


class GestaoTests(unittest.TestCase):
    setUp = base.HorariosIntegracaoTests.setUp

    def post(self, caminho, dados, client=None, csrf=None):
        cabecalhos = {"X-Requested-With":"MarciaNails"}
        if csrf: cabecalhos["X-CSRF-Token"] = csrf
        return (client or self.client).post(caminho, json=dados, headers=cabecalhos)

    def ativar(self, email="marcia@marcia.com", client=None, area="gestor"):
        return self.post("/api/acesso/ativar", {"email":email,"area":area,
            "senha":"123456","confirmacao":"123456","nome":"Márcia Teste",
            "telefone":"11900000003","estabelecimento":"Salão de Teste"}, client)

    def master(self):
        resultado = self.ativar("leocladison@gmail.com", area="proprietario")
        self.assertEqual(resultado.status_code, 200)
        return resultado.json["csrf"]

    def novo(self, email="gestor@teste.com"):
        csrf = self.master()
        resultado = self.post("/api/proprietario/usuarios", {"email":email}, csrf=csrf)
        self.assertEqual(resultado.status_code, 201)
        return resultado.json["usuario"]["id"], csrf

    def test_contas_iniciais_sem_senhas_e_marcia_paga(self):
        with self.models.Session() as s:
            marcia = s.query(self.models.UsuarioGestao).filter_by(email="marcia@marcia.com").one()
            self.assertEqual(marcia.plano, "pago")
            self.assertIsNone(marcia.senha_hash)
        for caminho in ["/proprietario", "/gestao"]:
            self.assertEqual(self.client.get(caminho).status_code, 200)
        pagina = self.client.get("/").get_data(as_text=True)
        self.assertIn('href="/gestao"', pagina)
        self.assertNotIn('href="/proprietario"', pagina)

    def test_primeiro_acesso_senha_bcrypt_e_cookie_protegido(self):
        resposta = self.ativar()
        self.assertEqual(resposta.status_code, 200)
        self.assertIn("HttpOnly", resposta.headers["Set-Cookie"])
        self.assertIn("SameSite=Lax", resposta.headers["Set-Cookie"])
        self.assertEqual(resposta.json["usuario"]["plano"], "pago")
        with self.models.Session() as s:
            conta = s.query(self.models.UsuarioGestao).filter_by(email="marcia@marcia.com").one()
            self.assertTrue(conta.senha_hash.startswith("$2b$"))
            self.assertNotIn("123456", conta.senha_hash)
        self.assertEqual(self.client.get("/api/gestao/agenda?data=2026-10-26").status_code, 200)

    def test_apenas_conta_pre_cadastrada_pode_ativar_e_senha_tem_seis_digitos(self):
        self.assertEqual(self.ativar("naocadastrado@teste.com").status_code, 401)
        dados = {"email":"marcia@marcia.com","area":"gestor","senha":"12345a","confirmacao":"12345a",
            "nome":"Ana Teste","telefone":"11900000003","estabelecimento":"Salão"}
        self.assertEqual(self.post("/api/acesso/ativar",dados).status_code, 400)

    def test_master_pendente_so_pode_ser_ativado_localmente(self):
        remoto=self.client.post("/api/acesso/ativar",json={"email":"leocladison@gmail.com","area":"proprietario",
            "senha":"123456","confirmacao":"123456"},headers={"X-Requested-With":"MarciaNails"},
            environ_overrides={"REMOTE_ADDR":"192.168.2.10"})
        self.assertEqual(remoto.status_code,403)
        resposta = self.post("/api/acesso/ativar", {"email":"leocladison@gmail.com","area":"proprietario",
            "senha":"123456","confirmacao":"123456"}, client=self.client)
        self.assertEqual(resposta.status_code, 200)
        outro = self.modulo.app.test_client()
        self.assertEqual(self.ativar("leocladison@gmail.com", client=outro, area="proprietario").status_code, 409)

    def test_rotas_restritas_exigem_sessao_e_papel_correto(self):
        for caminho in ["/api/proprietario/usuarios", "/api/gestao/agenda", "/api/gestao/clientes"]:
            self.assertEqual(self.client.get(caminho).status_code, 401)
        self.ativar()
        self.assertEqual(self.client.get("/api/proprietario/usuarios").status_code, 403)
        self.assertEqual(self.post("/api/proprietario/usuarios",{"email":"outro@teste.com"}).status_code, 403)

    def test_logout_revoga_a_sessao_e_csrf_e_obrigatorio(self):
        entrada = self.ativar()
        cookie_antigo=self.client.get_cookie("marcia_sessao").value
        self.assertEqual(self.post("/api/acesso/sair",{}).status_code, 403)
        self.assertEqual(self.post("/api/acesso/sair",{},csrf=entrada.json["csrf"]).status_code, 200)
        self.assertEqual(self.client.get("/api/gestao/agenda").status_code, 401)
        self.client.set_cookie("marcia_sessao",cookie_antigo)
        self.assertEqual(self.client.get("/api/gestao/agenda").status_code,401)

    def test_teste_comeca_na_ativacao_e_expira_em_30_dias(self):
        identificador, csrf = self.novo()
        gestor = self.modulo.app.test_client()
        resposta = self.ativar("gestor@teste.com", client=gestor)
        self.assertEqual(resposta.status_code, 200)
        self.assertEqual(resposta.json["usuario"]["vence_em"], "2026-11-25T07:00:00")
        self.assertTrue(resposta.json["usuario"]["pode_agendar"])

    def test_tres_concessoes_premium_e_limite_no_servidor(self):
        identificador, csrf = self.novo()
        gestor = self.modulo.app.test_client()
        self.ativar("gestor@teste.com",client=gestor)
        for numero in (1,2,3):
            resposta = self.post(f"/api/proprietario/usuarios/{identificador}/plano",{"acao":"premium"},csrf=csrf)
            self.assertEqual(resposta.status_code, 200)
            self.assertEqual(resposta.json["usuario"]["premium_concedidos"], numero)
        self.assertEqual(self.post(f"/api/proprietario/usuarios/{identificador}/plano",{"acao":"premium"},csrf=csrf).status_code, 409)

    def test_expirado_consulta_mas_nao_reserva_nem_publico_nem_gestor(self):
        identificador, csrf = self.novo()
        gestor = self.modulo.app.test_client()
        conta = self.ativar("gestor@teste.com",client=gestor).json
        with self.models.Session() as s:
            u = s.get(self.models.UsuarioGestao,identificador)
            u.vence_em = datetime(2026,10,26,6)
            s.commit()
        self.assertEqual(gestor.get("/api/gestao/agenda?data=2026-10-26").status_code, 200)
        dados = {"nome":"Cliente Teste","telefone":"11900000007","servico":"Manicure","data":"2026-10-26","horario":"09:30"}
        self.assertEqual(self.post("/api/gestao/agendamentos",dados,gestor,conta["csrf"]).status_code, 403)
        self.assertEqual(self.post("/api/agendamentos?salao="+conta["usuario"]["slug"],dados).status_code, 403)

    def test_redefinicao_so_pelo_master_e_revoga_sessoes(self):
        csrf = self.master()
        gestor = self.modulo.app.test_client()
        self.ativar(client=gestor)
        resposta = self.post("/api/proprietario/redefinir",{"email":"marcia@marcia.com"},csrf=csrf)
        self.assertEqual(resposta.status_code, 200)
        self.assertEqual(gestor.get("/api/gestao/agenda").status_code, 401)
        self.assertEqual(self.ativar(client=gestor).status_code, 200)

    def test_espera_progressiva_controlada_no_servidor(self):
        self.ativar()
        self.relogio.stop()
        agora = datetime(2026,10,26,7)
        for espera in [1,2,4,8,60]:
            with patch.object(self.modulo,"agora_sao_paulo",return_value=agora):
                falha = self.post("/api/acesso/entrar",{"email":"marcia@marcia.com","area":"gestor","senha":"000000"})
                self.assertEqual(falha.status_code, 401)
                bloqueio = self.post("/api/acesso/entrar",{"email":"marcia@marcia.com","area":"gestor","senha":"123456"})
                self.assertEqual(bloqueio.status_code, 429)
                self.assertEqual(int(bloqueio.headers["Retry-After"]),espera)
            agora += timedelta(seconds=espera)
        with patch.object(self.modulo,"agora_sao_paulo",return_value=agora):
            self.assertEqual(self.post("/api/acesso/entrar",{"email":"marcia@marcia.com","area":"gestor","senha":"123456"}).status_code, 200)

    def test_agendamento_futuro_exclusivo_do_gestor(self):
        sessao = self.ativar().json
        dados = {"nome":"Cliente Futuro","telefone":"11900000007","servico":"Manicure","data":"2027-02-01","horario":"09:30"}
        self.assertEqual(self.post("/api/agendamentos",dados).status_code,400)
        self.assertEqual(self.post("/api/gestao/agendamentos",dados,csrf=sessao["csrf"]).status_code,201)
        self.assertEqual(len(self.client.get("/api/gestao/agenda?data=2027-02-01").json["agendamentos"]),1)

    def test_agendas_e_buscas_nao_vazam_entre_estabelecimentos(self):
        identificador, csrf = self.novo()
        a = self.modulo.app.test_client()
        b = self.modulo.app.test_client()
        sa = self.ativar(client=a).json
        sb = self.ativar("gestor@teste.com",client=b).json
        dados = {"nome":"Cliente Exclusivo","telefone":"11900000007","servico":"Manicure","data":"2026-10-26","horario":"09:30"}
        self.assertEqual(self.post("/api/gestao/agendamentos",dados,a,sa["csrf"]).status_code,201)
        self.assertEqual(b.get("/api/gestao/clientes?q=Exclusivo").json["clientes"],[])
        self.assertEqual(b.get("/api/gestao/agenda?data=2026-10-26").json["agendamentos"],[])
        self.assertEqual(len(a.get("/api/gestao/clientes?q=Exclusivo").json["clientes"]),1)
        self.assertEqual(self.post("/api/gestao/agendamentos",dados,b,sb["csrf"]).status_code,201)

    def test_cadastro_repetido_normaliza_email_sem_criar_duplicata(self):
        identificador,csrf=self.novo()
        resposta=self.post("/api/proprietario/usuarios",{"email":" GESTOR@TESTE.COM "},csrf=csrf)
        self.assertEqual(resposta.status_code,409)
        self.assertEqual(len(self.client.get("/api/proprietario/usuarios").json["usuarios"]),2)

    def test_sessao_expirada_nao_libera_dados(self):
        self.ativar()
        with self.models.Session() as s:
            s.query(self.models.SessaoGestao).update({"expira_em":datetime(2026,10,26,6)})
            s.commit()
        self.assertEqual(self.client.get("/api/gestao/agenda").status_code,401)

    def test_primeiro_acesso_nao_aceita_plano_ou_papel_injetado(self):
        identificador,csrf=self.novo()
        gestor=self.modulo.app.test_client()
        dados={"email":"gestor@teste.com","area":"gestor","senha":"123456","confirmacao":"123456",
            "nome":"Pessoa Teste","telefone":"11900000003","estabelecimento":"Salão Teste", "plano":"pago", "papel":"proprietario"}
        resposta=self.post("/api/acesso/ativar",dados,client=gestor)
        self.assertEqual(resposta.status_code,200)
        self.assertEqual(resposta.json["usuario"]["plano"],"teste")
        self.assertEqual(resposta.json["usuario"]["papel"],"gestor")

    def test_post_sem_csrf_ou_de_origem_externa_nao_altera_plano(self):
        identificador,csrf=self.novo()
        caminho=f"/api/proprietario/usuarios/{identificador}/plano"
        self.assertEqual(self.post(caminho,{"acao":"pago"}).status_code,403)
        resposta=self.client.post(caminho,json={"acao":"pago"},headers={"X-Requested-With":"MarciaNails","X-CSRF-Token":csrf,"Origin":"https://outro.invalid"})
        self.assertEqual(resposta.status_code,403)
        with self.models.Session() as s:
            self.assertEqual(s.get(self.models.UsuarioGestao,identificador).plano,"teste")

    def test_estabelecimento_inexistente_retorna_404_sem_dados(self):
        for caminho in ("/?salao=inexistente", "/api/datas?salao=inexistente",
                        "/api/horarios?data=2026-10-27&salao=inexistente"):
            resposta = self.client.get(caminho)
            self.assertEqual(resposta.status_code, 404)
            self.assertEqual(resposta.json, {"mensagem":"Estabelecimento não encontrado."})

    def test_inicio_das_datas_futuras_pula_domingo(self):
        self.ativar()
        resposta = self.client.get("/api/gestao/agenda?data=2026-12-07")
        self.assertEqual(resposta.status_code, 200)
        self.assertEqual(resposta.json["futuro_a_partir_de"], "2026-12-07")
        livres = self.client.get("/api/gestao/horarios?data=2026-12-07").json["horarios"]
        self.assertEqual(len(livres), 18)

    def test_data_futura_mostra_reserva_existente_e_demais_horarios_livres(self):
        sessao = self.ativar().json
        dados = {"nome":"Cliente Futuro","telefone":"11900000007","servico":"Manicure",
                 "data":"2026-12-07","horario":"09:30"}
        self.assertEqual(self.post("/api/gestao/agendamentos",dados,csrf=sessao["csrf"]).status_code,201)
        agenda = self.client.get("/api/gestao/agenda?data=2026-12-07").json
        self.assertEqual(agenda["agendamentos"][0]["nome"], "Cliente Futuro")
        horarios = self.client.get("/api/gestao/horarios?data=2026-12-07").json["horarios"]
        self.assertEqual(len(horarios), 17)
        self.assertNotIn("09:30", horarios)
        self.assertIn("10:00", horarios)
        self.assertEqual(self.client.get("/api/gestao/horarios?data=2026-12-06").json["horarios"], [])

    def test_contador_premium_exclusivo_do_proprietario(self):
        csrf = self.master()
        gestores = self.client.get("/api/proprietario/usuarios").json["usuarios"]
        self.assertIn("premium_concedidos", gestores[0])
        gestor = self.modulo.app.test_client()
        ativacao = self.ativar(client=gestor).json
        self.assertNotIn("premium_concedidos", ativacao["usuario"])
        self.assertNotIn("premium_concedidos", gestor.get("/api/acesso/sessao").json["usuario"])
        self.assertNotIn("premium_concedidos", gestor.get("/api/gestao/agenda").json["usuario"])
        self.assertNotIn('id="premium-contador"', gestor.get("/gestao").get_data(as_text=True))

    def reserva_editavel(self):
        sessao = self.ativar().json
        dados = {"nome":"Cliente Original","telefone":"11900000007","servico":"Manicure",
                 "data":"2026-10-26","horario":"09:30"}
        reserva = self.post("/api/gestao/agendamentos",dados,csrf=sessao["csrf"])
        self.assertEqual(reserva.status_code,201)
        return reserva.json["agendamento"]["id"], sessao["csrf"], dados

    def test_alterar_reserva_preserva_id_e_atualiza_dados_e_horario(self):
        identificador,csrf,dados = self.reserva_editavel()
        dados.update(nome="Cliente Alterada",telefone="11900000008",servico="Pedicure",data="2027-02-01",horario="10:00")
        r=self.post(f"/api/gestao/agendamentos/{identificador}/alterar",dados,csrf=csrf)
        self.assertEqual(r.status_code,200)
        self.assertEqual(r.json["agendamento"]["id"],identificador)
        self.assertEqual(self.client.get("/api/gestao/agenda?data=2026-10-26").json["agendamentos"],[])
        atual=self.client.get("/api/gestao/agenda?data=2027-02-01").json["agendamentos"][0]
        self.assertEqual((atual["nome"],atual["telefone"],atual["servico"],atual["horario"]),
                         ("Cliente Alterada","11900000008","Pedicure","10:00"))

    def test_edicao_aceita_proprio_horario_mas_nao_sobrepoe_outra_reserva(self):
        identificador,csrf,dados = self.reserva_editavel()
        caminho=f"/api/gestao/agendamentos/{identificador}/alterar"
        self.assertEqual(self.post(caminho,dados,csrf=csrf).status_code,200)
        disponiveis=self.client.get(f"/api/gestao/horarios?data=2026-10-26&agendamento={identificador}").json["horarios"]
        self.assertIn("09:30",disponiveis)
        outra=dict(dados,horario="10:00")
        self.assertEqual(self.post("/api/gestao/agendamentos",outra,csrf=csrf).status_code,201)
        self.assertEqual(self.post(caminho,outra,csrf=csrf).status_code,409)
        self.assertEqual(self.client.get("/api/gestao/agenda?data=2026-10-26").json["agendamentos"][0]["horario"],"09:30")
        self.assertEqual(self.post(caminho,dict(dados,horario="12:00"),csrf=csrf).status_code,400)

    def test_excluir_libera_horario_e_preserva_registro_cancelado(self):
        identificador,csrf,dados=self.reserva_editavel()
        r=self.post(f"/api/gestao/agendamentos/{identificador}/excluir",{},csrf=csrf)
        self.assertEqual(r.status_code,200)
        self.assertEqual(self.client.get("/api/gestao/agenda?data=2026-10-26").json["agendamentos"],[])
        self.assertIn("09:30",self.client.get("/api/horarios?data=2026-10-26").json["horarios"])
        with self.models.Session() as s:
            self.assertEqual(s.get(self.models.Agendamento,identificador).status,"cancelado")
        self.assertEqual(self.post(f"/api/gestao/agendamentos/{identificador}/excluir",{},csrf=csrf).status_code,404)

    def test_outro_gestor_nao_altera_exclui_ou_ignora_reserva_alheia(self):
        _,mastercsrf=self.novo()
        a=self.modulo.app.test_client()
        sa=self.ativar(client=a).json
        b=self.modulo.app.test_client()
        sb=self.ativar("gestor@teste.com",client=b).json
        dados={"nome":"Cliente Privada","telefone":"11900000007","servico":"Manicure","data":"2026-10-26","horario":"09:30"}
        identificador=self.post("/api/gestao/agendamentos",dados,a,sa["csrf"]).json["agendamento"]["id"]
        for acao in ("alterar","excluir"):
            self.assertEqual(self.post(f"/api/gestao/agendamentos/{identificador}/{acao}",dados,b,sb["csrf"]).status_code,404)
        self.assertEqual(b.get(f"/api/gestao/horarios?data=2026-10-26&agendamento={identificador}").status_code,404)
        self.assertEqual(self.post(f"/api/gestao/agendamentos/{identificador}/excluir",{},a).status_code,403)
        anonimo=self.modulo.app.test_client()
        self.assertEqual(self.post(f"/api/gestao/agendamentos/{identificador}/excluir",{},anonimo).status_code,401)

    def test_plano_expirado_nao_altera_nem_exclui_reserva(self):
        identificador,csrf,dados=self.reserva_editavel()
        with self.models.Session() as s:
            u=s.query(self.models.UsuarioGestao).filter_by(email="marcia@marcia.com").one()
            u.plano="teste";u.vence_em=datetime(2026,10,25)
            s.commit()
        for acao in ("alterar","excluir"):
            self.assertEqual(self.post(f"/api/gestao/agendamentos/{identificador}/{acao}",dados,csrf=csrf).status_code,403)
