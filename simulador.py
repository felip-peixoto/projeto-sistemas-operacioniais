import copy
from estruturas import CPU

class Simulador:
    def __init__(self, config):
        #Config é o dicionario do parser_config
        self.relogio = 0
        self.algoritmo = config["algoritmo"]
        self.quantum = config["quantum"]
        
        self.cpus = [CPU(i) for i in range(config["cpus"])]
        
        # Filas de gerenciamento
        self.fila_novas = config["tarefas"]  # Tarefas que ainda vão ingressar
        self.fila_prontas = []               # Tarefas prontas para rodar
        self.fila_concluidas = []            # Tarefas que já terminaram
        
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

    def simular(self):
        total_tarefas = len(self.fila_novas)
        
        while len(self.fila_concluidas) < total_tarefas:
            tarefas_a_remover = []
            for tarefa in self.fila_novas:
                if tarefa.ingresso == self.relogio:
                    tarefa.estado = "Pronta"
                    self.fila_prontas.append(tarefa)
                    tarefas_a_remover.append(tarefa)

            for t in tarefas_a_remover:
                self.fila_novas.remove(t)

            # ==========================================
            # AQUI ENTRARÁ O ESCALONADOR 
            # ==========================================
            
            for cpu in self.cpus:
                if cpu.tarefa_atual is not None:
                    cpu.tarefa_atual.tempo_executado += 1
                    
                    if cpu.tarefa_atual.is_concluida():
                        cpu.tarefa_atual.estado = "Concluida"
                        self.fila_concluidas.append(cpu.tarefa_atual)
                        cpu.tarefa_atual = None # Libera a CPU
                else:
                    cpu.tempo_desligada += 1

            self.salvar_snapshot()

            self.relogio += 1

            #Será removida no furuto, apenas coloquei pois ainda não implementei os escalonadores.            
            if self.relogio > 1000:
                print("ERRO: Simulação travou em 1000 ticks!")
                break
                
        print(f"Simulação finalizada no tick {self.relogio}!")