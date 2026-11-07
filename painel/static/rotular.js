// Rotulagem das fotos originais: o Leonardo marca cada área de plantio com a espécie.
// Cada mudança é salva na hora em data/originais/<lote>/rotulos.json.
"use strict";

const CLASSES = [
  { id: "alface", nome: "Alface", cor: "#3d7a3a" },
  { id: "cebolinha", nome: "Cebolinha", cor: "#2c74b0" },
  { id: "rucula", nome: "Rúcula", cor: "#a8650f" },
  { id: "vazio", nome: "Vazio (só substrato)", cor: "#86664a" },
];
const LADO_MINIMO = 32;

let lote = null;
let fotos = [];
let indice = 0;
let classeAtiva = "alface";
let arrasto = null;

const $ = (id) => document.getElementById(id);
const classe = (id) => CLASSES.find((c) => c.id === id) || { id, nome: id, cor: "#55655a" };
const escapar = (s) => String(s ?? "").replace(/[&<>"]/g, (c) => ({ "&": "&amp;", "<": "&lt;", ">": "&gt;", '"': "&quot;" })[c]);
const urlLote = () => `/api/rotulagem/lotes/${encodeURIComponent(lote)}`;
const urlFoto = (f) => `${urlLote()}/fotos/${encodeURIComponent(f.arquivo)}`;

async function api(url, opcoes = {}) {
  const r = await fetch(url, { cache: "no-store", ...opcoes });
  const corpo = await r.json().catch(() => ({}));
  if (!r.ok) throw new Error(corpo.detail || `Erro ${r.status}`);
  return corpo;
}

function aviso(texto) {
  $("aviso").hidden = !texto;
  $("aviso").textContent = texto || "";
}

function status(texto, erro = false) {
  $("status").textContent = texto;
  $("status").classList.toggle("erro", erro);
}

function desenharClasses() {
  $("classes").innerHTML = CLASSES.map((c, i) =>
    `<button type="button" data-classe="${c.id}" aria-pressed="${c.id === classeAtiva}">` +
    `<span class="amostra" style="background:${c.cor}"></span>${i + 1}. ${escapar(c.nome)}</button>`).join("");
  $("classes").querySelectorAll("button").forEach((b) => b.addEventListener("click", () => escolher(b.dataset.classe)));
}

function escolher(id) {
  classeAtiva = id;
  desenharClasses();
}

async function carregarLotes() {
  const lotes = await api("/api/rotulagem/lotes");
  if (!lotes.length) {
    aviso("Nenhum lote em data/originais/. Cada lote é uma pasta com as fotos e um manifesto.json.");
    return;
  }
  const sel = $("lote");
  sel.innerHTML = lotes.map((l) => `<option value="${escapar(l.lote)}">${escapar(l.lote)}</option>`).join("");
  sel.onchange = () => abrirLote(sel.value);
  await abrirLote(lotes[0].lote);
}

async function abrirLote(nome) {
  lote = nome;
  fotos = (await api(urlLote())).fotos;
  const pendente = fotos.findIndex((f) => !f.revisada);
  indice = pendente >= 0 ? pendente : 0;
  mostrarFoto();
}

function mostrarFoto() {
  const f = fotos[indice];
  if (!f) return;
  const img = $("foto");
  img.alt = `Foto ${f.arquivo}`;
  img.onload = desenharMarcas;
  img.src = urlFoto(f);
  $("foto-nome").textContent = f.arquivo;
  $("foto-sessao").textContent = `| sessão ${f.sessao}`;
  $("posicao").textContent = `Foto ${indice + 1} de ${fotos.length}`;
  status(f.revisada ? (f.regioes.length ? "Revisada" : "Revisada: sem planta útil") : "Ainda não revisada");
  desenharRegioes();
  desenharLista();
}

function desenharMarcas() {
  const img = $("foto");
  const svg = $("marcas");
  const f = fotos[indice];
  if (!img.naturalWidth || !f) return;
  svg.setAttribute("viewBox", `0 0 ${img.naturalWidth} ${img.naturalHeight}`);
  svg.setAttribute("preserveAspectRatio", "none");
  const fonte = Math.round(img.naturalWidth / 30);
  const caixa = (r, previa) => {
    const c = classe(r.classe);
    const traco = Math.max(3, Math.round(img.naturalWidth / 300));
    let s = `<rect x="${r.x}" y="${r.y}" width="${r.lado}" height="${r.lado}" fill="none" stroke="${c.cor}" ` +
      `stroke-width="${traco}"${previa ? ' stroke-dasharray="12 8"' : ""}/>`;
    if (!previa) {
      s += `<rect x="${r.x}" y="${r.y}" width="${c.nome.length * fonte * 0.6 + fonte}" height="${fonte * 1.5}" fill="${c.cor}"/>` +
        `<text x="${r.x + fonte / 2}" y="${r.y + fonte * 1.1}" font-size="${fonte}" fill="#fff" font-weight="600">${escapar(c.nome)}</text>`;
    }
    return s;
  };
  svg.innerHTML = f.regioes.map((r) => caixa(r, false)).join("") + (arrasto?.regiao ? caixa(arrasto.regiao, true) : "");
}

function desenharRegioes() {
  const f = fotos[indice];
  const ol = $("regioes");
  if (!f.regioes.length) {
    ol.innerHTML = '<li class="vazia">Nenhuma área marcada</li>';
    return;
  }
  ol.innerHTML = f.regioes.map((r, i) =>
    `<li><span class="amostra" style="background:${classe(r.classe).cor}"></span>${escapar(classe(r.classe).nome)}` +
    ` <span class="nota">${r.lado} px</span> <button type="button" data-remover="${i}">Remover</button></li>`).join("");
  ol.querySelectorAll("[data-remover]").forEach((b) => b.addEventListener("click", () => {
    const regioes = f.regioes.filter((_, i) => i !== Number(b.dataset.remover));
    salvar(regioes, regioes.length > 0);
  }));
}

function desenharLista() {
  const revisadas = fotos.filter((f) => f.revisada).length;
  $("progresso").textContent = `${revisadas} de ${fotos.length} fotos revisadas`;
  $("lista").innerHTML = fotos.map((f, i) =>
    `<li><button type="button" data-ir="${i}" class="${i === indice ? "atual" : ""}" aria-current="${i === indice}">` +
    `<span class="marca ${f.revisada ? "ok" : ""}" aria-hidden="true"></span>${escapar(f.arquivo)}` +
    `<span class="nota">${f.regioes.length ? ` ${f.regioes.length} área${f.regioes.length > 1 ? "s" : ""}` : ""}</span></button></li>`).join("");
  $("lista").querySelectorAll("[data-ir]").forEach((b) => b.addEventListener("click", () => irPara(Number(b.dataset.ir))));
  const atual = $("lista").querySelector(".atual");
  if (atual) atual.scrollIntoView({ block: "nearest" });
}

function irPara(i) {
  if (i < 0 || i >= fotos.length) return;
  indice = i;
  mostrarFoto();
}

async function salvar(regioes, revisada) {
  const f = fotos[indice];
  try {
    const r = await api(urlFoto(f), {
      method: "PUT", headers: { "Content-Type": "application/json" }, body: JSON.stringify({ regioes, revisada }),
    });
    f.regioes = r.regioes;
    f.revisada = r.revisada;
    status(r.regioes.length ? `Salvo: ${r.regioes.length} área(s)` : "Salvo: sem planta útil");
  } catch (erro) {
    status(erro.message, true);
  }
  desenharMarcas();
  desenharRegioes();
  desenharLista();
}

// --- desenho do quadrado sobre a foto -------------------------------------
function pontoNaFoto(evento) {
  const img = $("foto");
  const caixa = img.getBoundingClientRect();
  return {
    x: ((evento.clientX - caixa.left) / caixa.width) * img.naturalWidth,
    y: ((evento.clientY - caixa.top) / caixa.height) * img.naturalHeight,
  };
}

function quadrado(a, b) {
  const img = $("foto");
  let lado = Math.max(Math.abs(b.x - a.x), Math.abs(b.y - a.y));
  let x = b.x < a.x ? a.x - lado : a.x;
  let y = b.y < a.y ? a.y - lado : a.y;
  x = Math.max(0, x);
  y = Math.max(0, y);
  lado = Math.min(lado, img.naturalWidth - x, img.naturalHeight - y);
  return { x: Math.round(x), y: Math.round(y), lado: Math.floor(lado), classe: classeAtiva };
}

const svg = $("marcas");
svg.addEventListener("pointerdown", (e) => {
  if (!fotos[indice]) return;
  svg.setPointerCapture(e.pointerId);
  arrasto = { inicio: pontoNaFoto(e), regiao: null };
});
svg.addEventListener("pointermove", (e) => {
  if (!arrasto) return;
  arrasto.regiao = quadrado(arrasto.inicio, pontoNaFoto(e));
  desenharMarcas();
});
svg.addEventListener("pointerup", () => {
  const regiao = arrasto?.regiao;
  arrasto = null;
  if (regiao && regiao.lado >= LADO_MINIMO) {
    salvar([...fotos[indice].regioes, regiao], true);
  } else {
    desenharMarcas();
  }
});

// --- teclado e botões ------------------------------------------------------
document.addEventListener("keydown", (e) => {
  if (e.target.closest("select, input, textarea")) return;
  const n = Number(e.key);
  if (n >= 1 && n <= CLASSES.length) escolher(CLASSES[n - 1].id);
  else if (e.key === "ArrowRight") irPara(indice + 1);
  else if (e.key === "ArrowLeft") irPara(indice - 1);
  else if ((e.key === "Delete" || e.key === "Backspace") && fotos[indice]?.regioes.length) {
    const regioes = fotos[indice].regioes.slice(0, -1);
    salvar(regioes, regioes.length > 0);
  }
});
$("anterior").addEventListener("click", () => irPara(indice - 1));
$("proxima").addEventListener("click", () => irPara(indice + 1));
$("sem-planta").addEventListener("click", async () => {
  await salvar([], true);
  irPara(indice + 1);
});
$("exportar").addEventListener("click", async () => {
  $("exportado").textContent = "Exportando...";
  try {
    const r = await api("/api/rotulagem/exportar", { method: "POST" });
    const partes = Object.entries(r.por_classe).map(([c, n]) => `${classe(c).nome.toLowerCase()} ${n}`).join(", ");
    $("exportado").textContent = r.recortes ? `${r.recortes} recortes gerados: ${partes}.` : "Nenhuma área marcada ainda.";
  } catch (erro) {
    $("exportado").textContent = erro.message;
  }
});

desenharClasses();
carregarLotes().catch((erro) => aviso(`O painel não respondeu: ${erro.message}`));
