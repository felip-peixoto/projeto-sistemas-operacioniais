import random


def obter_tupla_desempate(tarefa, tarefas_executavam_antes):
    # Se a tarefa foi expulsa pelo Quantum, 'estava_executando' deve ser falso
    # para permitir o Round-Robin real.
    estava_executando = 0 if tarefa in tarefas_executavam_antes else 1

    return (
        estava_executando,
        tarefa.ingresso,
        tarefa.duracao,
        random.random()
    )


def escalonar_srtf(fila_prontas, cpus):
    candidatas = fila_prontas.copy()
    tarefas_executavam_antes = []

    for cpu in cpus:
        if cpu.tarefa_atual is not None:
            candidatas.append(cpu.tarefa_atual)
            tarefas_executavam_antes.append(cpu.tarefa_atual)
            cpu.tarefa_atual = None

    if not candidatas:
        return [], False

    # VERIFICAÇÃO DE EMPATE/SORTEIO
    houve_sorteio = False
    chaves_vistas = set()
    for t in candidatas:
        # A chave base do SRTF antes do fator random
        chave_base = (
            t.duracao - t.tempo_executado,
            0 if t in tarefas_executavam_antes else 1,
            t.ingresso,
            t.duracao
        )
        if chave_base in chaves_vistas:
            # Detetada uma colisão exata! O sorteio vai atuar.
            houve_sorteio = True
        chaves_vistas.add(chave_base)

    # Ordenação: 1º Tempo Restante, depois a tupla de desempate
    candidatas.sort(key=lambda t: (
        t.duracao - t.tempo_executado,
        *obter_tupla_desempate(t, tarefas_executavam_antes)
    ))

    # Realoca nas CPUs
    fila_prontas.clear()
    for tarefa in candidatas:
        cpu_livre = next((c for c in cpus if c.tarefa_atual is None), None)
        if cpu_livre is not None:
            cpu_livre.alocar_tarefa(tarefa)
        else:
            tarefa.estado = "Pronta"
            fila_prontas.append(tarefa)

    return fila_prontas, houve_sorteio


def escalonar_priop(fila_prontas, cpus):
    candidatas = fila_prontas.copy()
    tarefas_executavam_antes = []

    for cpu in cpus:
        if cpu.tarefa_atual is not None:
            candidatas.append(cpu.tarefa_atual)
            tarefas_executavam_antes.append(cpu.tarefa_atual)
            cpu.tarefa_atual = None

    if not candidatas:
        return [], False

    # VERIFICAÇÃO DE EMPATE/SORTEIO
    houve_sorteio = False
    chaves_vistas = set()
    for t in candidatas:
        # A chave base do PRIOP antes do fator random
        chave_base = (
            -t.prioridade,
            0 if t in tarefas_executavam_antes else 1,
            t.ingresso,
            t.duracao
        )
        if chave_base in chaves_vistas:
            # Detetada uma colisão exata! O sorteio vai atuar.
            houve_sorteio = True
        chaves_vistas.add(chave_base)

    # Ordenação: 1º Prioridade, depois desempates
    candidatas.sort(key=lambda t: (
        -t.prioridade,
        *obter_tupla_desempate(t, tarefas_executavam_antes)
    ))

    fila_prontas.clear()
    for tarefa in candidatas:
        cpu_livre = next((c for c in cpus if c.tarefa_atual is None), None)
        if cpu_livre is not None:
            cpu_livre.alocar_tarefa(tarefa)
        else:
            tarefa.estado = "Pronta"
            fila_prontas.append(tarefa)

    return fila_prontas, houve_sorteio
