const $ = (id) => document.getElementById(id);

const estado = {
  aba: "minimax",
  treino: null,
  partidas: { minimax: null, rede: null },
  benchmark: null,
  timer: null,
  animacao: 0,
  geracaoAnimada: -2,
  formularioPronto: false,
};

function percentual(valor) {
  if (valor === null || valor === undefined) return "—";
  return `${(valor * 100).toFixed(1)}%`;
}

function numero(valor) {
  if (valor === null || valor === undefined) return "—";
  return Number(valor).toFixed(2);
}

async function api(caminho, corpo) {
  const opcoes = corpo
    ? {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify(corpo),
      }
    : undefined;
  const resposta = await fetch(caminho, opcoes);
  const dados = await resposta.json();
  if (!resposta.ok) {
    throw new Error(dados.erro || "Falha na requisição.");
  }
  return dados;
}

function mostrarErro(erro) {
  const caixa = $("erro");
  caixa.hidden = false;
  caixa.textContent = erro.message || String(erro);
}

function limparErro() {
  $("erro").hidden = true;
}

function desenharTabuleiro(elemento, partida, aoClicar) {
  elemento.replaceChildren();
  const tabuleiro = partida && partida.tabuleiro ? partida.tabuleiro : Array(9).fill(0);
  const linha = new Set((partida && partida.linha) || []);
  for (let i = 0; i < 9; i += 1) {
    const botao = document.createElement("button");
    botao.type = "button";
    botao.className = "casa";
    const indice = document.createElement("span");
    indice.className = "indice";
    indice.textContent = String(i + 1);
    botao.append(indice);
    const valor = tabuleiro[i];
    if (valor === 1) {
      botao.append("X");
      botao.classList.add("x");
    } else if (valor === 2) {
      botao.append("O");
      botao.classList.add("o");
    }
    if (partida && partida.ultima === i) botao.classList.add("ultima");
    if (linha.has(i)) botao.classList.add("venceu");
    const pode = Boolean(aoClicar && partida && partida.podeJogar && valor === 0);
    botao.disabled = !pode;
    if (pode) botao.addEventListener("click", () => aoClicar(i));
    elemento.append(botao);
  }
}

function preencherPlacar(elemento, partida, nomeOponente) {
  const placar = (partida && partida.placar) || {};
  const linhas = [
    ["Você", placar.voce || 0],
    [nomeOponente, placar.oponente || 0],
    ["Empates", placar.empates || 0],
  ];
  if (nomeOponente === "Rede") {
    linhas.push(["Acurácia da rede", percentual(placar.acuracia)]);
    linhas.push(["Aproveitamento", percentual(placar.aproveitamento)]);
    linhas.push(["Jogadas ótimas", `${placar.jogadasOtimas || 0}/${placar.jogadasRede || 0}`]);
    linhas.push(["Escolhas ilegais", placar.decisoesIlegais || 0]);
  }
  elemento.replaceChildren();
  for (const [rotulo, valor] of linhas) {
    const dt = document.createElement("dt");
    dt.textContent = rotulo;
    const dd = document.createElement("dd");
    dd.textContent = String(valor);
    elemento.append(dt, dd);
  }
}

function renderPartidas() {
  const minimax = estado.partidas.minimax;
  const rede = estado.partidas.rede;
  desenharTabuleiro($("tabuleiro-minimax"), minimax, (casa) => jogar("minimax", casa));
  desenharTabuleiro($("tabuleiro-rede"), rede, (casa) => jogar("rede", casa));
  $("anuncio-minimax").textContent = minimax ? minimax.anuncio : "Escolha quem começa e inicie a partida.";
  $("anuncio-rede").textContent = rede ? rede.anuncio : "Inicie uma partida contra a rede campeã.";
  preencherPlacar($("placar-minimax"), minimax, "Minimax");
  preencherPlacar($("placar-rede"), rede, "Rede");
  const aviso = $("aviso-rede");
  aviso.hidden = !(rede && rede.redeAleatoria);
}

