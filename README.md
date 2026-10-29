# SistemaAgendamento
Início da experiência prática da matéria Projeto de Software

# Sistema de Agendamento — Studio Márcia Nails

Projeto desenvolvido para a disciplina de Projeto de Software do curso de Análise e Desenvolvimento de Sistemas.

A proposta é criar um sistema de agendamento para o Studio Márcia Nails, um pequeno empreendimento de Salto/SP. O objetivo é organizar os horários e reduzir os conflitos de agenda e o tempo de espera das clientes.

## Funcionalidades previstas

- Consultar horários disponíveis.
- Agendar um atendimento.
- Permitir que a profissional acompanhe a agenda do dia.

## Tecnologias

Python, Flask, SQLAlchemy e SQLite.

## Situação atual

A PWA consulta horários, registra reservas no SQLite e oferece seleção acessível de datas e alto contraste. Há uma Área de Gestão para acompanhar atendimentos e um painel do proprietário para pré-cadastrar gestores e administrar planos.

## Executar localmente (PowerShell)

```powershell
python -m venv .venv
.\.venv\Scripts\python.exe -m pip install -r requirements.txt
.\.venv\Scripts\python.exe app.py
```

Abra http://127.0.0.1:5000/. O banco local fica em data/ e não deve ser versionado.

Para o primeiro acesso, consulte [as instruções de gestão](docs/gestao.md). Não há senha padrão. A conta marcia@marcia.com começa no plano pago para a demonstração acadêmica.

## Testes

```powershell
.\.venv\Scripts\python.exe -m unittest discover -s tests -v
```

Os testes de integração utilizam bancos SQLite temporários. O projeto é uma demonstração acadêmica local; o fluxo simplificado de ativação ainda não verifica a posse do e-mail.
