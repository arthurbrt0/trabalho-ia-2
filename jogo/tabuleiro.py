"""Estado do jogo da velha e verificação de vitória, empate ou partida em andamento."""

LINHAS = (
    (0, 1, 2),
    (3, 4, 5),
    (6, 7, 8),
    (0, 3, 6),
    (1, 4, 7),
    (2, 5, 8),
    (0, 4, 8),
    (2, 4, 6),
)

# 0 = casa vazia, 1 = X, 2 = O
VAZIO = 0
X = 1
O = 2


def outro(jogador):
    return O if jogador == X else X


def casas_livres(tabuleiro):
    return [i for i, casa in enumerate(tabuleiro) if casa == VAZIO]


def estado(tabuleiro):
    """Devolve (resultado, linha).

    resultado: 1 ou 2 se alguém venceu, 0 se empatou, None se ainda há jogo.
    linha: índices da trinca vencedora, ou None.
    """
    for a, b, c in LINHAS:
        valor = tabuleiro[a]
        if valor != VAZIO and valor == tabuleiro[b] == tabuleiro[c]:
            return valor, (a, b, c)
    if VAZIO not in tabuleiro:
        return 0, None
    return None, None


def tabuleiro_vazio():
    return [VAZIO] * 9


def simbolo(jogador):
    if jogador == X:
        return "X"
    if jogador == O:
        return "O"
    return "·"
