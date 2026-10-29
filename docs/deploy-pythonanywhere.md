# Publicação no PythonAnywhere

URL pública: https://leocladison.pythonanywhere.com/
Saúde da aplicação e do SQLite: https://leocladison.pythonanywhere.com/health

A cópia publicada veio da branch docs/regras-agendamento, commit b08191f, com os ajustes de implantação descritos aqui. Não foi copiado o banco local. A reserva fictícia utilizada para validar o fluxo público foi cancelada e seu horário foi liberado.

## Configuração

- Código: /home/leocladison/marcia-nails
- Ambiente: /home/leocladison/.virtualenvs/marcia-nails, Python 3.13.
- Dependências instaladas a partir de requirements.txt.
- Aplicação WSGI: deploy_pythonanywhere.application.
- Arquivo WSGI: /var/www/leocladison_pythonanywhere_com_wsgi.py.
- Mapeamento estático: /static/ para /home/leocladison/marcia-nails/static.
- HTTPS forçado no painel Web do PythonAnywhere.
- SQLite persistido em data/studio_marcia_nails.db; não versionar nem substituir o arquivo nas atualizações.

O arquivo WSGI acrescenta /home/leocladison/marcia-nails a sys.path e importa application de deploy_pythonanywhere. Não se inicia o servidor com app.run nesta hospedagem.

## Acessos

Proprietário: leocladison@leocladison.com. Gestora de demonstração: marcia@marcia.com, plano pago. O e-mail do proprietário é definido por MARCIA_OWNER_EMAIL no módulo de implantação; o padrão do ambiente local foi mantido para preservar os testes existentes.

Nenhuma senha padrão foi criada. No console Bash, execute:

```bash
cd /home/leocladison/marcia-nails
/home/leocladison/.virtualenvs/marcia-nails/bin/python definir_acessos.py
```

O próprio usuário deve digitar e confirmar uma senha de seis números para cada conta. A digitação fica oculta, e somente os hashes bcrypt são salvos. Ao concluir, os acessos são /proprietario e /gestao. O procedimento também pode redefinir essas duas senhas e revogar as sessões anteriores.

Na implantação pública, a definição de senhas pela rota /api/acesso/ativar foi bloqueada. O cadastro simplificado por e-mail foi concebido para uso local e não verifica sua posse; por isso, as duas contas publicadas usam a definição pelo console. A criação e redefinição de acessos adicionais pela interface não estão habilitadas de ponta a ponta nesta implantação. Isso deve ser revisto com verificação de e-mail antes do uso comercial.

/api/status-banco não expõe contagens no ambiente publicado. /health retorna 200 com status ok quando consegue consultar o banco e 503 em caso de falha. A rota está pronta para um monitor externo; nenhum serviço externo de alertas foi configurado nesta etapa.

## Atualização e manutenção

Os arquivos de implantação e a mudança de models.py ainda precisam ser incluídos no próximo commit feito pelo usuário. Antes de um futuro git pull no servidor, confira git status e preserve essas alterações locais; não use comandos que descartem modificações.

Após atualizar o código e as dependências, use Reload na aba Web e verifique /health e o fluxo público. Faça cópia consistente do SQLite antes de mudanças no banco. A hospedagem gratuita exige renovação periódica pelo botão Run until 1 month from today; confira o vencimento exibido no painel para manter o endereço ativo durante a correção acadêmica.

## Painel visual de monitoramento

/monitoramento consulta /health a cada 30 segundos enquanto estiver aberto. Mostra STATUS OK / UP e BANCO OK em verde quando a consulta SQL funciona; na falha confirmada da sonda, mostra DOWN e BANCO OFFLINE em vermelho. Sem resposta válida ou sem conexão do dispositivo, o serviço aparece como DOWN e o banco como NÃO VERIFICADO. Cada consulta tem limite de oito segundos. A tela informa a hora em São Paulo e a última transição observada desde que foi aberta, sem inventar percentual de uptime ou histórico anterior. O botão Verificar agora permite uma consulta imediata. Não há notificações externas, e o navegador pode reduzir a frequência de abas em segundo plano.
