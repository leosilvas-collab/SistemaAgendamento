const test=require("node:test");
const assert=require("node:assert/strict");
const vm=require("node:vm");
const fs=require("node:fs");
const path=require("node:path");
const codigo=fs.readFileSync(path.join(__dirname,"../static/monitoramento.js"),"utf8");
const resposta=(status,dados)=>({status,ok:status===200,json:async()=>dados});
const esperar=()=>new Promise(resolve=>setImmediate(resolve));
function painel(respostas){
  const elementos=new Map();let intervalo=0;
  const contexto={document:{getElementById(id){if(!elementos.has(id))elementos.set(id,{textContent:"",className:"",disabled:false,addEventListener(){}});return elementos.get(id);}},
    Intl,Date,AbortController,setTimeout,clearTimeout,setInterval(fn,ms){intervalo=ms;},
    fetch:async()=>{const r=respostas.shift();if(r instanceof Error)throw r;return r;}};
  vm.createContext(contexto);vm.runInContext(codigo,contexto);
  return {contexto,elementos,intervalo};
}
test("UP, DOWN por falha do banco e recuperação são sinalizados",async()=>{
  const p=painel([resposta(200,{status:"ok",banco:"ok"}),resposta(503,{status:"indisponivel",banco:"offline"}),resposta(200,{status:"ok",banco:"ok"})]);
  await esperar();assert.equal(p.intervalo,30000);
  assert.equal(p.elementos.get("estado-servico").textContent,"STATUS OK · UP");
  assert.equal(p.elementos.get("cartao-banco").className,"indicador ok");
  await p.contexto.verificar();
  assert.equal(p.elementos.get("estado-banco").textContent,"BANCO OFFLINE");
  assert.match(p.elementos.get("ultima-mudanca").textContent,/UP → DOWN/);
  await p.contexto.verificar();assert.match(p.elementos.get("ultima-mudanca").textContent,/DOWN → UP/);
});
test("falha de rede não afirma queda do banco sem evidência",async()=>{
  const p=painel([new Error("sem conexão")]);await esperar();
  assert.equal(p.elementos.get("estado-servico").textContent,"STATUS OFFLINE · DOWN");
  assert.equal(p.elementos.get("estado-banco").textContent,"BANCO NÃO VERIFICADO");
  assert.equal(p.elementos.get("verificar").disabled,false);
});
test("resposta inválida não aparece como UP",async()=>{
  const p=painel([resposta(200,{status:"ok"})]);await esperar();
  assert.equal(p.elementos.get("cartao-servico").className,"indicador falha");
});
