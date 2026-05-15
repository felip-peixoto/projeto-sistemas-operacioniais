def chave_srtf(tarefa):
    """
    Função auxiliar que cria a 'nota' da tarefa para o algoritmo SRTF.
    O Python vai usar essa nota para ordenar a fila.
    """
    tempo_restante = tarefa.duracao - tarefa.tempo_executado

    # CRITÉRIOS DE DESEMPATE DO PROFESSOR:
    # 1. Menor tempo restante (Característica principal do SRTF)
    # 2. Maior Prioridade (Assumindo que 1 é a melhor prioridade, se for o inverso, mude para -tarefa.prioridade)
    # 3. Maior Duração Original (Para o Python colocar o MAIOR primeiro, usamos o sinal negativo)
    # 4. Ingresso mais antigo (Menor valor de ingresso primeiro)
    # 5. ID em ordem alfabética (String ordena alfabeticamente por padrão)

    return (
        tempo_restante,       # 1º critério (Crescente)
        tarefa.prioridade,    # 2º critério (Crescente)
        # 3º critério (Decrescente, note o sinal de menos!)
        -tarefa.duracao,
        tarefa.ingresso,      # 4º critério (Crescente)
        tarefa.id             # 5º critério (Alfabético)
    )


def escalonar_srtf(fila_prontas, cpus):
    """
    Executa a lógica do SRTF Preemptivo.
    Pega quem está rodando e quem está esperando, avalia todos, e decide quem fica na CPU.
    """
    # 1. Juntamos todo mundo que PODE rodar (quem está na fila + quem já está nas CPUs)
    candidatas = fila_prontas.copy()
    for cpu in cpus:
        if cpu.tarefa_atual is not None:
            candidatas.append(cpu.tarefa_atual)
            cpu.tarefa_atual = None  # Tiramos a tarefa da CPU temporariamente

    # Se não tem ninguém para rodar, a gente vaza
    if not candidatas:
        return []

    # 2. A MÁGICA: Ordenamos todas as candidatas usando a nossa chave de desempate
    candidatas.sort(key=chave_srtf)

    # 3. Colocamos os "vencedores" de volta nas CPUs disponíveis
    fila_prontas.clear()  # Limpamos a fila original para reconstruí-la

    for tarefa in candidatas:
        # Tenta achar uma CPU livre para a tarefa vencedora
        cpu_livre = next((c for c in cpus if c.tarefa_atual is None), None)

        if cpu_livre is not None:
            # Tem CPU livre! Aloca a tarefa e muda o estado
            cpu_livre.alocar_tarefa(tarefa)
        else:
            # Acabaram as CPUs. Quem sobrou volta para a fila de prontas
            tarefa.estado = "Pronta"
            fila_prontas.append(tarefa)

    # Retornamos a fila de prontas atualizada (o Python atualiza a referência, mas é bom retornar)
    return fila_prontas
