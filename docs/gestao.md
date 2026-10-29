# Gestão na demonstração acadêmica

O mesmo visual móvel, os botões grandes, o alto contraste e a seleção de datas da PWA são usados nas duas áreas.

## Proprietário

Abra http://127.0.0.1:5000/proprietario no computador que executa o servidor. Não há link público para esta rota; o acesso aos dados exige autenticação e autorização no servidor.

A conta inicial é leocladison@gmail.com. No primeiro acesso, informe o e-mail e defina uma senha de exatamente seis números, com confirmação. Não existe senha padrão. A primeira ativação master só é aceita por conexão local (loopback).

O proprietário pré-cadastra apenas o e-mail de cada gestor. O painel apresenta os dados preenchidos posteriormente, o plano, o vencimento e o contador de concessões. Pode marcar o plano como pago ou conceder até três extensões de 30 dias; os dias são acrescentados ao vencimento vigente, ou à data atual quando o teste já venceu. O teste inicial tem 30 dias a partir da ativação, sem limite de quantidade de agendamentos.

“Autorizar redefinição de senha” libera uma nova definição pela Área de Gestão e encerra as sessões anteriores. Não envia e-mail e não reinicia o teste.

## Gestor

O botão Área de Gestão da PWA abre /gestao. Um e-mail pré-cadastrado sem senha abre os campos de nome, telefone, estabelecimento e senha de seis números com confirmação. Uma conta ativa solicita a senha existente.

A conta marcia@marcia.com é a conta de demonstração paga, sem vencimento e sem senha padrão. Complete o primeiro acesso para definir a senha. As reservas anteriores permanecem vinculadas à agenda da Márcia.

O gestor consulta a agenda do dia, procura clientes por nome ou telefone e faz reservas informando o serviço e um horário livre. A seleção de datas oferece os dias restantes da semana e até cinco semanas completas seguintes. O botão “Agendar a partir de…” permite informar uma data manualmente além desse período; continuam valendo expediente, duração, horários futuros e prevenção de sobreposição.

Cada estabelecimento tem seu link público próprio, disponível no painel. A agenda, a busca de clientes e os conflitos de horário são separados por estabelecimento. A página pública sem parâmetro continua sendo a do Studio Márcia Nails.

Ao vencer o teste, gestor e clientes deixam de criar reservas; o gestor continua consultando os atendimentos existentes. A área de pagamento é apenas informativa: não cobra, não simula transações nem ativa planos automaticamente.

## Proteções e limites

As senhas recebem hash bcrypt no servidor (custo 12). As sessões têm duração de oito horas, identificador aleatório em cookie HttpOnly/SameSite e registro revogável no banco; o logout revoga a sessão. Operações autenticadas exigem token CSRF e verificação de origem. As falhas de senha impõem esperas progressivas de 1, 2, 4, 8 e 60 segundos, mantidas no banco e reavaliadas pelo servidor.

O primeiro cadastro de gestor e a redefinição autorizada não verificam a posse do e-mail, por decisão de escopo desta demonstração local. Quem conhecer um e-mail pendente poderá completar esse cadastro. Esse fluxo e a senha curta precisam ser revistos antes de disponibilizar o sistema comercialmente. Não há recuperação automática da senha master.

O banco ganhou tabelas de usuários, sessões, tentativas e vínculos de agenda. As tabelas originais de clientes e agendamentos são preservadas. O vínculo guarda o nome informado em cada reserva para evitar misturar nomes entre estabelecimentos com o mesmo telefone. Dados e respostas privadas não entram no cache offline da PWA.

## Alteração e exclusão de atendimentos

Cada card da agenda oferece Alterar agendamento e Excluir agendamento. A alteração preenche o formulário com os dados existentes e permite mudar nome, telefone, serviço, data e horário. Ao mudar a data, consulte os horários antes de salvar. Cancelar alteração mantém a reserva original. O servidor verifica novamente o expediente e os conflitos, ignorando apenas a própria reserva durante a edição e mantendo o mesmo identificador.

A exclusão exige confirmação na interface. Ela retira o atendimento da agenda e libera o horário, preservando o registro no banco com status cancelado. Dados de outras reservas e cadastros de clientes não são apagados. Alteração e exclusão exigem sessão do gestor responsável, token CSRF e plano válido; testes vencidos permanecem somente para consulta.
