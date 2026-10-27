"""Integração entre HTTP, modelos e SQLite real em arquivo temporário."""

from datetime import datetime
import importlib.util
from pathlib import Path
from tempfile import TemporaryDirectory
import unittest
from unittest.mock import patch

from sqlalchemy import create_engine
from sqlalchemy.pool import NullPool


RAIZ = Path(__file__).resolve().parents[1]


def carregar_modulo(nome, arquivo):
    spec = importlib.util.spec_from_file_location(nome, RAIZ / arquivo)
    modulo = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(modulo)
    return modulo


class HorariosIntegracaoTests(unittest.TestCase):
    def setUp(self):
        self.pasta = TemporaryDirectory(prefix="agenda-teste-", dir=RAIZ / "tests")
        self.addCleanup(self.pasta.cleanup)
        caminho = Path(self.pasta.name) / "teste.db"
        self.engine = create_engine(f"sqlite:///{caminho.as_posix()}", poolclass=NullPool)
        self.addCleanup(self.engine.dispose)

        # models cria tabelas ao importar: direcionamos essa conexão ao arquivo
        # temporário antes do import, sem abrir data/studio_marcia_nails.db.
        with patch("sqlalchemy.create_engine", return_value=self.engine):
            self.models = carregar_modulo("models_integracao", "models.py")
        self.addCleanup(self.models.session.close)
        with patch.dict("sys.modules", {"models": self.models}):
            self.modulo = carregar_modulo("app_integracao", "app.py")
        self.relogio = patch.object(self.modulo, "agora_sao_paulo", return_value=datetime(2026, 10, 26, 7))
        self.relogio.start()
        self.addCleanup(self.relogio.stop)
        self.modulo.app.config["TESTING"] = True
        self.client = self.modulo.app.test_client()

    def reservar(self, data_hora):
        with self.models.Session() as sessao:
            cliente = self.models.Cliente(nome="Cliente fictícia", telefone="11900000000")
            sessao.add(self.models.Agendamento(
                cliente=cliente, data_hora=data_hora, servico="Manicure",
            ))
            sessao.commit()

    def test_banco_vazio_retorna_18_horarios(self):
        resposta = self.client.get("/api/horarios?data=2026-10-26")
        self.assertEqual(resposta.status_code, 200)
        dados = resposta.get_json()
        self.assertEqual(dados["data"], "2026-10-26")
        self.assertEqual(dados["duracao_minutos"], 30)
        self.assertEqual(len(dados["horarios"]), 18)
        self.assertEqual(dados["horarios"][0], "08:00")
        self.assertEqual(dados["horarios"][-1], "17:30")

    def test_reserva_gravada_no_sqlite_deixa_de_aparecer(self):
        self.reservar(datetime(2026, 10, 26, 9, 30))
        resposta = self.client.get("/api/horarios?data=2026-10-26")
        self.assertEqual(resposta.status_code, 200)
        self.assertEqual(len(resposta.json["horarios"]), 17)
        self.assertNotIn("09:30", resposta.json["horarios"])
        self.assertIn("09:00", resposta.json["horarios"])
        self.assertIn("10:00", resposta.json["horarios"])
        self.assertEqual(set(resposta.json), {"data", "duracao_minutos", "horarios"})
        self.assertNotIn("Cliente fictícia", resposta.get_data(as_text=True))
        self.assertNotIn("11900000000", resposta.get_data(as_text=True))

    def test_reserva_de_outro_dia_nao_bloqueia(self):
        self.reservar(datetime(2026, 10, 27, 9, 30))
        resposta = self.client.get("/api/horarios?data=2026-10-26")
        self.assertEqual(resposta.status_code, 200)
        self.assertEqual(len(resposta.json["horarios"]), 18)

    def test_domingo_retorna_lista_vazia(self):
        resposta = self.client.get("/api/horarios?data=2026-11-01")
        self.assertEqual(resposta.status_code, 200)
        self.assertEqual(resposta.json["horarios"], [])

    def test_data_ausente_ou_invalida_retorna_400(self):
        for sufixo in ["", "?data=", "?data=26/10/2026", "?data=2026-02-30",
                       "?data=20261026", "?data=texto", "?data=2026-10-26&data=2026-10-27"]:
            with self.subTest(sufixo=sufixo):
                resposta = self.client.get("/api/horarios" + sufixo)
                self.assertEqual(resposta.status_code, 400)
                self.assertEqual(resposta.json, {"mensagem": "Informe uma data válida no formato AAAA-MM-DD."})

    def test_falha_do_banco_retorna_erro_generico_e_registra_log(self):
        with patch.object(self.modulo, "Session", side_effect=RuntimeError("falha simulada interna")):
            with self.assertLogs(self.modulo.app.logger, level="ERROR") as registros:
                resposta = self.client.get("/api/horarios?data=2026-10-26")
        self.assertEqual(resposta.status_code, 500)
        self.assertEqual(resposta.json, {"mensagem": "Não foi possível consultar os horários."})
        self.assertNotIn("falha simulada interna", resposta.get_data(as_text=True))
        self.assertIn("falha simulada interna", "\n".join(registros.output))

    def test_inicio_entrega_pagina_com_formulario_acessivel(self):
        resposta = self.client.get("/")
        self.assertEqual(resposta.status_code, 200)
        self.assertTrue(resposta.content_type.startswith("text/html"))
        pagina = resposta.get_data(as_text=True)
        self.assertIn('lang="pt-BR"', pagina)
        self.assertIn('aria-controls="painel-datas"', pagina)
        self.assertNotIn("Consultar horários", pagina)
        self.assertIn('id="tentar-novamente" class="primario" type="button" hidden', pagina)
        self.assertIn("Corte de Cabelo", pagina)
        self.assertIn("Pedicure", pagina)
        self.assertIn("Manicure", pagina)
        self.assertIn("Escova", pagina)
        self.assertIn('aria-live="polite"', pagina)
        self.assertIn("Alto contraste", pagina)

    def test_status_da_aplicacao_permanece_disponivel_em_json(self):
        resposta = self.client.get("/api/status")
        self.assertEqual(resposta.status_code, 200)
        self.assertEqual(resposta.json["status"], "online")

    def test_manifesto_pwa_define_inicio_e_icones(self):
        resposta = self.client.get("/manifest.webmanifest")
        self.assertEqual(resposta.status_code, 200)
        self.assertEqual(resposta.json["start_url"], "/")
        self.assertEqual(resposta.json["display"], "standalone")
        for icone in resposta.json["icons"]:
            self.assertEqual(self.client.get(icone["src"]).status_code, 200)

    def test_service_worker_e_pagina_offline_estao_disponiveis(self):
        resposta = self.client.get("/sw.js")
        self.assertEqual(resposta.status_code, 200)
        self.assertIn("javascript", resposta.content_type)
        self.assertEqual(self.client.get("/static/offline.html").status_code, 200)

    def test_disponibilidade_nao_pode_ser_guardada_em_cache(self):
        resposta = self.client.get("/api/horarios?data=2026-10-26")
        self.assertEqual(resposta.status_code, 200)
        self.assertIn("no-store", resposta.headers.get("Cache-Control", ""))

    def test_consulta_rejeita_horarios_passados_e_preserva_encaixe(self):
        self.relogio.stop()
        with patch.object(self.modulo, "agora_sao_paulo", return_value=datetime(2026, 10, 26, 17, 29)):
            resposta = self.client.get("/api/horarios?data=2026-10-26")
        self.assertEqual(resposta.status_code, 200)
        self.assertEqual(resposta.json["horarios"], ["17:30"])

    def test_api_datas_prioriza_hoje_e_avanca_se_ultimo_horario_esta_ocupado(self):
        self.relogio.stop()
        with patch.object(self.modulo, "agora_sao_paulo", return_value=datetime(2026, 10, 26, 17, 20)):
            antes = self.client.get("/api/datas")
            self.assertEqual(antes.status_code, 200)
            self.assertEqual(antes.json["primeira_disponivel"], "2026-10-26")
            self.reservar(datetime(2026, 10, 26, 17, 30))
            depois = self.client.get("/api/datas")
        self.assertEqual(depois.status_code, 200)
        self.assertEqual(depois.json["primeira_disponivel"], "2026-10-27")
        self.assertEqual(len(depois.json["semanas"]), 6)
        self.assertIn("no-store", depois.headers["Cache-Control"])

    def test_consulta_data_passada_nao_retorna_horarios(self):
        resposta = self.client.get("/api/horarios?data=2026-10-25")
        self.assertEqual(resposta.status_code, 200)
        self.assertEqual(resposta.json["horarios"], [])

    def test_api_datas_nao_expoe_dados_de_clientes(self):
        self.reservar(datetime(2026, 10, 26, 9, 30))
        resposta = self.client.get("/api/datas")
        self.assertEqual(resposta.status_code, 200)
        self.assertNotIn("Cliente fictícia", resposta.get_data(as_text=True))
        self.assertNotIn("11900000000", resposta.get_data(as_text=True))

    def test_api_datas_falha_com_mensagem_generica(self):
        with patch.object(self.modulo, "Session", side_effect=RuntimeError("falha interna")):
            with self.assertLogs(self.modulo.app.logger, level="ERROR"):
                resposta = self.client.get("/api/datas")
        self.assertEqual(resposta.status_code, 500)
        self.assertEqual(resposta.json, {"mensagem": "Não foi possível consultar as datas."})
