"use strict";
const area = document.body.dataset.area;
const $ = id => document.getElementById(id);
let usuario = null, csrf = "", etapa = "email", timerLogin = null;
let calendario = null, semanas = 1, dataAgenda = "", horario = "", versaoAgenda = 0, versaoBusca = 0;
let edicao = null;
function texto(id,valor) { $(id).textContent = valor; }
function aviso(valor,erro=false) {
  texto("mensagem",valor); $("mensagem").className=erro ? "erro" : "sucesso";
}
function dataBr(valor) { return valor ? valor.slice(0,10).split("-").reverse().join("/") : "—"; }
async function api(caminho,dados) {
  const opcoes={cache:"no-store",headers:{Accept:"application/json"}};
  if (dados !== undefined) {
    opcoes.method="POST";
    Object.assign(opcoes.headers,{"Content-Type":"application/json","X-Requested-With":"MarciaNails","X-CSRF-Token":csrf});
    opcoes.body=JSON.stringify(dados);
  }
  const resposta=await fetch(caminho,opcoes);
  const corpo=await resposta.json();
  if (!resposta.ok) {
    const erro=new Error(corpo.mensagem || "Não foi possível concluir a operação.");
    erro.status=resposta.status; erro.espera=Number(resposta.headers.get("Retry-After") || corpo.espera || 0);
    throw erro;
  }
  return corpo;
}
function limparAcesso() {
  etapa="email"; $("email").readOnly=false;
  $("campo-senha").hidden=true; $("campo-confirmacao").hidden=true; $("dados-cadastro").hidden=true;
  $("trocar-email").hidden=true; $("senha").required=false; $("confirmacao-senha").required=false;
  ["nome","telefone","estabelecimento"].forEach(id=>{if($(id)) $(id).required=false;});
  texto("titulo-acesso","Entre com seu e-mail"); texto("entrar","Continuar");
  $("senha").value=""; $("confirmacao-senha").value=""; $("erro-acesso").hidden=true;
}
function esperar(segundos) {
  if (timerLogin) clearInterval(timerLogin);
  const fim=Date.now()+segundos*1000;
  $("entrar").disabled=true;
  timerLogin=setInterval(()=>{
    const restante=Math.max(0,Math.ceil((fim-Date.now())/1000));
    texto("entrar",restante ? "Aguarde "+restante+" s" : etapa==="cadastro" ? "Salvar cadastro e entrar" : "Entrar");
    if (!restante) { clearInterval(timerLogin); timerLogin=null; $("entrar").disabled=false; }
  },250);
}
async function mostrarPainel(resultado) {
  usuario=resultado.usuario; csrf=resultado.csrf;
  if (usuario.papel!==area) {
    $("acesso").hidden=false; $("painel").hidden=true;
    aviso("Há uma sessão de outra área aberta. Saia dela antes de acessar esta área.",true);
    // Permite encerrar a sessão atual sem mostrar dados do outro papel.
    $("painel").hidden=false; [...$("painel").children].forEach(el=>{el.hidden=!el.classList.contains("barra-painel");});
    texto("identificacao","Sessão de outra área"); return;
  }
  $("acesso").hidden=true; $("painel").hidden=false;
  [...$("painel").children].forEach(el=>{el.hidden=false;});
  texto("identificacao",usuario.nome || usuario.email);
  $("senha").value=""; $("confirmacao-senha").value="";
  if (area==="proprietario") await listarUsuarios();
  else {
    texto("nome-area",usuario.estabelecimento);
    atualizarPlano();
    calendario=await api("/api/datas?salao="+encodeURIComponent(usuario.slug));
    // A API considera o relógio de São Paulo e só oferece inícios ainda futuros.
    // Sem disponibilidade no período, mantém a consulta da agenda, sem oferecer reservas.
    dataAgenda=calendario.primeira_disponivel || calendario.hoje;
    desenharDatas();
    await carregarAgenda();
    if(!calendario.primeira_disponivel) aviso("Não há horários livres no período exibido. Você ainda pode consultar as agendas ou informar uma data futura.");
  }
}
$("form-acesso").addEventListener("submit",async evento=>{
  evento.preventDefault(); $("erro-acesso").hidden=true; $("entrar").disabled=true;
  try {
    const dados={email:$("email").value,area:area};
    if (etapa==="email") {
      const resultado=await api("/api/acesso/identificar",dados);
      etapa=resultado.etapa; $("email").readOnly=true;
      $("campo-senha").hidden=false; $("senha").required=true;
      $("senha").autocomplete=etapa==="cadastro" ? "new-password" : "current-password";
      $("dados-cadastro").hidden=etapa!=="cadastro"; $("campo-confirmacao").hidden=etapa!=="cadastro";
      $("confirmacao-senha").required=etapa==="cadastro";
      ["nome","telefone","estabelecimento"].forEach(id=>{if($(id)) $(id).required=etapa==="cadastro";});
      texto("titulo-acesso",etapa==="cadastro" ? "Complete seu cadastro" : "Digite sua senha");
      texto("entrar",etapa==="cadastro" ? "Salvar cadastro e entrar" : "Entrar");
      $("trocar-email").hidden=false;
      (etapa==="cadastro" && $("nome") ? $("nome") : $("senha")).focus();
    } else {
      dados.senha=$("senha").value;
      if (etapa==="cadastro") {
        dados.confirmacao=$("confirmacao-senha").value;
        ["nome","telefone","estabelecimento"].forEach(id=>{if($(id)) dados[id]=$(id).value;});
      }
      const resultado=await api(etapa==="cadastro" ? "/api/acesso/ativar" : "/api/acesso/entrar",dados);
      await mostrarPainel(resultado); aviso("Acesso realizado.");
    }
  } catch (erro) {
    texto("erro-acesso",erro.message); $("erro-acesso").hidden=false;
    if (erro.espera) esperar(erro.espera);
  } finally { if (!timerLogin) $("entrar").disabled=false; }
});
$("trocar-email").addEventListener("click",()=>{limparAcesso();$("email").focus();});
$("sair").addEventListener("click",async()=>{
  try { await api("/api/acesso/sair",{}); location.reload(); }
  catch(erro) {aviso(erro.message,true);}
});
function botao(rotulo,acao,classe="fechar-datas") {
  const elemento=document.createElement("button"); elemento.type="button"; elemento.className=classe;
  elemento.textContent=rotulo;
  elemento.addEventListener("click",async()=>{
    elemento.disabled=true;
    try { await acao(); } finally { elemento.disabled=false; }
  });
  return elemento;
}
async function listarUsuarios() {
  const resultado=await api("/api/proprietario/usuarios"); $("usuarios").replaceChildren();
  resultado.usuarios.forEach(u=>{
    const card=document.createElement("article"); card.className="cartao";
    const titulo=document.createElement("h3"); titulo.textContent=u.estabelecimento || u.email; card.append(titulo);
    const dados=["Nome: "+(u.nome||"Aguardando cadastro"),"E-mail: "+u.email,"Telefone: "+(u.telefone||"—"),
      "Plano: "+u.plano,"Vencimento do teste: "+(u.plano==="pago" ? "Não se aplica" : dataBr(u.vence_em)),
      "Testes premium concedidos: "+u.premium_concedidos+" de 3",
      u.redefinir ? "Redefinição autorizada" : u.ativado ? "Cadastro ativado" : "Aguardando primeiro acesso"];
    dados.forEach(linha=>{const p=document.createElement("p");p.textContent=linha;card.append(p);});
    const acoes=document.createElement("div");acoes.className="acoes-usuario";
    const pago=botao("Marcar como pago",()=>mudarPlano(u.id,"pago")); pago.disabled=u.plano==="pago";
    const premium=botao("Conceder mais 30 dias de teste",()=>mudarPlano(u.id,"premium"));
    premium.disabled=u.plano==="pago" || !u.ativado || u.premium_concedidos>=3;
    const reset=botao("Autorizar redefinição de senha",()=>autorizarReset(u.email));
    acoes.append(pago,premium,reset);card.append(acoes);$("usuarios").append(card);
  });
}
async function mudarPlano(id,acao) {
  try {await api("/api/proprietario/usuarios/"+id+"/plano",{acao});await listarUsuarios();aviso("Plano atualizado.");}
  catch(erro){aviso(erro.message,true);}
}
async function autorizarReset(email) {
  try {const r=await api("/api/proprietario/redefinir",{email});await listarUsuarios();aviso(r.mensagem);}
  catch(erro){aviso(erro.message,true);}
}
if (area==="proprietario") {
  $("novo-gestor").addEventListener("submit",async evento=>{
    evento.preventDefault();
    try {await api("/api/proprietario/usuarios",{email:$("email-novo").value});$("novo-gestor").reset();await listarUsuarios();aviso("E-mail pré-cadastrado. O gestor pode completar o cadastro na PWA.");}
    catch(erro){aviso(erro.message,true);}
  });
  $("form-redefinir").addEventListener("submit",evento=>{evento.preventDefault();autorizarReset($("email-redefinir").value);});
}
function atualizarPlano() {
  texto("info-plano",usuario.plano==="pago" ? "Plano pago — acesso liberado." : "Plano teste — vencimento em "+dataBr(usuario.vence_em)+(usuario.pode_agendar ? "." : ". Período expirado: somente consulta."));
  $("link-publico").href="/?salao="+encodeURIComponent(usuario.slug);
  $("campos-agendamento").disabled=!usuario.pode_agendar;
}
function nomeData(valor) {
  const item=calendario && calendario.semanas.flatMap(s=>s.dias).find(d=>d.data===valor);
  if (item) return item.rotulo+"\n"+item.descricao;
  const data=new Date(valor+"T12:00:00Z");
  return Number.isNaN(data.getTime()) ? dataBr(valor) : new Intl.DateTimeFormat("pt-BR",{
    weekday:"long",day:"numeric",month:"long",year:"numeric",timeZone:"UTC"
  }).format(data);
} 
function limparBuscaClientes() {
  // Invalida buscas em andamento para que uma resposta atrasada não restaure a lista.
  versaoBusca+=1;
  $("busca-clientes").reset();
  $("busca").value="";
  $("clientes-encontrados").replaceChildren();
  texto("resultado-busca","");
}
function desenharDatas(focar=false) {
  if (!calendario) return;
  $("opcoes-datas").replaceChildren();let primeiroNovo;
  calendario.semanas.slice(0,semanas).forEach((s,indice)=>{
    const h=document.createElement("h3");h.textContent=s.rotulo;$("opcoes-datas").append(h);
    s.dias.forEach(d=>{
      const b=botao(d.rotulo+"\n"+d.descricao+(d.data===dataAgenda ? "\nSelecionada" : "\nVer agenda"),()=>{
        dataAgenda=d.data;$("datas-gestor").hidden=true;$("data-grande").setAttribute("aria-expanded","false");carregarAgenda();$("data-grande").focus();
      },"horario opcao-data");
      b.setAttribute("aria-pressed",String(d.data===dataAgenda));
      if(indice===semanas-1 && !primeiroNovo)primeiroNovo=b;
      $("opcoes-datas").append(b);
    });
  });
  $("mais-datas").hidden=semanas>=calendario.semanas.length;
  texto("fim-datas",$("mais-datas").hidden ? "Todas as datas deste período estão sendo exibidas." : "Use Mostrar mais dias para acrescentar outra semana.");
  if(focar && primeiroNovo)primeiroNovo.focus();
}
function encerrarEdicao() {
  edicao=null;
  texto("titulo-agendamento","Novo agendamento");
  texto("salvar-agendamento","Confirmar Agendamento");
  $("aviso-edicao").hidden=true;$("data-edicao-painel").hidden=true;$("cancelar-edicao").hidden=true;
  $("form-agendamento").reset();limparBuscaClientes();
}
async function iniciarEdicao(reserva,dia) {
  edicao={id:reserva.id,data:dia,horario:reserva.horario};dataAgenda=dia;
  limparBuscaClientes();
  texto("titulo-agendamento","Alterar agendamento");texto("salvar-agendamento","Salvar alteração");
  texto("aviso-edicao","Altere os dados e confirme. A reserva atual será mantida até salvar a alteração.");
  $("aviso-edicao").hidden=false;$("data-edicao-painel").hidden=false;$("cancelar-edicao").hidden=false;
  $("data-edicao").value=dataBr(dia);
  $("cliente-nome").value=reserva.nome;$("cliente-telefone").value=reserva.telefone;$("servico").value=reserva.servico;
  await carregarAgenda();$("cliente-nome").focus();
}
function confirmarExclusao(reserva,card,botaoOrigem) {
  if(card.querySelector(".confirmar-exclusao"))return;
  const caixa=document.createElement("div");caixa.className="confirmar-exclusao";
  const p=document.createElement("p");p.textContent="Excluir o atendimento de "+reserva.nome+" às "+reserva.horario+"? O horário ficará livre.";
  const confirmar=botao("Sim, excluir agendamento",async()=>{
    try {
      const r=await api("/api/gestao/agendamentos/"+reserva.id+"/excluir",{});
      if(edicao && edicao.id===reserva.id)encerrarEdicao();
      await carregarAgenda();aviso(r.mensagem);
      $("mensagem").tabIndex=-1;$("mensagem").focus();
    }catch(erro){aviso(erro.status ? erro.message : "A conexão falhou. Consulte a agenda antes de tentar novamente.",true);}
  },"primario");
  const cancelar=botao("Manter agendamento",()=>{caixa.remove();botaoOrigem.focus();});
  caixa.append(p,confirmar,cancelar);card.append(caixa);confirmar.focus();
}
async function carregarAgenda() {
  const versao=++versaoAgenda;horario="";
  texto("data-grande",nomeData(dataAgenda)+"\nEscolher outro dia");
  texto("horario-escolhido","");texto("data-agenda","Consultando agenda…");
  $("atendimentos").replaceChildren();$("horarios-gestor").replaceChildren();
  try {
    const [agenda,livres]=await Promise.all([
      api("/api/gestao/agenda?data="+encodeURIComponent(dataAgenda)),
      api("/api/gestao/horarios?data="+encodeURIComponent(dataAgenda)+(edicao ? "&agendamento="+edicao.id : ""))]);
    if(versao!==versaoAgenda)return;
    usuario=agenda.usuario;atualizarPlano();
    texto("abrir-futuro","Agendar a partir de "+dataBr(agenda.futuro_a_partir_de));
    $("abrir-futuro").dataset.primeiraData=dataBr(agenda.futuro_a_partir_de);
    texto("data-agenda",dataBr(dataAgenda)+" — "+agenda.agendamentos.length+" atendimento(s).");
    agenda.agendamentos.forEach(a=>{
      const card=document.createElement("article");card.className="atendimento";
      const h=document.createElement("strong");h.textContent=a.horario;card.append(h);
      [a.nome,a.telefone,a.servico,"Status: "+a.status].forEach(v=>{const p=document.createElement("p");p.textContent=v;card.append(p);});
      const acoes=document.createElement("div");acoes.className="acoes-agendamento";
      const dia=dataAgenda;
      const alterar=botao("Alterar agendamento",()=>iniciarEdicao(a,dia),"primario");
      const excluir=botao("Excluir agendamento",()=>confirmarExclusao(a,card,excluir),"fechar-datas");
      alterar.setAttribute("aria-label","Alterar agendamento de "+a.nome+" às "+a.horario);
      excluir.setAttribute("aria-label","Excluir agendamento de "+a.nome+" às "+a.horario);
      alterar.disabled=!usuario.pode_agendar;excluir.disabled=!usuario.pode_agendar;
      acoes.append(alterar,excluir);card.append(acoes);
      $("atendimentos").append(card);
    });
    if(!agenda.agendamentos.length){const p=document.createElement("p");p.textContent="Nenhum atendimento nesta data.";$("atendimentos").append(p);}
    livres.horarios.forEach(h=>{
      const b=botao(h+" - Disponível",()=>{
        horario=h;$("horarios-gestor").querySelectorAll("button").forEach(item=>item.setAttribute("aria-pressed","false"));
        b.setAttribute("aria-pressed","true");texto("horario-escolhido","Selecionado: "+dataBr(dataAgenda)+" às "+horario);
      },"horario");b.disabled=!usuario.pode_agendar;b.setAttribute("aria-pressed","false");$("horarios-gestor").append(b);
    });
    if(edicao && edicao.data===dataAgenda && livres.horarios.includes(edicao.horario)) {
      horario=edicao.horario;
      $("horarios-gestor").querySelectorAll("button").forEach(b=>b.setAttribute("aria-pressed",String(b.textContent.startsWith(horario+" -"))));
      texto("horario-escolhido","Selecionado: "+dataBr(dataAgenda)+" às "+horario);
    }
    if(edicao)$("data-edicao").value=dataBr(dataAgenda);
    if(!livres.horarios.length) {
      const domingo=new Date(dataAgenda+"T12:00:00Z").getUTCDay()===0;
      texto("horario-escolhido",domingo ? "Domingo sem atendimento. Escolha uma data de segunda-feira a sábado." : "Não há horários livres futuros nesta data.");
    }
    return true;
  } catch(erro){if(versao===versaoAgenda)aviso(erro.message,true);return false;}
}
if(area==="gestor") {
  $("cancelar-edicao").addEventListener("click",async()=>{encerrarEdicao();await carregarAgenda();$("cliente-nome").focus();});
  $("consultar-edicao").addEventListener("click",async()=>{
    const valor=$("data-edicao").value;
    if(!/^[0-9]{2}\/[0-9]{2}\/[0-9]{4}$/.test(valor)){aviso("Informe uma data no formato DD/MM/AAAA.",true);return;}
    dataAgenda=valor.split("/").reverse().join("-");await carregarAgenda();
  });
  $("data-grande").addEventListener("click",()=>{const aberto=$("datas-gestor").hidden;$("datas-gestor").hidden=!aberto;$("data-grande").setAttribute("aria-expanded",String(aberto));desenharDatas();});
  $("mais-datas").addEventListener("click",()=>{semanas+=1;desenharDatas(true);});
  $("fechar-datas").addEventListener("click",()=>{$("datas-gestor").hidden=true;$("data-grande").setAttribute("aria-expanded","false");$("data-grande").focus();});
  $("abrir-futuro").addEventListener("click",()=>{const aberto=$("painel-futuro").hidden;$("painel-futuro").hidden=!aberto;$("abrir-futuro").setAttribute("aria-expanded",String(aberto));if(aberto){
    if(!$("data-manual").value)$("data-manual").value=$("abrir-futuro").dataset.primeiraData || "";
    $("data-manual").focus();
  }});
  $("form-futuro").addEventListener("submit",async evento=>{
    evento.preventDefault();const partes=$("data-manual").value.split("/");
    if(partes.length!==3)return;dataAgenda=partes.reverse().join("-");
    if(await carregarAgenda()) {
      $("painel-futuro").hidden=true;$("abrir-futuro").setAttribute("aria-expanded","false");
      $("data-agenda").tabIndex=-1;$("data-agenda").focus();
    }
  });
  $("busca-clientes").addEventListener("submit",async evento=>{
    evento.preventDefault();const versao=++versaoBusca;$("clientes-encontrados").replaceChildren();
    try {
      const r=await api("/api/gestao/clientes?q="+encodeURIComponent($("busca").value));
      if(versao!==versaoBusca)return;
      texto("resultado-busca",r.clientes.length ? "Selecione uma cliente ou preencha os campos manualmente." : "Nenhuma cliente encontrada. Você pode preencher nome e telefone manualmente.");
      r.clientes.forEach(c=>$("clientes-encontrados").append(botao(c.nome+" — "+c.telefone,()=>{
        $("cliente-nome").value=c.nome;$("cliente-telefone").value=c.telefone;$("cliente-nome").focus();
      },"primario cliente-busca")));
    }catch(erro){if(versao===versaoBusca)aviso(erro.message,true);}
  });
  $("form-agendamento").addEventListener("submit",async evento=>{
    evento.preventDefault();
    if(edicao && $("data-edicao").value!==dataBr(dataAgenda)){
      aviso("Consulte os horários da nova data antes de salvar a alteração.",true);return;
    }
    if(!horario){aviso("Selecione um horário livre.",true);return;}
    $("campos-agendamento").disabled=true;
    try {
      const alterando=edicao!==null;
      const destino=alterando ? "/api/gestao/agendamentos/"+edicao.id+"/alterar" : "/api/gestao/agendamentos";
      const r=await api(destino,{data:dataAgenda,horario:horario,servico:$("servico").value,
        nome:$("cliente-nome").value,telefone:$("cliente-telefone").value});
      encerrarEdicao();await carregarAgenda();
      aviso((alterando ? "Agendamento alterado: " : "Agendamento confirmado: ")+r.agendamento.nome+", "+dataBr(r.agendamento.data)+" às "+r.agendamento.horario+".");
      $("mensagem").tabIndex=-1;$("mensagem").focus();
    }catch(erro){
      aviso(erro.status ? erro.message : "A conexão falhou. Confira a agenda antes de tentar novamente: o atendimento pode ter sido salvo.",true);
      if(erro.status===409)await carregarAgenda();
    }
    finally{$("campos-agendamento").disabled=!usuario.pode_agendar;}
  });
}
$("contraste").addEventListener("click",()=>{
  const ativo=document.body.classList.toggle("alto-contraste");$("contraste").setAttribute("aria-pressed",String(ativo));
  try{localStorage.setItem("marcia-alto-contraste",String(ativo));}catch(erro){/* Preferência opcional. */}
});
try{if(localStorage.getItem("marcia-alto-contraste")==="true"){document.body.classList.add("alto-contraste");$("contraste").setAttribute("aria-pressed","true");}}catch(erro){/* Sem persistência. */}
limparAcesso();
api("/api/acesso/sessao").then(mostrarPainel).catch(erro=>{if(erro.status!==401)aviso(erro.message,true);});
