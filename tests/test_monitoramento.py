"""Monitoramento com SQLite temporário e falhas simuladas, sem interromper o site."""
import unittest
from unittest.mock import patch
import test_horarios_integracao as base

class MonitoramentoTests(unittest.TestCase):
    setUp = base.HorariosIntegracaoTests.setUp

    def test_health_ok_confere_o_banco_e_nao_expoe_dados(self):
        r=self.client.get("/health")
        self.assertEqual(r.status_code,200)
        self.assertEqual(r.json,{"banco":"ok","status":"ok"})
        self.assertIn("no-store",r.headers["Cache-Control"])

    def test_health_down_retorna_503_sem_detalhes_internos(self):
        with patch.object(self.modulo,"Session",side_effect=RuntimeError("detalhe privado")):
            r=self.client.get("/health")
        self.assertEqual(r.status_code,503)
        self.assertEqual(r.json,{"banco":"offline","status":"indisponivel"})
        self.assertNotIn("detalhe privado",r.get_data(as_text=True))
        self.assertIn("no-store",r.headers["Cache-Control"])

    def test_painel_publico_tem_estados_e_atualizacao_acessivel(self):
        r=self.client.get("/monitoramento")
        self.assertEqual(r.status_code,200)
        self.assertIn("no-store",r.headers["Cache-Control"])
        html=r.get_data(as_text=True)
        self.assertIn('id="estado-servico"',html)
        self.assertIn('id="estado-banco"',html)
        self.assertIn('aria-live="polite"',html)
        self.assertIn('/static/monitoramento.js',html)
        self.assertIn('enquanto esta página estiver aberta',html)
