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


def executar_escalonador(fila_prontas, cpus, algoritmo):
    """
    Função unificada de escalonamento. 
    Serve para SRTF, PRIOP e qualquer outro algoritmo futuro.
    """
    candidatas = fila_prontas.copy()
    tarefas_executavam_antes = []

    # 1. Retira as tarefas que estavam a executar nas CPUs
    for cpu in cpus:
        if cpu.tarefa_atual is not None:
            candidatas.append(cpu.tarefa_atual)
            tarefas_executavam_antes.append(cpu.tarefa_atual)
            cpu.tarefa_atual = None

    if not candidatas:
        return [], False

    # 2. Define a regra de ordenação primária consoante o algoritmo
    def obter_chave_primaria(t):
        if algoritmo == "SRTF":
            return t.duracao - t.tempo_executado
        elif algoritmo == "PRIOP":
            return -t.prioridade
        # Quando fores fazer o Projeto B, basta adicionares o PRIOPEnv aqui!
        return 0

    # 3. VERIFICAÇÃO DE EMPATE/SORTEIO
    houve_sorteio = False
    chaves_vistas = set()
    for t in candidatas:
        chave_base = (
            obter_chave_primaria(t),
            0 if t in tarefas_executavam_antes else 1,
            t.ingresso,
            t.duracao
        )
        if chave_base in chaves_vistas:
            houve_sorteio = True
        chaves_vistas.add(chave_base)

    # 4. ORDENAÇÃO GERAL (Chave primária + Desempates)
    candidatas.sort(key=lambda t: (
        obter_chave_primaria(t),
        *obter_tupla_desempate(t, tarefas_executavam_antes)
    ))

    # 5. REALOCAÇÃO NAS CPUs (Afinidade de CPU)
    fila_prontas.clear()
    for tarefa in candidatas:
        # Tenta achar a CPU que tem afinidade com esta tarefa (e que esteja livre)
        cpu_preferida = next(
            (c for c in cpus if c.tarefa_atual is None and c.ultima_tarefa == tarefa), None)

        if cpu_preferida is not None:
            cpu_alocar = cpu_preferida
        else:
            # Se a CPU dela já foi ocupada, pega qualquer uma livre
            cpu_alocar = next(
                (c for c in cpus if c.tarefa_atual is None), None)

        if cpu_alocar is not None:
            cpu_alocar.alocar_tarefa(tarefa)
        else:
            tarefa.estado = "Pronta"
            fila_prontas.append(tarefa)

    return fila_prontas, houve_sorteio
