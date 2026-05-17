# -*- coding: utf-8 -*-
# Simulador de Escalonamento em Sistemas Operacionais
# Frontend com suporte a time-travel e visualizacao em Gantt

import csv
import os
import copy
from dataclasses import dataclass, asdict
from pathlib import Path
from pprint import pprint
from typing import Any, List, Dict, Tuple, Optional
import http.server
import urllib.parse
import threading
import time

from parser_config import ler_arquivo_configuracao
from simulador import Simulador


@dataclass
class TCB:
    # Task Control Block simplificado
    id: str
    cor: str
    ingresso: int
    duracao: int
    prioridade: int
    lista_eventos: List[str]


# ========== PARSER DE CONFIGURACAO ==========

def limpar_texto(valor: str) -> str:
    return valor.strip()


def normalizar_algoritmo(valor: str) -> str:
    return limpar_texto(valor).lower()


def converter_inteiro(valor: str, nome_campo: str) -> int:
    texto = limpar_texto(valor)
    try:
        return int(texto)
    except ValueError as exc:
        raise ValueError(f"Campo '{nome_campo}' invalido: {valor!r}") from exc


def parse_lista_eventos(valor: str) -> List[str]:
    texto = limpar_texto(valor)
    if not texto:
        return []
    eventos = [limpar_texto(item) for item in texto.split(",")]
    return [item for item in eventos if item]


def ler_configuracao(caminho_arquivo: str = "config.txt") -> dict:
    # Abre arquivo de config e retorna dados pronto
    caminho = Path(caminho_arquivo)
    if not caminho.exists():
        raise FileNotFoundError(f"Arquivo nao encontrado: {caminho.resolve()}")

    tarefas: List[TCB] = []

    with caminho.open(mode="r", encoding="utf-8", newline="") as arquivo:
        leitor = csv.reader(arquivo, delimiter=";")
        linhas = [linha for linha in leitor if any(
            campo.strip() for campo in linha)]

    if not linhas:
        raise ValueError("Arquivo de configuracao vazio.")

    if len(linhas[0]) < 3:
        raise ValueError(
            "Primeira linha deve ter: algoritmo; quantum; qtde_cpus"
        )

    algoritmo, quantum, qtde_cpus = linhas[0][:3]
    configuracao_sistema = {
        "algoritmo": normalizar_algoritmo(algoritmo),
        "quantum": converter_inteiro(quantum, "quantum"),
        "qtde_cpus": converter_inteiro(qtde_cpus, "qtde_cpus"),
    }

    for numero_linha, linha in enumerate(linhas[1:], start=2):
        if len(linha) < 6:
            raise ValueError(
                f"Linha {numero_linha}: faltam campos (id; cor; ingresso; duracao; prioridade; eventos)"
            )

        id_tarefa = limpar_texto(linha[0])
        cor = limpar_texto(linha[1])
        ingresso = converter_inteiro(
            linha[2], f"ingresso linha {numero_linha}")
        duracao = converter_inteiro(linha[3], f"duracao linha {numero_linha}")
        prioridade = converter_inteiro(
            linha[4], f"prioridade linha {numero_linha}")
        lista_eventos = parse_lista_eventos(linha[5])

        tarefas.append(
            TCB(
                id=id_tarefa,
                cor=cor,
                ingresso=ingresso,
                duracao=duracao,
                prioridade=prioridade,
                lista_eventos=lista_eventos,
            )
        )

    return {
        "sistema": configuracao_sistema,
        "tarefas": [asdict(tarefa) for tarefa in tarefas],
    }


def imprimir_resultado(dados: dict) -> None:
    print("=== CONFIGURACAO DO SISTEMA ===")
    pprint(dados["sistema"], sort_dicts=False)
    print()
    print("=== LISTA DE TAREFAS (TCB) ===")
    for indice, tarefa in enumerate(dados["tarefas"], start=1):
        print(f"Tarefa {indice}:")
        pprint(tarefa, sort_dicts=False)
        print()


# ========== GERENCIADOR DE HISTORICO (TIME-TRAVEL) ==========

class GerenciadorHistorico:
    # Gerencia snapshots para voltar/avancar no tempo

    def __init__(self):
        self.snapshots: List[Dict[str, Any]] = []
        self.posicao_atual: int = -1

    def salvar_snapshot(self, estado_cpus: Any, estado_tarefas: Any) -> None:
        # Remove snapshots posteriores se estava voltando
        if self.posicao_atual < len(self.snapshots) - 1:
            self.snapshots = self.snapshots[:self.posicao_atual + 1]

        snapshot = {
            "cpus": copy.deepcopy(estado_cpus),
            "tarefas": copy.deepcopy(estado_tarefas)
        }

        self.snapshots.append(snapshot)
        self.posicao_atual = len(self.snapshots) - 1

    def voltar(self) -> Optional[Tuple[Any, Any]]:
        if self.posicao_atual > 0:
            self.posicao_atual -= 1
            snapshot = self.snapshots[self.posicao_atual]
            return (snapshot["cpus"], snapshot["tarefas"])
        return None

    def avancar(self) -> Optional[Tuple[Any, Any]]:
        if self.posicao_atual < len(self.snapshots) - 1:
            self.posicao_atual += 1
            snapshot = self.snapshots[self.posicao_atual]
            return (snapshot["cpus"], snapshot["tarefas"])
        return None

    def esta_no_presente(self) -> bool:
        return self.posicao_atual == len(self.snapshots) - 1

    def quantidade_snapshots(self) -> int:
        return len(self.snapshots)


# ========== GERADOR DE GANTT EM SVG ==========

