// Painel do AgroSense: busca o estado no servidor local a cada 15 s e desenha a bancada.
"use strict";

const ESPECIES = {
  alface: { nome: "Alface", cientifico: "Lactuca sativa" },
  cebolinha: { nome: "Cebolinha", cientifico: "Allium fistulosum" },
  rucula: { nome: "Rúcula", cientifico: "Eruca sativa" },
  vazio: { nome: "Vaso vazio", cientifico: "" },
};

const MOTIVOS = {
  ocioso: "Umidade dentro da faixa",
  ligou_solo_seco: "Solo abaixo do limiar: começou a regar",
  regando: "Regando até o limiar de parada",
  parou_solo_umido: "Parou: a umidade chegou ao limiar",
  parou_tempo_maximo: "Parou: tempo máximo de rega",
  parou_reservatorio_vazio: "Parou: reservatório vazio",
  parou_falha_sensor: "Parou: leitura do sensor inválida",
  bloqueado_especie_desconhecida: "Sem rega: espécie não confirmada",
  bloqueado_sem_irrigacao: "Sem rega: vaso vazio",
  bloqueado_falha_sensor: "Sem rega: sensor sem leitura",
  bloqueado_reservatorio_vazio: "Sem rega: reservatório vazio",
  bloqueado_intervalo: "Aguardando a água infiltrar",
};

const ESTADOS_NO = {
  online: "Nó online",
  dormindo: "Nó dormindo entre ciclos",
  offline: "Nó fora do ar: desconectou sem avisar",
};

let horas = 24;
let fotoAtual = null;
const cartoes = new Map();

