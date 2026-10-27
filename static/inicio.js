"use strict";
const form = document.getElementById("consulta");
const dia = document.getElementById("data");
const servico = document.getElementById("servico");
const lista = document.getElementById("lista-horarios");
const situacao = document.getElementById("situacao");
const regiao = document.querySelector(".horarios");
const tentarNovamente = document.getElementById("tentar-novamente");
let repetirDatas = false;
const selecao = document.getElementById("selecao");
const contraste = document.getElementById("contraste");
const escolherData = document.getElementById("escolher-data");
const painelDatas = document.getElementById("painel-datas");
const listaDatas = document.getElementById("lista-datas");
const maisDias = document.getElementById("mais-dias");
const avisoDatas = document.getElementById("limite-datas");
let calendario;
let semanasMostradas = 1;
let consulta = 0;
let versaoDatas = 0;
let controlador;
let reservaAtual = null;
let reservaEmEnvio = false;
const paginaAgenda = document.getElementById("pagina-agenda");
const formularioReserva = document.getElementById("form-reserva");
const camposReserva = document.getElementById("campos-reserva");
const erroReserva = document.getElementById("erro-reserva");
const estadoReserva = document.getElementById("estado-reserva");
const confirmarReserva = document.getElementById("confirmar-reserva");
const voltarAgenda = document.getElementById("voltar-agenda");
const confirmacao = document.getElementById("confirmacao");
function diaFormatado() { return dia.value.split("-").reverse().join("/"); }
function limparSelecao() {
  selecao.hidden = true;
  document.getElementById("resumo").textContent = "";
  reservaAtual = null;
}
function dataEscolhida() {
  return calendario ? calendario.semanas.flatMap(semana => semana.dias).find(item => item.data === dia.value) : null;
}
function atualizarBotaoData() {
  const item = dataEscolhida();
  document.getElementById("data-dia").textContent = item ? item.rotulo : "Nenhum horário livre";
  document.getElementById("data-extenso").textContent = item ? item.descricao : "Consulte as datas deste período";
  document.getElementById("titulo-horarios").textContent = calendario && dia.value === calendario.hoje
    ? "Horários Disponíveis para Hoje" : "Horários Disponíveis";
}
function fecharDatas() {
  painelDatas.hidden = true;
  escolherData.setAttribute("aria-expanded", "false");
  escolherData.focus();
}
function desenharDatas(focarNovos) {
  listaDatas.replaceChildren();
  if (!calendario) return;
  semanasMostradas = Math.min(semanasMostradas, calendario.semanas.length);
  let primeiroNovo;
  calendario.semanas.slice(0, semanasMostradas).forEach((semana, indice) => {
    const grupo = document.createElement("section");
    const titulo = document.createElement("h3");
    titulo.textContent = semana.rotulo;
    grupo.append(titulo);
    semana.dias.forEach(item => {
      const botao = document.createElement("button");
      botao.type = "button";
      botao.className = "horario opcao-data";
      botao.setAttribute("aria-pressed", String(item.data === dia.value));
      botao.disabled = !item.disponivel;
      const nome = document.createElement("strong");
      nome.textContent = item.rotulo;
      const extenso = document.createElement("span");
      extenso.textContent = item.descricao;
      const estado = document.createElement("small");
      estado.textContent = !item.disponivel ? "Sem horários livres"
        : item.data === dia.value ? "Selecionada" : "Selecionar esta data";
      botao.append(nome, extenso, estado);
      botao.addEventListener("click", () => {
        dia.value = item.data;
        atualizarBotaoData();
        fecharDatas();
        consultar();
      });
      if (indice === semanasMostradas - 1 && !primeiroNovo && item.disponivel) primeiroNovo = botao;
      grupo.append(botao);
    });
    listaDatas.append(grupo);
  });
  maisDias.hidden = semanasMostradas >= calendario.semanas.length;
  avisoDatas.textContent = maisDias.hidden ? "Todas as datas deste período estão sendo exibidas."
    : "Mostrando " + semanasMostradas + " de " + calendario.semanas.length + " semanas disponíveis para consulta.";
  if (focarNovos && primeiroNovo) primeiroNovo.focus();
  else if (focarNovos && maisDias.hidden) document.getElementById("fechar-datas").focus();
}
async function carregarDatas(preservar) {
  tentarNovamente.hidden = true;
  const versao = ++versaoDatas;
  const abortar = new AbortController();
  const timeout = setTimeout(() => abortar.abort(), 12000);
  try {
    const resposta = await fetch("/api/datas", {cache:"no-store", signal:abortar.signal, headers:{Accept:"application/json"}});
    const dados = await resposta.json();
    if (!resposta.ok || !Array.isArray(dados.semanas)) throw new Error("datas");
    if (versao !== versaoDatas) return;
    calendario = dados;
    const anterior = preservar ? dataEscolhida() : null;
    const novaData = anterior && anterior.disponivel ? anterior.data : dados.primeira_disponivel || "";
    const mudou = novaData !== dia.value;
    dia.value = novaData;
    atualizarBotaoData();
    escolherData.disabled = false;
    desenharDatas(false);
    if (!dia.value) {
      if (controlador) controlador.abort();
      consulta += 1;
      lista.replaceChildren();
      limparSelecao();
      regiao.setAttribute("aria-busy", "false");
      tentarNovamente.hidden = true;
      situacao.classList.remove("erro");
      situacao.textContent = "Não há horários livres na semana atual e nas cinco semanas seguintes. Tente novamente mais tarde.";
    } else if (!preservar || mudou) {
      await consultar();
    }
  } catch (erro) {
    if (versao !== versaoDatas) return;
    situacao.classList.add("erro");
    situacao.textContent = "Não foi possível consultar as datas. Verifique a conexão e toque em Tentar novamente.";
    repetirDatas = true;
    tentarNovamente.hidden = false;
  } finally { clearTimeout(timeout); }
}
function selecionar(horario, botao) {
  lista.querySelectorAll("button").forEach(item => {
    item.setAttribute("aria-pressed", "false");
    item.textContent = item.dataset.horario + " - Disponível";
  });
  botao.setAttribute("aria-pressed", "true");
  botao.textContent = horario + " - Selecionado";
  const [h, m] = horario.split(":").map(Number);
  const minutos = h * 60 + m + 30;
  const fim = String(Math.floor(minutos / 60)).padStart(2, "0") + ":" + String(minutos % 60).padStart(2, "0");
  document.getElementById("resumo").textContent = servico.value + " — " + diaFormatado() + ", das " + horario + " às " + fim + ".";
  reservaAtual = {data:dia.value, horario:horario, servico:servico.value};
  paginaAgenda.hidden = true;
  confirmacao.hidden = true;
  erroReserva.hidden = true;
  estadoReserva.textContent = "";
  confirmarReserva.disabled = false;
  selecao.hidden = false;
  document.getElementById("titulo-selecao").focus();
}
async function consultar(evento) {
  if (evento) evento.preventDefault();
  if (!dia.value) { await carregarDatas(false); return; }
  if (controlador) controlador.abort();
  controlador = new AbortController();
  const controladorLocal = controlador;
  const atual = ++consulta;
  const timeout = setTimeout(() => controladorLocal.abort(), 12000);
  lista.replaceChildren();
  limparSelecao();
  regiao.setAttribute("aria-busy", "true");
  tentarNovamente.hidden = true;
  situacao.classList.remove("erro");
  situacao.textContent = "Consultando os horários…";
  try {
    const resposta = await fetch("/api/horarios?data=" + encodeURIComponent(dia.value), {
      signal:controladorLocal.signal, cache:"no-store", headers:{Accept:"application/json"}
    });
    const dados = await resposta.json();
    if (!resposta.ok || !Array.isArray(dados.horarios)) throw new Error("consulta");
    if (atual !== consulta) return;
    situacao.textContent = dados.horarios.length
      ? diaFormatado() + " — " + dados.horarios.length + " horários livres. Toque para selecionar."
      : "Não há mais horários livres neste dia. Toque na data para escolher outro dia.";
    dados.horarios.forEach(horario => {
      const botao = document.createElement("button");
      botao.type = "button";
      botao.className = "horario";
      botao.dataset.horario = horario;
      botao.textContent = horario + " - Disponível";
      botao.setAttribute("aria-pressed", "false");
      botao.addEventListener("click", () => selecionar(horario, botao));
      lista.append(botao);
    });
  } catch (erro) {
    if (atual !== consulta) return;
    situacao.classList.add("erro");
    situacao.textContent = "Não foi possível consultar a agenda. Verifique a conexão e toque em Tentar novamente.";
    repetirDatas = false;
    tentarNovamente.hidden = false;
  } finally {
    clearTimeout(timeout);
    if (atual === consulta) { regiao.setAttribute("aria-busy", "false"); }
  }
}
escolherData.addEventListener("click", () => {
  if (!painelDatas.hidden) { fecharDatas(); return; }
  painelDatas.hidden = false;
  escolherData.setAttribute("aria-expanded", "true");
  carregarDatas(true);
});
maisDias.addEventListener("click", () => { semanasMostradas += 1; desenharDatas(true); });
document.getElementById("fechar-datas").addEventListener("click", fecharDatas);
painelDatas.addEventListener("keydown", evento => {
  if (evento.key === "Escape") { evento.preventDefault(); fecharDatas(); }
});
form.addEventListener("submit", consultar);
tentarNovamente.addEventListener("click", () => {
  if (repetirDatas || !dia.value) carregarDatas(true);
  else consultar();
});
servico.addEventListener("change", () => { limparSelecao(); consultar(); });

