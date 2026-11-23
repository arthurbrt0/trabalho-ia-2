"""Evolui a rede jogando contra o Minimax.

Currículo (escolha deste trabalho):
1. Primeiros 40% das gerações: modo médio. Metade das jogadas do oponente é
   aleatória, então a rede consegue vitória e empate e aprende a ocupar casa livre.
2. Dos 40% aos 70%: misto, metade das partidas no médio e metade no difícil.
3. O restante: só difícil, Minimax em toda jogada. O teto realista é o empate.

Quem começa alterna em toda avaliação. A rede exportada para o usuário não é
simplesmente a de maior aptidão da fase corrente: vitória contra jogada
aleatória vale mais do que empate contra o Minimax perfeito. A campeã é a de
melhor nota numa validação fixa, sempre no modo difícil.
"""

import json
import random
import threading
from pathlib import Path

from ag.algoritmo_genetico import Individuo, nova_geracao
from jogo.simulacao import jogar_partida
from rede.mlp import MLP, genes_aleatorios, numero_de_pesos

VITORIA = 10.0
EMPATE = 6.0
DERROTA = -8.0
PENALIDADE_ILEGAL = 3.0
BONUS_LEGAL = 0.2

ARQUIVO_TREINO = Path(__file__).resolve().parent.parent / "dados" / "treino.json"

CONFIG_PADRAO = {
    "populacao": 30,
    "geracoes": 30,
    "ocultos": 12,
    "elitismo": 4,
    "torneio": 4,
    "taxaCruzamento": 0.85,
    "taxaMutacao": 0.10,
    "sigma": 0.15,
    "alphaBlx": 0.5,
    "cruzamento": "blx",
    "jogosMedio": 6,
    "jogosDificil": 2,
    "paciencia": 12,
    "curriculo": "curriculo",
    "semente": 42,
    "limiarSucesso": 6.0,
}


def fase_da_geracao(geracao, total, curriculo):
    if curriculo == "medio":
        return "medio"
    if curriculo == "dificil":
        return "dificil"
    progresso = (geracao + 1) / max(total, 1)
    if progresso <= 0.4:
        return "medio"
    if progresso <= 0.7:
        return "misto"
    return "dificil"


