"""Reservas reais em SQLite temporário, inclusive duas requisições simultâneas."""
from concurrent.futures import ThreadPoolExecutor
from datetime import datetime
from threading import Barrier
import unittest
from unittest.mock import patch, MagicMock
from sqlalchemy.exc import OperationalError
from sqlalchemy import event
import test_horarios_integracao as base_testes


class ReservasIntegracaoTests(unittest.TestCase):
    # Compartilha somente a preparação do banco temporário e do relógio fixo.
    setUp = base_testes.HorariosIntegracaoTests.setUp
    reservar = base_testes.HorariosIntegracaoTests.reservar

    def dados(self, **alteracoes):
        dados = {"nome": "Ana Fictícia", "telefone": "(11) 90000-0000", "servico": "Manicure",
                 "data": "2026-10-26", "horario": "09:30", "website": ""}
        dados.update(alteracoes)
        return dados

    def enviar(self, dados=None, client=None, **kwargs):
        return (client or self.client).post("/api/agendamentos", json=dados or self.dados(),
            headers={"X-Requested-With": "MarciaNails", **kwargs.pop("headers", {})}, **kwargs)

    def test_grava_cliente_e_agendamento_e_remove_horario_da_consulta(self):
        resposta = self.enviar()
        self.assertEqual(resposta.status_code, 201)
        self.assertEqual(resposta.json["agendamento"]["horario"], "09:30")
        self.assertEqual(resposta.json["agendamento"]["fim"], "10:00")
        with self.models.Session() as sessao:
            self.assertEqual(sessao.query(self.models.Cliente).count(), 1)
            reserva = sessao.query(self.models.Agendamento).one()
            self.assertEqual(reserva.data_hora, datetime(2026,10,26,9,30))
            self.assertEqual(reserva.cliente.telefone, "11900000000")
        self.assertNotIn("09:30", self.client.get("/api/horarios?data=2026-10-26").json["horarios"])
        self.assertIn("no-store", resposta.headers["Cache-Control"])

    def test_segundo_horario_reutiliza_cliente_sem_expor_ou_sobrescrever_nome(self):
        self.assertEqual(self.enviar().status_code, 201)
        resposta = self.enviar(self.dados(nome="Outro Nome", horario="10:00", telefone="+55 11 90000-0000"))
        self.assertEqual(resposta.status_code, 201)
        self.assertEqual(resposta.json["agendamento"]["nome"], "Outro Nome")
        with self.models.Session() as sessao:
            self.assertEqual(sessao.query(self.models.Cliente).count(), 1)
            self.assertEqual(sessao.query(self.models.Cliente).one().nome, "Ana Fictícia")
            self.assertEqual(sessao.query(self.models.Agendamento).count(), 2)

    def test_horario_ocupado_retorna_409_sem_criar_cliente_orfao(self):
        self.reservar(datetime(2026,10,26,9,30))
        resposta = self.enviar()
        self.assertEqual(resposta.status_code, 409)
        with self.models.Session() as sessao:
            self.assertEqual(sessao.query(self.models.Agendamento).count(), 1)
            self.assertEqual(sessao.query(self.models.Cliente).count(), 1)

    def test_duas_confirmacoes_simultaneas_criam_apenas_uma_reserva(self):
        barreira = Barrier(2)
        def confirmar(telefone):
            with self.modulo.app.test_client() as cliente:
                barreira.wait(timeout=10)
                return self.enviar(self.dados(telefone=telefone), client=cliente).status_code
        with ThreadPoolExecutor(max_workers=2) as executor:
            resultados = list(executor.map(confirmar, ["11900000001", "11900000002"]))
        self.assertEqual(sorted(resultados), [201,409])
        with self.models.Session() as sessao:
            self.assertEqual(sessao.query(self.models.Agendamento).count(), 1)
            self.assertEqual(sessao.query(self.models.Cliente).count(), 1)

    def test_validacao_invalida_nao_grava_dados(self):
        self.assertEqual(self.enviar(self.dados(nome="")).status_code, 400)
        with self.models.Session() as sessao:
            self.assertEqual(sessao.query(self.models.Cliente).count(), 0)
            self.assertEqual(sessao.query(self.models.Agendamento).count(), 0)

    def test_falha_de_gravacao_desfaz_cliente_e_nao_expoe_excecao(self):
        def falhar(*args):
            raise RuntimeError("detalhe interno simulado")
        event.listen(self.models.Agendamento, "before_insert", falhar)
        self.addCleanup(event.remove, self.models.Agendamento, "before_insert", falhar)
        with self.assertLogs(self.modulo.app.logger, level="ERROR"):
            resposta = self.enviar()
        self.assertEqual(resposta.status_code, 500)
        self.assertNotIn("detalhe interno", resposta.get_data(as_text=True))
        with self.models.Session() as sessao:
            self.assertEqual(sessao.query(self.models.Cliente).count(), 0)
            self.assertEqual(sessao.query(self.models.Agendamento).count(), 0)

    def test_rejeita_origem_externa_e_envio_sem_cabecalho(self):
        self.assertEqual(self.enviar(headers={"Origin":"https://outro-exemplo.invalid"}).status_code, 403)
        self.assertEqual(self.client.post("/api/agendamentos",json=self.dados()).status_code, 403)
        self.assertEqual(self.client.post("/api/agendamentos",data="texto",headers={"X-Requested-With":"MarciaNails"}).status_code, 415)

    def test_limita_tentativas_repetidas(self):
        self.modulo.app.config["RESERVAS_POR_MINUTO"] = 2
        self.assertEqual(self.enviar().status_code, 201)
        self.assertEqual(self.enviar().status_code, 409)
        resposta = self.enviar()
        self.assertEqual(resposta.status_code, 429)
        self.assertIn("Retry-After", resposta.headers)

    def test_limita_tamanho_da_requisicao(self):
        self.assertEqual(self.enviar(self.dados(nome="A" * 10000)).status_code, 413)

    def test_horario_sobreposto_tambem_e_recusado(self):
        self.reservar(datetime(2026,10,26,9,15))
        self.assertEqual(self.enviar().status_code, 409)

    def test_erro_sql_nao_expoe_parametros_nem_no_log(self):
        fabrica = MagicMock()
        fabrica.return_value.__enter__.return_value.execute.side_effect = OperationalError(
            "consulta simulada", {"nome": "nome privado", "telefone": "telefone privado"}, Exception("erro privado"))
        with patch.object(self.modulo, "Session", fabrica):
            with self.assertLogs(self.modulo.app.logger, level="ERROR") as registros:
                resposta = self.enviar()
        self.assertEqual(resposta.status_code, 503)
        for texto in [resposta.get_data(as_text=True), "\n".join(registros.output)]:
            self.assertNotIn("nome privado", texto)
            self.assertNotIn("telefone privado", texto)
            self.assertNotIn("erro privado", texto)
