# MVP — Agendamento simplificado

Permitir que a cliente escolha um dia, consulte horários livres e agende sem criar conta ou senha. Márcia pode registrar um atendimento pelo mesmo fluxo, informando os dados da cliente.

## Serviços fixos do MVP

| Serviço | Duração |
|---|---|
| Corte de Cabelo | 30 minutos |
| Pedicure | 30 minutos |
| Manicure | 30 minutos |
| Escova | 30 minutos |

A personalização de serviços e durações por Márcia ficará para depois da conclusão das atividades acadêmicas.

## Dias e horários de atendimento

Márcia atende de segunda-feira a sábado. Todos os serviços do MVP têm duração de 30 minutos.

- Manhã: das 08:00 às 12:00, com último agendamento às 11:30;
- Almoço: das 12:00 às 13:00, sem agendamentos;
- Tarde: das 13:00 às 18:00, com último agendamento às 17:30;
- Domingo: sem atendimento.

A agenda oferece até 18 horários por dia. Apenas os horários livres devem aparecer para seleção.

## Fluxo

1. Escolher dia e serviço;
2. Consultar e selecionar um horário livre;
3. Informar nome e telefone com DDD;
4. Conferir o resumo e confirmar;
5. Visualizar serviço, data, início e término da reserva.

O registro da cliente acontece durante o agendamento, sem cadastro separado.

## Regras previstas

- Cada atendimento ocupa 30 minutos da agenda de Márcia;
- Horários ocupados não aparecem como disponíveis;
- Ao confirmar, conferir novamente a disponibilidade para impedir sobreposição;
- Se o horário tiver sido ocupado, mostrar um aviso e permitir escolher outro;
- Nome, telefone, serviço, dia e horário são obrigatórios;
- Dados de contato não aparecem na consulta pública de horários;
- A confirmação será na tela. Lembretes automáticos não fazem parte deste rascunho.

## Critérios de aceite da consulta de horários

- De segunda-feira a sábado, um dia sem reservas apresenta 18 horários disponíveis;
- Aos domingos, a agenda não oferece horários;
- Os horários são apresentados em ordem, com intervalos de 30 minutos;
- O último atendimento da manhã começa às 11:30 e termina às 12:00;
- O primeiro atendimento da tarde começa às 13:00;
- O último atendimento do dia começa às 17:30 e termina às 18:00;
- Horários reservados deixam de aparecer como disponíveis;
- Se não houver horários livres no dia escolhido, a página informa isso e permite selecionar outro dia.

## Ainda a definir antes de implementar

- Regras para bloquear horários, cancelar e remarcar.
- Proteção das operações e dos dados exclusivos de Márcia.

Os horários e a cliente do desenho são exemplos. O desenho não executa reservas nem comprova acessibilidade; esses critérios serão verificados na interface funcional.

## Rascunho

![Fluxo em três estados](rascunho-agendamento.png)