def partidas_da_fase(fase, config):
    """Lista (modo, rede_comeca), com os dois lados começando."""
    medio = max(2, int(config["jogosMedio"]))
    dificil = max(2, int(config["jogosDificil"]))
    if fase == "medio":
        return [("medio", i % 2 == 0) for i in range(medio)]
    if fase == "dificil":
        return [("dificil", i % 2 == 0) for i in range(dificil)]
    n_medio = max(2, medio // 2)
    n_dificil = max(2, dificil // 2)
    plano = [("medio", i % 2 == 0) for i in range(n_medio)]
    plano += [("dificil", i % 2 == 0) for i in range(n_dificil)]
    return plano


def pontuar(desfecho, ilegais, legais):
    if desfecho == "vitoria":
        nota = VITORIA
    elif desfecho == "empate":
        nota = EMPATE
    else:
        nota = DERROTA
    nota -= PENALIDADE_ILEGAL * ilegais
    nota += BONUS_LEGAL * legais
    return nota


def avaliar_individuo(individuo, rede, plano, sementes, medir_otimas=False):
    rede.definir_pesos(individuo.genes)
    total = 0.0
    vitorias = empates = derrotas = ilegais = legais = 0
    otimas = jogadas = 0
    for (modo, comeca), semente in zip(plano, sementes):
        rng = random.Random(semente)
        partida = jogar_partida(rede, modo, comeca, rng, medir_otimas=medir_otimas)
        total += pontuar(partida["desfecho"], partida["ilegais"], partida["legais"])
        vitorias += partida["desfecho"] == "vitoria"
        empates += partida["desfecho"] == "empate"
        derrotas += partida["desfecho"] == "derrota"
        ilegais += partida["ilegais"]
        legais += partida["legais"]
        otimas += partida["otimas"]
        jogadas += partida["jogadasRede"]
    individuo.aptidao = total / len(plano)
    individuo.vitorias = vitorias
    individuo.empates = empates
    individuo.derrotas = derrotas
    individuo.ilegais = ilegais
    individuo.legais = legais
    individuo.partidas = len(plano)
    return {
        "aptidao": individuo.aptidao,
        "vitorias": vitorias,
        "empates": empates,
        "derrotas": derrotas,
        "ilegais": ilegais,
        "legais": legais,
        "otimas": otimas,
        "jogadasRede": jogadas,
        "partidas": len(plano),
    }


def _resumo_individuo(ind):
    return {
        "aptidao": round(ind.aptidao, 4),
        "vitorias": ind.vitorias,
        "empates": ind.empates,
        "derrotas": ind.derrotas,
        "ilegais": ind.ilegais,
        "partidas": ind.partidas,
    }


class Treinador:
    def __init__(self, persistir=True):
        self.persistir = persistir
        self.lock = threading.RLock()
        self.config = dict(CONFIG_PADRAO)
        self.rng = random.Random(self.config["semente"])
        self.populacao = None
        self.geracao = -1
        self.historico = []
        self.diario = []
        self.ultimo_log = []
        self.partida_exemplo = None
        self.campeao = None
        self.nota_campeao = None
        self.stats_campeao = None
        self.topologia = (9, self.config["ocultos"], 9)
        self.executando = False
        self.parar = False
        self.alvo = -1
        self.motivo_parada = None
        self.encerrado = False
        self.sem_melhora = 0
        self.medindo = False
        self.marco = None
        self.sucesso_seguido = 0
        self._thread = None
        self._rede = MLP(self.topologia)
        self._plano_validacao = []
        self._sementes_validacao = []
        self._montar_validacao()
        if self.persistir:
            self._carregar()

    def _montar_validacao(self):
        base = random.Random(self.config["semente"] + 99991)
        n = max(2, int(self.config["jogosDificil"]))
        if n % 2:
            n += 1
        pares = [("dificil", i % 2 == 0) for i in range(n)]
        self._plano_validacao = pares
        self._sementes_validacao = [base.randrange(1, 10**9) for _ in pares]

    def descrever(self):
        cruzamento = self.config["cruzamento"]
        if cruzamento == "aritmetico":
            texto_cruzamento = (
                "Aritmético, para números reais: cada gene do filho é "
                "β·pai + (1−β)·mãe, com β sorteado em [0, 1]. O segundo filho usa 1−β."
            )
        else:
            alpha = self.config["alphaBlx"]
            texto_cruzamento = (
                f"BLX-α com α = {alpha}. Para cada peso, o filho é sorteado no intervalo "
                "entre os pais, expandido por α para os dois lados."
            )
        return {
            "topologia": (
                f"{self.topologia[0]}-{self.topologia[1]}-{self.topologia[2]}: "
                "9 entradas (1 peça da rede, −1 adversário, 0 vazio), "
                f"{self.topologia[1]} neurônios ocultos e 9 saídas (uma por casa). "
                "Ativação tanh nas duas camadas. Só há propagação; o AG mexe nos pesos."
            ),
            "cromossomo": (
                f"{numero_de_pesos(self.topologia)} números reais: todos os pesos e bias, "
                "da camada oculta até a saída."
            ),
            "aptidao": (
                f"Média das partidas: +{VITORIA:g} vitória, +{EMPATE:g} empate, "
                f"{DERROTA:g} derrota, −{PENALIDADE_ILEGAL:g} por casa ocupada escolhida "
                f"e +{BONUS_LEGAL:g} por jogada legal. No modo médio cada rede joga várias "
                "partidas, sempre as mesmas ao longo da fase, porque metade das jogadas "
                "do oponente é aleatória."
            ),
            "operadores": (
                f"Elitismo ({self.config['elitismo']}) e torneio (k = {self.config['torneio']}). "
                f"{texto_cruzamento} Taxa de cruzamento {self.config['taxaCruzamento']}. "
                f"Mutação gaussiana por gene, taxa {self.config['taxaMutacao']} e σ = {self.config['sigma']}."
            ),
            "curriculo": (
                "Ordem médio → misto → difícil (40% / 30% / 30% das gerações). "
                "Quem começa alterna a cada partida. A campeã é escolhida por uma "
                "validação fixa só no modo difícil, para não premiar quem só ganha do aleatório."
            ),
            "parada": (
                f"Para nas {self.config['geracoes']} gerações, ou por convergência: "
                f"{self.config['paciencia']} gerações sem melhora relevante na validação difícil "
                f"(só conta depois que o currículo entra no difícil), ou nota ≥ "
                f"{self.config['limiarSucesso']} por 3 gerações seguidas."
            ),
            "acuracia": (
                "Acurácia = jogadas da rede que estão entre as ótimas do Minimax "
                "divididas pelo total de jogadas dela. O aproveitamento é "
                "(vitórias + empates) / partidas."
            ),
        }

    def aplicar_config(self, dados):
        with self.lock:
            if self.executando:
                raise RuntimeError("Pare o treino antes de mudar os parâmetros.")
            nova = dict(self.config)
            inteiros = {
                "populacao": (4, 120),
                "geracoes": (1, 400),
                "ocultos": (4, 48),
                "elitismo": (1, 30),
                "torneio": (2, 12),
                "jogosMedio": (2, 20),
                "jogosDificil": (2, 20),
                "paciencia": (3, 80),
                "semente": (0, 10**9),
            }
            for chave, (baixo, alto) in inteiros.items():
                if chave in dados and dados[chave] not in (None, ""):
                    nova[chave] = max(baixo, min(alto, int(dados[chave])))
            reais = {
                "taxaCruzamento": (0.0, 1.0),
                "taxaMutacao": (0.0, 1.0),
                "sigma": (0.01, 1.5),
                "alphaBlx": (0.0, 1.0),
                "limiarSucesso": (0.0, 12.0),
            }
            for chave, (baixo, alto) in reais.items():
                if chave in dados and dados[chave] not in (None, ""):
                    nova[chave] = max(baixo, min(alto, float(dados[chave])))
            if dados.get("cruzamento") in ("blx", "aritmetico"):
                nova["cruzamento"] = dados["cruzamento"]
            if dados.get("curriculo") in ("curriculo", "medio", "dificil"):
                nova["curriculo"] = dados["curriculo"]
            if nova["elitismo"] >= nova["populacao"]:
                nova["elitismo"] = max(1, nova["populacao"] // 4)
            if nova["torneio"] > nova["populacao"]:
                nova["torneio"] = nova["populacao"]
            topologia_mudou = nova["ocultos"] != self.config["ocultos"]
            self.config = nova
            self.topologia = (9, self.config["ocultos"], 9)
            self._rede = MLP(self.topologia)
            self._montar_validacao()
            if topologia_mudou:
                self._zerar_populacao()
            elif (
                not str(self.motivo_parada or "").startswith("Convergência")
                and self.geracao + 1 < self.config["geracoes"]
            ):
                self.encerrado = False
                if self.motivo_parada and str(self.motivo_parada).startswith("Limite"):
                    self.motivo_parada = None
            return self.foto()

    def _zerar_populacao(self):
        self.populacao = None
        self.geracao = -1
        self.historico = []
        self.diario = []
        self.ultimo_log = []
        self.partida_exemplo = None
        self.campeao = None
        self.nota_campeao = None
        self.stats_campeao = None
        self.motivo_parada = None
        self.encerrado = False
        self.sem_melhora = 0
        self.medindo = False
        self.marco = None
        self.sucesso_seguido = 0
        if self.persistir:
            self._salvar()

    def pedir(self, acao):
        with self.lock:
            if self.executando:
                return self.foto()
            self.parar = False
            if acao == "reiniciar":
                self._zerar_populacao()
                self.rng = random.Random(self.config["semente"])
                self._montar_validacao()
                self.alvo = 0
            elif str(self.motivo_parada or "").startswith("Convergência"):
                return self.foto()
            elif self.geracao + 1 >= self.config["geracoes"]:
                return self.foto()
            elif acao == "uma":
                self.encerrado = False
                self.alvo = 0 if self.geracao < 0 else self.geracao + 1
            else:
                self.encerrado = False
                if self.motivo_parada and str(self.motivo_parada).startswith("Limite"):
                    self.motivo_parada = None
                self.alvo = self.config["geracoes"] - 1
            self.executando = True
            self._thread = threading.Thread(target=self._loop, name="treino-ag", daemon=True)
            self._thread.start()
            return self.foto()

    def interromper(self):
        with self.lock:
            self.parar = True
            return self.foto()

    def _loop(self):
        try:
            while not self.parar and not self.encerrado and self.geracao < self.alvo:
                if self.populacao is None:
                    individuos = [
                        Individuo(genes_aleatorios(self.topologia, self.rng))
                        for _ in range(self.config["populacao"])
                    ]
                    self._avaliar(individuos, 0, operadores=None)
                else:
                    with self.lock:
                        atual = self.populacao
                        campeao = None if self.campeao is None else self.campeao[:]
                        config = dict(self.config)
                        rng = self.rng
                    filhos, info = nova_geracao(atual, config, rng, campeao)
                    self._avaliar(filhos, self.geracao + 1, operadores=info)
        except Exception as erro:
            with self.lock:
                self.motivo_parada = f"Erro no treino: {erro}"
                self.encerrado = True
                self.diario.append(self.motivo_parada)
        finally:
            with self.lock:
                self.executando = False

    def _avaliar(self, individuos, geracao, operadores):
        config = self.config
        fase = fase_da_geracao(geracao, config["geracoes"], config["curriculo"])
        plano = partidas_da_fase(fase, config)
        sementes = self._sementes_da_fase(fase, len(plano))
        for individuo in individuos:
            avaliar_individuo(individuo, self._rede, plano, sementes)

        ordenada = sorted(individuos, key=lambda ind: ind.aptidao, reverse=True)
        melhor = ordenada[0]
        notas = [ind.aptidao for ind in ordenada]
        media = sum(notas) / len(notas)
        pior = notas[-1]

        aptidao_fase = melhor.aptidao
        stats_fase = _resumo_individuo(melhor)
        nota_validacao = self._validar(melhor)
        melhor.aptidao = aptidao_fase
        melhor.vitorias = stats_fase["vitorias"]
        melhor.empates = stats_fase["empates"]
        melhor.derrotas = stats_fase["derrotas"]
        melhor.ilegais = stats_fase["ilegais"]
        melhor.partidas = stats_fase["partidas"]

        partida = self._partida_demonstracao(melhor.genes, fase, geracao)

        with self.lock:
            self.populacao = ordenada
            self.geracao = geracao
            if self.nota_campeao is None or nota_validacao > self.nota_campeao + 1e-9:
                self.campeao = melhor.genes[:]
                self.nota_campeao = nota_validacao
                self.stats_campeao = {
                    "aptidao": round(nota_validacao, 4),
                    "vitorias": melhor.vitorias,
                    "empates": melhor.empates,
                    "derrotas": melhor.derrotas,
                    "ilegais": melhor.ilegais,
                    "partidas": melhor.partidas,
                }
            # A validação sobrescreveu as estatísticas do melhor. Guarda as da fase
            # de novo na população e deixa a validação só na nota da campeã.
            melhor.aptidao = aptidao_fase
            melhor.vitorias = stats_fase["vitorias"]
            melhor.empates = stats_fase["empates"]
            melhor.derrotas = stats_fase["derrotas"]
            melhor.ilegais = stats_fase["ilegais"]
            melhor.partidas = stats_fase["partidas"]
            self.stats_campeao = dict(self.stats_campeao or {})
            self.partida_exemplo = partida
            parou, motivo = self._atualizar_convergencia(fase, nota_validacao)
            if geracao + 1 >= config["geracoes"]:
                parou = True
                motivo = f"Limite de {config['geracoes']} gerações atingido."
            if parou:
                self.encerrado = True
                self.motivo_parada = motivo
            self.historico.append(
                {
                    "geracao": geracao,
                    "fase": fase,
                    "melhor": round(aptidao_fase, 4),
                    "media": round(media, 4),
                    "pior": round(pior, 4),
                    "validacao": round(nota_validacao, 4),
                    "campea": round(self.nota_campeao, 4),
                }
            )
            self.ultimo_log = self._montar_log(
                geracao,
                fase,
                melhor,
                media,
                pior,
                nota_validacao,
                plano,
                operadores,
                motivo if parou else None,
            )
            self.diario.extend(self.ultimo_log)
            self.diario = self.diario[-250:]
            print(
                f"Geração {geracao + 1}/{config['geracoes']} fase={fase} "
                f"melhor={aptidao_fase:.2f} média={media:.2f} "
                f"validação={nota_validacao:.2f} campeã={self.nota_campeao:.2f}",
                flush=True,
            )
            if self.persistir:
                self._salvar()

    def _salvar(self):
        populacao = []
        for ind in self.populacao or []:
            populacao.append(
                {
                    "genes": [round(g, 6) for g in ind.genes],
                    "aptidao": ind.aptidao,
                    "vitorias": ind.vitorias,
                    "empates": ind.empates,
                    "derrotas": ind.derrotas,
                    "ilegais": ind.ilegais,
                    "legais": ind.legais,
                    "partidas": ind.partidas,
                }
            )
        dados = {
            "config": self.config,
            "geracao": self.geracao,
            "historico": self.historico,
            "diario": self.diario[-120:],
            "ultimo_log": self.ultimo_log,
            "partidaExemplo": self.partida_exemplo,
            "campeao": None if self.campeao is None else [round(g, 6) for g in self.campeao],
            "notaCampea": self.nota_campeao,
            "encerrado": self.encerrado,
            "motivoParada": self.motivo_parada,
            "semMelhora": self.sem_melhora,
            "medindo": self.medindo,
            "marco": self.marco,
            "sucessoSeguido": self.sucesso_seguido,
            "populacao": populacao,
        }
        ARQUIVO_TREINO.parent.mkdir(parents=True, exist_ok=True)
        ARQUIVO_TREINO.write_text(json.dumps(dados, ensure_ascii=False), encoding="utf-8")

    def _carregar(self):
        if not ARQUIVO_TREINO.exists():
            return
        try:
            dados = json.loads(ARQUIVO_TREINO.read_text(encoding="utf-8"))
        except (OSError, json.JSONDecodeError):
            return
        config = dados.get("config")
        if isinstance(config, dict):
            for chave in CONFIG_PADRAO:
                if chave in config:
                    self.config[chave] = config[chave]
        self.topologia = (9, int(self.config["ocultos"]), 9)
        self._rede = MLP(self.topologia)
        self.geracao = int(dados.get("geracao", -1))
        self.rng = random.Random(self.config["semente"] + max(self.geracao, 0) * 1000 + 1)
        self._montar_validacao()
        self.historico = dados.get("historico") or []
        self.diario = dados.get("diario") or []
        self.ultimo_log = dados.get("ultimo_log") or []
        self.partida_exemplo = dados.get("partidaExemplo")
        self.campeao = dados.get("campeao")
        if self.campeao is not None and len(self.campeao) != numero_de_pesos(self.topologia):
            self.campeao = None
            self.nota_campeao = None
        else:
            self.nota_campeao = dados.get("notaCampea")
        self.encerrado = bool(dados.get("encerrado"))
        self.motivo_parada = dados.get("motivoParada")
        self.sem_melhora = int(dados.get("semMelhora") or 0)
        self.medindo = bool(dados.get("medindo"))
        self.marco = dados.get("marco")
        self.sucesso_seguido = int(dados.get("sucessoSeguido") or 0)
        populacao = []
        for item in dados.get("populacao") or []:
            genes = item.get("genes")
            if not genes or len(genes) != numero_de_pesos(self.topologia):
                populacao = []
                break
            ind = Individuo([float(g) for g in genes])
            ind.aptidao = item.get("aptidao")
            ind.vitorias = item.get("vitorias") or 0
            ind.empates = item.get("empates") or 0
            ind.derrotas = item.get("derrotas") or 0
            ind.ilegais = item.get("ilegais") or 0
            ind.legais = item.get("legais") or 0
            ind.partidas = item.get("partidas") or 0
            populacao.append(ind)
        self.populacao = populacao or None
        if self.populacao is None:
            self.geracao = -1

    def _sementes_da_fase(self, fase, quantidade):
        """As mesmas partidas para todos e para toda a fase.

        Sem isso a aptidão muda de geração em geração só por causa do acaso
        do modo médio, e o elitismo não consegue guardar quem jogou melhor.
        """
        codigo = {"medio": 11, "misto": 29, "dificil": 47}[fase]
        base = random.Random(self.config["semente"] * 1009 + codigo * 9176 + quantidade)
        return [base.randrange(1, 10**9) for _ in range(quantidade)]

    def _validar(self, individuo):
        """Nota no difícil com sementes fixas. Não deixa essa nota na população."""
        aptidao = individuo.aptidao
        vitorias, empates, derrotas = individuo.vitorias, individuo.empates, individuo.derrotas
        ilegais, legais, partidas = individuo.ilegais, individuo.legais, individuo.partidas
        rede = MLP(self.topologia)
        stats = avaliar_individuo(
            individuo,
            rede,
            self._plano_validacao,
            self._sementes_validacao,
            medir_otimas=False,
        )
        nota = stats["aptidao"]
        individuo.aptidao = aptidao
        individuo.vitorias = vitorias
        individuo.empates = empates
        individuo.derrotas = derrotas
        individuo.ilegais = ilegais
        individuo.legais = legais
        individuo.partidas = partidas
        return nota

    def _partida_demonstracao(self, genes, fase, geracao):
        modo = "medio" if fase == "medio" else "dificil"
        rede = MLP(self.topologia)
        rede.definir_pesos(genes)
        rng = random.Random(self.config["semente"] + 5000 + geracao)
        partida = jogar_partida(rede, modo, geracao % 2 == 0, rng, medir_otimas=False)
        partida["lances"] = [
            {"casa": lance["casa"], "jogador": lance["jogador"], "lado": lance["lado"]}
            for lance in partida["lances"]
        ]
        del partida["tabuleiro"]
        return partida

    def _atualiza_medicao(self, fase):
        curriculo = self.config["curriculo"]
        return fase == "dificil" or curriculo in ("medio", "dificil")

    def _atualizar_convergencia(self, fase, nota_validacao):
        if not self._atualiza_medicao(fase):
            self.sem_melhora = 0
            self.sucesso_seguido = 0
            self.medindo = False
            return False, None
        if not self.medindo:
            self.medindo = True
            self.marco = nota_validacao
            self.sem_melhora = 0
            self.sucesso_seguido = 0
            return False, None
        if nota_validacao > self.marco + 0.05:
            self.marco = nota_validacao
            self.sem_melhora = 0
        else:
            self.sem_melhora += 1
        if nota_validacao >= self.config["limiarSucesso"]:
            self.sucesso_seguido += 1
        else:
            self.sucesso_seguido = 0
        if self.sucesso_seguido >= 3:
            return True, (
                "Convergência: a validação no difícil ficou em "
                f"{nota_validacao:.2f} ou mais por 3 gerações."
            )
        if self.sem_melhora >= self.config["paciencia"]:
            return True, (
                "Convergência: a melhor validação não melhora há "
                f"{self.sem_melhora} gerações."
            )
        return False, None

    def _montar_log(self, geracao, fase, melhor, media, pior, validacao, plano, operadores, motivo):
        nomes = {"medio": "Médio", "dificil": "Difícil", "misto": "Misto"}
        comeca_rede = sum(1 for _modo, comeca in plano if comeca)
        linhas = [
            f"Geração {geracao + 1} · fase {nomes.get(fase, fase)} · {len(plano)} partidas por rede "
            f"({comeca_rede} começadas pela rede, {len(plano) - comeca_rede} pelo Minimax).",
            f"Aptidão — melhor {melhor.aptidao:.2f}, média {media:.2f}, pior {pior:.2f}.",
            (
                f"Melhor da geração: {melhor.vitorias} "
                f"{'vitória' if melhor.vitorias == 1 else 'vitórias'}, "
                f"{melhor.empates} {'empate' if melhor.empates == 1 else 'empates'}, "
                f"{melhor.derrotas} {'derrota' if melhor.derrotas == 1 else 'derrotas'}, "
                f"{melhor.ilegais} "
                f"{'casa ocupada' if melhor.ilegais == 1 else 'casas ocupadas'}."
            ),
            f"Validação fixa no difícil: {validacao:.2f}. Campeã guardada: {self.nota_campeao:.2f}.",
        ]
        if operadores is None:
            linhas.append("População inicial aleatória. Seleção, cruzamento e mutação ainda não rodaram.")
        else:
            nome = "BLX-α" if self.config["cruzamento"] == "blx" else "aritmético"
            campea = " A campeã do difícil foi recolocada na elite." if operadores["campeaReinserida"] else ""
            linhas.append(
                f"Elitismo: {operadores['elitismo']} cromossomos copiados sem cruzar e sem mutar.{campea}"
            )
            linhas.append(
                f"Torneio k = {self.config['torneio']}: {operadores['cruzamentos']} cruzamentos {nome} "
                f"e {operadores['copiasSemCruzamento']} pares copiados sem cruzar."
            )
            linhas.append(
                f"Mutação gaussiana: {operadores['genesMutados']} pesos alterados "
                f"(taxa {self.config['taxaMutacao']}, σ = {self.config['sigma']})."
            )
        linhas.append(
            "Partidas com semente fixa nesta fase: a aptidão é comparável à geração anterior."
        )
        if motivo:
            linhas.append(motivo)
        else:
            linhas.append(
                f"Sem melhora relevante há {self.sem_melhora} gerações "
                f"(paciência {self.config['paciencia']})."
            )
        return linhas

    def genes_campea(self):
        with self.lock:
            if self.campeao is None:
                return None, self.topologia
            return self.campeao[:], self.topologia

    def testar(self, jogos, modo):
        genes, topologia = self.genes_campea()
        aleatoria = genes is None
        rede = MLP(topologia)
        if genes is None:
            rng_genes = random.Random(self.config["semente"] + 17)
            rede.definir_pesos(genes_aleatorios(topologia, rng_genes))
        else:
            rede.definir_pesos(genes)
        jogos = max(2, min(80, int(jogos)))
        if jogos % 2:
            jogos += 1
        rng_semente = random.Random()
        vitorias = empates = derrotas = ilegais = otimas = jogadas = 0
        for i in range(jogos):
            partida = jogar_partida(
                rede,
                modo,
                i % 2 == 0,
                random.Random(rng_semente.randrange(1, 10**9)),
                medir_otimas=True,
            )
            vitorias += partida["desfecho"] == "vitoria"
            empates += partida["desfecho"] == "empate"
            derrotas += partida["desfecho"] == "derrota"
            ilegais += partida["ilegais"]
            otimas += partida["otimas"]
            jogadas += partida["jogadasRede"]
        acuracia = (otimas / jogadas) if jogadas else 0.0
        aproveitamento = (vitorias + empates) / jogos
        return {
            "modo": modo,
            "jogos": jogos,
            "vitorias": vitorias,
            "empates": empates,
            "derrotas": derrotas,
            "ilegais": ilegais,
            "jogadas": jogadas,
            "otimas": otimas,
            "acuracia": acuracia,
            "aproveitamento": aproveitamento,
            "redeAleatoria": aleatoria,
        }

    def foto(self):
        populacao = []
        if self.populacao:
            for ind in self.populacao:
                populacao.append(_resumo_individuo(ind))
        fase = None
        if self.geracao >= 0:
            fase = fase_da_geracao(self.geracao, self.config["geracoes"], self.config["curriculo"])
        return {
            "executando": self.executando,
            "geracao": self.geracao,
            "maxGeracoes": self.config["geracoes"],
            "fase": fase,
            "encerrado": self.encerrado,
            "motivoParada": self.motivo_parada,
            "semMelhora": self.sem_melhora,
            "historico": list(self.historico),
            "populacao": populacao,
            "log": list(self.ultimo_log),
            "diario": list(self.diario),
            "partidaExemplo": self.partida_exemplo,
            "redePronta": self.campeao is not None,
            "notaCampea": self.nota_campeao,
            "topologia": list(self.topologia),
            "pesos": numero_de_pesos(self.topologia),
            "config": dict(self.config),
            "descricao": self.descrever(),
        }
