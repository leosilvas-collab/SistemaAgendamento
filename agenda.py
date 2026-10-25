"""Disponibilidade da agenda: regras independentes de Flask e SQLite."""

from collections.abc import Iterable
from datetime import date, datetime, time, timedelta


DURACAO_MINUTOS = 30
DURACAO = timedelta(minutes=DURACAO_MINUTOS)


def horarios_disponiveis(dia: date, ocupados: Iterable[datetime]) -> list[str]:
    """Retorna os inícios livres; datas e horas representam o horário local do salão."""
    if dia.weekday() == 6:
        return []

    reservas = tuple(ocupados)
    livres = []
    for abertura, fechamento in [(time(8), time(12)), (time(13), time(18))]:
        inicio = datetime.combine(dia, abertura)
        limite = datetime.combine(dia, fechamento)
        while inicio + DURACAO <= limite:
            fim = inicio + DURACAO
            # Intervalos encostados são permitidos; sobreposição não é.
            if not any(inicio < reserva + DURACAO and fim > reserva for reserva in reservas):
                livres.append(inicio.strftime("%H:%M"))
            inicio = fim
    return livres
