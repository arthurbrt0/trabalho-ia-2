"""MLP de duas camadas (oculta + saída). Só a propagação é implementada.

Topologia padrão 9-18-9:
- 9 entradas: tabuleiro visto pela rede (1 peça dela, -1 adversário, 0 vazio)
- 18 neurônios na camada oculta
- 9 saídas: uma pontuação por casa

Os pesos não são ajustados por backpropagation. O cromossomo do algoritmo
genético é a lista de todos os pesos e bias, camada após camada.
"""

import math


def codificar(tabuleiro, jogador):
    """Entrada da rede a partir do jogador que está na vez."""
    entrada = []
    for casa in tabuleiro:
        if casa == 0:
            entrada.append(0.0)
        elif casa == jogador:
            entrada.append(1.0)
        else:
            entrada.append(-1.0)
    return entrada


def numero_de_pesos(topologia):
    total = 0
    for entrada, saida in zip(topologia, topologia[1:]):
        total += entrada * saida + saida
    return total


def genes_aleatorios(topologia, rng):
    """Inicialização de Glorot (uniforme), bias em zero.

    Cada fatia do cromossomo corresponde a uma camada, na mesma ordem
    usada por definir_pesos.
    """
    genes = []
    for entrada, saida in zip(topologia, topologia[1:]):
        limite = math.sqrt(6.0 / (entrada + saida))
        for _ in range(entrada * saida):
            genes.append(rng.uniform(-limite, limite))
        for _ in range(saida):
            genes.append(0.0)
    return genes


def _tanh(valor):
    # math.tanh já satura; o recorte evita overflow em pesos soltos do AG.
    if valor > 20:
        return 1.0
    if valor < -20:
        return -1.0
    return math.tanh(valor)


class MLP:
    def __init__(self, topologia=(9, 18, 9)):
        self.topologia = tuple(topologia)
        if len(self.topologia) != 3:
            raise ValueError("A rede deste trabalho tem uma camada oculta e uma de saída.")
        if self.topologia[0] != 9 or self.topologia[2] != 9:
            raise ValueError("Entrada e saída têm 9 neurônios, uma casa cada.")
        self.camadas = []
        self.definir_pesos([0.0] * numero_de_pesos(self.topologia))

    def definir_pesos(self, genes):
        esperado = numero_de_pesos(self.topologia)
        if len(genes) != esperado:
            raise ValueError(f"Cromossomo com {len(genes)} genes; a rede espera {esperado}.")
        self.camadas = []
        cursor = 0
        for entrada, saida in zip(self.topologia, self.topologia[1:]):
            pesos = []
            for _ in range(saida):
                pesos.append(genes[cursor : cursor + entrada])
                cursor += entrada
            bias = genes[cursor : cursor + saida]
            cursor += saida
            self.camadas.append((pesos, bias))

    def propagar(self, entrada):
        """Propagação para a frente. Ativação tanh na oculta e na saída."""
        ativacao = entrada
        for pesos, bias in self.camadas:
            proxima = []
            for j in range(len(bias)):
                soma = bias[j]
                linha = pesos[j]
                for i, valor in enumerate(ativacao):
                    soma += linha[i] * valor
                proxima.append(_tanh(soma))
            ativacao = proxima
        return ativacao

    def escolher(self, tabuleiro, jogador):
        """Devolve (casa_jogada, escolha_bruta_era_ilegal).

        A casa jogada é a de maior saída entre as livres. Se o argmax absoluto
        cai numa casa ocupada, a jogada segue na melhor casa livre e o chamador
        penaliza a escolha ilegal.
        """
        saida = self.propagar(codificar(tabuleiro, jogador))
        ordem = sorted(range(9), key=lambda i: (saida[i], -i), reverse=True)
        bruta = ordem[0]
        ilegal = tabuleiro[bruta] != 0
        for casa in ordem:
            if tabuleiro[casa] == 0:
                return casa, ilegal
        return None, True
