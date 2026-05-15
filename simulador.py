import copy
from estruturas import CPU
from escalonadores import escalonar_srtf


class Simulador:
    def __init__(self, config):
        # Config é o dicionario do parser_config
        self.relogio = 0
        self.algoritmo = config["algoritmo"]
        self.quantum = config["quantum"]

        self.cpus = [CPU(i) for i in range(config["cpus"])]

        # Filas de gerenciamento
        self.fila_novas = config["tarefas"]
        self.fila_prontas = []
        self.fila_concluidas = []

        self.historico_estados = []

    def salvar_snapshot(self):
        snapshot = {
            "tempo": self.relogio,
            # copy.deepcopy cria um clone real dos objetos naquele exato milissegundo
            "cpus": copy.deepcopy(self.cpus),
            "fila_prontas": copy.deepcopy(self.fila_prontas),
            "fila_concluidas": copy.deepcopy(self.fila_concluidas)
        }
        self.historico_estados.append(snapshot)

    def avancar_tick(self):
        """
        Executa apenas UM instante de tempo (passo-a-passo).
        É isso que a UI vai chamar quando o usuário apertar 'Avançar'.
        """
        # Verifica se já acabou tudo
        if len(self.fila_concluidas) == len(self.fila_novas) + len(self.fila_prontas) + len(self.fila_concluidas):
            # Cuidado: a lógica acima é só ilustrativa para saber o total.
            # O melhor é ter salvo o 'total_tarefas' no __init__
            pass  # Continua executando caso precise desligar CPUs

        # 2. Chegada de Novas Tarefas
        tarefas_a_remover = []
        for tarefa in self.fila_novas:
            if tarefa.ingresso == self.relogio:
                tarefa.estado = "Pronta"
                self.fila_prontas.append(tarefa)
                tarefas_a_remover.append(tarefa)

        for t in tarefas_a_remover:
            self.fila_novas.remove(t)

        # ==========================================
        # 3. AQUI ENTRARÁ O ESCALONADOR
        # (Ele vai organizar as tarefas nas CPUs)
        if self.algoritmo == "SRTF":
            self.fila_prontas = escalonar_srtf(self.fila_prontas, self.cpus)
        # ==========================================

            # 1. Tira a foto do estado ATUAL (antes de modificar) para o botão de retroceder
        self.salvar_snapshot()

        # 4. Executar as tarefas nas CPUs
        for cpu in self.cpus:
            if cpu.tarefa_atual is not None:
                cpu.tarefa_atual.tempo_executado += 1

                if cpu.tarefa_atual.is_concluida():
                    cpu.tarefa_atual.estado = "Concluida"
                    self.fila_concluidas.append(cpu.tarefa_atual)
                    cpu.tarefa_atual = None  # Libera o processador
            else:
                cpu.tempo_desligada += 1

        # 5. O tempo passa...
        self.relogio += 1

        # Previsão para o Projeto B: Aqui será o momento ideal para verificar
        # se alguma tarefa precisa sair do estado "Suspensa" após um I/O.

    def retroceder_tick(self):
        """
        Volta o sistema exatamente para como estava no tick anterior.
        """
        if len(self.historico_estados) == 0:
            print("Já estamos no instante zero, não dá para retroceder mais!")
            return False

        # Pega a última "foto" salva e remove ela da lista do histórico
        estado_anterior = self.historico_estados.pop()

        # Restaura a memória do computador usando o backup
        self.relogio = estado_anterior["tempo"]
        self.cpus = estado_anterior["cpus"]
        self.fila_prontas = estado_anterior["fila_prontas"]
        self.fila_concluidas = estado_anterior["fila_concluidas"]
        # (O ideal é também salvar a fila_novas no snapshot para restaurá-la perfeitamente)

        return True
