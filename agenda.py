"""Regras da agenda, independentes de Flask e SQLite."""

from collections.abc import Iterable
from datetime import date, datetime, time, timedelta
from zoneinfo import ZoneInfo


DURACAO_MINUTOS = 30
DURACAO = timedelta(minutes=DURACAO_MINUTOS)
FUSO = ZoneInfo("America/Sao_Paulo")
DIAS = ("Segunda-feira", "Terça-feira", "Quarta-feira", "Quinta-feira", "Sexta-feira", "Sábado", "Domingo")
MESES = ("janeiro", "fevereiro", "março", "abril", "maio", "junho", "julho", "agosto", "setembro", "outubro", "novembro", "dezembro")


def agora_sao_paulo() -> datetime:
    return datetime.now(FUSO)


def horario_local(agora: datetime) -> datetime:
    """O SQLite guarda horas locais sem fuso; convertemos antes de comparar."""
    if agora.tzinfo is not None:
        return agora.astimezone(FUSO).replace(tzinfo=None)
    return agora


def limite_consulta(hoje: date) -> date:
    segunda_atual = hoje - timedelta(days=hoje.weekday())
    return segunda_atual + timedelta(weeks=5, days=5)


def horarios_disponiveis(dia: date, ocupados: Iterable[datetime], agora: datetime | None = None) -> list[str]:
    """Sem relógio explícito, calcula apenas a grade; a API sempre passa o relógio."""
    if dia.weekday() == 6:
        return []
    momento = horario_local(agora) if agora is not None else None
    reservas = tuple(ocupados)
    livres = []
    for abertura, fechamento in [(time(8), time(12)), (time(13), time(18))]:
        inicio = datetime.combine(dia, abertura)
        limite = datetime.combine(dia, fechamento)
        while inicio + DURACAO <= limite:
            fim = inicio + DURACAO
            # O início deve ser futuro. Intervalos encostados não se sobrepõem.
            if (momento is None or inicio > momento) and not any(
                inicio < reserva + DURACAO and fim > reserva for reserva in reservas
            ):
                livres.append(inicio.strftime("%H:%M"))
            inicio = fim
    return livres


def datas_disponiveis(agora: datetime, ocupados: Iterable[datetime]) -> dict:
    hoje = horario_local(agora).date()
    limite = limite_consulta(hoje)
    segunda = hoje - timedelta(days=hoje.weekday())
    reservas_por_dia = {}
    for reserva in ocupados:
        reservas_por_dia.setdefault(reserva.date(), []).append(reserva)
    grupos = {}
    primeira = None
    dia = hoje
    while dia <= limite:
        if dia.weekday() != 6:
            livres = horarios_disponiveis(dia, reservas_por_dia.get(dia, []), agora)
            numero_semana = (dia - segunda).days // 7
            grupo = grupos.setdefault(numero_semana, {
                "rotulo": "Esta semana" if numero_semana == 0 else f"Semana de {(segunda + timedelta(weeks=numero_semana)).strftime('%d/%m')}",
                "dias": [],
            })
            grupo["dias"].append({
                "data": dia.isoformat(),
                "rotulo": ("Hoje — " if dia == hoje else "") + DIAS[dia.weekday()],
                "descricao": f"{dia.day} de {MESES[dia.month - 1]} de {dia.year}",
                "disponivel": bool(livres),
                "quantidade_horarios": len(livres),
            })
            if primeira is None and livres:
                primeira = dia.isoformat()
        dia += timedelta(days=1)
    return {"hoje": hoje.isoformat(), "limite": limite.isoformat(),
            "primeira_disponivel": primeira, "semanas": list(grupos.values())}