async function novaPartida(tipo) {
  limparErro();
  try {
    const corpo = {
      tipo,
      euComeco: $(tipo === "minimax" ? "comeco-minimax" : "comeco-rede").checked,
      dificuldade: $("dificuldade-minimax").value,
    };
    estado.partidas[tipo] = await api("/api/partida/nova", corpo);
    renderPartidas();
  } catch (erro) {
    mostrarErro(erro);
  }
}

async function jogar(tipo, casa) {
  if (estado.enviando) return;
  estado.enviando = true;
  limparErro();
  if (estado.partidas[tipo]) estado.partidas[tipo].podeJogar = false;
  renderPartidas();
  try {
    estado.partidas[tipo] = await api("/api/partida/jogada", { tipo, casa });
  } catch (erro) {
    mostrarErro(erro);
  } finally {
    estado.enviando = false;
    renderPartidas();
  }
}

async function zerar(tipo) {
  limparErro();
  try {
    estado.partidas[tipo] = await api("/api/partida/zerar", { tipo });
    renderPartidas();
  } catch (erro) {
    mostrarErro(erro);
  }
}

function preencherCartas(descricao) {
  const ordem = [
    ["Topologia", descricao.topologia],
    ["Cromossomo", descricao.cromossomo],
    ["Aptidão", descricao.aptidao],
    ["Operadores", descricao.operadores],
    ["Currículo", descricao.curriculo],
    ["Parada e acurácia", `${descricao.parada} ${descricao.acuracia}`],
  ];
  const caixa = $("cartas");
  caixa.replaceChildren();
  for (const [titulo, texto] of ordem) {
    const artigo = document.createElement("article");
    const h3 = document.createElement("h3");
    h3.textContent = titulo;
    const p = document.createElement("p");
    p.textContent = texto;
    artigo.append(h3, p);
    caixa.append(artigo);
  }
}

function preencherFormulario(config) {
  if (estado.formularioPronto) return;
  const form = $("form-treino");
  for (const campo of form.elements) {
    if (campo.name && config[campo.name] !== undefined) {
      campo.value = config[campo.name];
    }
  }
  estado.formularioPronto = true;
}

function lerFormulario() {
  const dados = {};
  for (const campo of $("form-treino").elements) {
    if (!campo.name) continue;
    dados[campo.name] = campo.type === "number" ? Number(campo.value) : campo.value;
  }
  return dados;
}

function marcarFase(fase, curriculo) {
  for (const item of $("fases").querySelectorAll("span")) {
    const qual = item.dataset.fase;
    const ativa = curriculo === "medio"
      ? qual === "medio"
      : curriculo === "dificil"
        ? qual === "dificil"
        : qual === fase;
    item.classList.toggle("ativa", Boolean(ativa));
  }
}

