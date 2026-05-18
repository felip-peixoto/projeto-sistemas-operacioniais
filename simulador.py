import copy
import random
from estruturas import CPU
from escalonadores import executar_escalonador


class Simulador:
    def __init__(self, config):
        random.seed()

        algoritmos_suportados = ["SRTF", "PRIOP"]
        if config["algoritmo"] not in algoritmos_suportados:
            print(f"ERRO: algoritmo '{config['algoritmo']}' não implementado. "
                  f"Suportados: {algoritmos_suportados}")
            exit(1)

        self.relogio = 0
        self.algoritmo = config["algoritmo"]
        self.quantum = config["quantum"]
        self.cpus = [CPU(i) for i in range(config["cpus"])]

        self.fila_novas = config["tarefas"]
        self.fila_prontas = []
        self.fila_suspensas = []
        self.fila_concluidas = []

        self.houve_sorteio_neste_tick = False
        self.total_tarefas_sistema = len(config["tarefas"])
        self.historico_estados = []

    def forcar_mudanca_estado(self, id_tarefa, novo_estado):
        todas = (self.fila_novas + self.fila_prontas +
                 self.fila_suspensas + self.fila_concluidas +
                 [c.tarefa_atual for c in self.cpus if c.tarefa_atual])

        tarefa = next((t for t in todas if t.id == id_tarefa), None)
        if not tarefa:
            return False, f"Tarefa '{id_tarefa}' não encontrada."

        novo_estado = novo_estado.capitalize()

        #Seguimos as transicoes do livro do Maziero
        #Pronta -> Executando é responsabilidade do escalonador.
        transicoes = {
            "Nova":       ["Pronta"],
            "Pronta":     ["Suspensa"],
            "Executando": ["Pronta", "Suspensa", "Concluida"],
            "Suspensa":   ["Pronta"],
            "Concluida":  [],
        }

        if novo_estado == "Executando":
            return False, "Coloque a tarefa como 'Pronta' e o escalonador a alocará."

        if novo_estado not in transicoes.get(tarefa.estado, []):
            return False, (f"Transição inválida: '{tarefa.estado}' → '{novo_estado}'.")

        # Remove da fila/CPU atual
        for fila in (self.fila_novas, self.fila_prontas,
                     self.fila_suspensas, self.fila_concluidas):
            if tarefa in fila:
                fila.remove(tarefa)
        for cpu in self.cpus:
            if cpu.tarefa_atual == tarefa:
                cpu.tarefa_atual = None

        tarefa.estado = novo_estado

        destino = {
            "Pronta":    self.fila_prontas,
            "Suspensa":  self.fila_suspensas,
            "Concluida": self.fila_concluidas,
        }
        if novo_estado in destino:
            destino[novo_estado].append(tarefa)

        return True, f"Tarefa {id_tarefa} → {novo_estado}."

    def salvar_snapshot(self):
        todas = (self.fila_novas + self.fila_prontas +
                 self.fila_suspensas + self.fila_concluidas)
        for cpu in self.cpus:
            if cpu.tarefa_atual and cpu.tarefa_atual not in todas:
                todas.append(cpu.tarefa_atual)

        self.historico_estados.append({
            "tempo":           self.relogio,
            "cpus":            copy.deepcopy(self.cpus),
            "tarefas":         copy.deepcopy(todas),
            "fila_novas":      copy.deepcopy(self.fila_novas),
            "fila_prontas":    copy.deepcopy(self.fila_prontas),
            "fila_suspensas":  copy.deepcopy(self.fila_suspensas),
            "fila_concluidas": copy.deepcopy(self.fila_concluidas),
            "sorteio":         self.houve_sorteio_neste_tick,
        })

    def retroceder_tick(self):
        """Restaura o estado do tick anterior. Retorna False se já está no início."""
        if not self.historico_estados:
            return False
        s = self.historico_estados.pop()
        self.relogio = s["tempo"]
        self.cpus = s["cpus"]
        self.fila_novas = s["fila_novas"]
        self.fila_prontas = s["fila_prontas"]
        self.fila_suspensas = s["fila_suspensas"]
        self.fila_concluidas = s["fila_concluidas"]
        return True

    def _precisa_escalonar(self, houve_nova_tarefa):
        tem_cpu_livre = any(c.tarefa_atual is None for c in self.cpus)
        tem_tarefa_esperando = bool(self.fila_prontas)
        return houve_nova_tarefa or (tem_cpu_livre and tem_tarefa_esperando)

    def avancar_tick(self):
        if len(self.fila_concluidas) >= self.total_tarefas_sistema:
            return

        # 1. Tarefas cujo ingresso coincide com o relógio entram na fila de prontas.
        chegando = [t for t in self.fila_novas if t.ingresso == self.relogio]
        for t in chegando:
            t.estado = "Pronta"
            self.fila_prontas.append(t)
            self.fila_novas.remove(t)

        self.houve_sorteio_neste_tick = False

        # 2. Escalonamento — somente quando necessário.
        if self._precisa_escalonar(bool(chegando)):
            self.fila_prontas, sorteio = executar_escalonador(
                self.fila_prontas, self.cpus, self.algoritmo
            )
            self.houve_sorteio_neste_tick = sorteio

        # 3. Snapshot do estado antes da execução (para o Gantt e histórico).
        self.salvar_snapshot()

        # 4. Cada CPU executa 1 tick; verifica conclusão e expiração de quantum.
        for cpu in self.cpus:
            if cpu.tarefa_atual is None:
                cpu.tempo_desligada += 1
                cpu.desligar()
                continue

            cpu.tarefa_atual.tempo_executado += 1
            cpu.tarefa_atual.tempo_no_quantum += 1

            if cpu.tarefa_atual.is_concluida():
                cpu.tarefa_atual.estado = "Concluida"
                self.fila_concluidas.append(cpu.tarefa_atual)
                cpu.tarefa_atual = None

            elif cpu.tarefa_atual.tempo_no_quantum >= self.quantum:
                # Quantum esgotado: devolve à fila de prontas para reescalonamento.
                cpu.tarefa_atual.estado = "Pronta"
                cpu.tarefa_atual.tempo_no_quantum = 0
                self.fila_prontas.append(cpu.tarefa_atual)
                cpu.tarefa_atual = None

        self.relogio += 1
