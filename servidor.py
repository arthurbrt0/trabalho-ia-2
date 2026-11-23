"""Front-end mínimo do jogo da velha.

Três modos, no navegador:
- você joga contra o Minimax (médio ou difícil)
- a rede aprende com o Minimax, geração por geração
- você joga contra a rede treinada e a acurácia aparece na tela

Sem bibliotecas externas. Rode: python servidor.py
"""

import json
import os
import random
import sys
import threading
import webbrowser
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path
from urllib.parse import urlparse

from jogo.minimax import aquecer, jogada, jogadas_otimas
from jogo.tabuleiro import O, X, estado, outro, simbolo, tabuleiro_vazio
from rede.mlp import MLP, genes_aleatorios
from treino.treinador import Treinador

RAIZ = Path(__file__).resolve().parent
STATIC = RAIZ / "static"

treinador = Treinador()
salas = {}
trava_salas = threading.RLock()


class Sala:
    def __init__(self, tipo):
        self.tipo = tipo
        self.ativa = False
        self.tabuleiro = tabuleiro_vazio()
        self.humano = X
        self.vez = X
        self.fim = False
        self.vencedor = None
        self.linha = None
        self.ultima = None
        self.dificuldade = "dificil"
        self.anuncio = "Escolha quem começa e inicie a partida."
        self.rede = None
        self.rede_aleatoria = False
        self.rng = random.Random()
        self.placar = {
            "humano": 0,
            "oponente": 0,
            "empates": 0,
            "jogadas": 0,
            "otimas": 0,
            "ilegais": 0,
        }

    def zerar_placar(self):
        for chave in self.placar:
            self.placar[chave] = 0

    def nova(self, eu_comeco, dificuldade):
        self.ativa = True
        self.tabuleiro = tabuleiro_vazio()
        self.humano = X if eu_comeco else O
        self.vez = X
        self.fim = False
        self.vencedor = None
        self.linha = None
        self.ultima = None
        self.dificuldade = dificuldade if dificuldade in ("medio", "dificil") else "dificil"
        self.rng = random.Random()
        self.rede = None
        self.rede_aleatoria = False
        if self.tipo == "rede":
            genes, topologia = treinador.genes_campea()
            self.rede = MLP(topologia)
            if genes is None:
                self.rede.definir_pesos(genes_aleatorios(topologia, random.Random()))
                self.rede_aleatoria = True
            else:
                self.rede.definir_pesos(genes)
        quem = "Você" if eu_comeco else ("Minimax" if self.tipo == "minimax" else "Rede")
        self.anuncio = f"{quem} começa com X."
        if self.rede_aleatoria:
            self.anuncio += " A rede ainda não foi treinada: os pesos são aleatórios."
        if self.vez != self.humano:
            self._jogada_oponente()

    def jogar(self, casa):
        if not self.ativa or self.fim:
            raise ValueError("Não há partida em andamento.")
        if self.vez != self.humano:
            raise ValueError("Não é a sua vez.")
        if casa < 0 or casa > 8 or self.tabuleiro[casa] != 0:
            raise ValueError("Essa casa não está livre.")
        self.tabuleiro[casa] = self.humano
        self.ultima = casa
        self.vez = outro(self.vez)
        if self._encerrar():
            return
        self._jogada_oponente()

    def _jogada_oponente(self):
        if self.fim:
            return
        vez = self.vez
        if self.tipo == "minimax":
            casa = jogada(self.tabuleiro, vez, self.dificuldade, self.rng)
            ilegal = False
            otima = casa in jogadas_otimas(self.tabuleiro, vez)
        else:
            casa, ilegal = self.rede.escolher(self.tabuleiro, vez)
            otima = casa in jogadas_otimas(self.tabuleiro, vez)
            self.placar["jogadas"] += 1
            self.placar["otimas"] += int(otima)
            self.placar["ilegais"] += int(ilegal)
        if casa is None:
            return
        self.tabuleiro[casa] = vez
        self.ultima = casa
        nome = "Minimax" if self.tipo == "minimax" else "Rede"
        extra = ""
        if self.tipo == "rede" and ilegal:
            extra = " A primeira escolha da rede estava ocupada."
        elif self.tipo == "rede":
            extra = " Jogada ótima." if otima else " Jogada fora do ótimo do Minimax."
        self.anuncio = f"{nome} jogou na casa {casa + 1}.{extra}"
        self.vez = outro(vez)
        self._encerrar()

    def _encerrar(self):
        resultado, linha = estado(self.tabuleiro)
        if resultado is None:
            return False
        self.fim = True
        self.vencedor = resultado
        self.linha = list(linha) if linha else None
        if resultado == 0:
            self.placar["empates"] += 1
            self.anuncio = "Empate."
        elif resultado == self.humano:
            self.placar["humano"] += 1
            self.anuncio = "Você venceu."
        else:
            self.placar["oponente"] += 1
            nome = "Minimax" if self.tipo == "minimax" else "A rede"
            self.anuncio = f"{nome} venceu."
        return True

    def foto(self):
        partidas = self.placar["humano"] + self.placar["oponente"] + self.placar["empates"]
        jogadas = self.placar["jogadas"]
        acuracia = (self.placar["otimas"] / jogadas) if jogadas else None
        aproveitamento = None
        if self.tipo == "rede" and partidas:
            aproveitamento = (self.placar["oponente"] + self.placar["empates"]) / partidas
        return {
            "tipo": self.tipo,
            "ativa": self.ativa,
            "tabuleiro": self.tabuleiro[:],
            "humano": self.humano,
            "vez": self.vez,
            "fim": self.fim,
            "vencedor": self.vencedor,
            "linha": self.linha,
            "ultima": self.ultima,
            "dificuldade": self.dificuldade,
            "anuncio": self.anuncio,
            "podeJogar": self.ativa and not self.fim and self.vez == self.humano,
            "seuSimbolo": simbolo(self.humano) if self.ativa else None,
            "redeAleatoria": self.rede_aleatoria,
            "placar": {
                "voce": self.placar["humano"],
                "oponente": self.placar["oponente"],
                "empates": self.placar["empates"],
                "partidas": partidas,
                "jogadasRede": jogadas,
                "jogadasOtimas": self.placar["otimas"],
                "decisoesIlegais": self.placar["ilegais"],
                "acuracia": acuracia,
                "aproveitamento": aproveitamento,
            },
        }


