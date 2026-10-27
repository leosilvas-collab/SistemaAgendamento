"""Testa as respostas HTTP sem abrir o SQLite real do projeto."""

import importlib.util
import logging
from pathlib import Path
from types import ModuleType
import unittest
from unittest.mock import MagicMock, patch


class StatusBancoTests(unittest.TestCase):
    def setUp(self):
        self.session = MagicMock()
        models = ModuleType("models")
        models.session = self.session
        models.Session = MagicMock()
        models.Session.return_value.__enter__.return_value = self.session
        models.Cliente = type("Cliente", (), {})
        models.Agendamento = type("Agendamento", (), {})

        # Substituir models evita a criação automática do banco durante o import.
        caminho = Path(__file__).resolve().parents[1] / "app.py"
        spec = importlib.util.spec_from_file_location("app_em_teste", caminho)
        modulo = importlib.util.module_from_spec(spec)
        with patch.dict("sys.modules", {"models": models}):
            spec.loader.exec_module(modulo)
        self.app = modulo.app
        self.app.config["TESTING"] = True
        self.client = self.app.test_client()

    def test_falha_retorna_500_e_mensagem_generica_sem_detalhes(self):
        detalhe_interno = "falha simulada: caminho /dados/interno.db"
        self.session.query.side_effect = RuntimeError(detalhe_interno)

        with patch.object(self.app.logger, "handle"):
            resposta = self.client.get("/api/status-banco")

        self.assertEqual(resposta.status_code, 500)
        self.assertEqual(resposta.get_json(), {
            "banco": "erro",
            "mensagem": "Não foi possível consultar o banco de dados.",
        })
        self.assertNotIn(detalhe_interno, resposta.get_data(as_text=True))

    def test_falha_registra_excecao_no_log_do_servidor(self):
        self.session.query.side_effect = RuntimeError("falha simulada da consulta")

        with self.assertLogs(self.app.logger, level=logging.ERROR) as registros:
            resposta = self.client.get("/api/status-banco")

        self.assertEqual(resposta.status_code, 500)
        self.assertIn("falha simulada da consulta", "\n".join(registros.output))
        self.assertIsNotNone(registros.records[0].exc_info)

    def test_consulta_bem_sucedida_preserva_as_contagens(self):
        clientes = MagicMock()
        clientes.count.return_value = 2
        agendamentos = MagicMock()
        agendamentos.count.return_value = 3
        self.session.query.side_effect = [clientes, agendamentos]

        resposta = self.client.get("/api/status-banco")

        self.assertEqual(resposta.status_code, 200)
        self.assertEqual(resposta.get_json(), {
            "banco": "conectado",
            "total_clientes": 2,
            "total_agendamentos": 3,
        })


if __name__ == "__main__":
    unittest.main()