class GeradorSVGGantt:
    # Gera grafico Gantt em SVG puro (sem libs externas)

    LARGURA_CELULA = 30
    ALTURA_CELULA = 40
    MARGEM_ESQUERDA = 150
    MARGEM_TOPO = 80
    MARGEM_DIREITA = 20
    MARGEM_RODAPE = 80

    COR_OCIOSA = "#F5F5F5"
    COR_TEXTO = "#000000"

    def __init__(self, historico: Any, lista_tarefas_tcb: List[Any]):
        self.historico = historico
        self.tarefas_tcb = lista_tarefas_tcb

        # Compatibilidade com o backend atual:
        # - pode vir um GerenciadorHistorico
        # - pode vir a lista historico_estados do simulador
        if hasattr(historico, "quantidade_snapshots"):
            self.total_ticks = historico.quantidade_snapshots()
            self.snapshots = historico.snapshots
        else:
            self.snapshots = historico
            self.total_ticks = len(historico)

        self.tarefas_ordenadas = sorted(
            lista_tarefas_tcb,
            key=lambda t: t.id,
            reverse=True
        )
        self.num_tarefas = len(self.tarefas_ordenadas)

        self.mapa_tarefa_indice = {
            tarefa.id: idx for idx, tarefa in enumerate(self.tarefas_ordenadas)
        }

        self.mapa_tarefa_cor = {
            tarefa.id: tarefa.cor for tarefa in self.tarefas_tcb
        }

        # Largura mínima para que a legenda (2 colunas de ~200px cada) não seja cortada
        # MARGEM_ESQUERDA + COL1(200px) + COL2(200px) + margem direita
        largura_minima_legenda = self.MARGEM_ESQUERDA + 200 + 200 + 40
        largura_por_ticks = (
            self.MARGEM_ESQUERDA +
            (self.total_ticks * self.LARGURA_CELULA) +
            self.MARGEM_DIREITA
        )
        self.largura_svg = max(largura_por_ticks, largura_minima_legenda)

        # Descobre nº de CPUs para calcular altura das barras de ociosidade
        try:
            if hasattr(historico, 'snapshots') and historico.snapshots:
                num_cpus_est = len(historico.snapshots[0].get('cpus', []))
            elif isinstance(historico, list) and historico:
                num_cpus_est = len(historico[0].get('cpus', []))
            else:
                num_cpus_est = 2
        except Exception:
            num_cpus_est = 2

        # Cada barra de CPU ocupa 18px + 6px de gap; legenda tem 4 linhas de 20px + cabeçalho
        extra_cpu = 40 + num_cpus_est * (18 + 6)  # título + barras
        extra_legenda = 20 + 4 * 20 + 10              # título + 4 linhas + margem
        self.altura_svg = (
            self.MARGEM_TOPO +
            (self.num_tarefas * self.ALTURA_CELULA) +
            extra_cpu +
            extra_legenda
        )

    def obter_cor_tarefa(self, id_tarefa: str) -> str:
        # Lê a cor direto da TCB, que já deve vir no formato Hexadecimal do txt (ex: FF0000)
        cor_lida = str(self.mapa_tarefa_cor.get(id_tarefa, "000000")).strip()

        # Adiciona o hashtag '#' na frente caso não tenha vindo
        if not cor_lida.startswith("#"):
            return f"#{cor_lida}"
        return cor_lida

    def calcular_posicao_x(self, tick: int) -> float:
        return self.MARGEM_ESQUERDA + (tick * self.LARGURA_CELULA)

    def calcular_posicao_y(self, indice_tarefa: int) -> float:
        return self.MARGEM_TOPO + (indice_tarefa * self.ALTURA_CELULA)

    def gerar_svg_completo(self) -> str:
        linhas = []

        linhas.append('<?xml version="1.0" encoding="UTF-8"?>')
        linhas.append('<svg xmlns="http://www.w3.org/2000/svg"')
        linhas.append(f'     width="{self.largura_svg}"')
        linhas.append(f'     height="{self.altura_svg}"')
        linhas.append(
            f'     viewBox="0 0 {self.largura_svg} {self.altura_svg}">')
        linhas.append('')

        linhas.append('<defs>')
        linhas.append('  <style type="text/css">')
        linhas.append(
            '    .label { font-size: 12px; font-family: Arial, sans-serif; }')
        linhas.append(
            '    .tick { font-size: 10px; font-family: Arial, sans-serif; }')
        linhas.append('    rect { stroke: #333333; stroke-width: 1; }')
        linhas.append('  </style>')
        linhas.append('</defs>')
        linhas.append('')

        linhas.append(
            f'<rect x="0" y="0" width="{self.largura_svg}" height="{self.altura_svg}"')
        linhas.append(
            '      fill="#FFFFFF" stroke="#000000" stroke-width="2"/>')
        linhas.append('')

        # Grid vertical
        for tick in range(self.total_ticks + 1):
            x = self.calcular_posicao_x(tick)
            y_inicio = self.MARGEM_TOPO
            y_fim = self.MARGEM_TOPO + (self.num_tarefas * self.ALTURA_CELULA)
            linhas.append(
                f'<line x1="{x}" y1="{y_inicio}" x2="{x}" y2="{y_fim}" stroke="#CCCCCC" stroke-width="0.5"/>')

        linhas.append('')

        # Grid horizontal
        for idx_tarefa in range(self.num_tarefas + 1):
            y = self.calcular_posicao_y(idx_tarefa)
            x_inicio = self.MARGEM_ESQUERDA
            x_fim = self.MARGEM_ESQUERDA + \
                (self.total_ticks * self.LARGURA_CELULA)
            linhas.append(
                f'<line x1="{x_inicio}" y1="{y}" x2="{x_fim}" y2="{y}" stroke="#CCCCCC" stroke-width="0.5"/>')

        linhas.append('')

        # Blocos de tarefas
        for tick in range(self.total_ticks):
            if tick >= len(self.snapshots):
                break

            snapshot = self.snapshots[tick]

            # 1. ÍCONE DE ALEATORIEDADE/SORTEIO (Req 4.3)
            # Coloca um dado no topo da régua de tempo caso o escalonador tenha feito sorteio
            houve_sorteio = snapshot.get("sorteio", False)
            if houve_sorteio:
                x_sorteio = self.calcular_posicao_x(
                    tick) + (self.LARGURA_CELULA / 2)
                y_sorteio = self.MARGEM_TOPO - 15
                # Dado SVG puro: quadrado com 3 pontos visíveis (sem emoji)
                d = 10  # tamanho do dado
                rx = x_sorteio - d / 2
                ry = y_sorteio - d
                linhas.append(
                    f'<rect x="{rx}" y="{ry}" width="{d}" height="{d}" rx="2" fill="#fff" stroke="#333" stroke-width="1.2"/>')
                # 3 pontos em diagonal (canto sup-esq, centro, canto inf-dir) — face do 3
                for (dpx, dpy) in [(-2.8, -2.8), (0, 0), (2.8, 2.8)]:
                    linhas.append(
                        f'<circle cx="{x_sorteio + dpx}" cy="{y_sorteio - d/2 + dpy}" r="1.2" fill="#333"/>')

            # Mapeia o estado exato das tarefas nesta "foto" do tempo
            tarefas_neste_tick = snapshot.get("tarefas", [])
            mapa_estado_tarefa = {t.id: t for t in tarefas_neste_tick}

            for idx_tarefa, tarefa_base in enumerate(self.tarefas_ordenadas):
                x = self.calcular_posicao_x(tick)
                y = self.calcular_posicao_y(idx_tarefa)
                padding = 2

                tarefa_momento = mapa_estado_tarefa.get(tarefa_base.id)
                if not tarefa_momento:
                    continue

                estado = getattr(tarefa_momento, 'estado', 'Nova')
                cor_base = self.obter_cor_tarefa(tarefa_base.id)

                # ==========================================
                # REQUISITO 2.1: CORES E PROCESSADORES
                # ==========================================
                if estado == "Executando":
                    # Pinta com a cor da tarefa e escreve o ID da CPU dentro (ex: P0)
                    cpu_id = ""
                    for cpu in snapshot.get("cpus", []):
                        if getattr(cpu, 'tarefa_atual', None) and cpu.tarefa_atual.id == tarefa_base.id:
                            cpu_id = str(cpu.id)
                            break

                    linhas.append(
                        f'<rect x="{x + padding}" y="{y + padding}" width="{self.LARGURA_CELULA - 2*padding}" height="{self.ALTURA_CELULA - 2*padding}" fill="{cor_base}"/>')
                    linhas.append(
                        f'<text x="{x + self.LARGURA_CELULA/2}" y="{y + self.ALTURA_CELULA/2 + 4}" font-size="10" font-family="Arial" text-anchor="middle" fill="#FFFFFF" font-weight="bold">P{cpu_id}</text>')

                elif estado == "Suspensa":
                    # Cor preta conforme PDF
                    linhas.append(
                        f'<rect x="{x + padding}" y="{y + padding}" width="{self.LARGURA_CELULA - 2*padding}" height="{self.ALTURA_CELULA - 2*padding}" fill="#000000"/>')

                elif estado == "Pronta":
                    # Ausência de cor (transparente), mas com borda tracejada pra ver que ela está na fila
                    linhas.append(
                        f'<rect x="{x + padding}" y="{y + padding}" width="{self.LARGURA_CELULA - 2*padding}" height="{self.ALTURA_CELULA - 2*padding}" fill="none" stroke="{cor_base}" stroke-width="2" stroke-dasharray="2,2"/>')

                # ==========================================
                # REQUISITO 2.2: ÍCONES DE INGRESSO E CONCLUSÃO
                # ==========================================
                # Ícone de Ingresso (Uma bolinha verde)
                if tick == tarefa_base.ingresso:
                    cx = x + padding + 5
                    cy = y + padding + 5
                    # Círculo branco com borda preta indica ingresso da tarefa
                    linhas.append(
                        f'<circle cx="{cx}" cy="{cy}" r="4" fill="#FFFFFF" stroke="#000" stroke-width="1.2"/>')

                # Ícone de Conclusão (Um X vermelho no exato instante em que ela conclui)
                estado_anterior = "Nova"
                if tick > 0:
                    snap_ant = self.snapshots[tick-1]
                    t_ant = {t.id: t for t in snap_ant.get(
                        "tarefas", [])}.get(tarefa_base.id)
                    if t_ant:
                        estado_anterior = getattr(t_ant, 'estado', 'Nova')

                if estado == "Concluida" and estado_anterior != "Concluida":
                    # X formado pelas duas diagonais do retângulo da célula
                    x1c = x + padding
                    y1c = y + padding
                    x2c = x + self.LARGURA_CELULA - padding
                    y2c = y + self.ALTURA_CELULA - padding
                    linhas.append(
                        f'<line x1="{x1c}" y1="{y1c}" x2="{x2c}" y2="{y2c}" stroke="#CC0000" stroke-width="2.5" stroke-linecap="round"/>')
                    linhas.append(
                        f'<line x1="{x2c}" y1="{y1c}" x2="{x1c}" y2="{y2c}" stroke="#CC0000" stroke-width="2.5" stroke-linecap="round"/>')

        # Labels de tempo
        for tick in range(0, self.total_ticks + 1, max(1, self.total_ticks // 10)):
            x = self.calcular_posicao_x(tick)
            y = self.MARGEM_TOPO - 10
            linhas.append(
                f'<text x="{x}" y="{y}" class="tick" text-anchor="middle">{tick}</text>')

        linhas.append('')

        # Labels de tarefas
        for idx_tarefa, tarefa in enumerate(self.tarefas_ordenadas):
            x = self.MARGEM_ESQUERDA - 10
            y = self.calcular_posicao_y(
                idx_tarefa) + (self.ALTURA_CELULA / 2) + 5
            linhas.append(
                f'<text x="{x}" y="{y}" class="label" text-anchor="end">{tarefa.id}</text>')

        # ==========================================
        # OCIOSIDADE DE CPU: uma barra por CPU abaixo do gantt
        # Cinza = ociosa, verde claro = executando
        # ==========================================
        ALT_BARRA = 18   # altura de cada barra de CPU
        GAP_BARRA = 6    # espaço entre barras
        GAP_TITULO = 20   # espaço entre o gantt e o bloco de CPUs

        # Descobre quais CPUs existem a partir do primeiro snapshot
        cpus_ids = []
        if self.snapshots:
            cpus_ids = [getattr(c, 'id', i)
                        for i, c in enumerate(self.snapshots[0].get('cpus', []))]

        # Linha separadora entre gantt e CPUs
        y_sep = self.MARGEM_TOPO + self.num_tarefas * self.ALTURA_CELULA + 8
        linhas.append(f'<line x1="{self.MARGEM_ESQUERDA}" y1="{y_sep}" '
                      f'x2="{self.calcular_posicao_x(self.total_ticks)}" y2="{y_sep}" '
                      f'stroke="#CCCCCC" stroke-width="1"/>')

        # Título "Ociosidade de CPUs" alinhado à esquerda da margem
        y_titulo_cpu = y_sep + 14
        linhas.append(f'<text x="{self.MARGEM_ESQUERDA}" y="{y_titulo_cpu}" '
                      f'font-size="11" font-family="Arial" font-weight="bold" fill="#555">'
                      f'Ociosidade de CPUs:</text>')

        # Uma barra por CPU
        y_primeira_barra = y_titulo_cpu + 6
        for idx_cpu, cpu_id in enumerate(cpus_ids):
            y_barra = y_primeira_barra + idx_cpu * (ALT_BARRA + GAP_BARRA)

            # Label "P0", "P1" etc. à esquerda da barra, alinhado verticalmente ao centro
            linhas.append(f'<text x="{self.MARGEM_ESQUERDA - 6}" y="{y_barra + ALT_BARRA//2 + 4}" '
                          f'font-size="10" font-family="Arial" text-anchor="end" fill="#333">P{cpu_id}</text>')

            # Pinta tick a tick
            total_ociosa = 0
            for tick in range(self.total_ticks):
                if tick >= len(self.snapshots):
                    break
                cpus_snap = self.snapshots[tick].get('cpus', [])
                executando = any(
                    getattr(c, 'id', None) == cpu_id and getattr(
                        c, 'tarefa_atual', None) is not None
                    for c in cpus_snap
                )
                cor_barra = "#E8F5E9" if executando else "#EF9A9A"
                if not executando:
                    total_ociosa += 1
                xb = self.calcular_posicao_x(tick)
                linhas.append(f'<rect x="{xb}" y="{y_barra}" '
                              f'width="{self.LARGURA_CELULA}" height="{ALT_BARRA}" '
                              f'fill="{cor_barra}" stroke="#BBBBBB" stroke-width="0.5"/>')

            # Contador de ticks ociosa à direita das barras
            x_fim = self.calcular_posicao_x(self.total_ticks) + 6
            linhas.append(f'<text x="{x_fim}" y="{y_barra + ALT_BARRA//2 + 4}" '
                          f'font-size="10" font-family="Arial" fill="#888">'
                          f'{total_ociosa} ticks ociosa</text>')

        # ==========================================
        # LEGENDA — uma linha por item, empilhada verticalmente
        # Posicionada abaixo das barras de CPU
        # ==========================================
        num_cpus = len(cpus_ids) if cpus_ids else 1
        y_leg_base = y_primeira_barra + num_cpus * (ALT_BARRA + GAP_BARRA) + 16
        x_leg = self.MARGEM_ESQUERDA   # alinha com o gantt
        ICON_W = 16   # largura do ícone
        ICON_H = 14   # altura do ícone
        TEXT_OFF = 22   # deslocamento texto → ícone
        LINE_H = 20   # altura de cada linha da legenda
        COL2 = 200  # deslocamento da segunda coluna

        linhas.append(f'<text x="{x_leg}" y="{y_leg_base}" '
                      f'font-size="11" font-family="Arial" font-weight="bold" fill="#333">'
                      f'Legenda:</text>')

        # Linha 1, coluna 1: Executando
        y = y_leg_base + LINE_H
        linhas.append(
            f'<rect x="{x_leg}" y="{y - ICON_H + 2}" width="{ICON_W}" height="{ICON_H}" fill="#4CAF50" stroke="#333" stroke-width="1"/>')
        linhas.append(
            f'<text x="{x_leg + TEXT_OFF}" y="{y}" font-size="10" font-family="Arial" fill="#333">Executando (cor da tarefa)</text>')

        # Linha 1, coluna 2: Pronta
        linhas.append(
            f'<rect x="{x_leg + COL2}" y="{y - ICON_H + 2}" width="{ICON_W}" height="{ICON_H}" fill="none" stroke="#4CAF50" stroke-width="1.5" stroke-dasharray="3,2"/>')
        linhas.append(
            f'<text x="{x_leg + COL2 + TEXT_OFF}" y="{y}" font-size="10" font-family="Arial" fill="#333">Pronta / aguardando CPU</text>')

        # Linha 2, coluna 1: Suspensa
        y += LINE_H
        linhas.append(
            f'<rect x="{x_leg}" y="{y - ICON_H + 2}" width="{ICON_W}" height="{ICON_H}" fill="#000000" stroke="#333" stroke-width="1"/>')
        linhas.append(
            f'<text x="{x_leg + TEXT_OFF}" y="{y}" font-size="10" font-family="Arial" fill="#333">Suspensa (bloqueada)</text>')

        # Linha 2, coluna 2: CPU ociosa
        linhas.append(
            f'<rect x="{x_leg + COL2}" y="{y - ICON_H + 2}" width="{ICON_W}" height="{ICON_H}" fill="#EF9A9A" stroke="#BBBBBB" stroke-width="1"/>')
        linhas.append(
            f'<text x="{x_leg + COL2 + TEXT_OFF}" y="{y}" font-size="10" font-family="Arial" fill="#333">CPU ociosa / desligada</text>')

        # Linha 3, coluna 1: Ingresso
        y += LINE_H
        linhas.append(
            f'<circle cx="{x_leg + ICON_W//2}" cy="{y - ICON_H//2}" r="5" fill="#FFFFFF" stroke="#000" stroke-width="1.2"/>')
        linhas.append(
            f'<text x="{x_leg + TEXT_OFF}" y="{y}" font-size="10" font-family="Arial" fill="#333">Ingresso da tarefa no sistema</text>')

        # Linha 3, coluna 2: Conclusão
        lx1, ly1 = x_leg + COL2,            y - ICON_H + 2
        lx2, ly2 = x_leg + COL2 + ICON_W,   y + 2
        linhas.append(
            f'<line x1="{lx1}" y1="{ly1}" x2="{lx2}" y2="{ly2}" stroke="#CC0000" stroke-width="2" stroke-linecap="round"/>')
        linhas.append(
            f'<line x1="{lx2}" y1="{ly1}" x2="{lx1}" y2="{ly2}" stroke="#CC0000" stroke-width="2" stroke-linecap="round"/>')
        linhas.append(
            f'<text x="{x_leg + COL2 + TEXT_OFF}" y="{y}" font-size="10" font-family="Arial" fill="#333">Conclusão da tarefa</text>')

        # Linha 4, coluna 1: Sorteio (dado SVG — quadrado com 3 pontos em diagonal)
        y += LINE_H
        d = 13
        dx, dy = x_leg, y - ICON_H + 1
        linhas.append(
            f'<rect x="{dx}" y="{dy}" width="{d}" height="{d}" rx="2" fill="#fff" stroke="#333" stroke-width="1.2"/>')
        for (dpx, dpy) in [(-3, -3), (0, 0), (3, 3)]:
            linhas.append(
                f'<circle cx="{dx + d//2 + dpx}" cy="{dy + d//2 + dpy}" r="1.4" fill="#333"/>')
        linhas.append(
            f'<text x="{x_leg + TEXT_OFF}" y="{y}" font-size="10" font-family="Arial" fill="#333">Sorteio por empate no escalonamento</text>')

        linhas.append('')
        linhas.append('</svg>')

        return "\n".join(linhas)


def gerar_svg_gantt(
    historico: GerenciadorHistorico,
    lista_tarefas_tcb: List[Any],
    caminho_saida: str = "gantt.svg"
) -> str:
    # Gera arquivo SVG com grafico de Gantt
    gerador = GeradorSVGGantt(historico, lista_tarefas_tcb)
    svg_content = gerador.gerar_svg_completo()

    with open(caminho_saida, 'w', encoding='utf-8') as arquivo:
        arquivo.write(svg_content)

    print(f"Grafico Gantt gerado: {caminho_saida}")
    return caminho_saida


# ========== INTERFACE DO USUARIO ==========

def exibir_estado_sistema(
    tick_atual: int,
    estado_cpus: Any,
    estado_tarefas: Any,
    historico: GerenciadorHistorico = None,
) -> str:
    # Exibe estado atual e pega comando do usuario

    os.system("cls" if os.name == "nt" else "clear")

    print("=" * 70)
    if historico and historico.esta_no_presente():
        print(f"TICK: {tick_atual} [PRESENTE]")
    else:
        print(f"TICK: {tick_atual} [HISTORICO]")
    print("=" * 70)
    print()

    print("CPUs em execucao:")
    if isinstance(estado_cpus, dict):
        for cpu, tarefa in estado_cpus.items():
            tarefa_exibida = tarefa if tarefa else "Ociosa"
            print(f"  {cpu}: {tarefa_exibida}")
    elif isinstance(estado_cpus, list):
        for indice, tarefa in enumerate(estado_cpus):
            tarefa_exibida = tarefa if tarefa else "Ociosa"
            print(f"  CPU {indice}: {tarefa_exibida}")
    else:
        pprint(estado_cpus, sort_dicts=False)

    print()
    print("Estado das tarefas:")
    if not estado_tarefas:
        print("  (nenhuma)")
    elif isinstance(estado_tarefas, dict):
        for nome, info in estado_tarefas.items():
            print(f"  {nome}: {info}")
    else:
        for tarefa in estado_tarefas:
            if isinstance(tarefa, dict):
                identificador = tarefa.get("id", "?")
                estado = tarefa.get("estado", "?")
                print(f"  {identificador}: {estado}")
            else:
                print(f"  {tarefa}")

    print()
    print("-" * 70)

    if historico:
        print(
            "Comandos: [Enter/'>'] avancar | ['<'] voltar | ['help'] | ['sair']")
    else:
        print("Comandos: [Enter] avancar | ['sair']")

    print("-" * 70)

    while True:
        cmd = input("\n> ").strip()

        if cmd == "" or cmd == ">":
            return "AVANCAR"
        elif cmd == "<" and historico:
            resultado = historico.voltar()
            if resultado is None:
                print("Ja esta no comeco do historico.")
                continue
            return "VOLTAR"
        elif cmd.lower() == "help":
            print("\nComandos disponiveis:")
            print("  [Enter] ou '>'  -> Avancar para proximo tick")
            print("  '<'             -> Voltar um tick")
            print("  'help'          -> Mostra esta mensagem")
            print("  'sair'          -> Encerra simulacao")
            input("\nPressione Enter para continuar...")
            return "CONTINUAR"
        elif cmd.lower() == "sair":
            return "SAIR"
        else:
            print(f"Comando desconhecido: {cmd}")


def imprimir_gantt(motor: Any) -> None:
    print("\nGRAFICO DE GANTT (Linha do Tempo):")

    regua = "Tempo:  "
    for tick in range(motor.relogio + 1):
        regua += f" {tick:02d} "
    print(regua)

    for i in range(len(motor.cpus)):
        linha = f"CPU {i}:  "

        for estado in motor.historico_estados:
            cpu_passado = estado["cpus"][i]
            if cpu_passado.tarefa_atual:
                linha += f"[{cpu_passado.tarefa_atual.id}] "
            else:
                linha += "[--] "

        cpu_agora = motor.cpus[i]
        if cpu_agora.tarefa_atual:
            linha += f"[{cpu_agora.tarefa_atual.id}] "
        else:
            linha += "[--] "

        print(linha)


def imprimir_estado_atual(motor: Any) -> None:
    print(f"\n{'=' * 45}")
    print(f"BASTIDORES - TICK: {motor.relogio}")
    print(f"{'=' * 45}")
    print(f"Fila de Novas: {[t.id for t in motor.fila_novas]}")
    print(f"Fila de Prontas: {[t.id for t in motor.fila_prontas]}")
    print(f"Fila de Concluidas: {[t.id for t in motor.fila_concluidas]}")
    print(
        f"Houve Sorteio? {'SIM' if motor.houve_sorteio_neste_tick else 'NAO'}")
    print("=" * 45)


def modificar_tarefa_manualmente(motor: Any) -> None:
    todas_tarefas = motor.fila_novas + motor.fila_prontas + motor.fila_concluidas
    for cpu in motor.cpus:
        if cpu.tarefa_atual:
            todas_tarefas.append(cpu.tarefa_atual)

    print("\n--- MODIFICAR TAREFA ---")
    print(f"Tarefas no sistema: {[t.id for t in todas_tarefas]}")
    id_alvo = input(
        "Digite o ID da tarefa que deseja alterar (ou ENTER para cancelar): ").strip()

    tarefa_encontrada = next(
        (t for t in todas_tarefas if t.id == id_alvo), None)
    if not tarefa_encontrada:
        print("Tarefa nao encontrada.")
        return

    print(
        f"Editando Tarefa {tarefa_encontrada.id} | Duracao: {tarefa_encontrada.duracao} | Prioridade: {tarefa_encontrada.prioridade} | Estado: {tarefa_encontrada.estado}")
    nova_duracao = input("Nova Duracao (ENTER para manter): ").strip()
    nova_prioridade = input("Nova Prioridade (ENTER para manter): ").strip()
    novo_estado = input(
        "Forcar Estado [Suspensa, Pronta, Nova] (ENTER para manter): ").strip()

    if nova_duracao:
        tarefa_encontrada.duracao = int(nova_duracao)
    if nova_prioridade:
        tarefa_encontrada.prioridade = int(nova_prioridade)
    if novo_estado:
        tarefa_encontrada.estado = novo_estado
        print("Aviso: mover a tarefa manualmente entre filas e complexo. Status alterado na memoria.")
    if novo_estado.lower() == "suspensa":
        if tarefa_encontrada in motor.fila_prontas:
            motor.fila_prontas.remove(tarefa_encontrada)

        for cpu in motor.cpus:
            if cpu.tarefa_atual == tarefa_encontrada:
                cpu.tarefa_atual = None

        tarefa_encontrada.estado = "Suspensa"
        motor.fila_suspensas.append(tarefa_encontrada)
        print(
            f"Tarefa {tarefa_encontrada.id} movida para a Fila de Suspensas.")
    print("Modificacao aplicada!\n")


def executar_passo_a_passo(motor: Any) -> None:
    total_tarefas = len(motor.fila_novas)
    while len(motor.fila_concluidas) < motor.total_tarefas_sistema:
        # Trecho legado preservado por respeito ao codigo antigo:
        # imprimir_gantt(motor)
        # imprimir_estado_atual(motor)
        # comando = input("\n[ENTER] Avancar | [V] Voltar | [M] Modificar Tarefa | [S] Sair: ").strip().upper()
        # if comando == 'S':
        #     break
        # elif comando == 'V':
        #     if motor.retroceder_tick():
        #         print("\nVoltando no tempo...")
        # elif comando == 'M':
        #     modificar_tarefa_manualmente(motor)
        # else:
        #     motor.avancar_tick()

        motor.avancar_tick()

        todas_tarefas = motor.fila_novas + motor.fila_prontas + motor.fila_concluidas
        for cpu in motor.cpus:
            if cpu.tarefa_atual:
                todas_tarefas.append(cpu.tarefa_atual)

        gerar_svg_gantt(motor.historico_estados,
                        todas_tarefas, "gantt_resultado.svg")

        imprimir_gantt(motor)
        imprimir_estado_atual(motor)

        comando = input(
            "\n[ENTER] Avancar | [V] Voltar | [M] Modificar Tarefa | [S] Sair: ").strip().upper()

        if comando == 'S':
            break
        elif comando == 'V':
            if motor.retroceder_tick():
                print("\nVoltando no tempo...")
        elif comando == 'M':
            modificar_tarefa_manualmente(motor)

    print("\n--- FIM DA SIMULACAO PASSO A PASSO ---")
    imprimir_relatorio_ociosidade(motor)


def executar_completo(motor: Any) -> None:
    print("\nRodando Execucao Completa...")
    total_tarefas = len(motor.fila_novas)

    while len(motor.fila_concluidas) < total_tarefas:
        motor.avancar_tick()

        if motor.relogio > 200:
            print("Abordado por limite de seguranca de ticks.")
            break

    todas_tarefas = motor.fila_novas + motor.fila_prontas + motor.fila_concluidas
    for cpu in motor.cpus:
        if cpu.tarefa_atual:
            todas_tarefas.append(cpu.tarefa_atual)
    gerar_svg_gantt(motor.historico_estados,
                    todas_tarefas, "gantt_resultado.svg")

    imprimir_gantt(motor)
    print("\n--- FIM DA SIMULACAO COMPLETA ---")
    imprimir_relatorio_ociosidade(motor)


def imprimir_relatorio_ociosidade(motor: Any) -> None:
    print("\nRELATORIO DE OCIOSIDADE DOS PROCESSADORES:")
    for cpu in motor.cpus:
        print(f"CPU {cpu.id}: Desligada/Ociosa por {cpu.tempo_desligada} ticks.")
    print("=" * 45)


# ========== SERVIDOR WEB (http.server) ==========
def _montar_lista_tarefas_para_grafico(motor: Any) -> List[Any]:
    todas_tarefas = []
    try:
        todas_tarefas = motor.fila_novas + motor.fila_prontas + motor.fila_concluidas
    except Exception:
        todas_tarefas = []

    for cpu in getattr(motor, 'cpus', []):
        if getattr(cpu, 'tarefa_atual', None):
            todas_tarefas.append(cpu.tarefa_atual)

    return todas_tarefas


def _gerar_svg_atual(motor: Any, caminho: str = "gantt_resultado.svg") -> None:
    tarefas = _montar_lista_tarefas_para_grafico(motor)
    try:
        # Log diagnóstico: estado inicial do motor antes de gerar SVG
        try:
            hist_len = len(getattr(motor, 'historico_estados', []))
        except Exception:
            hist_len = getattr(getattr(
                motor, 'historico_estados', None), 'quantidade_snapshots', lambda: 'N/A')()
        print(
            f"[DIAG] Gerando SVG: relogio={getattr(motor, 'relogio', '?')} | historico_len={hist_len} | tarefas_total={len(tarefas)}")

        # motor.historico_estados pode ser uma lista ou GerenciadorHistorico
        gerar_svg_gantt(motor.historico_estados, tarefas, caminho)
    except Exception as exc:
        print("Erro ao gerar SVG no servidor web:", exc)


def make_handler_class(motor: Any, svg_path: str = "gantt_resultado.svg"):
    class SimHandler(http.server.BaseHTTPRequestHandler):
        server_motor = motor
        server_lock = threading.Lock()
        server_mode = 'idle'
        server_worker = None
        server_stop_event = None
        server_arquivo_atual = None  # Nenhum arquivo carregado ainda

        def _redirect_root(self):
            self.send_response(303)
            self.send_header('Location', '/')
            self.end_headers()

        def _read_svg(self) -> str:
            try:
                with open(svg_path, 'r', encoding='utf-8') as f:
                    return f.read()
            except Exception:
                return '<div>SVG nao gerado ainda.</div>'

        def _start_completo(self):
            if type(self).server_worker and type(self).server_worker.is_alive():
                return
            type(self).server_mode = 'completo'
            type(self).server_stop_event = threading.Event()

            def worker():
                motor = type(self).server_motor
                total_tarefas = getattr(motor, 'total_tarefas_sistema', None)
                try:
                    tarefas_all = getattr(motor, 'fila_novas', [
                    ]) + getattr(motor, 'fila_prontas', []) + getattr(motor, 'fila_concluidas', [])
                    max_ingresso = max((getattr(t, 'ingresso', 0)
                                       for t in tarefas_all), default=0)
                    sum_dur = sum((getattr(t, 'duracao', 0)
                                  for t in tarefas_all))
                    expected_end = max_ingresso + sum_dur + 10
                except Exception:
                    expected_end = 10000

                safety = 100000
                last_log_time = -1
                while not type(self).server_stop_event.is_set():
                    with type(self).server_lock:
                        try:
                            if total_tarefas is not None and len(motor.fila_concluidas) >= total_tarefas:
                                break

                            filas_vazias = (len(getattr(motor, 'fila_prontas', [])) == 0 and
                                            len(getattr(motor, 'fila_novas', [])) == 0)
                            cpus_ociosas = all(getattr(
                                cpu, 'tarefa_atual', None) is None for cpu in getattr(motor, 'cpus', []))
                            if filas_vazias and cpus_ociosas:
                                break

                            if getattr(motor, 'relogio', 0) > expected_end:
                                break

                            motor.avancar_tick()
                            _gerar_svg_atual(motor, svg_path)

                            if getattr(motor, 'relogio', 0) % 5 == 0 and getattr(motor, 'relogio', 0) != last_log_time:
                                last_log_time = getattr(motor, 'relogio', 0)
                        except Exception:
                            break
                    time.sleep(0.01)
                    safety -= 1
                    if safety <= 0:
                        break

                try:
                    # Atualiza o SVG de trabalho normal
                    _gerar_svg_atual(motor, svg_path)
                    # Salva também uma cópia permanente do resultado final (Req 2.4)
                    arquivo_final = type(
                        self).server_arquivo_atual or "simulacao"
                    nome_final = arquivo_final.replace(
                        ".txt", "") + "_gantt_final.svg"
                    _gerar_svg_atual(motor, nome_final)
                    print(f"[WEB] SVG final salvo em: {nome_final}")
                except Exception:
                    pass
                type(self).server_mode = 'idle'

            type(self).server_worker = threading.Thread(
                target=worker, daemon=True)
            type(self).server_worker.start()

        def _stop_worker(self):
            if type(self).server_stop_event:
                type(self).server_stop_event.set()
            if type(self).server_worker:
                type(self).server_worker.join(timeout=1)
            type(self).server_worker = None
            type(self).server_stop_event = None
            type(self).server_mode = 'idle'

        def do_GET(self):
            parsed = urllib.parse.urlparse(self.path)
            path = parsed.path

            if path == '/' or path == '':
                with self.server_lock:
                    motor = self.server_motor
                    mode = type(self).server_mode

                # Se ainda não há nenhum cenário carregado, exibe tela de seleção
                if motor is None:
                    arquivos_txt = [f for f in os.listdir(
                        '.') if f.endswith('.txt')]
                    opcoes_html = "".join(
                        [f'<option value="{f}">{f}</option>' for f in arquivos_txt])
                    html = f'''<!doctype html>
<html>
<head>
  <meta charset="utf-8">
  <title>Simulador S.O. - Selecionar Configuração (.txt)</title>
  <style>
    body{{display:flex;flex-direction:column;align-items:center;justify-content:center;min-height:80vh;font-family:Arial,sans-serif;background:#fafafa;color:#333;}}
    .card{{background:#fff;border:1px solid #e0e0e0;padding:40px 60px;border-radius:12px;box-shadow:0 4px 16px rgba(0,0,0,0.08);text-align:center;}}
    h2{{margin-bottom:8px;}}
    p{{color:#666;margin-bottom:24px;}}
    select{{padding:8px 12px;border-radius:6px;border:1px solid #ccc;font-size:15px;min-width:220px;}}
    button{{padding:10px 24px;background:#2e7d32;color:#fff;border:none;border-radius:6px;font-size:15px;font-weight:bold;cursor:pointer;margin-left:8px;}}
    button:hover{{background:#1b5e20;}}
  </style>
</head>
<body>
  <div class="card">
    <h2>ICSO30 - Sistemas Operacionais: Projeto A</h2>
    <h3>Felipe Dias Peixoto e Bruno Seiji Fujihara</h3>  
    <p>Nenhum cenário carregado. Selecione um arquivo <code>.txt</code> para começar.</p>
    <form action="/selecionar_arquivo" method="GET" style="display:flex;gap:8px;justify-content:center;align-items:center;">
      <select name="arquivo">{opcoes_html}</select>
      <button type="submit">Carregar</button>
    </form>
    {'<p style="color:#c00;margin-top:16px;">⚠️ Nenhum arquivo .txt encontrado na pasta do projeto.</p>' if not arquivos_txt else ''}
  </div>
</body>
</html>'''
                    encoded = html.encode('utf-8')
                    self.send_response(200)
                    self.send_header(
                        'Content-Type', 'text/html; charset=utf-8')
                    self.send_header('Content-Length', str(len(encoded)))
                    self.end_headers()
                    self.wfile.write(encoded)
                    return

                with self.server_lock:
                    svg_content = self._read_svg()

                # 1. Escaneia a pasta procurando por arquivos TXT de configuração
                arquivos_txt = [f for f in os.listdir(
                    '.') if f.endswith('.txt')]

                seletor_arquivo_html = ""
                if mode == 'idle':
                    opcoes_html = "".join(
                        [f'<option value="{f}" {"selected" if f == type(self).server_arquivo_atual else ""}>{f}</option>' for f in arquivos_txt])
                    seletor_arquivo_html = f"""
                    <div class="sys-card" style="text-align: center;">
                        <form action="/selecionar_arquivo" method="GET" style="display: flex; gap: 8px; justify-content: center; align-items: center; margin: 0;">
                            <strong>Selecionar Configurações (.txt):</strong>
                            <select name="arquivo" style="padding: 6px; border-radius: 4px; border: 1px solid #ccc; cursor: pointer;">
                                {opcoes_html}
                            </select>
                            <button type="submit" style="padding: 6px 12px; background: #2e7d32; color: white; border: none; border-radius: 4px; cursor: pointer; font-weight: bold;">Carregar Arquivo</button>
                        </form>
                    </div>
                    """
                else:
                    seletor_arquivo_html = f"""
                    <div class="sys-card" style="text-align: center; background-color: #eee;">
                        <strong>Configuração em Execução:</strong> <span class="highlight">{type(self).server_arquivo_atual}</span> (Reinicie para trocar)
                    </div>
                    """

                # 2. Monta o Card de Informações Gerais do Sistema
                info_sistema_html = f"""
                <div class="sys-card">
                    <strong>Algoritmo Ativo:</strong> <span class="highlight">{motor.algoritmo.upper()}</span> | 
                    <strong>Quantum:</strong> <span class="highlight">{motor.quantum}</span> | 
                    <strong>Quantidade de CPUs:</strong> <span class="highlight">{len(motor.cpus)}</span>
                </div>
                """

                # 3. Varre o sistema para pegar o TCB de todas as tarefas e montar a tabela
                todas_tarefas = motor.fila_novas + motor.fila_prontas + \
                    motor.fila_suspensas + motor.fila_concluidas
                for cpu in motor.cpus:
                    if cpu.tarefa_atual and cpu.tarefa_atual not in todas_tarefas:
                        todas_tarefas.append(cpu.tarefa_atual)

                todas_tarefas.sort(key=lambda t: t.id)

                tabela_tcb_html = """
                <table class="tcb-table">
                    <thead>
                        <tr>
                            <th>ID da Tarefa</th>
                            <th>Cor</th>
                            <th>Prioridade</th>
                            <th>Ingresso</th>
                            <th>Duração Total</th>
                            <th>Tempo Executado</th>
                            <th>Estado Atual</th>
                            <th>Ação Manual (Forçar Estado)</th>
                        </tr>
                    </thead>
                    <tbody>
                """

                for t in todas_tarefas:
                    cor_hex = t.cor if t.cor.startswith("#") else f"#{t.cor}"
                    tabela_tcb_html += f"""
                    <tr>
                        <td><strong>{t.id}</strong></td>
                        <td><div style="background-color: {cor_hex}; width: 18px; height: 18px; border-radius: 3px; border: 1px solid #333; margin: auto;"></div></td>
                        <td>{t.prioridade}</td>
                        <td>{t.ingresso}</td>
                        <td>{t.duracao} ticks</td>
                        <td>{t.tempo_executado} ticks</td>
                        <td><span class="badge state-{t.estado.lower()}">{t.estado}</span></td>
                        <td>
                            <form action="/editar" method="GET" style="display: flex; gap: 4px; justify-content: center; margin: 0;">
                                <input type="hidden" name="id" value="{t.id}">
                                <select name="estado" style="padding: 4px; border-radius: 4px; border: 1px solid #ccc;">
                                    <option value="">-- Alterar para --</option>
                                    <option value="Nova">Nova</option>
                                    <option value="Pronta">Pronta</option>
                                    <option value="Suspensa">Suspensa</option>
                                    <option value="Concluida">Concluida</option>
                                </select>
                                <button type="submit" style="padding: 4px 8px; background: #d32f2f; color: white; border: none; border-radius: 4px; cursor: pointer;">Aplicar</button>
                            </form>
                        </td>
                    </tr>
                    """
                tabela_tcb_html += "</tbody></table>"

                if mode == 'idle':
                    controls_html = (
                        '<a class="button" href="/modo/passo">Modo Passo a Passo</a>'
                        '<a class="button" href="/modo/completo">Execucao Completa</a>'
                    )
                    manual_html = ''
                elif mode == 'passo':
                    controls_html = ''
                    manual_html = '<a class="button" href="/voltar">Voltar</a><a class="button" href="/avancar">Avancar</a>'
                else:
                    controls_html = '<a class="button" href="/modo/stop">Parar Execucao</a>'
                    manual_html = ''

                reiniciar_html = '<a class="button" href="/reiniciar">Reiniciar</a>'

                html = f'''<!doctype html>
<html>
<head>
  <meta charset="utf-8">
  <title>Simulador S.O. - Dashboard</title>
  <style>
    body{{display:flex;flex-direction:column;align-items:center;font-family:Arial,sans-serif;margin:20px;background-color:#fafafa;color:#333;}}
    .tick{{font-weight:700;font-size:16px;margin-bottom:12px;background:#333;color:#fff;padding:8px 16px;border-radius:20px;}}
    .sys-card{{background:#fff;border:1px solid #e0e0e0;padding:12px 24px;border-radius:8px;margin-bottom:12px;box-shadow:0 2px 4px rgba(0,0,0,0.05);min-width: 400px;}}
    .highlight{{color:#1976d2;font-weight:bold;}}
    .controls{{margin:12px;}}
    a.button{{display:inline-block;padding:10px 16px;background:#1976d2;color:#fff;text-decoration:none;border-radius:4px;margin:0 6px;font-weight:bold;}}
    .svgwrap{{max-width:95%;overflow:auto;border:1px solid #ddd;padding:16px;background:#fff;border-radius:8px;margin-bottom:24px;box-shadow:0 2px 8px rgba(0,0,0,0.05);}}
    .tcb-table{{width:85%;border-collapse:collapse;background:#fff;border-radius:8px;overflow:hidden;box-shadow:0 2px 8px rgba(0,0,0,0.05);border:1px solid #e0e0e0;margin-top:12px;text-align:center;}}
    .tcb-table th{{background:#424242;color:#fff;padding:12px;font-size:14px;}}
    .tcb-table td{{padding:10px;border-bottom:1px solid #eee;font-size:14px;}}
    .badge{{display:inline-block;padding:4px 8px;border-radius:12px;font-size:12px;font-weight:bold;color:#fff;}}
    .state-nova{{background:#ffb300;color:#000;}}
    .state-pronta{{background:#29b6f6;}}
    .state-executando{{background:#66bb6a;}}
    .state-suspensa{{background:#ef5350;}}
    .state-concluida{{background:#78909c;}}
  </style>
</head>
<body>
  
  {seletor_arquivo_html}
  {info_sistema_html}

    <div class="controls">
      {controls_html}
      {manual_html}
      {reiniciar_html}
  </div>
  
   <div class="tick">Tick Atual: {getattr(self.server_motor, 'relogio', '?')} | Estado: {mode.upper()}</div>
   
  <div class="svgwrap">
    <h3 style="margin-top:0;border-bottom:2px solid #1976d2;padding-bottom:6px;">Gráfico de Gantt da Simulação</h3>
    {svg_content}
  </div>
  

  

 
  {tabela_tcb_html}
</body>
</html>'''

                encoded = html.encode('utf-8')
                self.send_response(200)
                self.send_header('Content-Type', 'text/html; charset=utf-8')
                self.send_header('Content-Length', str(len(encoded)))
                self.end_headers()
                self.wfile.write(encoded)

            elif path == '/selecionar_arquivo':
                with type(self).server_lock:
                    try:
                        query = urllib.parse.parse_qs(parsed.query)
                        arquivo_escolhido = query.get('arquivo', [None])[0]

                        pode_carregar = (type(self).server_motor is None or type(
                            self).server_mode == 'idle')
                        if arquivo_escolhido and pode_carregar:
                            cfg = ler_arquivo_configuracao(arquivo_escolhido)
                            if cfg:
                                type(self).server_motor = Simulador(cfg)
                                type(self).server_arquivo_atual = arquivo_escolhido
                                _gerar_svg_atual(
                                    type(self).server_motor, svg_path)
                                print(
                                    f"[WEB] Novo cenário carregado: {arquivo_escolhido}")
                    except Exception as e:
                        print("[WEB] Erro ao carregar novo arquivo:", e)
                self._redirect_root()

            elif path == '/editar':
                with type(self).server_lock:
                    try:
                        query = urllib.parse.parse_qs(parsed.query)
                        id_tarefa = query.get('id', [None])[0]
                        novo_estado = query.get('estado', [None])[0]

                        if id_tarefa and novo_estado:
                            motor = type(self).server_motor
                            sucesso, mensagem = motor.forcar_mudanca_estado(
                                id_tarefa, novo_estado)
                            print(f"[WEB EDIT] {mensagem}")
                    except Exception as e:
                        print("[WEB EDIT] Erro ao editar tarefa:", e)
                self._redirect_root()

            elif path == '/avancar':
                with type(self).server_lock:
                    try:
                        motor = type(self).server_motor
                        if type(self).server_mode == 'passo':
                            motor.avancar_tick()
                            _gerar_svg_atual(motor, svg_path)
                    except Exception as e:
                        print("[WEB] AVANCAR error:", e)
                self._redirect_root()

            elif path == '/voltar':
                with type(self).server_lock:
                    try:
                        motor = type(self).server_motor
                        if type(self).server_mode == 'passo':
                            motor.retroceder_tick()
                            _gerar_svg_atual(motor, svg_path)
                    except Exception as e:
                        print("[WEB] VOLTAR error:", e)
                self._redirect_root()

            elif path == '/modo/completo':
                try:
                    with type(self).server_lock:
                        self._start_completo()
                    worker = type(self).server_worker
                    if worker:
                        worker.join()
                except Exception as e:
                    print("[WEB] MODO completo error:", e)
                self._redirect_root()

            elif path == '/modo/passo':
                with type(self).server_lock:
                    try:
                        self._stop_worker()
                        type(self).server_mode = 'passo'
                        _gerar_svg_atual(type(self).server_motor, svg_path)
                    except Exception as e:
                        print("[WEB] MODO passo error:", e)
                self._redirect_root()

            elif path == '/modo/stop':
                with type(self).server_lock:
                    try:
                        self._stop_worker()
                    except Exception as e:
                        print("[WEB] MODO stop error:", e)
                self._redirect_root()

            elif path == '/reiniciar':
                with type(self).server_lock:
                    try:
                        self._stop_worker()
                        cfg = None
                        try:
                            # Recarrega usando dinamicamente o arquivo ativo selecionado
                            arq = type(self).server_arquivo_atual
                            cfg = ler_arquivo_configuracao(
                                arq) if arq else None
                        except Exception as e:
                            print("[WEB] REINICIAR config load error:", e)

                        if cfg:
                            type(self).server_motor = Simulador(cfg)
                            _gerar_svg_atual(type(self).server_motor, svg_path)
                            type(self).server_mode = 'idle'
                    except Exception as e:
                        print("[WEB] REINICIAR error:", e)
                self._redirect_root()

            else:
                self.send_response(404)
                self.send_header('Content-Type', 'text/plain; charset=utf-8')
                self.end_headers()
                self.wfile.write(b'404 Not Found')

        def log_message(self, format, *args):
            return

    return SimHandler


def iniciar_servidor_web(motor: Any, host: str = '127.0.0.1', port: int = 8000):
    if motor is not None:
        _gerar_svg_atual(motor, 'gantt_resultado.svg')
    handler = make_handler_class(motor, 'gantt_resultado.svg')
    server_address = (host, port)
    httpd = http.server.HTTPServer(server_address, handler)
    print(f"Servidor web iniciado em http://{host}:{port}/")
    try:
        httpd.serve_forever()
    except KeyboardInterrupt:
        print('\nServidor finalizado pelo usuario (KeyboardInterrupt)')
        httpd.server_close()