def sala(tipo):
    if tipo not in ("minimax", "rede"):
        raise ValueError("Modo de jogo desconhecido.")
    with trava_salas:
        if tipo not in salas:
            salas[tipo] = Sala(tipo)
        return salas[tipo]


class Tratador(BaseHTTPRequestHandler):
    def do_GET(self):
        caminho = urlparse(self.path).path
        if caminho == "/":
            self._arquivo(STATIC / "index.html", "text/html; charset=utf-8")
        elif caminho == "/estilo.css":
            self._arquivo(STATIC / "estilo.css", "text/css; charset=utf-8")
        elif caminho == "/app.js":
            self._arquivo(STATIC / "app.js", "text/javascript; charset=utf-8")
        elif caminho == "/api/treino":
            with treinador.lock:
                self._json(200, treinador.foto())
        elif caminho == "/api/partidas":
            with trava_salas:
                fotos = {"minimax": sala("minimax").foto(), "rede": sala("rede").foto()}
            self._json(200, fotos)
        else:
            self._json(404, {"erro": "Não encontrado."})

    def do_POST(self):
        caminho = urlparse(self.path).path
        try:
            dados = self._corpo()
            if caminho == "/api/treino/config":
                foto = treinador.aplicar_config(dados)
                self._json(200, foto)
            elif caminho == "/api/treino/acao":
                acao = dados.get("acao")
                if acao not in ("reiniciar", "uma", "completo"):
                    raise ValueError("Ação de treino desconhecida.")
                self._json(200, treinador.pedir(acao))
            elif caminho == "/api/treino/parar":
                self._json(200, treinador.interromper())
            elif caminho == "/api/benchmark":
                jogos = dados.get("jogos", 30)
                self._json(
                    200,
                    {
                        "dificil": treinador.testar(jogos, "dificil"),
                        "medio": treinador.testar(jogos, "medio"),
                    },
                )
            elif caminho == "/api/partida/nova":
                jogo = sala(dados.get("tipo"))
                with trava_salas:
                    jogo.nova(bool(dados.get("euComeco", True)), dados.get("dificuldade", "dificil"))
                    foto = jogo.foto()
                self._json(200, foto)
            elif caminho == "/api/partida/jogada":
                jogo = sala(dados.get("tipo"))
                casa = dados.get("casa")
                if isinstance(casa, float) and casa.is_integer():
                    casa = int(casa)
                if not isinstance(casa, int):
                    raise ValueError("Casa inválida.")
                with trava_salas:
                    jogo.jogar(casa)
                    foto = jogo.foto()
                self._json(200, foto)
            elif caminho == "/api/partida/zerar":
                jogo = sala(dados.get("tipo"))
                with trava_salas:
                    jogo.zerar_placar()
                    foto = jogo.foto()
                self._json(200, foto)
            else:
                self._json(404, {"erro": "Não encontrado."})
        except ValueError as erro:
            self._json(400, {"erro": str(erro)})
        except RuntimeError as erro:
            self._json(409, {"erro": str(erro)})
        except Exception as erro:
            self._json(500, {"erro": f"Falha no servidor: {erro}"})

    def _corpo(self):
        tamanho = int(self.headers.get("Content-Length", "0") or 0)
        if tamanho <= 0:
            return {}
        bruto = self.rfile.read(tamanho).decode("utf-8")
        return json.loads(bruto) if bruto else {}

    def _arquivo(self, caminho, tipo):
        if not caminho.exists():
            self._json(404, {"erro": "Arquivo ausente."})
            return
        corpo = caminho.read_bytes()
        self.send_response(200)
        self.send_header("Content-Type", tipo)
        self.send_header("Content-Length", str(len(corpo)))
        self.send_header("Cache-Control", "no-store")
        self.end_headers()
        self.wfile.write(corpo)

    def _json(self, codigo, dados):
        corpo = json.dumps(dados, ensure_ascii=False).encode("utf-8")
        self.send_response(codigo)
        self.send_header("Content-Type", "application/json; charset=utf-8")
        self.send_header("Content-Length", str(len(corpo)))
        self.send_header("Cache-Control", "no-store")
        self.end_headers()
        self.wfile.write(corpo)

    def log_message(self, formato, *args):
        return


def main():
    try:
        sys.stdout.reconfigure(encoding="utf-8")
    except Exception:
        pass
    print("Preparando o Minimax...", flush=True)
    aquecer()
    porta = 8080
    httpd = None
    for candidata in range(porta, porta + 10):
        try:
            httpd = ThreadingHTTPServer(("127.0.0.1", candidata), Tratador)
            porta = candidata
            break
        except OSError:
            continue
    if httpd is None:
        raise SystemExit("Nenhuma porta livre entre 8080 e 8089.")
    url = f"http://127.0.0.1:{porta}"
    print(f"Jogo da velha em {url}", flush=True)
    if os.environ.get("SEM_NAVEGADOR") != "1":
        webbrowser.open(url)
    try:
        httpd.serve_forever()
    except KeyboardInterrupt:
        print("\nServidor encerrado.")
        httpd.shutdown()


if __name__ == "__main__":
    main()