function desenharGrafico(historico) {
  const canvas = $("grafico");
  const largura = canvas.clientWidth || 640;
  const altura = 240;
  const dpr = window.devicePixelRatio || 1;
  canvas.width = Math.floor(largura * dpr);
  canvas.height = Math.floor(altura * dpr);
  const ctx = canvas.getContext("2d");
  ctx.setTransform(dpr, 0, 0, dpr, 0, 0);
  ctx.clearRect(0, 0, largura, altura);
  ctx.fillStyle = "#fbf8f2";
  ctx.fillRect(0, 0, largura, altura);
  if (!historico || !historico.length) {
    ctx.fillStyle = "#6d6458";
    ctx.font = "14px Segoe UI";
    ctx.fillText("O gráfico aparece na primeira geração.", 16, 32);
    return;
  }
  const margem = { esq: 42, dir: 12, topo: 12, baixo: 26 };
  const areaL = largura - margem.esq - margem.dir;
  const areaA = altura - margem.topo - margem.baixo;
  const valores = historico.flatMap((p) => [p.melhor, p.media, p.pior, p.validacao, p.campea]);
  let min = Math.min(...valores);
  let max = Math.max(...valores);
  if (min === max) {
    min -= 1;
    max += 1;
  }
  const folga = (max - min) * 0.08;
  min -= folga;
  max += folga;
  const xDe = (indice) => margem.esq + (historico.length === 1 ? areaL / 2 : (indice / (historico.length - 1)) * areaL);
  const yDe = (valor) => margem.topo + ((max - valor) / (max - min)) * areaA;
  const faixas = { medio: "#f4ecdf", misto: "#e6eef6", dificil: "#f6e7dc" };
  for (let i = 0; i < historico.length; i += 1) {
    const ini = i === 0 ? margem.esq : (xDe(i - 1) + xDe(i)) / 2;
    const fim = i === historico.length - 1 ? largura - margem.dir : (xDe(i) + xDe(i + 1)) / 2;
    ctx.fillStyle = faixas[historico[i].fase] || "#fbf8f2";
    ctx.fillRect(ini, margem.topo, fim - ini, areaA);
  }
  ctx.strokeStyle = "#e4dccf";
  ctx.lineWidth = 1;
  ctx.font = "11px Segoe UI";
  ctx.fillStyle = "#6d6458";
  for (let i = 0; i < 4; i += 1) {
    const valor = min + ((max - min) * i) / 3;
    const y = yDe(valor);
    ctx.beginPath();
    ctx.moveTo(margem.esq, y);
    ctx.lineTo(largura - margem.dir, y);
    ctx.stroke();
    ctx.fillText(valor.toFixed(1), 4, y + 4);
  }
  const series = [
    ["melhor", "#143e66"],
    ["media", "#8d7344"],
    ["validacao", "#9a6230"],
    ["campea", "#1f7a4d"],
  ];
  for (const [chave, cor] of series) {
    ctx.beginPath();
    ctx.strokeStyle = cor;
    ctx.lineWidth = chave === "campea" ? 2.4 : 1.6;
    historico.forEach((ponto, indice) => {
      const x = xDe(indice);
      const y = yDe(ponto[chave]);
      if (indice === 0) ctx.moveTo(x, y);
      else ctx.lineTo(x, y);
    });
    ctx.stroke();
  }
}

function renderPopulacao(populacao) {
  const caixa = $("populacao");
  caixa.replaceChildren();
  if (!populacao || !populacao.length) {
    caixa.textContent = "A população aparece depois de criar os cromossomos.";
    return;
  }
  const notas = populacao.map((ind) => ind.aptidao);
  const min = Math.min(...notas);
  const max = Math.max(...notas);
  populacao.forEach((ind, indice) => {
    const linha = document.createElement("div");
    linha.className = "ind";
    const id = document.createElement("span");
    id.textContent = String(indice + 1);
    const barra = document.createElement("div");
    barra.className = "barra";
    const preenchido = document.createElement("span");
    const largura = max === min ? 100 : ((ind.aptidao - min) / (max - min)) * 100;
    preenchido.style.width = `${largura}%`;
    barra.append(preenchido);
    const texto = document.createElement("span");
    texto.textContent = `${ind.aptidao.toFixed(2)} · ${ind.vitorias}V ${ind.empates}E ${ind.derrotas}D · ${ind.ilegais} ilegais`;
    linha.append(id, barra, texto);
    caixa.append(linha);
  });
}

function renderDiario(linhas) {
  const lista = $("diario");
  lista.replaceChildren();
  const recentes = (linhas || []).slice(-40);
  if (!recentes.length) {
    const item = document.createElement("li");
    item.textContent = "Crie a população para ver a avaliação inicial. Cada geração seguinte mostra elitismo, torneio, cruzamento e mutação.";
    lista.append(item);
    return;
  }
  for (const linha of recentes) {
    const item = document.createElement("li");
    item.textContent = linha;
    lista.append(item);
  }
  lista.scrollTop = lista.scrollHeight;
}

function renderNumeros(treino) {
  const ultimo = treino.historico && treino.historico.length
    ? treino.historico[treino.historico.length - 1]
    : null;
  const linhas = [
    ["Geração", treino.geracao < 0 ? "—" : `${treino.geracao + 1} / ${treino.maxGeracoes}`],
    ["Fase", ultimo ? { medio: "Médio", misto: "Misto", dificil: "Difícil" }[ultimo.fase] || ultimo.fase : "—"],
    ["Melhor", ultimo ? numero(ultimo.melhor) : "—"],
    ["Média", ultimo ? numero(ultimo.media) : "—"],
    ["Pior", ultimo ? numero(ultimo.pior) : "—"],
    ["Validação difícil", ultimo ? numero(ultimo.validacao) : "—"],
    ["Campeã", numero(treino.notaCampea)],
    ["Gerações sem melhora", treino.semMelhora ?? 0],
  ];
  const caixa = $("numeros");
  caixa.replaceChildren();
  for (const [rotulo, valor] of linhas) {
    const dt = document.createElement("dt");
    dt.textContent = rotulo;
    const dd = document.createElement("dd");
    dd.textContent = String(valor);
    caixa.append(dt, dd);
  }
}

