import random


def obter_tupla_desempate(tarefa, tarefas_executavam_antes):
    """
      1. Continuidade
      2. Instante de ingresso
      3. Duração total
      4. Sorteio
    """
    estava_executando = 0 if tarefa in tarefas_executavam_antes else 1
    return (estava_executando, tarefa.ingresso, tarefa.duracao, random.random())


def executar_escalonador(fila_prontas, cpus, algoritmo):
    # Reúne candidatos: fila de prontas + tarefas que ocupavam as CPUs.
    # As CPUs são esvaziadas aqui; a realocação ocorre ao final.
    candidatas = fila_prontas.copy()
    tarefas_executavam_antes = []

    for cpu in cpus:
        if cpu.tarefa_atual is not None:
            candidatas.append(cpu.tarefa_atual)
            tarefas_executavam_antes.append(cpu.tarefa_atual)
            cpu.tarefa_atual = None

    if not candidatas:
        return [], False

    def obter_chave_primaria(t):
        if algoritmo == "SRTF":
            return t.duracao - t.tempo_executado   # menor tempo restante primeiro
        elif algoritmo == "PRIOP":
            return -t.prioridade                   # maior prioridade primeiro
        return 0

    # Detecta empate nos critérios determinísticos para sinalizar sorteio no Gantt.
    houve_sorteio = False
    chaves_vistas = set()
    for t in candidatas:
        chave = (
            obter_chave_primaria(t),
            0 if t in tarefas_executavam_antes else 1,
            t.ingresso,
            t.duracao
        )
        if chave in chaves_vistas:
            houve_sorteio = True
        chaves_vistas.add(chave)

    candidatas.sort(key=lambda t: (
        obter_chave_primaria(t),
        *obter_tupla_desempate(t, tarefas_executavam_antes)
    ))

    # Realoca nas CPUs respeitando afinidade: tenta devolver cada tarefa à CPU
    # onde ela estava antes. Se essa CPU já foi tomada, usa qualquer livre.
    fila_prontas.clear()
    for tarefa in candidatas:
        cpu_alocar = (
            next(
                (c for c in cpus if c.tarefa_atual is None and c.ultima_tarefa == tarefa), None)
            or next((c for c in cpus if c.tarefa_atual is None), None)
        )

        if cpu_alocar is not None:
            cpu_alocar.alocar_tarefa(tarefa)
        else:
            tarefa.estado = "Pronta"
            fila_prontas.append(tarefa)

    return fila_prontas, houve_sorteio
