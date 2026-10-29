"""Validação de entrada e limite de tentativas do MVP, sem acesso ao banco."""
from collections import OrderedDict, deque
from datetime import datetime
import re
from threading import Lock
from time import monotonic
import unicodedata

from agenda import horario_local, horarios_disponiveis, limite_consulta

SERVICOS = frozenset({"Corte de Cabelo", "Pedicure", "Manicure", "Escova"})


class ReservaInvalida(ValueError):
    pass


def validar_reserva(dados, agora: datetime, permitir_futuro: bool = False) -> dict:
    campos = {"nome", "telefone", "servico", "data", "horario", "website"}
    if not isinstance(dados, dict) or set(dados) - campos:
        raise ReservaInvalida("Informe apenas os dados solicitados para a reserva.")
    for campo in ("nome", "telefone", "servico", "data", "horario"):
        if not isinstance(dados.get(campo), str) or not dados[campo].strip():
            raise ReservaInvalida("Preencha nome, telefone, serviço, data e horário.")
    if dados.get("website", "") != "":
        raise ReservaInvalida("Não foi possível validar o formulário.")
    bruto = dados["nome"]
    if any(unicodedata.category(c).startswith("C") for c in bruto):
        raise ReservaInvalida("Informe um nome válido.")
    nome = " ".join(unicodedata.normalize("NFC", bruto).split())
    if not 2 <= len(nome) <= 100 or not all(c.isalpha() or c in " '-.\u2019" for c in nome) or sum(c.isalpha() for c in nome) < 2:
        raise ReservaInvalida("Informe um nome de 2 a 100 caracteres, usando letras.")
    bruto = dados["telefone"].strip()
    if len(bruto) > 30 or not re.fullmatch(r"[0-9 ()+\-]+", bruto):
        raise ReservaInvalida("Informe um telefone válido com DDD.")
    telefone = re.sub(r"[^0-9]", "", bruto)
    if len(telefone) in (12, 13) and telefone.startswith("55"):
        telefone = telefone[2:]
    if len(telefone) not in (10, 11) or telefone[0] == "0" or telefone[1] == "0" or len(set(telefone[2:])) == 1:
        raise ReservaInvalida("Informe um telefone válido com DDD.")
    if dados["servico"] not in SERVICOS:
        raise ReservaInvalida("Selecione um dos serviços disponíveis.")
    try:
        data_hora = datetime.strptime(dados["data"] + " " + dados["horario"], "%Y-%m-%d %H:%M")
        if data_hora.strftime("%Y-%m-%d %H:%M") != dados["data"] + " " + dados["horario"]:
            raise ValueError
    except ValueError:
        raise ReservaInvalida("Selecione uma data e um horário válidos.") from None
    dia = data_hora.date()
    momento = horario_local(agora)
    if dia < momento.date() or (not permitir_futuro and dia > limite_consulta(momento.date())):
        raise ReservaInvalida("Selecione uma data dentro do período disponível.")
    if dados["horario"] not in horarios_disponiveis(dia, [], agora):
        raise ReservaInvalida("Esse horário já começou ou está fora do expediente. Escolha outro.")
    return {"nome": nome, "telefone": telefone, "servico": dados["servico"], "data_hora": data_hora}


class LimiteDeTentativas:
    """Proteção básica de um processo; em múltiplos processos, usar limite compartilhado."""
    def __init__(self):
        self.registros = OrderedDict()
        self.lock = Lock()

    def permitir(self, chave: str, limite: int) -> bool:
        agora = monotonic()
        with self.lock:
            fila = self.registros.setdefault(chave, deque())
            while fila and fila[0] <= agora - 60:
                fila.popleft()
            self.registros.move_to_end(chave)
            if len(self.registros) > 1000:
                self.registros.popitem(last=False)
            if len(fila) >= limite:
                return False
            fila.append(agora)
            return True
