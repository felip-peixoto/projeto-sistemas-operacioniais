import copy
from estruturas import CPU
from escalonadores import executar_escalonador
import random


class Simulador:
    def __init__(self, config):
        random.seed()
        algoritmos_suportados = ["SRTF", "PRIOP"]
        if config["algoritmo"] not in algoritmos_suportados:
            print(
                f"🛑 ERRO FATAL: O algoritmo '{config['algoritmo']}' não foi implementado!")
            print(f"Algoritmos suportados: {algoritmos_suportados}")
            exit(1)

        self.relogio = 0
        self.algoritmo = config["algoritmo"]
        self.quantum = config["quantum"]

        self.cpus = [CPU(i) for i in range(config["cpus"])]

        self.fila_novas = config["tarefas"]
        self.fila_prontas = []
        self.fila_concluidas = []
        self.fila_suspensas = []
        self.houve_sorteio_neste_tick = False
        self.historico_estados = []
        self.total_tarefas_sistema = len(config["tarefas"])

    # -------------------------------------------------------
    # BUG 1 CORRIGIDO: forcar_mudanca_estado estava definido
    # fora da classe como função solta (com `self` como
    # parâmetro normal), então motor.forcar_mudanca_estado(...)
    # jogava AttributeError — silenciado pelo try/except do
    # frontend e a mudança nunca acontecia.
    # -------------------------------------------------------
    def forcar_mudanca_estado(self, id_tarefa, novo_estado):
        """
        Altera o estado de uma tarefa manualmente, respeitando as transições.
        Retorna: (sucesso: bool, mensagem: str)
        """
        # 1. Procurar a tarefa em todo o sistema
        tarefa_encontrada = None
        estado_atual = None

        todas_tarefas = self.fila_novas + self.fila_prontas + \
            self.fila_suspensas + self.fila_concluidas
        for cpu in self.cpus:
            if cpu.tarefa_atual is not None:
                todas_tarefas.append(cpu.tarefa_atual)

        for t in todas_tarefas:
            if t.id == id_tarefa:
                tarefa_encontrada = t
                estado_atual = t.estado
                break

        if not tarefa_encontrada:
            return False, f"Erro: Tarefa com ID '{id_tarefa}' não encontrada."

        # 2. Formatar e validar o estado
        novo_estado = novo_estado.capitalize()
        estados_possiveis = ["Nova", "Pronta",
                             "Executando", "Suspensa", "Concluida"]

        if novo_estado not in estados_possiveis:
            return False, f"Erro: O estado '{novo_estado}' não existe. Opções: {estados_possiveis}"

        # 3. Regras de Transição (Livro do Maziero)
        transicoes_validas = {
            "Nova": ["Pronta"],
            "Pronta": ["Executando"],
            "Executando": ["Pronta", "Suspensa", "Concluida"],
            "Suspensa": ["Pronta"],
            "Concluida": []
        }

        if novo_estado not in transicoes_validas.get(estado_atual, []):
            return False, f"Erro: Transição Inválida! Tarefa '{estado_atual}' não pode ir direto para '{novo_estado}'."

        if novo_estado == "Executando":
            return False, "Aviso: Para forçar uma tarefa a Executar, coloque-a como 'Pronta' e deixe o Escalonador agir."

        # 4. Aplicar a mudança
        tarefa_encontrada.estado = novo_estado

        # Remove da lista antiga
        if tarefa_encontrada in self.fila_novas:
            self.fila_novas.remove(tarefa_encontrada)
        if tarefa_encontrada in self.fila_prontas:
            self.fila_prontas.remove(tarefa_encontrada)
        if tarefa_encontrada in self.fila_suspensas:
            self.fila_suspensas.remove(tarefa_encontrada)
        if tarefa_encontrada in self.fila_concluidas:
            self.fila_concluidas.remove(tarefa_encontrada)

        # Se a tarefa estava executando em alguma CPU, libera a CPU
        for cpu in self.cpus:
            if cpu.tarefa_atual == tarefa_encontrada:
                cpu.tarefa_atual = None

        # Adiciona na fila correta
        if novo_estado == "Pronta":
            self.fila_prontas.append(tarefa_encontrada)
        elif novo_estado == "Suspensa":
            self.fila_suspensas.append(tarefa_encontrada)
        elif novo_estado == "Concluida":
            self.fila_concluidas.append(tarefa_encontrada)

        return True, f"Sucesso! Status da tarefa {id_tarefa} alterado para {novo_estado}."

    # -------------------------------------------------------
    # BUG 2 CORRIGIDO: salvar_snapshot agora grava todas as
    # filas e o relogio. retroceder_tick restaura exatamente
    # as mesmas chaves que foram salvas.
    # -------------------------------------------------------
    def salvar_snapshot(self):
        todas_tarefas = self.fila_novas + self.fila_prontas + \
            self.fila_suspensas + self.fila_concluidas
        for cpu in self.cpus:
            if cpu.tarefa_atual and cpu.tarefa_atual not in todas_tarefas:
                todas_tarefas.append(cpu.tarefa_atual)

        snapshot = {
            "tempo": self.relogio,
            "cpus": copy.deepcopy(self.cpus),
            "tarefas": copy.deepcopy(todas_tarefas),
            "fila_novas": copy.deepcopy(self.fila_novas),
            "fila_prontas": copy.deepcopy(self.fila_prontas),
            "fila_suspensas": copy.deepcopy(self.fila_suspensas),
            "fila_concluidas": copy.deepcopy(self.fila_concluidas),
            "sorteio": getattr(self, 'houve_sorteio_neste_tick', False),
        }
        self.historico_estados.append(snapshot)

    def avancar_tick(self):
        """
        Executa apenas UM instante de tempo (passo-a-passo).
        """
        if getattr(self, 'total_tarefas_sistema', None) is not None and len(self.fila_concluidas) >= self.total_tarefas_sistema:
            return

        # Chegada de novas tarefas
        tarefas_a_remover = []
        for tarefa in self.fila_novas:
            if tarefa.ingresso == self.relogio:
                tarefa.estado = "Pronta"
                self.fila_prontas.append(tarefa)
                tarefas_a_remover.append(tarefa)

        for t in tarefas_a_remover:
            self.fila_novas.remove(t)

        self.houve_sorteio_neste_tick = False

        tem_nova_tarefa = len(tarefas_a_remover) > 0
        tem_cpu_livre = any(cpu.tarefa_atual is None for cpu in self.cpus)
        tem_tarefa_esperando = len(self.fila_prontas) > 0

        precisa_escalonar = tem_nova_tarefa or (
            tem_cpu_livre and tem_tarefa_esperando)

        if precisa_escalonar:
            self.fila_prontas, sorteio = executar_escalonador(
                self.fila_prontas, self.cpus, self.algoritmo
            )
            if sorteio:
                self.houve_sorteio_neste_tick = True

        # Salva snapshot ANTES de executar o tick
        self.salvar_snapshot()

        # Executar as tarefas nas CPUs
        for cpu in self.cpus:
            if cpu.tarefa_atual is not None:
                cpu.tarefa_atual.tempo_executado += 1
                cpu.tarefa_atual.tempo_no_quantum += 1

                if cpu.tarefa_atual.is_concluida():
                    cpu.tarefa_atual.estado = "Concluida"
                    self.fila_concluidas.append(cpu.tarefa_atual)
                    cpu.tarefa_atual = None

                elif self.algoritmo in {"PRIOP", "SRTF"} and cpu.tarefa_atual.tempo_no_quantum >= self.quantum:
                    cpu.tarefa_atual.estado = "Pronta"
                    cpu.tarefa_atual.tempo_no_quantum = 0
                    self.fila_prontas.append(cpu.tarefa_atual)
                    cpu.tarefa_atual = None
            else:
                cpu.tempo_desligada += 1
                cpu.desligar()

        self.relogio += 1

    def retroceder_tick(self):
        if len(self.historico_estados) == 0:
            return False

        estado_anterior = self.historico_estados.pop()
        self.relogio = estado_anterior["tempo"]
        self.cpus = estado_anterior["cpus"]
        self.fila_novas = estado_anterior["fila_novas"]
        self.fila_prontas = estado_anterior["fila_prontas"]
        self.fila_suspensas = estado_anterior["fila_suspensas"]
        self.fila_concluidas = estado_anterior["fila_concluidas"]
        return True
