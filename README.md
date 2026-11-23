# Jogo da Velha — RN + AG + Minimax

Trabalho T2 de Inteligência Artificial (PUCRS). A rede é uma MLP 9-12-9 e só faz propagação. O algoritmo genético evolui os pesos. O Minimax, nos modos médio e difícil, é o adversário do treino.

## Rodar

É preciso Python 3.10 ou mais recente. Não há biblioteca para instalar.

```bash
python servidor.py
```

O navegador abre em `http://127.0.0.1:8080`.

## O que dá para fazer

- **Você × Minimax:** jogar no modo difícil (Minimax em toda jogada) ou médio (50% Minimax, 50% jogada aleatória).
- **Aprendizagem:** criar a população, avançar uma geração ou treinar até o limite. O gráfico, a população e o diário mostram o ciclo do AG.
- **Você × Rede:** jogar contra a rede campeã. A acurácia é a fração de jogadas da rede que também são ótimas para o Minimax. O botão "Testar acurácia" repete isso em várias partidas automáticas.

A campeã e a população ficam em `dados/treino.json`.
