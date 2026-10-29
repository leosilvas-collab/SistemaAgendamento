"use strict";
const $=id=>document.getElementById(id);
const relogio=new Intl.DateTimeFormat("pt-BR",{dateStyle:"short",timeStyle:"medium",timeZone:"America/Sao_Paulo"});
let verificando=false,estadoAnterior=null;
function indicador(id,classe,estado){$("cartao-"+id).className="indicador "+classe;$("estado-"+id).textContent=estado;}
function mostrar(resultado){
  const {ok,banco,detalhe}=resultado;
  indicador("servico",ok ? "ok" : "falha",ok ? "STATUS OK · UP" : "STATUS OFFLINE · DOWN");
  indicador("banco",banco==="ok" ? "ok" : "falha",banco==="ok" ? "BANCO OK" : banco==="offline" ? "BANCO OFFLINE" : "BANCO NÃO VERIFICADO");
  $("detalhe").textContent=detalhe;
  const agora=relogio.format(new Date());
  $("ultima-verificacao").textContent=agora;
  const estado=ok ? "UP" : "DOWN";
  if(estadoAnterior!==estado){
    $("ultima-mudanca").textContent=estadoAnterior===null ? "Primeira leitura: "+estado+" — "+agora : estadoAnterior+" → "+estado+" — "+agora;
    estadoAnterior=estado;
  }
}
async function verificar(){
  if(verificando)return;
  verificando=true;$("verificar").disabled=true;
  const controle=new AbortController();
  const limite=setTimeout(()=>controle.abort(),8000);
  try{
    const resposta=await fetch("/health",{cache:"no-store",signal:controle.signal,headers:{Accept:"application/json"}});
    const dados=await resposta.json();
    const ok=resposta.ok && dados.status==="ok" && dados.banco==="ok";
    mostrar({ok,banco:ok ? "ok" : resposta.status===503 && dados.banco==="offline" ? "offline" : "desconhecido",
      detalhe:ok ? "A aplicação respondeu e a consulta ao SQLite foi concluída com sucesso." : "A verificação detectou uma falha. Consulte os logs do servidor para investigar."});
  }catch(erro){
    mostrar({ok:false,banco:"desconhecido",detalhe:"Não foi possível receber uma resposta válida em até 8 segundos. Pode haver falha no serviço ou na conexão deste dispositivo. O banco não pôde ser verificado."});
  }finally{clearTimeout(limite);verificando=false;$("verificar").disabled=false;}
}
$("verificar").addEventListener("click",verificar);
setInterval(verificar,30000);
verificar();