function tabuleiroDeLances(lances, ate) {
  const tabuleiro = Array(9).fill(0);
  const limite = Math.min(ate, lances.length);
  for (let i = 0; i < limite; i += 1) {
    tabuleiro[lances[i].casa] = lances[i].jogador;
  }
  const ultima = limite > 0 ? lances[limite - 1].casa : null;
  return { tabuleiro, ultima, podeJogar: false, linha: null };
}

function esperar(ms) {
  return new Promise((resolver) => setTimeout(resolver, ms));
}

async function animar(partida) {
  const meu = ++estado.animacao;
  const lances = (partida && partida.lances) || [];
  const demo = $("tabuleiro-demo");
  const anuncio = $("anuncio-demo");
  if (!lances.length) {
    desenharTabuleiro(demo, null, null);
    anuncio.textContent = "Sem partida de exemplo nesta geração.";
    return;
  }
  const quem = partida.redeComeca ? "A rede começa com X." : "O Minimax começa com X.";
  for (let passo = 0; passo <= lances.length; passo += 1) {
    if (meu !== estado.animacao) return;
    desenharTabuleiro(demo, tabuleiroDeLances(lances, passo), null);
    if (passo < lances.length) {
      const lance = lances[passo];
      const nome = lance.lado === "rede" ? "Rede" : "Minimax";
      anuncio.textContent = `${quem} ${nome} na casa ${lance.casa + 1}.`;
      await esperar(320);
    }
  }
  if (meu !== estado.animacao) return;
  const nomes = { vitoria: "A rede venceu.", empate: "Empate.", derrota: "A rede perdeu." };
  anuncio.textContent = `${quem} ${nomes[partida.desfecho] || ""} Modo ${partida.modo}.`;
}

function renderTreino(treino) {
  estado.treino = treino;
  if (treino.descricao) preencherCartas(treino.descricao);
  if (treino.config) preencherFormulario(treino.config);
  $("cromossomo").textContent = treino.pesos
    ? `Cromossomo com ${treino.pesos} pesos. Topologia ${treino.topologia.join("-")}.`
    : "";
  marcarFase(treino.fase, treino.config && treino.config.curriculo);
  desenharGrafico(treino.historico || []);
  renderPopulacao(treino.populacao || []);
  renderDiario(treino.diario || []);
  renderNumeros(treino);
  const motivo = $("motivo");
  if (treino.executando) motivo.textContent = "Treinando. A população e o gráfico atualizam ao fim de cada geração.";
  else if (treino.motivoParada) motivo.textContent = treino.motivoParada;
  else if (treino.geracao < 0) motivo.textContent = "O primeiro passo avalia a população inicial. Os operadores entram a partir da geração seguinte.";
  else motivo.textContent = "Pronto para a próxima geração. Quem começa alterna em cada partida da avaliação.";
  const travado = Boolean(treino.executando);
  for (const id of ["criar-pop", "uma-geracao", "treinar"]) $(id).disabled = travado || (id !== "criar-pop" && treino.encerrado);
  $("criar-pop").disabled = travado;
  $("parar").disabled = !travado;
  for (const campo of $("form-treino").elements) campo.disabled = travado;
  if (treino.geracao !== estado.geracaoAnimada && treino.partidaExemplo) {
    estado.geracaoAnimada = treino.geracao;
    animar(treino.partidaExemplo);
  }
  if (treino.executando) acompanhar();
}

async function atualizarTreino() {
  try {
    const foto = await api("/api/treino");
    renderTreino(foto);
    if (!foto.executando && estado.timer) {
      clearInterval(estado.timer);
      estado.timer = null;
    }
  } catch (erro) {
    mostrarErro(erro);
  }
}

