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
