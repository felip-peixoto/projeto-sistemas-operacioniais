# -*- coding: utf-8 -*-

"""
Frontend do simulador de Sistema Operacional.

A ideia deste arquivo e concentrar tres responsabilidades didaticas:
1. Ler a configuracao do arquivo TXT.
2. Guardar o historico da simulacao.
3. Desenhar o grafico SVG e servir a interface web.

O objetivo aqui e manter o codigo simples, legivel e facil de explicar na apresentacao.
"""

# ==========================================
# IMPORTACOES
# ==========================================

import copy
import csv
import os
import threading
import time
import urllib.parse
from dataclasses import dataclass, asdict
from pathlib import Path
from pprint import pprint
from typing import Any, Dict, List, Optional, Tuple

import http.server

from parser_config import ler_arquivo_configuracao
from simulador import Simulador


# ==========================================
# MONTAGEM DOS DADOS DE CONFIGURACAO
# ==========================================

@dataclass
class TCB:
    """Representa uma tarefa no formato simplificado usado pela interface."""

    id: str
    cor: str
    ingresso: int
    duracao: int
    prioridade: int
    lista_eventos: List[str]


# Estes valores sao usados quando o arquivo de entrada nao informa algum campo.
PADRAO_ALGORITMO = "SRTF"
PADRAO_QUANTUM = 2
PADRAO_CPUS = 2
PADRAO_PRIORIDADE = 1
PADRAO_COR = "AAAAAA"


# Aqui limpamos espacos extras para facilitar a leitura do arquivo TXT.
def limpar_texto(valor: str) -> str:
    return valor.strip()


# Aqui deixamos o algoritmo em minusculo padronizado.
def normalizar_algoritmo(valor: str) -> str:
    return limpar_texto(valor).lower()


# Aqui convertemos um texto para inteiro e mostramos um erro simples se der problema.
def converter_inteiro(valor: str, nome_campo: str) -> int:
    texto = limpar_texto(valor)
    try:
        return int(texto)
    except ValueError as erro:
        raise ValueError(f"Campo '{nome_campo}' invalido: {valor!r}") from erro


# Aqui quebramos a lista de eventos separada por virgula.
def parse_lista_eventos(valor: str) -> List[str]:
    texto = limpar_texto(valor)
    if not texto:
        return []

    eventos = []
    partes = texto.split(",")
    for parte in partes:
        item = limpar_texto(parte)
        if item:
            eventos.append(item)

    return eventos


# Aqui lemos o arquivo TXT e montamos a estrutura de configuracao.
def ler_configuracao(caminho_arquivo: str = "config.txt") -> dict:
    caminho = Path(caminho_arquivo)
    if not caminho.exists():
        raise FileNotFoundError(f"Arquivo nao encontrado: {caminho.resolve()}")

    linhas_validas: List[List[str]] = []

    with caminho.open(mode="r", encoding="utf-8", newline="") as arquivo:
        leitor = csv.reader(arquivo, delimiter=";")
        for linha in leitor:
            tem_conteudo = False
            for campo in linha:
                if campo.strip():
                    tem_conteudo = True
                    break
            if tem_conteudo:
                linhas_validas.append(linha)

    if not linhas_validas:
        raise ValueError("Arquivo de configuracao vazio.")

    primeira_linha = linhas_validas[0]
    if len(primeira_linha) < 3:
        raise ValueError("Primeira linha deve ter: algoritmo; quantum; qtde_cpus")

    algoritmo = normalizar_algoritmo(primeira_linha[0])
    quantum = converter_inteiro(primeira_linha[1], "quantum")
    qtde_cpus = converter_inteiro(primeira_linha[2], "qtde_cpus")

    if len(primeira_linha) > 3 and primeira_linha[3].strip():
        alpha = converter_inteiro(primeira_linha[3], "alpha")
    else:
        alpha = None

    tarefas: List[TCB] = []

    for numero_linha, linha in enumerate(linhas_validas[1:], start=2):
        if len(linha) < 6:
            raise ValueError(
                f"Linha {numero_linha}: faltam campos (id; cor; ingresso; duracao; prioridade; eventos)"
            )

        id_tarefa = limpar_texto(linha[0])
        cor = limpar_texto(linha[1])
        ingresso = converter_inteiro(linha[2], f"ingresso linha {numero_linha}")
        duracao = converter_inteiro(linha[3], f"duracao linha {numero_linha}")
        prioridade = converter_inteiro(linha[4], f"prioridade linha {numero_linha}")
        lista_eventos = parse_lista_eventos(linha[5])

        tarefa = TCB(
            id=id_tarefa,
            cor=cor,
            ingresso=ingresso,
            duracao=duracao,
            prioridade=prioridade,
            lista_eventos=lista_eventos,
        )
        tarefas.append(tarefa)

    return {
        "algoritmo": algoritmo,
        "quantum": quantum,
        "cpus": qtde_cpus,
        "alpha": alpha,
        "tarefas": tarefas,
    }


# Aqui mostramos o resultado do parser de forma simples no terminal.
def imprimir_resultado(dados: dict) -> None:
    print("=== CONFIGURACAO DO SISTEMA ===")
    pprint(dados["sistema"], sort_dicts=False)
    print()
    print("=== LISTA DE TAREFAS (TCB) ===")
    for indice, tarefa in enumerate(dados["tarefas"], start=1):
        print(f"Tarefa {indice}:")
        pprint(tarefa, sort_dicts=False)
        print()


# ==========================================
# MODO DE HISTORICO DA SIMULACAO
# ==========================================

class GerenciadorHistorico:
    """Guarda snapshots para permitir voltar e avancar no tempo."""

    def __init__(self):
        self.snapshots: List[Dict[str, Any]] = []
        self.posicao_atual = -1

    # Aqui salvamos uma copia profunda do estado atual.
    def salvar_snapshot(self, estado_cpus: Any, estado_tarefas: Any) -> None:
        if self.posicao_atual < len(self.snapshots) - 1:
            self.snapshots = self.snapshots[: self.posicao_atual + 1]

        snapshot = {
            "cpus": copy.deepcopy(estado_cpus),
            "tarefas": copy.deepcopy(estado_tarefas),
        }
        self.snapshots.append(snapshot)
        self.posicao_atual = len(self.snapshots) - 1

    # Aqui voltamos um passo no historico, se existir.
    def voltar(self) -> Optional[Tuple[Any, Any]]:
        if self.posicao_atual > 0:
            self.posicao_atual -= 1
            snapshot = self.snapshots[self.posicao_atual]
            return snapshot["cpus"], snapshot["tarefas"]
        return None

    # Aqui avancamos um passo no historico, se existir.
    def avancar(self) -> Optional[Tuple[Any, Any]]:
        if self.posicao_atual < len(self.snapshots) - 1:
            self.posicao_atual += 1
            snapshot = self.snapshots[self.posicao_atual]
            return snapshot["cpus"], snapshot["tarefas"]
        return None

    def esta_no_presente(self) -> bool:
        return self.posicao_atual == len(self.snapshots) - 1

    def quantidade_snapshots(self) -> int:
        return len(self.snapshots)


# ==========================================
# MODO DE GERACAO DO SVG
# ==========================================