const $ = (id) => document.getElementById(id);
const escapar = (s) => String(s ?? "").replace(/[&<>"]/g, (c) => ({ "&": "&amp;", "<": "&lt;", ">": "&gt;", '"': "&quot;" })[c]);
const especie = (rotulo) => ESPECIES[rotulo] || { nome: rotulo || "Sem espécie", cientifico: "" };
const hora = (ts) => new Date(ts * 1000).toLocaleTimeString("pt-BR", { hour: "2-digit", minute: "2-digit" });
const diaHora = (ts) => new Date(ts * 1000).toLocaleString("pt-BR",
  { day: "2-digit", month: "2-digit", hour: "2-digit", minute: "2-digit" });
const decimal = (v, casas) => v.toFixed(casas).replace(".", ",");

function haQuanto(segundos) {
  if (segundos == null) return "";
  if (segundos < 90) return "há menos de 2 min";
  const min = Math.round(segundos / 60);
  if (min < 60) return `há ${min} min`;
  const h = Math.round(min / 60);
  return h < 48 ? `há ${h} h` : `há ${Math.round(h / 24)} dias`;
}

async function buscar(url) {
  const r = await fetch(url, { cache: "no-store" });
  if (!r.ok) throw new Error(`${url}: ${r.status}`);
  return r.json();
}

function aviso(texto) {
  const el = $("aviso");
  el.hidden = !texto;
  el.textContent = texto || "";
}

function desenharNo(no) {
  const el = $("no");
  el.dataset.estado = no.status || "";
  if (no.ultima_mensagem == null) {
    el.textContent = "Aguardando o nó";
    return;
  }
  el.textContent = `${ESTADOS_NO[no.status] || "Nó"}, último contato ${haQuanto(no.visto_ha_s)}`;
}

function desenharAmbiente(amb) {
  if (!amb) return;
  $("amb-temp").textContent = amb.temperatura_c != null ? `${decimal(amb.temperatura_c, 1)} °C` : "—";
  $("amb-umid").textContent = amb.umidade_ar_pct != null ? `${Math.round(amb.umidade_ar_pct)}%` : "—";
  $("amb-luz").textContent = amb.lux != null && amb.lux >= 0 ? `${Math.round(amb.lux)} lx` : "—";
  const res = $("amb-res");
  res.textContent = amb.reservatorio_ok ? "Com água" : "Vazio, regas bloqueadas";
  res.classList.toggle("alerta", !amb.reservatorio_ok);
  $("amb-hora").textContent = `Leitura das ${hora(amb.ts)}.` +
    (amb.sensores_ok ? "" : " O sensor de temperatura e umidade não respondeu.");
}

function desenharFoto(foto) {
  const img = $("foto");
  const marcas = $("foto-marcas");
  if (!foto) {
    img.hidden = true;
    $("foto-vazia").hidden = false;
    marcas.innerHTML = "";
    $("foto-legenda").textContent = "Sem foto ainda";
    return;
  }
  if (foto.ts !== fotoAtual) {
    img.src = `/api/foto?t=${foto.ts}`;
    fotoAtual = foto.ts;
  }
  img.hidden = false;
  $("foto-vazia").hidden = true;
  marcas.setAttribute("viewBox", `0 0 ${foto.largura || 320} ${foto.altura || 240}`);
  marcas.setAttribute("preserveAspectRatio", "xMidYMid meet");
  marcas.innerHTML = (foto.vasos || []).map((v) => {
    const rotulo = v.visto ? `${especie(v.visto).nome} ${Math.round(v.confianca * 100)}%` : "Não reconhecido";
    const largura = rotulo.length * 5 + 8;
    return `<rect x="${v.x}" y="${v.y}" width="${v.lado}" height="${v.lado}"/>` +
      `<rect class="etiqueta" x="${v.x}" y="${v.y}" width="${largura}" height="12"/>` +
      `<text x="${v.x + 4}" y="${v.y + 9}" font-size="8">${escapar(rotulo)}</text>`;
  }).join("");
  $("foto-legenda").textContent = `Foto das ${hora(foto.ts)}, com o que a câmera reconheceu em cada vaso`;
}

function criarCartao(n) {
  const art = document.createElement("article");
  art.className = "vaso";
  art.innerHTML = `
    <header class="herbario">
      <h3></h3><p class="cientifico"></p><p class="origem"></p>
    </header>
    <div class="leitura">
      <div class="coluna" role="img"><div class="agua"></div><div class="faixa"></div></div>
      <div class="numeros">
        <div>
          <p class="umidade"></p>
          <ul class="limites"><li class="liga"></li><li class="desliga"></li></ul>
        </div>
        <div><p class="bomba"></p><p class="motivo"></p><p class="ultima"></p></div>
      </div>
    </div>
    <div class="grafico"><svg role="img"></svg></div>`;
  const q = (sel) => art.querySelector(sel);
  const cartao = {
    art, nome: q("h3"), cientifico: q(".cientifico"), origem: q(".origem"), coluna: q(".coluna"),
    agua: q(".agua"), faixa: q(".faixa"), umidade: q(".umidade"), liga: q(".liga"), desliga: q(".desliga"),
    bomba: q(".bomba"), motivo: q(".motivo"), ultima: q(".ultima"), grafico: q(".grafico svg"),
  };
  cartoes.set(n, cartao);
  return cartao;
}

function origemDaEspecie(v) {
  if (!v.especie) return `Vaso ${v.vaso + 1}, a câmera ainda não confirmou a espécie`;
  if (v.fixa) return `Vaso ${v.vaso + 1}, <span class="fixa">espécie definida à mão</span>`;
  return `Vaso ${v.vaso + 1}, reconhecida pela câmera (${Math.round((v.confianca || 0) * 100)}%)`;
}

function desenharVasos(vasos, historico, janelaS) {
  const lista = $("vasos");
  const vazio = lista.querySelector(".vazio-geral");
  if (vazio && vasos.length) vazio.remove();
  for (const v of vasos) {
    const c = cartoes.get(v.vaso) || criarCartao(v.vaso);
    if (!c.art.isConnected) lista.append(c.art);
    const e = especie(v.especie);
    const temLimites = v.liga_abaixo != null && v.desliga_em != null;
    c.art.classList.toggle("sem-especie", !v.especie || v.especie === "vazio");
    c.nome.textContent = e.nome;
    c.cientifico.textContent = e.cientifico;
    c.cientifico.hidden = !e.cientifico;
    c.origem.innerHTML = origemDaEspecie(v);

    const solo = v.solo_pct;
    c.agua.style.height = `${solo ?? 0}%`;
    c.faixa.hidden = !temLimites;
    if (temLimites) {
      c.faixa.style.bottom = `${v.liga_abaixo}%`;
      c.faixa.style.height = `${v.desliga_em - v.liga_abaixo}%`;
    }
    c.coluna.setAttribute("aria-label", solo == null ? "Sem leitura de umidade" :
      `Umidade do solo ${solo}%` + (temLimites ? `, liga abaixo de ${v.liga_abaixo}% e desliga em ${v.desliga_em}%` : ""));
    c.umidade.innerHTML = solo == null ? "—<small>sem leitura</small>" : `${solo}%<small>de umidade</small>`;
    c.liga.textContent = temLimites ? `Liga abaixo de ${v.liga_abaixo}%` : "Sem limiares: espécie sem perfil";
    c.desliga.textContent = temLimites ? `Desliga em ${v.desliga_em}%` : "";

    c.bomba.className = `bomba${v.bomba ? " ligada" : ""}`;
    c.bomba.textContent = v.bomba ? "Regando agora" : "Bomba desligada";
    c.motivo.textContent = MOTIVOS[v.motivo] || v.motivo || "";
    c.ultima.textContent = v.ultima_rega ? `Última rega em ${diaHora(v.ultima_rega)}` : "Nenhuma rega registrada";
    desenharGrafico(c.grafico, (historico.vasos || {})[String(v.vaso)], janelaS);
  }
}

function desenharGrafico(svg, pontos, janelaS) {
  const W = 300, H = 120, esq = 26, dir = 6, topo = 6, base = 18;
  svg.setAttribute("viewBox", `0 0 ${W} ${H}`);
  svg.setAttribute("aria-label", janelaS > 86400 ? "Umidade nos últimos 7 dias" : "Umidade nas últimas 24 horas");
  if (!pontos || !pontos.length) {
    svg.innerHTML = `<text x="${W / 2}" y="${H / 2}" text-anchor="middle">Sem histórico neste período</text>`;
    return;
  }
  const agora = Date.now() / 1000;
  const inicio = agora - janelaS;
  const x = (t) => (esq + ((t - inicio) / janelaS) * (W - esq - dir)).toFixed(1);
  const y = (v) => (topo + (1 - v / 100) * (H - topo - base)).toFixed(1);
  const [, , , liga, desliga] = pontos[pontos.length - 1];
  let s = "";
  for (const v of [0, 50, 100]) {
    s += `<line class="eixo" x1="${esq}" x2="${W - dir}" y1="${y(v)}" y2="${y(v)}"/>` +
      `<text x="${esq - 4}" y="${Number(y(v)) + 3}" text-anchor="end">${v}</text>`;
  }
  if (liga != null && desliga != null) {
    s += `<rect class="banda" x="${esq}" width="${W - esq - dir}" y="${y(desliga)}" height="${(y(liga) - y(desliga)).toFixed(1)}"/>`;
  }
  const validos = pontos.filter((p) => p[1] != null);
  s += `<polyline class="linha" points="${validos.map((p) => `${x(p[0])},${y(p[1])}`).join(" ")}"/>`;
  for (const p of pontos.filter((p) => p[2])) {
    s += `<rect class="rega" x="${(Number(x(p[0])) - 1).toFixed(1)}" y="${H - base + 3}" width="2.5" height="6"/>`;
  }
  s += `<text x="${esq}" y="${H - 1}">${janelaS > 86400 ? "7 dias atrás" : "24 h atrás"}</text>` +
    `<text x="${W - dir}" y="${H - 1}" text-anchor="end">agora</text>`;
  svg.innerHTML = s;
}

function desenharRegas(eventos) {
  const ol = $("regas");
  if (!eventos.length) {
    ol.innerHTML = "<li><span></span><span>Nenhuma rega registrada ainda.</span></li>";
    return;
  }
  ol.innerHTML = eventos.map((e) => {
    const quem = `${escapar(especie(e.especie).nome)}, vaso ${e.vaso + 1}`;
    const oque = e.bomba ? "começou a regar" : (MOTIVOS[e.motivo] || "parou").replace(/^Parou: /, "parou porque ");
    return `<li><time datetime="${new Date(e.ts * 1000).toISOString()}">${diaHora(e.ts)}</time>` +
      `<span class="${e.bomba ? "ligou" : ""}">${quem}: ${escapar(oque)}</span></li>`;
  }).join("");
}

async function atualizar() {
  try {
    const [estado, historico, eventos] = await Promise.all([
      buscar("/api/estado"), buscar(`/api/historico?horas=${horas}`), buscar("/api/eventos?limite=12")]);
    aviso(null);
    desenharNo(estado.no);
    desenharAmbiente(estado.ambiente);
    desenharFoto(estado.foto);
    desenharVasos(estado.vasos, historico, horas * 3600);
    desenharRegas(eventos);
  } catch (erro) {
    aviso("O painel não respondeu. Confira se o app.py continua rodando neste computador.");
  }
}

document.querySelectorAll(".janela button").forEach((botao) => {
  botao.addEventListener("click", () => {
    horas = Number(botao.dataset.horas);
    document.querySelectorAll(".janela button").forEach((b) => b.setAttribute("aria-pressed", String(b === botao)));
    atualizar();
  });
});

atualizar();
setInterval(atualizar, 15000);
