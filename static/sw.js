"use strict";
const CACHE = "marcia-nails-estatico-v10";
const ARQUIVOS = ["/static/inicio.css", "/static/inicio.js", "/static/gestao.css", "/static/gestao.js", "/static/icone-192.png", "/static/icone-512.png", "/static/offline.html"];
self.addEventListener("install", evento => {
  evento.waitUntil(caches.open(CACHE).then(cache => cache.addAll(ARQUIVOS)));
});
self.addEventListener("activate", evento => {
  evento.waitUntil(caches.keys().then(chaves => Promise.all(
    chaves.filter(chave => chave.startsWith("marcia-nails-estatico-") && chave !== CACHE).map(chave => caches.delete(chave))
  )).then(() => self.clients.claim()));
});
self.addEventListener("fetch", evento => {
  const pedido = evento.request;
  const url = new URL(pedido.url);
  // Disponibilidade e dados de clientes nunca entram no cache offline.
  if (pedido.method !== "GET" || url.origin !== self.location.origin || url.pathname.startsWith("/api/")) return;
  if (pedido.mode === "navigate") {
    evento.respondWith(fetch(pedido).catch(() => caches.match("/static/offline.html")));
  } else if (ARQUIVOS.includes(url.pathname)) {
    evento.respondWith(fetch(pedido).catch(() => caches.match(pedido)));
  }
});
