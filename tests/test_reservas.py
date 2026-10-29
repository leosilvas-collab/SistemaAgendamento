"""Validação dos dados de reserva, sem acesso ao banco."""
from datetime import datetime
import unittest

from reservas import validar_reserva, ReservaInvalida


class ValidacaoReservaTests(unittest.TestCase):
    def dados(self, **alteracoes):
        dados = {"nome": "Ana Silva", "telefone": "(11) 90000-0000", "servico": "Manicure",
                 "data": "2026-10-26", "horario": "09:30", "website": ""}
        dados.update(alteracoes)
        return dados

    def validar(self, dados):
        return validar_reserva(dados, datetime(2026, 10, 26, 7))

    def test_normaliza_nome_e_telefone(self):
        dados = self.validar(self.dados(nome="  Ana   Silva  ", telefone="+55 (11) 90000-0000"))
        self.assertEqual(dados["nome"], "Ana Silva")
        self.assertEqual(dados["telefone"], "11900000000")

    def test_rejeita_campos_vazios_tipos_errados_e_valores_invalidos(self):
        casos = [{"nome": ""}, {"nome": "A"}, {"nome": ["Ana"]}, {"nome": "<script>alert(1)</script>"},
                 {"telefone": "abc11900000000"}, {"telefone": "123"}, {"telefone": 11900000000},
                 {"servico": "Pé e Mão"}, {"data": "26/10/2026"}, {"data": "2026-02-30"},
                 {"data": "2026-12-31"}, {"horario": "09:15"}, {"horario": "12:00"},
                 {"horario": "18:00"}, {"website": "spam"}, {"cliente_id": 1}, {"status": "confirmado"}]
        for caso in casos:
            with self.subTest(caso=caso), self.assertRaises(ReservaInvalida):
                self.validar(self.dados(**caso))
        for dados in [None, [], "texto", {}]:
            with self.subTest(dados=dados), self.assertRaises(ReservaInvalida):
                self.validar(dados)

    def test_rejeita_domingo_e_horario_que_ja_comecou(self):
        for dados, agora in [(self.dados(data="2026-11-01"), datetime(2026,10,26,7)),
                             (self.dados(horario="09:30"), datetime(2026,10,26,9,30))]:
            with self.subTest(dados=dados), self.assertRaises(ReservaInvalida):
                validar_reserva(dados, agora)

    def test_aceita_encaixe_sem_antecedencia_adicional(self):
        dados = validar_reserva(self.dados(horario="17:30"), datetime(2026,10,26,17,29))
        self.assertEqual(dados["data_hora"], datetime(2026,10,26,17,30))