function acompanhar() {
  if (estado.timer) return;
  estado.timer = setInterval(atualizarTreino, 700);
}

async function acaoTreino(acao) {
  limparErro();
  try {
    const foto = await api("/api/treino/acao", { acao });
    renderTreino(foto);
    acompanhar();
  } catch (erro) {
    mostrarErro(erro);
  }
}

function renderBenchmark(resultado) {
  const caixa = $("benchmark-resultado");
  caixa.replaceChildren();
  if (!resultado) return;
  for (const chave of ["dificil", "medio"]) {
    const bloco = resultado[chave];
    const titulo = document.createElement("h3");
    titulo.textContent = chave === "dificil" ? "Contra o difícil" : "Contra o médio";
    const texto = document.createElement("p");
    texto.textContent = bloco.redeAleatoria
      ? "Rede aleatória, sem treino."
      : `${bloco.jogos} partidas. Acurácia ${percentual(bloco.acuracia)}. Aproveitamento ${percentual(bloco.aproveitamento)}. ${bloco.vitorias} vitórias, ${bloco.empates} empates, ${bloco.derrotas} derrotas.`;
    caixa.append(titulo, texto);
  }
}

function trocarAba(nome) {
  estado.aba = nome;
  for (const botao of document.querySelectorAll(".aba")) {
    botao.classList.toggle("ativa", botao.dataset.aba === nome);
  }
  $("painel-minimax").hidden = nome !== "minimax";
  $("painel-treino").hidden = nome !== "treino";
  $("painel-rede").hidden = nome !== "rede";
  if (nome === "treino" && estado.treino) desenharGrafico(estado.treino.historico || []);
}

function ligar() {
  for (const botao of document.querySelectorAll(".aba")) {
    botao.addEventListener("click", () => trocarAba(botao.dataset.aba));
  }
  $("nova-minimax").addEventListener("click", () => novaPartida("minimax"));
  $("nova-rede").addEventListener("click", () => novaPartida("rede"));
  $("zerar-minimax").addEventListener("click", () => zerar("minimax"));
  $("zerar-rede").addEventListener("click", () => zerar("rede"));
  $("criar-pop").addEventListener("click", () => acaoTreino("reiniciar"));
  $("uma-geracao").addEventListener("click", () => acaoTreino("uma"));
  $("treinar").addEventListener("click", () => acaoTreino("completo"));
  $("parar").addEventListener("click", async () => {
    try {
      renderTreino(await api("/api/treino/parar", {}));
    } catch (erro) {
      mostrarErro(erro);
    }
  });
  $("rever").addEventListener("click", () => {
    if (estado.treino && estado.treino.partidaExemplo) animar(estado.treino.partidaExemplo);
  });
  $("form-treino").addEventListener("submit", async (evento) => {
    evento.preventDefault();
    limparErro();
    try {
      estado.formularioPronto = true;
      const foto = await api("/api/treino/config", lerFormulario());
      estado.formularioPronto = false;
      renderTreino(foto);
    } catch (erro) {
      mostrarErro(erro);
    }
  });
  $("benchmark").addEventListener("click", async () => {
    limparErro();
    $("benchmark").disabled = true;
    try {
      estado.benchmark = await api("/api/benchmark", { jogos: 30 });
      renderBenchmark(estado.benchmark);
    } catch (erro) {
      mostrarErro(erro);
    } finally {
      $("benchmark").disabled = false;
    }
  });
  window.addEventListener("resize", () => {
    if (estado.aba === "treino" && estado.treino) desenharGrafico(estado.treino.historico || []);
  });
}

async function iniciar() {
  ligar();
  desenharTabuleiro($("tabuleiro-minimax"), null, null);
  desenharTabuleiro($("tabuleiro-rede"), null, null);
  desenharTabuleiro($("tabuleiro-demo"), null, null);
  try {
    const [treino, partidas] = await Promise.all([api("/api/treino"), api("/api/partidas")]);
    estado.partidas = partidas;
    renderPartidas();
    renderTreino(treino);
  } catch (erro) {
    mostrarErro(erro);
  }
}

iniciar();
