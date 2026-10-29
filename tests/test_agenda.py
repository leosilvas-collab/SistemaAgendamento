"""Regras da agenda com datas fixas e sem acesso ao banco."""

from datetime import date, datetime, time, timedelta
import unittest

from agenda import horarios_disponiveis, datas_disponiveis, agora_sao_paulo


ESPERADOS = [
    "08:00", "08:30", "09:00", "09:30", "10:00", "10:30", "11:00", "11:30",
    "13:00", "13:30", "14:00", "14:30", "15:00", "15:30", "16:00", "16:30",
    "17:00", "17:30",
]


class HorariosTests(unittest.TestCase):
    def test_segunda_a_sabado_oferecem_exatamente_18_horarios(self):
        segunda = date(2026, 10, 26)
        for deslocamento in range(6):
            dia = segunda + timedelta(days=deslocamento)
            with self.subTest(dia=dia):
                self.assertEqual(horarios_disponiveis(dia, []), ESPERADOS)

    def test_domingo_nao_oferece_horarios(self):
        self.assertEqual(horarios_disponiveis(date(2026, 11, 1), []), [])

    def test_nao_oferece_horarios_no_almoco_ou_fora_do_expediente(self):
        horarios = horarios_disponiveis(date(2026, 10, 26), [])
        for horario in ["07:30", "12:00", "12:30", "18:00"]:
            with self.subTest(horario=horario):
                self.assertNotIn(horario, horarios)
        for horario in ["08:00", "11:30", "13:00", "17:30"]:
            self.assertIn(horario, horarios)

    def test_reserva_remove_apenas_o_horario_ocupado(self):
        dia = date(2026, 10, 26)
        ocupados = [datetime.combine(dia, time(9, 30))]
        self.assertEqual(
            horarios_disponiveis(dia, ocupados),
            [h for h in ESPERADOS if h != "09:30"],
        )

    def test_reserva_de_outro_dia_nao_bloqueia_o_dia_consultado(self):
        self.assertEqual(
            horarios_disponiveis(date(2026, 10, 26), [datetime(2026, 10, 27, 9, 30)]),
            ESPERADOS,
        )

    def test_dia_totalmente_ocupado_retorna_lista_vazia(self):
        dia = date(2026, 10, 26)
        ocupados = [datetime.combine(dia, time.fromisoformat(h)) for h in ESPERADOS]
        self.assertEqual(horarios_disponiveis(dia, ocupados), [])

    def test_reserva_duplicada_nao_remove_outros_horarios(self):
        reserva = datetime(2026, 10, 26, 9, 30)
        self.assertEqual(
            horarios_disponiveis(reserva.date(), [reserva, reserva]),
            [h for h in ESPERADOS if h != "09:30"],
        )

    def test_reserva_fora_da_grade_bloqueia_todos_os_intervalos_sobrepostos(self):
        # Protege contra registros antigos inseridos manualmente, como 09:15.
        self.assertEqual(
            horarios_disponiveis(date(2026, 10, 26), [datetime(2026, 10, 26, 9, 15)]),
            [h for h in ESPERADOS if h not in {"09:00", "09:30"}],
        )


class EncaixesTests(unittest.TestCase):
    def test_hoje_ainda_oferece_17h30_as_17h29(self):
        self.assertEqual(horarios_disponiveis(date(2026, 10, 26), [], datetime(2026, 10, 26, 17, 29)), ["17:30"])

    def test_horario_que_ja_comecou_nao_e_oferecido(self):
        for minuto in [30, 31]:
            with self.subTest(minuto=minuto):
                self.assertEqual(horarios_disponiveis(date(2026, 10, 26), [], datetime(2026, 10, 26, 17, minuto)), [])

    def test_almoco_preserva_os_dez_horarios_da_tarde(self):
        self.assertEqual(horarios_disponiveis(date(2026, 10, 26), [], datetime(2026, 10, 26, 12, 20)), ESPERADOS[8:])

    def test_datas_passadas_nao_tem_disponibilidade(self):
        self.assertEqual(horarios_disponiveis(date(2026, 10, 26), [], datetime(2026, 10, 27, 7)), [])

    def test_hoje_tem_prioridade_quando_existe_encaixe(self):
        dados = datas_disponiveis(datetime(2026, 10, 26, 17, 20), [])
        self.assertEqual(dados["primeira_disponivel"], "2026-10-26")

    def test_ultimo_horario_ocupado_avanca_para_o_dia_seguinte(self):
        dados = datas_disponiveis(datetime(2026, 10, 26, 17, 20), [datetime(2026, 10, 26, 17, 30)])
        self.assertEqual(dados["primeira_disponivel"], "2026-10-27")

    def test_sabado_encerrado_pula_domingo(self):
        dados = datas_disponiveis(datetime(2026, 10, 31, 17, 31), [])
        self.assertEqual(dados["primeira_disponivel"], "2026-11-02")

    def test_periodo_contem_resto_da_semana_e_cinco_semanas_completas(self):
        dados = datas_disponiveis(datetime(2026, 10, 28, 7), [])
        self.assertEqual([len(s["dias"]) for s in dados["semanas"]], [4, 6, 6, 6, 6, 6])
        self.assertEqual(dados["limite"], "2026-12-05")
        self.assertTrue(dados["semanas"][0]["dias"][0]["rotulo"].startswith("Hoje"))
        for semana in dados["semanas"]:
            for dia in semana["dias"]:
                self.assertNotEqual(date.fromisoformat(dia["data"]).weekday(), 6)

    def test_domingo_mostra_cinco_semanas_sem_grupo_vazio(self):
        dados = datas_disponiveis(datetime(2026, 11, 1, 7), [])
        self.assertEqual([len(s["dias"]) for s in dados["semanas"]], [6] * 5)

    def test_periodo_totalmente_ocupado_nao_inventa_data(self):
        agora = datetime(2026, 10, 26, 7)
        dados = datas_disponiveis(agora, [])
        reservas = [datetime.combine(date.fromisoformat(dia["data"]), time.fromisoformat(h))
                    for s in dados["semanas"] for dia in s["dias"] for h in ESPERADOS]
        self.assertIsNone(datas_disponiveis(agora, reservas)["primeira_disponivel"])

    def test_relogio_usa_fuso_de_sao_paulo(self):
        self.assertEqual(agora_sao_paulo().tzinfo.key, "America/Sao_Paulo")

    def test_instante_utc_e_convertido_antes_de_filtrar(self):
        from datetime import timezone
        agora = datetime(2026, 10, 26, 20, 20, tzinfo=timezone.utc)
        self.assertEqual(horarios_disponiveis(date(2026, 10, 26), [], agora), ["17:30"])
