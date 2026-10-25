"""Regras da agenda com datas fixas e sem acesso ao banco."""

from datetime import date, datetime, time, timedelta
import unittest

from agenda import horarios_disponiveis


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