voltarAgenda.addEventListener("click", () => {
  if (reservaEmEnvio) return;
  paginaAgenda.hidden = false;
  limparSelecao();
  consultar();
  escolherData.focus();
});
formularioReserva.addEventListener("submit", async evento => {
  evento.preventDefault();
  if (reservaEmEnvio || !reservaAtual || !formularioReserva.reportValidity()) return;
  const dados = {...reservaAtual,
    nome:document.getElementById("nome").value,
    telefone:document.getElementById("telefone").value,
    website:document.getElementById("website").value};
  reservaEmEnvio = true;
  camposReserva.disabled = true;
  voltarAgenda.disabled = true;
  erroReserva.hidden = true;
  estadoReserva.textContent = "Salvando seu agendamento…";
  formularioReserva.setAttribute("aria-busy", "true");
  const abortar = new AbortController();
  const timeout = setTimeout(() => abortar.abort(), 15000);
  try {
    const resposta = await fetch("/api/agendamentos", {
      method:"POST", cache:"no-store", signal:abortar.signal,
      headers:{"Content-Type":"application/json", "X-Requested-With":"MarciaNails"},
      body:JSON.stringify(dados)
    });
    const resultado = await resposta.json();
    if (!resposta.ok) {
      erroReserva.textContent = resultado.mensagem || "Não foi possível confirmar o agendamento.";
      erroReserva.hidden = false;
      if (resposta.status === 409) reservaAtual = null;
      return;
    }
    if (resposta.status !== 201 || !resultado.agendamento) throw new Error("resposta");
    const reserva = resultado.agendamento;
    document.getElementById("resumo-confirmado").textContent = reserva.nome + " — "
      + reserva.data.split("-").reverse().join("/") + ", das " + reserva.horario + " às "
      + reserva.fim + " (" + reserva.servico + ").";
    selecao.hidden = true;
    confirmacao.hidden = false;
    formularioReserva.reset();
    reservaAtual = null;
    document.getElementById("titulo-confirmacao").focus();
  } catch (erro) {
    // Uma falha de rede pode ocorrer depois do commit: não repetimos o POST.
    erroReserva.textContent = "Não foi possível verificar a confirmação. Confira com o salão antes de repetir a reserva.";
    erroReserva.hidden = false;
  } finally {
    clearTimeout(timeout);
    reservaEmEnvio = false;
    camposReserva.disabled = false;
    confirmarReserva.disabled = !reservaAtual;
    voltarAgenda.disabled = false;
    estadoReserva.textContent = "";
    formularioReserva.setAttribute("aria-busy", "false");
  }
});
document.getElementById("voltar-inicio").addEventListener("click", async () => {
  confirmacao.hidden = true;
  paginaAgenda.hidden = false;
  limparSelecao();
  await carregarDatas(false);
  escolherData.focus();
});

contraste.addEventListener("click", () => {
  const ativo = document.body.classList.toggle("alto-contraste");
  contraste.setAttribute("aria-pressed", String(ativo));
  try { localStorage.setItem("marcia-alto-contraste", String(ativo)); } catch (erro) { /* Preferência opcional. */ }
});
try {
  if (localStorage.getItem("marcia-alto-contraste") === "true") {
    document.body.classList.add("alto-contraste"); contraste.setAttribute("aria-pressed", "true");
  }
} catch (erro) { /* Não impede a consulta. */ }
if ("serviceWorker" in navigator) {
  window.addEventListener("load", () => navigator.serviceWorker.register("/sw.js").catch(() => {
    // A consulta online continua disponível sem a instalação da PWA.
  }));
}
carregarDatas(false);
