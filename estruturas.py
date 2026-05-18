class Task:
    def __init__(self, id_tarefa, cor, ingresso, duracao, prioridade, lista_eventos):
        self.id = id_tarefa
        self.cor = cor
        self.ingresso = int(ingresso)
        self.duracao = int(duracao)
        self.prioridade = int(prioridade)
        self.lista_eventos = lista_eventos

        self.tempo_executado = 0
        self.tempo_no_quantum = 0
        self.estado = "Nova"

    def is_concluida(self):
        return self.tempo_executado >= self.duracao


class CPU:
    def __init__(self, id_cpu):
        self.id = id_cpu
        self.tarefa_atual = None
        self.ultima_tarefa = None
        self.tempo_desligada = 0
        self.ligada = True

    def alocar_tarefa(self, tarefa):
        self.tarefa_atual = tarefa
        self.ultima_tarefa = tarefa
        self.ligada = True
        self.tarefa_atual.estado = "Executando"

    def desligar(self):
        self.tarefa_atual = None
        self.ligada = False
