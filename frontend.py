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

        self.largura_svg = (
            self.MARGEM_ESQUERDA +
            (self.total_ticks * self.LARGURA_CELULA) +
            self.MARGEM_DIREITA
        )

        self.altura_svg = (
            self.MARGEM_TOPO +
            (self.num_tarefas * self.ALTURA_CELULA) +
            self.MARGEM_RODAPE
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
            cpus = snapshot.get("cpus", [])

            tarefas_executando = set()
            for cpu in cpus:
                if hasattr(cpu, 'tarefa_atual') and cpu.tarefa_atual is not None:
                    tarefas_executando.add(cpu.tarefa_atual.id)

            for idx_tarefa, tarefa in enumerate(self.tarefas_ordenadas):
                x = self.calcular_posicao_x(tick)
                y = self.calcular_posicao_y(idx_tarefa)

                if tarefa.id in tarefas_executando:
                    cor = self.obter_cor_tarefa(tarefa.id)
                else:
                    cor = self.COR_OCIOSA

                padding = 2
                linhas.append(
                    f'<rect x="{x + padding}" y="{y + padding}" '
                    f'width="{self.LARGURA_CELULA - 2*padding}" '
                    f'height="{self.ALTURA_CELULA - 2*padding}" '
                    f'fill="{cor}"/>'
                )

        linhas.append('')

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
        server_mode = 'idle'  # 'idle', 'passo', 'completo'
        server_worker = None
        server_stop_event = None

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
                # heuristica de fim: ultimo ingresso + soma das duracoes + margem
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
                            # verifica se terminou por contagem
                            if total_tarefas is not None and len(motor.fila_concluidas) >= total_tarefas:
                                break

                            # verifica se nao ha mais trabalho (filas vazias e CPUs ociosas)
                            filas_vazias = (len(getattr(motor, 'fila_prontas', [])) == 0 and
                                            len(getattr(motor, 'fila_novas', [])) == 0)
                            cpus_ociosas = all(getattr(
                                cpu, 'tarefa_atual', None) is None for cpu in getattr(motor, 'cpus', []))
                            if filas_vazias and cpus_ociosas:
                                break

                            # safety by expected_end
                            if getattr(motor, 'relogio', 0) > expected_end:
                                break

                            # avancar tick
                            motor.avancar_tick()
                            _gerar_svg_atual(motor, svg_path)
                            # log every 5 ticks
                            if getattr(motor, 'relogio', 0) % 5 == 0 and getattr(motor, 'relogio', 0) != last_log_time:
                                last_log_time = getattr(motor, 'relogio', 0)
                                print(
                                    f"[WORKER] relogio={last_log_time} | novas={len(getattr(motor, 'fila_novas', []))} prontas={len(getattr(motor, 'fila_prontas', []))} concluidas={len(getattr(motor, 'fila_concluidas', []))}")
                        except Exception:
                            break
                    time.sleep(0.01)
                    safety -= 1
                    if safety <= 0:
                        break

                # Garante svg final e volta para idle
                try:
                    _gerar_svg_atual(motor, svg_path)
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
                    svg_content = self._read_svg()

                mode = type(self).server_mode

                # Default: show initial two options only when idle
                if mode == 'idle':
                    controls_html = (
                        '<a class="button" href="/modo/passo">Modo Passo a Passo</a>'
                        '<a class="button" href="/modo/completo">Execucao Completa</a>'
                    )
                    manual_html = ''
                elif mode == 'passo':
                    # In passo mode, hide initial buttons and show manual controls
                    controls_html = ''
                    manual_html = '<a class="button" href="/voltar">Voltar</a><a class="button" href="/avancar">Avancar</a>'
                else:  # completo
                    controls_html = '<a class="button" href="/modo/stop">Parar Execucao</a>'
                    manual_html = ''

                # Reiniciar sempre disponível
                reiniciar_html = '<a class="button" href="/reiniciar">Reiniciar</a>'

                html = f'''<!doctype html>
<html>
<head>
  <meta charset="utf-8">
  <title>Simulador - Gantt</title>
  <style>
    body{{display:flex;flex-direction:column;align-items:center;font-family:Arial,Helvetica,sans-serif;margin:20px;}}
    .controls{{margin:12px;}}
    a.button{{display:inline-block;padding:8px 12px;background:#1976d2;color:#fff;text-decoration:none;border-radius:4px;margin:0 6px}}
    .tick{{font-weight:700;margin-bottom:8px}}
    .svgwrap{{max-width:95%;overflow:auto;border:1px solid #ddd;padding:8px}}
  </style>
</head>
<body>
  <div class="tick">Tick Atual: {getattr(self.server_motor, 'relogio', '?')} | Modo: {mode}</div>
    <div class="controls">
        {controls_html}
        {manual_html}
        {reiniciar_html}
    </div>
  <div class="svgwrap">{svg_content}</div>
</body>
</html>'''

                encoded = html.encode('utf-8')
                self.send_response(200)
                self.send_header('Content-Type', 'text/html; charset=utf-8')
                self.send_header('Content-Length', str(len(encoded)))
                self.end_headers()
                self.wfile.write(encoded)

            elif path == '/avancar':
                with type(self).server_lock:
                    try:
                        motor = type(self).server_motor
                        print(
                            f"[WEB] AVANCAR pressed | before relogio={getattr(motor, 'relogio', '?')} | novas={len(getattr(motor, 'fila_novas', []))} prontas={len(getattr(motor, 'fila_prontas', []))} concluidas={len(getattr(motor, 'fila_concluidas', []))}")
                        # permit only in passo mode
                        if type(self).server_mode == 'passo':
                            motor.avancar_tick()
                            _gerar_svg_atual(motor, svg_path)
                            print(
                                f"[WEB] AVANCAR result | after relogio={getattr(motor, 'relogio', '?')} | novas={len(getattr(motor, 'fila_novas', []))} prontas={len(getattr(motor, 'fila_prontas', []))} concluidas={len(getattr(motor, 'fila_concluidas', []))}")
                        else:
                            print(
                                f"[WEB] AVANCAR ignored (mode={type(self).server_mode})")
                    except Exception as e:
                        print("[WEB] AVANCAR error:", e)
                self._redirect_root()

            elif path == '/voltar':
                with type(self).server_lock:
                    try:
                        motor = type(self).server_motor
                        print(
                            f"[WEB] VOLTAR pressed | before relogio={getattr(motor, 'relogio', '?')} | novas={len(getattr(motor, 'fila_novas', []))} prontas={len(getattr(motor, 'fila_prontas', []))} concluidas={len(getattr(motor, 'fila_concluidas', []))}")
                        # permit only in passo mode
                        if type(self).server_mode == 'passo':
                            motor.retroceder_tick()
                            _gerar_svg_atual(motor, svg_path)
                            print(
                                f"[WEB] VOLTAR result | after relogio={getattr(motor, 'relogio', '?')} | novas={len(getattr(motor, 'fila_novas', []))} prontas={len(getattr(motor, 'fila_prontas', []))} concluidas={len(getattr(motor, 'fila_concluidas', []))}")
                        else:
                            print(
                                f"[WEB] VOLTAR ignored (mode={type(self).server_mode})")
                    except Exception as e:
                        print("[WEB] VOLTAR error:", e)
                self._redirect_root()

            elif path == '/modo/completo':
                try:
                    # start worker under lock, then wait for it to finish (but don't hold lock while joining)
                    with type(self).server_lock:
                        print(
                            f"[WEB] MODO completo requested | relogio={getattr(type(self).server_motor, 'relogio', '?')}")
                        self._start_completo()
                        print("[WEB] MODO completo started")

                    worker = type(self).server_worker
                    if worker:
                        # wait until worker thread finishes to show final result
                        worker.join()
                        print("[WEB] MODO completo finished")
                except Exception as e:
                    print("[WEB] MODO completo error:", e)
                self._redirect_root()

            elif path == '/modo/passo':
                with type(self).server_lock:
                    try:
                        # stop any background worker
                        self._stop_worker()
                        type(self).server_mode = 'passo'
                        _gerar_svg_atual(type(self).server_motor, svg_path)
                        print(
                            f"[WEB] MODO passo selected | relogio={getattr(type(self).server_motor, 'relogio', '?')}")
                    except Exception as e:
                        print("[WEB] MODO passo error:", e)
                self._redirect_root()

            elif path == '/modo/stop':
                with type(self).server_lock:
                    try:
                        print(
                            f"[WEB] MODO stop requested | relogio={getattr(type(self).server_motor, 'relogio', '?')}")
                        self._stop_worker()
                        print("[WEB] MODO stop executed")
                    except Exception as e:
                        print("[WEB] MODO stop error:", e)
                self._redirect_root()

            elif path == '/reiniciar':
                with type(self).server_lock:
                    try:
                        print(
                            f"[WEB] REINICIAR requested | relogio={getattr(type(self).server_motor, 'relogio', '?')}")
                        # stop background worker if any
                        self._stop_worker()
                        cfg = None
                        try:
                            cfg = ler_arquivo_configuracao("config.txt")
                        except Exception as e:
                            print("[WEB] REINICIAR config load error:", e)

                        if not cfg:
                            print(
                                "[WEB] REINICIAR failed: config.txt not found or invalid")
                        else:
                            type(self).server_motor = Simulador(cfg)
                            _gerar_svg_atual(type(self).server_motor, svg_path)
                            type(self).server_mode = 'idle'
                            print("[WEB] REINICIAR done: motor reset")
                    except Exception as e:
                        print("[WEB] REINICIAR error:", e)
                self._redirect_root()

            else:
                self.send_response(404)
                self.send_header('Content-Type', 'text/plain; charset=utf-8')
                self.end_headers()
                self.wfile.write(b'404 Not Found')

        def log_message(self, format, *args):
            # Silencia logs de acerto no console para ficar mais limpo
            return

    return SimHandler


def iniciar_servidor_web(motor: Any, host: str = '127.0.0.1', port: int = 8000):
    # Diagnóstico rápido: imprime estado inicial do motor
    try:
        hist_len = len(getattr(motor, 'historico_estados', []))
    except Exception:
        hist_len = getattr(getattr(motor, 'historico_estados', None),
                           'quantidade_snapshots', lambda: 'N/A')()
    print(
        f"[DIAG] iniciar_servidor_web: relogio={getattr(motor, 'relogio', '?')} | historico_len={hist_len} | fila_novas={len(getattr(motor, 'fila_novas', []))}")
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


def main() -> None:
    print("Iniciando o Sistema Operacional...")
    config = ler_arquivo_configuracao("config.txt")
    if not config:
        return

    motor = Simulador(config)

    print("\nSelecione o Modo de Execucao (Req 1.5):")
    print("1 - Modo Passo a Passo (com controle manual)")
    print("2 - Execucao Completa (resultado direto)")
    escolha = input("Opcao: ").strip()

    if escolha == '2':
        executar_completo(motor)
    else:
        executar_passo_a_passo(motor)


if __name__ == "__main__":
    main()
