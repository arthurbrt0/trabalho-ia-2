"""Uma partida completa entre a rede e o Minimax."""

from jogo.minimax import jogada, jogadas_otimas
from jogo.tabuleiro import X, estado, outro, tabuleiro_vazio


def jogar_partida(rede, modo, rede_comeca, rng, medir_otimas=False):
    """A rede joga com um símbolo; o Minimax (ou o modo médio) joga com o outro.

    Quem começa é sempre o X. Se a rede não começa, ela é o O.
    Casa ilegal no argmax é penalizada e a partida segue na melhor casa livre,
    para o jogo terminar e a aptidão ainda enxergar a qualidade das casas legais.
    """
    tabuleiro = tabuleiro_vazio()
    simbolo_rede = X if rede_comeca else outro(X)
    ilegais = 0
    legais = 0
    otimas = 0
    jogadas_rede = 0
    lances = []
    vez = X

    for _ in range(9):
        resultado, linha = estado(tabuleiro)
        if resultado is not None:
            break
        if vez == simbolo_rede:
            casa, ilegal = rede.escolher(tabuleiro, vez)
            if casa is None:
                break
            jogadas_rede += 1
            if ilegal:
                ilegais += 1
            else:
                legais += 1
            foi_otima = False
            if medir_otimas:
                foi_otima = casa in jogadas_otimas(tabuleiro, vez)
                if foi_otima:
                    otimas += 1
            tabuleiro[casa] = vez
            lances.append(
                {
                    "casa": casa,
                    "jogador": vez,
                    "lado": "rede",
                    "ilegal": ilegal,
                    "otima": foi_otima,
                }
            )
        else:
            casa = jogada(tabuleiro, vez, modo, rng)
            if casa is None:
                break
            tabuleiro[casa] = vez
            lances.append(
                {
                    "casa": casa,
                    "jogador": vez,
                    "lado": "minimax",
                    "ilegal": False,
                    "otima": True,
                }
            )
        vez = outro(vez)

    resultado, linha = estado(tabuleiro)
    if resultado is None:
        # Tabuleiro inconsistente: trata como derrota da rede.
        resultado = outro(simbolo_rede)
        linha = None

    if resultado == 0:
        desfecho = "empate"
    elif resultado == simbolo_rede:
        desfecho = "vitoria"
    else:
        desfecho = "derrota"

    return {
        "desfecho": desfecho,
        "ilegais": ilegais,
        "legais": legais,
        "otimas": otimas,
        "jogadasRede": jogadas_rede,
        "lances": lances,
        "tabuleiro": tabuleiro[:],
        "linha": list(linha) if linha else None,
        "resultado": resultado,
        "simboloRede": simbolo_rede,
        "redeComeca": rede_comeca,
        "modo": modo,
    }
