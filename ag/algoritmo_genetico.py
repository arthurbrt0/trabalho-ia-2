"""Ciclo do AG: elitismo, torneio, cruzamento real e mutação gaussiana.

O cromossomo é uma lista de double (pesos e bias). O cruzamento de um ponto
em binário não serve para esse código, então há dois operadores para reais:

- BLX-α (Eshelman e Schaffer): para cada gene, sorteia no intervalo dos pais
  expandido por α. É o operador padrão.
- Aritmético: filho = β * pai1 + (1 - β) * pai2, com β em [0, 1].
"""

LIMITE_PESO = 4.0


class Individuo:
    __slots__ = (
        "genes",
        "aptidao",
        "vitorias",
        "empates",
        "derrotas",
        "ilegais",
        "legais",
        "partidas",
    )

    def __init__(self, genes):
        self.genes = genes
        self.aptidao = None
        self.vitorias = 0
        self.empates = 0
        self.derrotas = 0
        self.ilegais = 0
        self.legais = 0
        self.partidas = 0

    def copiar_genes(self):
        novo = Individuo(self.genes[:])
        return novo


def _recortar(valor):
    if valor > LIMITE_PESO:
        return LIMITE_PESO
    if valor < -LIMITE_PESO:
        return -LIMITE_PESO
    return valor


def torneio(populacao, tamanho, rng):
    tamanho = min(tamanho, len(populacao))
    grupo = rng.sample(populacao, tamanho)
    return max(grupo, key=lambda ind: ind.aptidao)


def selecionar_pais(populacao, tamanho, rng):
    primeiro = torneio(populacao, tamanho, rng)
    if len(populacao) == 1:
        return primeiro, primeiro
    segundo = torneio(populacao, tamanho, rng)
    for _ in range(3):
        if segundo is not primeiro:
            break
        segundo = torneio(populacao, tamanho, rng)
    return primeiro, segundo


def cruzamento_blx(pai, mae, rng, alpha):
    """BLX-α. Dois filhos, um sorteio independente por gene."""
    filho_a = []
    filho_b = []
    for a, b in zip(pai, mae):
        inferior = a if a < b else b
        superior = b if a < b else a
        alcance = superior - inferior
        baixo = inferior - alpha * alcance
        alto = superior + alpha * alcance
        if alto < baixo:
            baixo, alto = alto, baixo
        filho_a.append(_recortar(rng.uniform(baixo, alto)))
        filho_b.append(_recortar(rng.uniform(baixo, alto)))
    return filho_a, filho_b


def cruzamento_aritmetico(pai, mae, rng):
    """Cruzamento aritmético. Um β por gene, os dois filhos são complementares."""
    filho_a = []
    filho_b = []
    for a, b in zip(pai, mae):
        beta = rng.random()
        filho_a.append(_recortar(beta * a + (1.0 - beta) * b))
        filho_b.append(_recortar((1.0 - beta) * a + beta * b))
    return filho_a, filho_b


def mutar(genes, rng, taxa, sigma):
    alterados = 0
    for i in range(len(genes)):
        if rng.random() < taxa:
            genes[i] = _recortar(genes[i] + rng.gauss(0.0, sigma))
            alterados += 1
    return alterados


def nova_geracao(populacao, config, rng, campeao=None):
    """Monta a geração seguinte. A aptidão é recalculada depois, fora daqui.

    Elitismo copia os melhores cromossomos sem cruzar e sem mutar.
    O restante nasce de torneio, cruzamento (se cair na taxa) e mutação.
    A campeã validada no modo difícil, se existir, ocupa a última vaga
    da elite para não se perder quando a fase do currículo muda.
    """
    if any(ind.aptidao is None for ind in populacao):
        raise ValueError("A população precisa estar avaliada antes do ciclo.")

    ordenada = sorted(populacao, key=lambda ind: ind.aptidao, reverse=True)
    elitismo = min(config["elitismo"], len(ordenada))
    elites = [ordenada[i].copiar_genes() for i in range(elitismo)]

    reinclusa = False
    if campeao is not None and elites:
        elites[-1] = Individuo(campeao[:])
        reinclusa = True

    filhos = list(elites)
    cruzamentos = 0
    clones = 0
    genes_mutados = 0
    operador = config["cruzamento"]

    while len(filhos) < len(populacao):
        pai, mae = selecionar_pais(populacao, config["torneio"], rng)
        if rng.random() < config["taxaCruzamento"]:
            if operador == "aritmetico":
                genes_a, genes_b = cruzamento_aritmetico(pai.genes, mae.genes, rng)
            else:
                genes_a, genes_b = cruzamento_blx(
                    pai.genes, mae.genes, rng, config["alphaBlx"]
                )
            cruzamentos += 1
        else:
            genes_a = pai.genes[:]
            genes_b = mae.genes[:]
            clones += 1
        genes_mutados += mutar(genes_a, rng, config["taxaMutacao"], config["sigma"])
        genes_mutados += mutar(genes_b, rng, config["taxaMutacao"], config["sigma"])
        filhos.append(Individuo(genes_a))
        if len(filhos) < len(populacao):
            filhos.append(Individuo(genes_b))

    return filhos, {
        "elitismo": elitismo,
        "campeaReinserida": reinclusa,
        "cruzamentos": cruzamentos,
        "copiasSemCruzamento": clones,
        "genesMutados": genes_mutados,
        "melhorAnterior": ordenada[0].aptidao,
    }
