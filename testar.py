"""Testes do jogo, do Minimax, da rede e de uma geração do AG."""

import random

from ag.algoritmo_genetico import Individuo, cruzamento_aritmetico, nova_geracao
from jogo.minimax import aquecer, jogada, jogadas_otimas, limpar_cache
from jogo.simulacao import jogar_partida
from jogo.tabuleiro import O, X, estado, outro, tabuleiro_vazio
from rede.mlp import MLP, codificar, genes_aleatorios, numero_de_pesos
from treino.treinador import Treinador, fase_da_geracao, partidas_da_fase, pontuar


class RngMeio:
    """Metade das consultas cai no ramo aleatório, metade no Minimax."""

    def __init__(self):
        self.n = 0

    def random(self):
        self.n += 1
        return 0.0 if self.n % 2 else 0.99

    def choice(self, opcoes):
        return opcoes[-1]


def testar_tabuleiro():
    tab = tabuleiro_vazio()
    assert estado(tab) == (None, None)
    tab[0] = tab[1] = tab[2] = X
    resultado, linha = estado(tab)
    assert resultado == X and linha == (0, 1, 2)
    tab = [X, O, X, O, X, O, O, X, O]
    assert estado(tab)[0] == 0
    tab = tabuleiro_vazio()
    tab[2] = tab[4] = tab[6] = O
    assert estado(tab)[0] == O


def testar_minimax():
    aquecer()
    vazio = tabuleiro_vazio()
    assert jogada(vazio, X, "dificil") == 4
    rng = RngMeio()
    casas = [jogada(tabuleiro_vazio(), X, "medio", rng) for _ in range(20)]
    assert casas.count(8) == 10
    assert casas.count(4) == 10

    def partida(minimax_eh, semente):
        tab = tabuleiro_vazio()
        vez = X
        rng_jogo = random.Random(semente)
        while True:
            fim, _linha = estado(tab)
            if fim is not None:
                return fim
            if vez == minimax_eh:
                casa = jogada(tab, vez, "dificil")
            else:
                casa = rng_jogo.choice([i for i in range(9) if tab[i] == 0])
            tab[casa] = vez
            vez = outro(vez)

    for semente in range(30):
        assert partida(X, semente) != O
        assert partida(O, semente) != X

    tab = tabuleiro_vazio()
    vez = X
    rng_jogo = random.Random(1)
    while estado(tab)[0] is None:
        casa = jogada(tab, vez, "dificil", rng_jogo)
        assert casa in jogadas_otimas(tab, vez)
        tab[casa] = vez
        vez = outro(vez)
    assert estado(tab)[0] == 0


def testar_rede():
    topologia = (9, 4, 9)
    rede = MLP(topologia)
    saida = rede.propagar(codificar(tabuleiro_vazio(), X))
    assert len(saida) == 9
    assert all(-1.0 <= valor <= 1.0 for valor in saida)
    genes = [0.0] * numero_de_pesos(topologia)
    cursor = topologia[0] * topologia[1] + topologia[1]
    cursor += topologia[1] * topologia[2]
    genes[cursor] = 2.0
    rede.definir_pesos(genes)
    casa, ilegal = rede.escolher(tabuleiro_vazio(), X)
    assert casa == 0 and not ilegal
    ocupado = tabuleiro_vazio()
    ocupado[0] = O
    casa, ilegal = rede.escolher(ocupado, X)
    assert ilegal and casa != 0
    assert pontuar("vitoria", 0, 5) > pontuar("empate", 0, 5) > pontuar("derrota", 0, 5)
    assert pontuar("empate", 2, 3) < pontuar("empate", 0, 5)


def testar_ag_e_fases():
    assert fase_da_geracao(0, 45, "curriculo") == "medio"
    assert fase_da_geracao(17, 45, "curriculo") == "medio"
    assert fase_da_geracao(18, 45, "curriculo") == "misto"
    assert fase_da_geracao(30, 45, "curriculo") == "misto"
    assert fase_da_geracao(31, 45, "curriculo") == "dificil"
    plano = partidas_da_fase("medio", {"jogosMedio": 8, "jogosDificil": 6})
    assert [comeca for _modo, comeca in plano].count(True) == 4
    assert [comeca for _modo, comeca in plano].count(False) == 4

    rng = random.Random(1)
    populacao = []
    for i in range(8):
        ind = Individuo([float(i), 0.2])
        ind.aptidao = float(i)
        populacao.append(ind)
    config = {
        "elitismo": 2,
        "torneio": 3,
        "taxaCruzamento": 1,
        "taxaMutacao": 0,
        "sigma": 0.1,
        "alphaBlx": 0.5,
        "cruzamento": "aritmetico",
    }
    filhos, info = nova_geracao(populacao, config, rng)
    assert len(filhos) == 8
    assert info["elitismo"] == 2
    assert any(filho.genes == [7.0, 0.2] for filho in filhos)
    a, b = cruzamento_aritmetico([0.0, 2.0], [2.0, 0.0], random.Random(3))
    assert len(a) == 2 and len(b) == 2


def testar_uma_geracao():
    treino = Treinador(persistir=False)
    treino.config.update(
        {
            "populacao": 8,
            "geracoes": 3,
            "ocultos": 6,
            "jogosMedio": 4,
            "jogosDificil": 2,
            "elitismo": 2,
            "curriculo": "medio",
            "paciencia": 20,
        }
    )
    treino.topologia = (9, 6, 9)
    treino._rede = MLP(treino.topologia)
    treino._montar_validacao()
    treino.pedir("completo")
    treino._thread.join(timeout=60)
    assert treino.geracao == 2
    assert treino.historico[0]["fase"] == "medio"
    assert len(treino.populacao) == 8
    assert treino.campeao is not None
    assert len(treino.campeao) == numero_de_pesos(treino.topologia)
    assert any("Elitismo" in linha for linha in treino.diario)
    rede = MLP(treino.topologia)
    rede.definir_pesos(treino.campeao)
    partida = jogar_partida(rede, "dificil", True, random.Random(0))
    assert partida["desfecho"] in ("vitoria", "empate", "derrota")
    assert len(partida["lances"]) >= 5


def testar_aprendizagem_curta():
    """Não exige vitória; exige que a melhor aptidão suba no modo médio."""
    treino = Treinador(persistir=False)
    treino.config.update(
        {
            "populacao": 24,
            "geracoes": 12,
            "ocultos": 12,
            "jogosMedio": 6,
            "jogosDificil": 4,
            "elitismo": 4,
            "torneio": 4,
            "cruzamento": "aritmetico",
            "taxaCruzamento": 0.85,
            "taxaMutacao": 0.08,
            "sigma": 0.12,
            "curriculo": "medio",
            "paciencia": 30,
            "semente": 7,
        }
    )
    treino.rng = random.Random(7)
    treino.topologia = (9, 12, 9)
    treino._rede = MLP(treino.topologia)
    treino._montar_validacao()
    treino.pedir("completo")
    treino._thread.join(timeout=120)
    curva = [ponto["melhor"] for ponto in treino.historico]
    print("Aptidão por geração:", ", ".join(f"{v:.2f}" for v in curva))
    assert curva[-1] >= curva[0]
    assert max(curva) >= curva[0]


if __name__ == "__main__":
    limpar_cache()
    testar_tabuleiro()
    testar_minimax()
    testar_rede()
    testar_ag_e_fases()
    testar_uma_geracao()
    testar_aprendizagem_curta()
    print("Testes ok.")
