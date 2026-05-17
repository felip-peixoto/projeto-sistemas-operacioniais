import copy
from estruturas import CPU
from escalonadores import executar_escalonador


class Simulador:
    def __init__(self, config):
        algoritmos_suportados = ["SRTF", "PRIOP"]
        if config["algoritmo"] not in algoritmos_suportados:
            print(
                f"🛑 ERRO FATAL: O algoritmo '{config['algoritmo']}' não foi implementado!")
            print(f"Algoritmos suportados: {algoritmos_suportados}")
            exit(1)  # Encerra o programa na hora
        # Config é o dicionario do parser_config

        self.relogio = 0
        self.algoritmo = config["algoritmo"]
        self.quantum = config["quantum"]

        self.cpus = [CPU(i) for i in range(config["cpus"])]

        # Filas de gerenciamento
        self.fila_novas = config["tarefas"]
        self.fila_prontas = []
        self.fila_concluidas = []
        self.fila_suspensas = []  # Solução do Ponto 2
        self.houve_sorteio_neste_tick = False  # Solução do Ponto 5
        self.historico_estados = []
        self.total_tarefas_sistema = len(config["tarefas"])

    def salvar_snapshot(self):
        snapshot = {
            "tempo": self.relogio,
            "cpus": copy.deepcopy(self.cpus),
            "fila_novas": copy.deepcopy(self.fila_novas),  # Solução do Ponto 1
            "fila_prontas": copy.deepcopy(self.fila_prontas),
            "fila_suspensas": copy.deepcopy(self.fila_suspensas),
            "fila_concluidas": copy.deepcopy(self.fila_concluidas),
            "sorteio": self.houve_sorteio_neste_tick  # <--- SALVA AQUI
        }
        self.historico_estados.append(snapshot)

    def avancar_tick(self):
        """
        Executa apenas UM instante de tempo (passo-a-passo).
        É isso que a UI vai chamar quando o usuário apertar 'Avançar'.
        """
        # Verifica se já acabou tudo — evita avanços infinitos
        if getattr(self, 'total_tarefas_sistema', None) is not None and len(self.fila_concluidas) >= self.total_tarefas_sistema:
            return

        # 2. Chegada de Novas Tarefas
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

        # ==========================================
        # 3. AQUI ENTRARÁ O ESCALONADOR
        # (Ele vai organizar as tarefas nas CPUs)
        if precisa_escalonar:
            self.fila_prontas, sorteio = executar_escalonador(
                self.fila_prontas, self.cpus, self.algoritmo
            )
            if sorteio:
                self.houve_sorteio_neste_tick = True
        # ==========================================

            # 1. Tira a foto do estado ATUAL (antes de modificar) para o botão de retroceder
        self.salvar_snapshot()

        # 4. Executar as tarefas nas CPUs
        for cpu in self.cpus:
            if cpu.tarefa_atual is not None:
                cpu.tarefa_atual.tempo_executado += 1
                cpu.tarefa_atual.tempo_no_quantum += 1  # <--- Relógio do quantum avança!

                # Regra 1: A tarefa terminou de vez?
                if cpu.tarefa_atual.is_concluida():
                    cpu.tarefa_atual.estado = "Concluida"
                    self.fila_concluidas.append(cpu.tarefa_atual)
                    cpu.tarefa_atual = None

                # Regra 2: Estourou o Quantum? (Só aplica se o algoritmo for PRIOP)
                elif self.algoritmo == "PRIOP" and cpu.tarefa_atual.tempo_no_quantum == self.quantum:
                    cpu.tarefa_atual.estado = "Pronta"
                    cpu.tarefa_atual.tempo_no_quantum = 0  # Zera para a próxima rodada
                    self.fila_prontas.append(
                        cpu.tarefa_atual)  # Vai pro fim da fila
                    cpu.tarefa_atual = None  # Chuta da CPU!
            else:
                cpu.tempo_desligada += 1
                cpu.desligar()

        # 5. O tempo passa...
        self.relogio += 1

        # Previsão para o Projeto B: Aqui será o momento ideal para verificar
        # se alguma tarefa precisa sair do estado "Suspensa" após um I/O.

    def retroceder_tick(self):
        if len(self.historico_estados) == 0:
            return False

        estado_anterior = self.historico_estados.pop()
        self.relogio = estado_anterior["tempo"]
        self.cpus = estado_anterior["cpus"]
        self.fila_novas = estado_anterior["fila_novas"]  # Restauro do Ponto 1
        self.fila_prontas = estado_anterior["fila_prontas"]
        self.fila_suspensas = estado_anterior["fila_suspensas"]
        self.fila_concluidas = estado_anterior["fila_concluidas"]
        return True