class GeradorSVGGantt:
    """Desenha o grafico Gantt em SVG puro, sem bibliotecas externas."""

    LARGURA_CELULA = 30
    ALTURA_CELULA = 40
    MARGEM_ESQUERDA = 150
    MARGEM_TOPO = 80
    MARGEM_DIREITA = 20
    MARGEM_RODAPE = 80

    def __init__(self, historico: Any, lista_tarefas_tcb: List[Any]):
        self.historico = historico
        self.tarefas_tcb = lista_tarefas_tcb

        # Aqui descobrimos quantos ticks existem no historico.
        if hasattr(historico, "quantidade_snapshots"):
            self.total_ticks = historico.quantidade_snapshots()
            self.snapshots = historico.snapshots
        else:
            self.snapshots = historico
            self.total_ticks = len(historico)

        # Aqui ordenamos as tarefas por id para desenhar de forma previsivel.
        self.tarefas_ordenadas = sorted(
            lista_tarefas_tcb,
            key=lambda tarefa: tarefa.id,
            reverse=True,
        )
        self.num_tarefas = len(self.tarefas_ordenadas)

        # Aqui criamos um mapa para achar a cor de cada tarefa rapidamente.
        self.mapa_tarefa_cor: Dict[str, str] = {}
        for tarefa in self.tarefas_tcb:
            self.mapa_tarefa_cor[tarefa.id] = tarefa.cor

        largura_minima_legenda = self.MARGEM_ESQUERDA + 200 + 200 + 40
        largura_por_ticks = (
            self.MARGEM_ESQUERDA
            + (self.total_ticks * self.LARGURA_CELULA)
            + self.MARGEM_DIREITA
            + 120
        )
        self.largura_svg = max(largura_por_ticks, largura_minima_legenda)

        # Aqui calculamos a altura final com base na quantidade de CPUs.
        try:
            if hasattr(historico, "snapshots") and historico.snapshots:
                num_cpus_est = len(historico.snapshots[0].get("cpus", []))
            elif isinstance(historico, list) and historico:
                num_cpus_est = len(historico[0].get("cpus", []))
            else:
                num_cpus_est = 2
        except Exception:
            num_cpus_est = 2

        extra_cpu = 40 + num_cpus_est * (18 + 6)
        extra_legenda = 20 + 4 * 20 + 10
        self.altura_svg = (
            self.MARGEM_TOPO
            + (self.num_tarefas * self.ALTURA_CELULA)
            + extra_cpu
            + extra_legenda
        )

    # Aqui traduzimos a cor do arquivo para uma cor que o SVG entende.
    def obter_cor_tarefa(self, id_tarefa: str) -> str:
        cor_lida = str(self.mapa_tarefa_cor.get(id_tarefa, PADRAO_COR)).strip()
        cor_minuscula = cor_lida.lower()

        mapa_nomes = {
            "vermelho": "#ff4d4d",
            "azul": "#4d79ff",
            "verde": "#39b54a",
            "cinza": "#aaaaaa",
        }

        if cor_minuscula in mapa_nomes:
            return mapa_nomes[cor_minuscula]

        if cor_lida.startswith("#"):
            return cor_lida

        if len(cor_lida) == 6:
            return f"#{cor_lida}"

        return "#AAAAAA"

    # Aqui calculamos a posicao horizontal de um tick.
    def calcular_posicao_x(self, tick: int) -> float:
        return self.MARGEM_ESQUERDA + (tick * self.LARGURA_CELULA)

    # Aqui calculamos a posicao vertical de uma tarefa.
    def calcular_posicao_y(self, indice_tarefa: int) -> float:
        return self.MARGEM_TOPO + (indice_tarefa * self.ALTURA_CELULA)

    # Aqui montamos todo o texto SVG linha por linha.
    def gerar_svg_completo(self) -> str:
        linhas: List[str] = []

        linhas.append('<?xml version="1.0" encoding="UTF-8"?>')
        linhas.append('<svg xmlns="http://www.w3.org/2000/svg"')
        linhas.append(f'     width="{self.largura_svg}"')
        linhas.append(f'     height="{self.altura_svg}"')
        linhas.append(f'     viewBox="0 0 {self.largura_svg} {self.altura_svg}">')
        linhas.append('')

        linhas.append('<defs>')
        linhas.append('  <style type="text/css">')
        linhas.append('    .label { font-size: 12px; font-family: Arial, sans-serif; }')
        linhas.append('    .tick { font-size: 10px; font-family: Arial, sans-serif; }')
        linhas.append('    rect { stroke: #333333; stroke-width: 1; }')
        linhas.append('  </style>')
        linhas.append('</defs>')
        linhas.append('')

        linhas.append(f'<rect x="0" y="0" width="{self.largura_svg}" height="{self.altura_svg}"')
        linhas.append('      fill="#FFFFFF" stroke="#000000" stroke-width="2"/>')
        linhas.append('')

        # Aqui desenhamos as linhas verticais da grade.
        for tick in range(self.total_ticks + 1):
            x = self.calcular_posicao_x(tick)
            y_inicio = self.MARGEM_TOPO
            y_fim = self.MARGEM_TOPO + (self.num_tarefas * self.ALTURA_CELULA)
            linhas.append(
                f'<line x1="{x}" y1="{y_inicio}" x2="{x}" y2="{y_fim}" stroke="#CCCCCC" stroke-width="0.5"/>'
            )

        linhas.append('')

        # Aqui desenhamos as linhas horizontais da grade.
        for indice_tarefa in range(self.num_tarefas + 1):
            y = self.calcular_posicao_y(indice_tarefa)
            x_inicio = self.MARGEM_ESQUERDA
            x_fim = self.MARGEM_ESQUERDA + (self.total_ticks * self.LARGURA_CELULA)
            linhas.append(
                f'<line x1="{x_inicio}" y1="{y}" x2="{x_fim}" y2="{y}" stroke="#CCCCCC" stroke-width="0.5"/>'
            )

        linhas.append('')

        # Aqui desenhamos cada instante da simulacao.
        for tick in range(self.total_ticks):
            if tick >= len(self.snapshots):
                break

            snapshot_atual = self.snapshots[tick]

            # Quando o escalonador faz sorteio, mostramos um simbolo simples.
            houve_sorteio = snapshot_atual.get("sorteio", False)
            if houve_sorteio:
                x_sorteio = self.calcular_posicao_x(tick) + (self.LARGURA_CELULA / 2)
                y_sorteio = self.MARGEM_TOPO - 15
                tamanho = 10
                linhas.append(
                    f'<rect x="{x_sorteio - (tamanho / 2)}" y="{y_sorteio - tamanho}" width="{tamanho}" height="{tamanho}" rx="2" fill="#FFFFFF" stroke="#333333" stroke-width="1"/>'
                )
                linhas.append(
                    f'<circle cx="{x_sorteio - 2.5}" cy="{y_sorteio - 7}" r="1.2" fill="#333333"/>'
                )
                linhas.append(
                    f'<circle cx="{x_sorteio}" cy="{y_sorteio - 5}" r="1.2" fill="#333333"/>'
                )
                linhas.append(
                    f'<circle cx="{x_sorteio + 2.5}" cy="{y_sorteio - 3}" r="1.2" fill="#333333"/>'
                )

            tarefas_neste_tick = snapshot_atual.get("tarefas", [])
            mapa_estado_tarefa: Dict[str, Any] = {}
            for tarefa_snapshot in tarefas_neste_tick:
                mapa_estado_tarefa[tarefa_snapshot.id] = tarefa_snapshot

            for indice_tarefa, tarefa_base in enumerate(self.tarefas_ordenadas):
                tarefa_momento = mapa_estado_tarefa.get(tarefa_base.id)
                if not tarefa_momento:
                    continue

                x = self.calcular_posicao_x(tick)
                y = self.calcular_posicao_y(indice_tarefa)
                padding = 2
                estado = getattr(tarefa_momento, 'estado', 'Nova')
                cor_base = self.obter_cor_tarefa(tarefa_base.id)

                # Aqui pintamos o estado de cada tarefa de forma simples.
                if estado == "Executando":
                    cpu_id = ""
                    for cpu in snapshot_atual.get("cpus", []):
                        if getattr(cpu, 'tarefa_atual', None) and cpu.tarefa_atual.id == tarefa_base.id:
                            cpu_id = str(cpu.id)
                            break

                    linhas.append(
                        f'<rect x="{x + padding}" y="{y + padding}" width="{self.LARGURA_CELULA - 2 * padding}" height="{self.ALTURA_CELULA - 2 * padding}" fill="{cor_base}"/>'
                    )
                    linhas.append(
                        f'<text x="{x + (self.LARGURA_CELULA / 2)}" y="{y + (self.ALTURA_CELULA / 2) + 4}" font-size="10" font-family="Arial" text-anchor="middle" fill="#FFFFFF" font-weight="bold">P{cpu_id}</text>'
                    )
                elif estado == "Suspensa":
                    linhas.append(
                        f'<rect x="{x + padding}" y="{y + padding}" width="{self.LARGURA_CELULA - 2 * padding}" height="{self.ALTURA_CELULA - 2 * padding}" fill="#000000"/>'
                    )
                elif estado == "Pronta":
                    linhas.append(
                        f'<rect x="{x + padding}" y="{y + padding}" width="{self.LARGURA_CELULA - 2 * padding}" height="{self.ALTURA_CELULA - 2 * padding}" fill="none" stroke="{cor_base}" stroke-width="2" stroke-dasharray="2,2"/>'
                    )

                # Aqui marcamos o momento de ingresso da tarefa.
                if tick == tarefa_base.ingresso:
                    cx = x + padding + 5
                    cy = y + padding + 5
                    linhas.append(
                        f'<circle cx="{cx}" cy="{cy}" r="4" fill="#00FF00" stroke="#000000"/>'
                    )

                # Aqui marcamos a conclusao da tarefa com um X simples.
                estado_anterior = "Nova"
                if tick > 0:
                    snapshot_anterior = self.snapshots[tick - 1]
                    tarefas_anteriores = snapshot_anterior.get("tarefas", [])
                    for tarefa_anterior in tarefas_anteriores:
                        if tarefa_anterior.id == tarefa_base.id:
                            estado_anterior = getattr(tarefa_anterior, 'estado', 'Nova')
                            break

                if estado == "Concluida" and estado_anterior != "Concluida":
                    x1 = x + padding
                    y1 = y + padding
                    x2 = x + self.LARGURA_CELULA - padding
                    y2 = y + self.ALTURA_CELULA - padding
                    linhas.append(
                        f'<line x1="{x1}" y1="{y1}" x2="{x2}" y2="{y2}" stroke="#CC0000" stroke-width="2.5" stroke-linecap="round"/>'
                    )
                    linhas.append(
                        f'<line x1="{x2}" y1="{y1}" x2="{x1}" y2="{y2}" stroke="#CC0000" stroke-width="2.5" stroke-linecap="round"/>'
                    )

        # Aqui colocamos os numeros do tempo no topo.
        passo_rotulo = max(1, self.total_ticks // 10)
        for tick in range(0, self.total_ticks + 1, passo_rotulo):
            x = self.calcular_posicao_x(tick)
            y = self.MARGEM_TOPO - 10
            linhas.append(
                f'<text x="{x}" y="{y}" class="tick" text-anchor="middle">{tick}</text>'
            )

        linhas.append('')

        # Aqui colocamos os nomes das tarefas na lateral esquerda.
        for indice_tarefa, tarefa in enumerate(self.tarefas_ordenadas):
            x = self.MARGEM_ESQUERDA - 10
            y = self.calcular_posicao_y(indice_tarefa) + (self.ALTURA_CELULA / 2) + 5
            linhas.append(
                f'<text x="{x}" y="{y}" class="label" text-anchor="end">{tarefa.id}</text>'
            )

        # Aqui desenhamos a parte de uso ocioso das CPUs.
        alt_barra = 18
        gap_barra = 6
        y_sep = self.MARGEM_TOPO + self.num_tarefas * self.ALTURA_CELULA + 8
        linhas.append(
            f'<line x1="{self.MARGEM_ESQUERDA}" y1="{y_sep}" x2="{self.calcular_posicao_x(self.total_ticks)}" y2="{y_sep}" stroke="#CCCCCC" stroke-width="1"/>'
        )

        y_titulo_cpu = y_sep + 14
        linhas.append(
            f'<text x="{self.MARGEM_ESQUERDA}" y="{y_titulo_cpu}" font-size="11" font-family="Arial" font-weight="bold" fill="#555555">Ociosidade de CPUs:</text>'
        )

        y_primeira_barra = y_titulo_cpu + 6
        if self.snapshots:
            cpu_base = self.snapshots[0].get('cpus', [])
        else:
            cpu_base = []

        identificadores_cpu = []
        for indice_cpu, cpu in enumerate(cpu_base):
            identificadores_cpu.append(getattr(cpu, 'id', indice_cpu))

        for indice_cpu, cpu_id in enumerate(identificadores_cpu):
            y_barra = y_primeira_barra + indice_cpu * (alt_barra + gap_barra)
            linhas.append(
                f'<text x="{self.MARGEM_ESQUERDA - 6}" y="{y_barra + (alt_barra // 2) + 4}" font-size="10" font-family="Arial" text-anchor="end" fill="#333333">CPU {cpu_id}</text>'
            )

            total_ociosa = 0
            for tick in range(self.total_ticks):
                if tick >= len(self.snapshots):
                    break
                cpus_snapshot = self.snapshots[tick].get('cpus', [])
                esta_executando = False
                for cpu_snapshot in cpus_snapshot:
                    if getattr(cpu_snapshot, 'id', None) == cpu_id and getattr(cpu_snapshot, 'tarefa_atual', None) is not None:
                        esta_executando = True
                        break

                if not esta_executando:
                    total_ociosa += 1

                x_barra = self.calcular_posicao_x(tick)
                cor_barra = '#E8F5E9' if esta_executando else '#EF9A9A'
                linhas.append(
                    f'<rect x="{x_barra + 2}" y="{y_barra}" width="{self.LARGURA_CELULA - 4}" height="{alt_barra}" fill="{cor_barra}" stroke="#BBBBBB" stroke-width="0.5"/>'
                )

            x_fim = self.calcular_posicao_x(self.total_ticks) + 6
            linhas.append(
                f'<text x="{x_fim}" y="{y_barra + (alt_barra // 2) + 4}" font-size="10" font-family="Arial" fill="#888888">{total_ociosa} ticks ociosa</text>'
            )

        # Aqui criamos a legenda de forma simples e direta.
        num_cpus = len(identificadores_cpu) if identificadores_cpu else 1
        y_leg_base = y_primeira_barra + num_cpus * (alt_barra + gap_barra) + 16
        x_leg = self.MARGEM_ESQUERDA
        icon_w = 16
        icon_h = 14
        text_off = 22
        line_h = 20
        col2 = 200

        linhas.append(
            f'<text x="{x_leg}" y="{y_leg_base}" font-size="11" font-family="Arial" font-weight="bold" fill="#333333">Legenda:</text>'
        )

        y_linha = y_leg_base + line_h
        linhas.append(
            f'<rect x="{x_leg}" y="{y_linha - icon_h + 2}" width="{icon_w}" height="{icon_h}" fill="#4CAF50" stroke="#333333" stroke-width="1"/>'
        )
        linhas.append(
            f'<text x="{x_leg + text_off}" y="{y_linha}" font-size="10" font-family="Arial" fill="#333333">Executando</text>'
        )

        linhas.append(
            f'<rect x="{x_leg + col2}" y="{y_linha - icon_h + 2}" width="{icon_w}" height="{icon_h}" fill="none" stroke="#4CAF50" stroke-width="1.5" stroke-dasharray="3,2"/>'
        )
        linhas.append(
            f'<text x="{x_leg + col2 + text_off}" y="{y_linha}" font-size="10" font-family="Arial" fill="#333333">Pronta</text>'
        )

        y_linha += line_h
        linhas.append(
            f'<rect x="{x_leg}" y="{y_linha - icon_h + 2}" width="{icon_w}" height="{icon_h}" fill="#000000" stroke="#333333" stroke-width="1"/>'
        )
        linhas.append(
            f'<text x="{x_leg + text_off}" y="{y_linha}" font-size="10" font-family="Arial" fill="#333333">Suspensa</text>'
        )

        linhas.append(
            f'<rect x="{x_leg + col2}" y="{y_linha - icon_h + 2}" width="{icon_w}" height="{icon_h}" fill="#EF9A9A" stroke="#BBBBBB" stroke-width="1"/>'
        )
        linhas.append(
            f'<text x="{x_leg + col2 + text_off}" y="{y_linha}" font-size="10" font-family="Arial" fill="#333333">CPU ociosa</text>'
        )

        y_linha += line_h
        linhas.append(
            f'<circle cx="{x_leg + (icon_w // 2)}" cy="{y_linha - (icon_h // 2)}" r="5" fill="#FFFFFF" stroke="#000000" stroke-width="1.2"/>'
        )
        linhas.append(
            f'<text x="{x_leg + text_off}" y="{y_linha}" font-size="10" font-family="Arial" fill="#333333">Ingresso</text>'
        )

        x1 = x_leg + col2
        y1 = y_linha - icon_h + 2
        x2 = x1 + icon_w
        y2 = y1 + icon_h
        linhas.append(
            f'<line x1="{x1}" y1="{y1}" x2="{x2}" y2="{y2}" stroke="#CC0000" stroke-width="2" stroke-linecap="round"/>'
        )
        linhas.append(
            f'<line x1="{x2}" y1="{y1}" x2="{x1}" y2="{y2}" stroke="#CC0000" stroke-width="2" stroke-linecap="round"/>'
        )
        linhas.append(
            f'<text x="{x1 + text_off}" y="{y_linha}" font-size="10" font-family="Arial" fill="#333333">Conclusao</text>'
        )

        linhas.append('</svg>')
        return "\n".join(linhas)


# Aqui criamos o arquivo SVG e gravamos em disco.
def gerar_svg_gantt(
    historico: GerenciadorHistorico,
    lista_tarefas_tcb: List[Any],
    caminho_saida: str = "gantt.svg",
) -> str:
    gerador = GeradorSVGGantt(historico, lista_tarefas_tcb)
    svg_content = gerador.gerar_svg_completo()

    with open(caminho_saida, 'w', encoding='utf-8') as arquivo:
        arquivo.write(svg_content)

    print(f"Grafico Gantt gerado: {caminho_saida}")
    return caminho_saida


# ==========================================
# MODO TERMINAL (CLI)
# ==========================================

# Aqui mostramos o estado atual e pedimos um comando ao usuario.
def exibir_estado_sistema(
    tick_atual: int,
    estado_cpus: Any,
    estado_tarefas: Any,
    historico: GerenciadorHistorico = None,
) -> str:
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
        for cpu_nome, tarefa in estado_cpus.items():
            if tarefa:
                tarefa_exibida = tarefa
            else:
                tarefa_exibida = "Ociosa"
            print(f"  {cpu_nome}: {tarefa_exibida}")
    elif isinstance(estado_cpus, list):
        for indice_cpu, tarefa in enumerate(estado_cpus):
            if tarefa:
                tarefa_exibida = tarefa
            else:
                tarefa_exibida = "Ociosa"
            print(f"  CPU {indice_cpu}: {tarefa_exibida}")
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
        print("Comandos: [Enter/'>'] avancar | ['<'] voltar | ['help'] | ['sair']")
    else:
        print("Comandos: [Enter] avancar | ['sair']")

    print("-" * 70)

    while True:
        comando = input("\n> ").strip()

        if comando == "" or comando == ">":
            return "AVANCAR"
        if comando == "<" and historico:
            resultado = historico.voltar()
            if resultado is None:
                print("Ja esta no comeco do historico.")
                continue
            return "VOLTAR"
        if comando.lower() == "help":
            print("\nComandos disponiveis:")
            print("  [Enter] ou '>'  -> Avancar para proximo tick")
            print("  '<'             -> Voltar um tick")
            print("  'help'          -> Mostra esta mensagem")
            print("  'sair'          -> Encerra simulacao")
            input("\nPressione Enter para continuar...")
            return "CONTINUAR"
        if comando.lower() == "sair":
            return "SAIR"

        print(f"Comando desconhecido: {comando}")


# Aqui imprimimos a linha do tempo simples no terminal.
def imprimir_gantt(motor: Any) -> None:
    print("\nGRAFICO DE GANTT (Linha do Tempo):")

    regua = "Tempo:  "
    for tick in range(motor.relogio + 1):
        regua += f" {tick:02d} "
    print(regua)

    for indice_cpu in range(len(motor.cpus)):
        linha = f"CPU {indice_cpu}:  "

        for estado in motor.historico_estados:
            cpu_passado = estado["cpus"][indice_cpu]
            if cpu_passado.tarefa_atual:
                linha += f"[{cpu_passado.tarefa_atual.id}] "
            else:
                linha += "[--] "

        cpu_agora = motor.cpus[indice_cpu]
        if cpu_agora.tarefa_atual:
            linha += f"[{cpu_agora.tarefa_atual.id}] "
        else:
            linha += "[--] "

        print(linha)


# Aqui resumimos o estado atual do simulador.
def imprimir_estado_atual(motor: Any) -> None:
    print(f"\n{'=' * 45}")
    print(f"BASTIDORES - TICK: {motor.relogio}")
    print(f"{'=' * 45}")
    print(f"Fila de Novas: {[t.id for t in motor.fila_novas]}")
    print(f"Fila de Prontas: {[t.id for t in motor.fila_prontas]}")
    print(f"Fila de Concluidas: {[t.id for t in motor.fila_concluidas]}")
    print(f"Houve Sorteio? {'SIM' if motor.houve_sorteio_neste_tick else 'NAO'}")
    print("=" * 45)


# Aqui permitimos alterar uma tarefa manualmente pelo terminal.
def modificar_tarefa_manualmente(motor: Any) -> None:
    todas_tarefas = []
    for tarefa in motor.fila_novas:
        todas_tarefas.append(tarefa)
    for tarefa in motor.fila_prontas:
        todas_tarefas.append(tarefa)
    for tarefa in motor.fila_concluidas:
        todas_tarefas.append(tarefa)
    for cpu in motor.cpus:
        if cpu.tarefa_atual:
            todas_tarefas.append(cpu.tarefa_atual)

    print("\n--- MODIFICAR TAREFA ---")
    ids = []
    for tarefa in todas_tarefas:
        ids.append(tarefa.id)
    print(f"Tarefas no sistema: {ids}")

    id_alvo = input("Digite o ID da tarefa que deseja alterar (ou ENTER para cancelar): ").strip()

    tarefa_encontrada = None
    for tarefa in todas_tarefas:
        if tarefa.id == id_alvo:
            tarefa_encontrada = tarefa
            break

    if not tarefa_encontrada:
        print("Tarefa nao encontrada.")
        return

    print(
        f"Editando Tarefa {tarefa_encontrada.id} | Duracao: {tarefa_encontrada.duracao} | Prioridade: {tarefa_encontrada.prioridade} | Estado: {tarefa_encontrada.estado}"
    )
    nova_duracao = input("Nova Duracao (ENTER para manter): ").strip()
    nova_prioridade = input("Nova Prioridade (ENTER para manter): ").strip()
    novo_estado = input("Forcar Estado [Suspensa, Pronta, Nova] (ENTER para manter): ").strip()

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
        print(f"Tarefa {tarefa_encontrada.id} movida para a Fila de Suspensas.")

    print("Modificacao aplicada!\n")


# Aqui avançamos passo a passo e atualizamos o SVG a cada tick.
def executar_passo_a_passo(motor: Any) -> None:
    while len(motor.fila_concluidas) < motor.total_tarefas_sistema:
        motor.avancar_tick()

        todas_tarefas = []
        for tarefa in motor.fila_novas:
            todas_tarefas.append(tarefa)
        for tarefa in motor.fila_prontas:
            todas_tarefas.append(tarefa)
        for tarefa in motor.fila_concluidas:
            todas_tarefas.append(tarefa)
        for tarefa in motor.fila_suspensas:
            todas_tarefas.append(tarefa)
        for cpu in motor.cpus:
            if cpu.tarefa_atual:
                todas_tarefas.append(cpu.tarefa_atual)

        gerar_svg_gantt(motor.historico_estados, todas_tarefas, "gantt_resultado.svg")

        imprimir_gantt(motor)
        imprimir_estado_atual(motor)

        comando = input("\n[ENTER] Avancar | [V] Voltar | [M] Modificar Tarefa | [S] Sair: ").strip().upper()

        if comando == "S":
            break
        if comando == "V":
            if motor.retroceder_tick():
                print("\nVoltando no tempo...")
        elif comando == "M":
            modificar_tarefa_manualmente(motor)

    print("\n--- FIM DA SIMULACAO PASSO A PASSO ---")
    imprimir_relatorio_ociosidade(motor)


# Aqui rodamos a simulacao ate o fim, sem pausas manuais.
def executar_completo(motor: Any) -> None:
    print("\nRodando Execucao Completa...")
    total_tarefas = len(motor.fila_novas)

    while len(motor.fila_concluidas) < total_tarefas:
        motor.avancar_tick()
        if motor.relogio > 200:
            print("Abordado por limite de seguranca de ticks.")
            break

    todas_tarefas = []
    for tarefa in motor.fila_novas:
        todas_tarefas.append(tarefa)
    for tarefa in motor.fila_prontas:
        todas_tarefas.append(tarefa)
    for tarefa in motor.fila_concluidas:
        todas_tarefas.append(tarefa)
    for tarefa in motor.fila_suspensas:
        todas_tarefas.append(tarefa)
    for cpu in motor.cpus:
        if cpu.tarefa_atual:
            todas_tarefas.append(cpu.tarefa_atual)

    gerar_svg_gantt(motor.historico_estados, todas_tarefas, "gantt_resultado.svg")

    imprimir_gantt(motor)
    print("\n--- FIM DA SIMULACAO COMPLETA ---")
    imprimir_relatorio_ociosidade(motor)


# Aqui mostramos quanto tempo cada CPU ficou ociosa.
def imprimir_relatorio_ociosidade(motor: Any) -> None:
    print("\nRELATORIO DE OCIOSIDADE DOS PROCESSADORES:")
    for cpu in motor.cpus:
        print(f"CPU {cpu.id}: Desligada/Ociosa por {cpu.tempo_desligada} ticks.")
    print("=" * 45)


# ==========================================
# MODO WEB
# ==========================================

# Aqui juntamos todas as tarefas para desenhar o grafico.
def _montar_lista_tarefas_para_grafico(motor: Any) -> List[Any]:
    todas_tarefas = []

    try:
        for tarefa in motor.fila_novas:
            todas_tarefas.append(tarefa)
        for tarefa in motor.fila_prontas:
            todas_tarefas.append(tarefa)
        for tarefa in motor.fila_suspensas:
            todas_tarefas.append(tarefa)
        for tarefa in motor.fila_concluidas:
            todas_tarefas.append(tarefa)
    except Exception:
        todas_tarefas = []

    for cpu in getattr(motor, 'cpus', []):
        tarefa_cpu = getattr(cpu, 'tarefa_atual', None)
        if tarefa_cpu:
            todas_tarefas.append(tarefa_cpu)

    return todas_tarefas


# Aqui geramos o SVG atual com base no historico do simulador.
def _gerar_svg_atual(motor: Any, caminho: str = "gantt_resultado.svg") -> None:
    if motor is None:
        return

    tarefas = _montar_lista_tarefas_para_grafico(motor)
    try:
        if hasattr(motor, 'historico_estados'):
            historico_len = len(motor.historico_estados)
        else:
            historico_len = 0

        print(
            f"[DIAG] Gerando SVG: relogio={getattr(motor, 'relogio', '?')} | historico_len={historico_len} | tarefas_total={len(tarefas)}"
        )

        gerar_svg_gantt(motor.historico_estados, tarefas, caminho)
    except Exception as erro:
        print("Erro ao gerar SVG no servidor web:", erro)


# Aqui criamos a classe do servidor web que responde as rotas.
def make_handler_class(motor: Any, svg_path: str = "gantt_resultado.svg"):
    class SimHandler(http.server.BaseHTTPRequestHandler):
        server_motor = motor
        server_lock = threading.Lock()
        server_mode = 'idle'
        server_worker = None
        server_stop_event = None
        server_arquivo_atual = None
        # Indicador de que a simulacao terminou (todas as tarefas concluidas)
        server_finished = False

        # Aqui montamos uma resposta HTML com cabeçalhos corretos.
        def _responder_html(self, html: str, status: int = 200) -> None:
            conteudo = html.encode('utf-8')
            self.send_response(status)
            self.send_header('Content-Type', 'text/html; charset=utf-8')
            self.send_header('Content-Length', str(len(conteudo)))
            self.end_headers()
            self.wfile.write(conteudo)

        # Aqui redirecionamos o navegador para a raiz depois de uma acao.
        def _redirecionar_raiz(self) -> None:
            self.send_response(303)
            self.send_header('Location', '/')
            self.end_headers()

        # Aqui listamos os arquivos TXT da pasta atual para a tela inicial.
        def _listar_arquivos_txt(self) -> List[str]:
            arquivos_txt = []
            for nome_arquivo in os.listdir('.'):
                if nome_arquivo.endswith('.txt'):
                    arquivos_txt.append(nome_arquivo)
            return arquivos_txt

        # Aqui criamos a tela inicial com o seletor de arquivo.
        def _renderizar_tela_selecao(self, mensagem_erro: str = '') -> str:
            arquivos_txt = self._listar_arquivos_txt()
            opcoes = []
            for nome_arquivo in arquivos_txt:
                opcoes.append(f'<option value="{nome_arquivo}">{nome_arquivo}</option>')

            mensagem_html = ''
            if mensagem_erro:
                mensagem_html = f'<p class="erro">{mensagem_erro}</p>'
            elif not arquivos_txt:
                mensagem_html = '<p class="erro">Nenhum arquivo .txt encontrado na pasta do projeto.</p>'

            return f'''<!doctype html>
<html>
<head>
  <meta charset="utf-8">
  <title>Simulador - Selecao de Configuracao</title>
  <style>
    body{{margin:0;min-height:100vh;display:flex;align-items:center;justify-content:center;font-family:Arial,sans-serif;background:#fafafa;color:#222;}}
    .card{{background:#fff;border:1px solid #e0e0e0;padding:36px 48px;border-radius:12px;box-shadow:0 4px 16px rgba(0,0,0,0.08);text-align:center;max-width:720px;}}
    h2{{margin:0 0 8px;}}
    p{{color:#666;line-height:1.5;}}
    form{{display:flex;gap:8px;justify-content:center;align-items:center;flex-wrap:wrap;margin-top:16px;}}
    select{{padding:8px 12px;border-radius:6px;border:1px solid #ccc;min-width:240px;}}
    button{{padding:10px 22px;background:#2e7d32;color:#fff;border:none;border-radius:6px;font-weight:bold;cursor:pointer;}}
    .erro{{color:#b00020;font-weight:bold;}}
  </style>
</head>
<body>
  <div class="card">
    <h2>Simulador de Sistema Operacional Multitarefa</h2>
    <p>Selecione um arquivo TXT para iniciar a simulacao.</p>
    <form action="/selecionar_arquivo" method="GET">
      <select name="arquivo">
        {''.join(opcoes)}
      </select>
      <button type="submit">Carregar</button>
    </form>
    {mensagem_html}
  </div>
</body>
</html>'''

        # Aqui lemos o SVG pronto do disco para mostrar na pagina.
        def _ler_svg(self) -> str:
            try:
                with open(svg_path, 'r', encoding='utf-8') as arquivo_svg:
                    return arquivo_svg.read()
            except Exception:
                return '<div>SVG nao gerado ainda.</div>'

        # Aqui finalizamos a thread de execucao completa, se estiver rodando.
        def _parar_thread(self) -> None:
            if type(self).server_stop_event:
                type(self).server_stop_event.set()
            if type(self).server_worker:
                type(self).server_worker.join(timeout=1)
            type(self).server_worker = None
            type(self).server_stop_event = None
            type(self).server_mode = 'idle'
            type(self).server_finished = False

        # Aqui iniciamos a execucao automatica ate o fim.
        def _iniciar_execucao_completa(self) -> None:
            if type(self).server_worker and type(self).server_worker.is_alive():
                return

            type(self).server_mode = 'completo'
            type(self).server_stop_event = threading.Event()

            def worker():
                motor_local = type(self).server_motor
                total_tarefas = getattr(motor_local, 'total_tarefas_sistema', None)

                limite_esperado = 10000
                if motor_local is not None:
                    todas_tarefas = []
                    for tarefa in getattr(motor_local, 'fila_novas', []):
                        todas_tarefas.append(tarefa)
                    for tarefa in getattr(motor_local, 'fila_prontas', []):
                        todas_tarefas.append(tarefa)
                    for tarefa in getattr(motor_local, 'fila_concluidas', []):
                        todas_tarefas.append(tarefa)

                    maior_ingresso = 0
                    soma_duracao = 0
                    for tarefa in todas_tarefas:
                        if tarefa.ingresso > maior_ingresso:
                            maior_ingresso = tarefa.ingresso
                        soma_duracao += tarefa.duracao
                    limite_esperado = maior_ingresso + soma_duracao + 10

                contador_seguro = 100000

                while not type(self).server_stop_event.is_set():
                    with type(self).server_lock:
                        if motor_local is None:
                            break

                        if total_tarefas is not None and len(motor_local.fila_concluidas) >= total_tarefas:
                            break

                        filas_vazias = len(getattr(motor_local, 'fila_novas', [])) == 0 and len(getattr(motor_local, 'fila_prontas', [])) == 0
                        cpus_ociosas = True
                        for cpu in getattr(motor_local, 'cpus', []):
                            if getattr(cpu, 'tarefa_atual', None) is not None:
                                cpus_ociosas = False
                                break

                        if filas_vazias and cpus_ociosas:
                            break

                        if getattr(motor_local, 'relogio', 0) > limite_esperado:
                            break

                        motor_local.avancar_tick()
                        _gerar_svg_atual(motor_local, svg_path)

                    time.sleep(0.01)
                    contador_seguro -= 1
                    if contador_seguro <= 0:
                        break

                try:
                    _gerar_svg_atual(motor_local, svg_path)
                except Exception:
                    pass

                type(self).server_mode = 'idle'

            type(self).server_worker = threading.Thread(target=worker, daemon=True)
            type(self).server_worker.start()
            # quando a execucao completa terminar no worker, marcamos finished dentro do worker

        # Aqui calculamos a classe CSS do estado da tarefa.
        def _classe_estado(self, estado: str) -> str:
            estado_minusculo = estado.lower()
            if estado_minusculo == 'nova':
                return 'state-nova'
            if estado_minusculo == 'pronta':
                return 'state-pronta'
            if estado_minusculo == 'executando':
                return 'state-executando'
            if estado_minusculo == 'suspensa':
                return 'state-suspensa'
            return 'state-concluida'

        # Aqui criamos a tabela com as tarefas do sistema.
        def _montar_tabela_tcb(self, motor_local: Any) -> str:
            tarefas_do_sistema = []
            for tarefa in motor_local.fila_novas:
                tarefas_do_sistema.append(tarefa)
            for tarefa in motor_local.fila_prontas:
                tarefas_do_sistema.append(tarefa)
            for tarefa in motor_local.fila_suspensas:
                tarefas_do_sistema.append(tarefa)
            for tarefa in motor_local.fila_concluidas:
                tarefas_do_sistema.append(tarefa)
            for cpu in motor_local.cpus:
                if cpu.tarefa_atual and cpu.tarefa_atual not in tarefas_do_sistema:
                    tarefas_do_sistema.append(cpu.tarefa_atual)

            tarefas_do_sistema.sort(key=lambda tarefa: tarefa.id)

            linhas_tabela = []
            linhas_tabela.append('<table class="tcb-table">')
            linhas_tabela.append('<thead>')
            linhas_tabela.append('<tr>')
            linhas_tabela.append('<th>ID</th>')
            linhas_tabela.append('<th>Cor</th>')
            linhas_tabela.append('<th>Prioridade</th>')
            linhas_tabela.append('<th>Ingresso</th>')
            linhas_tabela.append('<th>Duração</th>')
            linhas_tabela.append('<th>Tempo Executado</th>')
            linhas_tabela.append('<th>Estado Atual</th>')
            linhas_tabela.append('<th>Mudar Estado</th>')
            linhas_tabela.append('</tr>')
            linhas_tabela.append('</thead>')
            linhas_tabela.append('<tbody>')

            for tarefa_atual in tarefas_do_sistema:
                if tarefa_atual.cor.startswith('#'):
                    cor_exibida = tarefa_atual.cor
                else:
                    cor_exibida = f"#{tarefa_atual.cor}"

                linhas_tabela.append('<tr>')
                linhas_tabela.append(f'<td><strong>{tarefa_atual.id}</strong></td>')
                linhas_tabela.append(
                    f'<td><div style="width:18px;height:18px;border-radius:3px;border:1px solid #333;background:{cor_exibida};margin:auto;"></div></td>'
                )
                linhas_tabela.append(f'<td>{tarefa_atual.prioridade}</td>')
                linhas_tabela.append(f'<td>{tarefa_atual.ingresso}</td>')
                linhas_tabela.append(f'<td>{tarefa_atual.duracao}</td>')
                linhas_tabela.append(f'<td>{tarefa_atual.tempo_executado}</td>')
                linhas_tabela.append(
                    f'<td><span class="badge {self._classe_estado(tarefa_atual.estado)}">{tarefa_atual.estado}</span></td>'
                )
                linhas_tabela.append('<td>')
                linhas_tabela.append(
                    f'<form action="/editar" method="GET" style="display:flex;gap:4px;justify-content:center;margin:0;">'
                    f'<input type="hidden" name="id" value="{tarefa_atual.id}">'
                    '<select name="estado" style="padding:4px;border-radius:4px;border:1px solid #ccc;">'
                    '<option value="">-- Alterar --</option>'
                    '<option value="Nova">Nova</option>'
                    '<option value="Pronta">Pronta</option>'
                    '<option value="Suspensa">Suspensa</option>'
                    '<option value="Concluida">Concluida</option>'
                    '</select>'
                    '<button type="submit" style="padding:4px 8px;background:#2e7d32;color:white;border:none;border-radius:4px;cursor:pointer;">Aplicar</button>'
                    '</form>'
                )
                linhas_tabela.append('</td>')
                linhas_tabela.append('</tr>')

            linhas_tabela.append('</tbody>')
            linhas_tabela.append('</table>')
            return ''.join(linhas_tabela)

        # Aqui montamos a pagina principal do dashboard web.
        def _renderizar_dashboard(self) -> str:
            motor_local = type(self).server_motor
            svg_content = self._ler_svg()

            arquivos_txt = self._listar_arquivos_txt()
            opcoes = []
            for nome_arquivo in arquivos_txt:
                if nome_arquivo == type(self).server_arquivo_atual:
                    opcoes.append(f'<option value="{nome_arquivo}" selected>{nome_arquivo}</option>')
                else:
                    opcoes.append(f'<option value="{nome_arquivo}">{nome_arquivo}</option>')

            # Calcula dinamicamente se a simulacao terminou (para evitar flag presa)
            finished_local = False
            if motor_local is not None:
                total = getattr(motor_local, 'total_tarefas_sistema', None)
                if total is not None and len(motor_local.fila_concluidas) >= total:
                    finished_local = True

            # Atualiza a flag do servidor (sincronia com o estado real)
            type(self).server_finished = finished_local

            notice_html = ''
            if finished_local:
                notice_html = '<div style="padding:10px;background:#ffd54f;color:#3e2723;border-radius:6px;margin-bottom:12px;font-weight:bold;">Simulação finalizada — todas as tarefas concluídas.</div>'

            if type(self).server_mode == 'idle':
                seletor_arquivo_html = (
                    '<div class="sys-card" style="text-align:center;">'
                    '<form action="/selecionar_arquivo" method="GET" style="display:flex;gap:8px;justify-content:center;align-items:center;margin:0;">'
                    '<strong>Selecionar Configuracao (TXT):</strong>'
                    f'<select name="arquivo" style="padding:6px;border-radius:4px;border:1px solid #ccc;cursor:pointer;">{''.join(opcoes)}</select>'
                    '<button type="submit" style="padding:6px 12px;background:#2e7d32;color:white;border:none;border-radius:4px;cursor:pointer;font-weight:bold;">Carregar Arquivo</button>'
                    '</form>'
                    '</div>'
                )
            else:
                seletor_arquivo_html = (
                    '<div class="sys-card" style="text-align:center;background-color:#eeeeee;">'
                    f'<strong>Arquivo em execucao:</strong> <span class="highlight">{type(self).server_arquivo_atual}</span> (reinicie para trocar)'
                    '</div>'
                )

            informacoes_html = (
                '<div class="sys-card">'
                f'<strong>Algoritmo Ativo:</strong> <span class="highlight">{motor_local.algoritmo.upper()}</span> | '
                f'<strong>Quantum:</strong> <span class="highlight">{motor_local.quantum}</span> | '
                f'<strong>Quantidade de CPUs:</strong> <span class="highlight">{len(motor_local.cpus)}</span>'
                '</div>'
            )

            if type(self).server_mode == 'idle':
                botoes_html = (
                    '<a class="button" href="/modo/passo">Modo Passo a Passo</a>'
                    '<a class="button" href="/modo/completo">Execucao Completa</a>'
                )
            elif type(self).server_mode == 'passo':
                # Se terminou, desabilita o botao Avancar e mostra somente Voltar
                if finished_local:
                    botoes_html = '<a class="button" href="/voltar">Voltar</a><span class="button disabled">Avancar</span>'
                else:
                    botoes_html = '<a class="button" href="/voltar">Voltar</a><a class="button" href="/avancar">Avancar</a>'
            else:
                botoes_html = '<a class="button" href="/modo/stop">Parar Execucao</a>'

            reiniciar_html = '<div class="restart-zone"><a class="button restart" href="/reiniciar">Reiniciar</a></div>'
            tabela_tcb_html = self._montar_tabela_tcb(motor_local)

            return f'''<!doctype html>
<html>
<head>
  <meta charset="utf-8">
  <title>Simulador Sistema Operacional</title>
  <style>
    body{{display:flex;flex-direction:column;align-items:center;font-family:Arial,sans-serif;margin:20px;background-color:#fafafa;color:#333333;}}
    .tick{{font-weight:700;font-size:16px;margin-bottom:12px;background:#333333;color:#ffffff;padding:8px 16px;border-radius:20px;}}
    .sys-card{{background:#ffffff;border:1px solid #e0e0e0;padding:12px 24px;border-radius:8px;margin-bottom:12px;box-shadow:0 2px 4px rgba(0,0,0,0.05);min-width:400px;}}
    .highlight{{color:#1976d2;font-weight:bold;}}
    .controls{{margin:12px;}}
    a.button{{display:inline-block;padding:10px 16px;background:#1976d2;color:#ffffff;text-decoration:none;border-radius:4px;margin:0 6px;font-weight:bold;}}
    a.button.disabled{{opacity:0.5;pointer-events:none;cursor:default;}}
    a.button.restart{{background:#c62828;}}
    .restart-zone{{width:85%;display:flex;justify-content:center;margin:10px 0 18px;padding-top:14px;border-top:1px solid #d9d9d9;}}
    .svgwrap{{max-width:95%;overflow:auto;border:1px solid #dddddd;padding:16px;background:#ffffff;border-radius:8px;margin-bottom:24px;box-shadow:0 2px 8px rgba(0,0,0,0.05);}}
    .tcb-table{{width:85%;border-collapse:collapse;background:#ffffff;border-radius:8px;overflow:hidden;box-shadow:0 2px 8px rgba(0,0,0,0.05);border:1px solid #e0e0e0;margin-top:12px;text-align:center;}}
    .tcb-table th{{background:#424242;color:#ffffff;padding:12px;font-size:14px;}}
    .tcb-table td{{padding:10px;border-bottom:1px solid #eeeeee;font-size:14px;}}
    .badge{{display:inline-block;padding:4px 8px;border-radius:12px;font-size:12px;font-weight:bold;color:#ffffff;}}
    .state-nova{{background:#ffb300;color:#000000;}}
    .state-pronta{{background:#29b6f6;}}
    .state-executando{{background:#66bb6a;}}
    .state-suspensa{{background:#ef5350;}}
    .state-concluida{{background:#78909c;}}
  </style>
</head>
<body>
    <div class="tick">Tick Atual: {motor_local.relogio} | Estado: {type(self).server_mode.upper()}</div>
    {notice_html}
  {seletor_arquivo_html}
  {informacoes_html}
  <div class="controls">
    {botoes_html}
  </div>
  <div class="svgwrap">
    <h3 style="margin-top:0;border-bottom:2px solid #1976d2;padding-bottom:6px;">Grafico de Gantt da Simulacao</h3>
    {svg_content}
  </div>
  {reiniciar_html}
  <h3 style="margin-bottom:6px;">Bloco de Controle de Tarefas (TCB)</h3>
  {tabela_tcb_html}
</body>
</html>'''

        # Aqui recebemos as requisições GET da interface web.
        def do_GET(self):
            parsed = urllib.parse.urlparse(self.path)
            caminho = parsed.path

            if caminho == '/' or caminho == '':
                if type(self).server_motor is None:
                    html = self._renderizar_tela_selecao()
                    self._responder_html(html)
                    return

                html = self._renderizar_dashboard()
                self._responder_html(html)
                return

            if caminho == '/selecionar_arquivo':
                with type(self).server_lock:
                    try:
                        query = urllib.parse.parse_qs(parsed.query)
                        arquivo_escolhido = query.get('arquivo', [None])[0]

                        if arquivo_escolhido and type(self).server_mode == 'idle':
                            configuracao = ler_arquivo_configuracao(arquivo_escolhido)
                            if configuracao:
                                type(self).server_motor = Simulador(configuracao)
                                type(self).server_arquivo_atual = arquivo_escolhido
                                type(self).server_finished = False
                                _gerar_svg_atual(type(self).server_motor, svg_path)
                                print(f"[WEB] Novo cenario carregado: {arquivo_escolhido}")
                    except Exception as erro:
                        print("[WEB] Erro ao carregar novo arquivo:", erro)
                self._redirecionar_raiz()
                return

            if caminho == '/editar':
                with type(self).server_lock:
                    try:
                        query = urllib.parse.parse_qs(parsed.query)
                        id_tarefa = query.get('id', [None])[0]
                        novo_estado = query.get('estado', [None])[0]

                        if id_tarefa and novo_estado:
                            motor_local = type(self).server_motor
                            sucesso, mensagem = motor_local.forcar_mudanca_estado(id_tarefa, novo_estado)
                            print(f"[WEB EDIT] {mensagem}")
                            if sucesso:
                                type(self).server_finished = False
                                _gerar_svg_atual(type(self).server_motor, svg_path)
                    except Exception as erro:
                        print("[WEB EDIT] Erro ao editar tarefa:", erro)
                self._redirecionar_raiz()
                return

            if caminho == '/avancar':
                with type(self).server_lock:
                    try:
                        motor_local = type(self).server_motor
                        if type(self).server_mode == 'passo':
                            # Avanca um tick e atualiza SVG
                            motor_local.avancar_tick()
                            _gerar_svg_atual(motor_local, svg_path)
                            # Se todas as tarefas concluídas, marca finished
                            if getattr(motor_local, 'total_tarefas_sistema', None) is not None and len(motor_local.fila_concluidas) >= motor_local.total_tarefas_sistema:
                                type(self).server_finished = True
                    except Exception as erro:
                        print("[WEB] AVANCAR error:", erro)
                self._redirecionar_raiz()
                return

            if caminho == '/voltar':
                with type(self).server_lock:
                    try:
                        motor_local = type(self).server_motor
                        if type(self).server_mode == 'passo':
                            motor_local.retroceder_tick()
                            _gerar_svg_atual(motor_local, svg_path)
                    except Exception as erro:
                        print("[WEB] VOLTAR error:", erro)
                self._redirecionar_raiz()
                return

            if caminho == '/modo/completo':
                with type(self).server_lock:
                    print(f"[WEB] Modo completo solicitado no tick {type(self).server_motor.relogio}")
                    self._iniciar_execucao_completa()
                worker = type(self).server_worker
                if worker:
                    worker.join()
                # apos execucao completa, marcar finished
                type(self).server_finished = True
                self._redirecionar_raiz()
                return

            if caminho == '/modo/passo':
                with type(self).server_lock:
                    self._parar_thread()
                    type(self).server_mode = 'passo'
                    if type(self).server_motor is not None:
                        _gerar_svg_atual(type(self).server_motor, svg_path)
                    print(f"[WEB] Modo passo selecionado no tick {getattr(type(self).server_motor, 'relogio', '?')}")
                self._redirecionar_raiz()
                return

            if caminho == '/modo/stop':
                with type(self).server_lock:
                    print(f"[WEB] Parada solicitada no tick {getattr(type(self).server_motor, 'relogio', '?')}")
                    self._parar_thread()
                self._redirecionar_raiz()
                return

            if caminho == '/reiniciar':
                with type(self).server_lock:
                    self._parar_thread()
                    type(self).server_motor = None
                    type(self).server_arquivo_atual = None
                    type(self).server_mode = 'idle'
                    type(self).server_finished = False
                    print("[WEB] Servidor voltou para a tela inicial")
                self._redirecionar_raiz()
                return

            self.send_response(404)
            self.send_header('Content-Type', 'text/plain; charset=utf-8')
            self.end_headers()
            self.wfile.write(b'404 Not Found')

        # Aqui recebemos o envio inicial do arquivo TXT, se ele vier por formulario.
        def do_POST(self):
            caminho = urllib.parse.urlparse(self.path).path
            if caminho != '/upload':
                self.send_response(404)
                self.end_headers()
                return

            try:
                arquivo_enviado, conteudo = self._ler_arquivo_enviado()
                nome_temporario = 'config_upload.txt'
                with open(nome_temporario, 'w', encoding='utf-8') as arquivo_saida:
                    arquivo_saida.write(conteudo)

                configuracao = ler_arquivo_configuracao(nome_temporario)
                with type(self).server_lock:
                    type(self).server_motor = Simulador(configuracao)
                    type(self).server_arquivo_atual = arquivo_enviado
                    type(self).server_mode = 'idle'
                    _gerar_svg_atual(type(self).server_motor, svg_path)

                self._redirecionar_raiz()
            except Exception as erro:
                html = self._renderizar_tela_selecao(mensagem_erro=f'Erro ao carregar o arquivo: {erro}')
                self._responder_html(html, status=400)

        # Aqui fazemos o parser simples de upload sem bibliotecas extras.
        def _ler_arquivo_enviado(self) -> Tuple[str, str]:
            content_type = self.headers.get('Content-Type', '')
            if 'boundary=' not in content_type:
                raise ValueError('Upload invalido: boundary ausente.')

            boundary = content_type.split('boundary=', 1)[1].strip().strip('"')
            tamanho = int(self.headers.get('Content-Length', '0'))
            corpo = self.rfile.read(tamanho)
            separador = ('--' + boundary).encode('utf-8')

            partes = corpo.split(separador)
            for parte in partes:
                if b'name="config_file"' not in parte:
                    continue

                indice_cabecalho = parte.find(b'\r\n\r\n')
                if indice_cabecalho == -1:
                    continue

                cabecalho = parte[:indice_cabecalho].decode('utf-8', errors='ignore')
                conteudo = parte[indice_cabecalho + 4:].rstrip(b'\r\n-')
                nome_arquivo = 'config_upload.txt'

                linhas_cabecalho = cabecalho.split('\r\n')
                for linha_cabecalho in linhas_cabecalho:
                    if 'filename=' in linha_cabecalho:
                        nome_arquivo = linha_cabecalho.split('filename=', 1)[1].strip().strip('"')
                        break

                return nome_arquivo, conteudo.decode('utf-8', errors='replace')

            raise ValueError('Arquivo nao encontrado no upload.')

        def log_message(self, format, *args):
            return

    return SimHandler


# Aqui iniciamos o servidor web e geramos o SVG inicial, se houver motor.
def iniciar_servidor_web(motor: Any, host: str = '127.0.0.1', port: int = 8000):
    if motor is not None:
        _gerar_svg_atual(motor, 'gantt_resultado.svg')

    handler = make_handler_class(motor, 'gantt_resultado.svg')
    servidor = http.server.HTTPServer((host, port), handler)
    print(f'Servidor web iniciado em http://{host}:{port}/')

    try:
        servidor.serve_forever()
    except KeyboardInterrupt:
        print('\nServidor finalizado pelo usuario (KeyboardInterrupt)')
        servidor.server_close()


# ==========================================
# EXECUCAO DIRETA DO ARQUIVO
# ==========================================

# Aqui deixamos um modo direto, caso alguem execute este arquivo sozinho.
def main() -> None:
    print("Iniciando o Sistema Operacional...")

    config = ler_configuracao("config.txt")
    if not config:
        print("Erro: nao foi possivel carregar o arquivo de configuracao.")
        return

    motor = Simulador(config)

    print("\nIniciando servidor web para controle da simulacao...")
    print("Acesse no navegador: http://127.0.0.1:8000")

    iniciar_servidor_web(motor, host='127.0.0.1', port=8000)


if __name__ == "__main__":
    main()
