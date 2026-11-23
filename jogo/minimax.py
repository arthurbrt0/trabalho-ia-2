"""Minimax com dois modos de jogo.

Difícil: a jogada é sempre a do Minimax.
Médio: em cada jogada, 50% usam o Minimax e 50% são aleatórias entre as casas livres.
"""

import random

from jogo.tabuleiro import O, X, estado, outro

# Valor de uma posição já resolvida, do ponto de vista de `eu`.
# A chave é (código do tabuleiro, de quem é a vez, jogador maximizado).
_CACHE = {}


def limpar_cache():
    _CACHE.clear()


def _codigo(tabuleiro):
    codigo = 0
    for casa in tabuleiro:
        codigo = codigo * 3 + casa
    return codigo


def _vazias(tabuleiro):
    return sum(1 for casa in tabuleiro if casa == 0)


def _valor_terminal(tabuleiro, eu):
    """Pontuação exata se a partida acabou; None se ainda há jogo.

    Vitória rápida vale mais e derrota rápida vale menos, então o Minimax
    fecha o jogo quando pode e adia a derrota quando não pode.
    """
    resultado, _linha = estado(tabuleiro)
    if resultado is None:
        return None
    if resultado == 0:
        return 0
    saldo = 10 + _vazias(tabuleiro)
    if resultado == eu:
        return saldo
    return -saldo


def _valor(tabuleiro, vez, eu):
    codigo = _codigo(tabuleiro)
    chave = (codigo, vez, eu)
    guardado = _CACHE.get(chave)
    if guardado is not None:
        return guardado

    terminal = _valor_terminal(tabuleiro, eu)
    if terminal is not None:
        _CACHE[chave] = terminal
        return terminal

    if vez == eu:
        melhor = -10**9
        for i in range(9):
            if tabuleiro[i] == 0:
                tabuleiro[i] = vez
                melhor = max(melhor, _valor(tabuleiro, outro(vez), eu))
                tabuleiro[i] = 0
    else:
        melhor = 10**9
        for i in range(9):
            if tabuleiro[i] == 0:
                tabuleiro[i] = vez
                melhor = min(melhor, _valor(tabuleiro, outro(vez), eu))
                tabuleiro[i] = 0

    _CACHE[chave] = melhor
    return melhor


def jogadas_otimas(tabuleiro, jogador):
    """Todas as casas com o valor máximo do Minimax."""
    melhor = -10**9
    casas = []
    adversario = outro(jogador)
    for i in range(9):
        if tabuleiro[i] != 0:
            continue
        tabuleiro[i] = jogador
        valor = _valor(tabuleiro, adversario, jogador)
        tabuleiro[i] = 0
        if valor > melhor:
            melhor = valor
            casas = [i]
        elif valor == melhor:
            casas.append(i)
    return casas


# Entre jogadas com o mesmo valor, o difícil fica estável: centro, cantos, bordas.
# Sem isso, no começo do jogo toda casa vale empate e o Minimax jogaria qualquer uma.
_PREFERENCIA = {4: 3, 0: 2, 2: 2, 6: 2, 8: 2, 1: 1, 3: 1, 5: 1, 7: 1}


def jogada_minimax(tabuleiro, jogador, rng=None):
    """Uma jogada ótima. O desempate não usa sorte, para o treino não oscilar à toa."""
    del rng
    casas = jogadas_otimas(tabuleiro, jogador)
    if not casas:
        return None
    return max(casas, key=lambda casa: _PREFERENCIA[casa])


def jogada(tabuleiro, jogador, modo, rng=None):
    """Escolhe a casa do oponente no modo `medio` ou `dificil`."""
    if rng is None:
        rng = random
    livres = [i for i in range(9) if tabuleiro[i] == 0]
    if not livres:
        return None
    if modo == "medio" and rng.random() < 0.5:
        return rng.choice(livres)
    return jogada_minimax(tabuleiro, jogador, rng)


def aquecer():
    """Resolve o jogo de tabuleiro vazio uma vez para encher o cache."""
    vazio = [0] * 9
    rng = random.Random(0)
    jogada_minimax(vazio, X, rng)
    jogada_minimax(vazio, O, rng)
