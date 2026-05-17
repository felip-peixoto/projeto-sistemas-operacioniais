from estruturas import Task

# Valores padrão do sistema (Req. 3.2)
# Usados quando um campo não é informado no arquivo de configuração.
PADRAO_ALGORITMO = "SRTF"
PADRAO_QUANTUM = 2
PADRAO_CPUS = 2
PADRAO_PRIORIDADE = 1
PADRAO_COR = "AAAAAA"  # cinza neutro


def ler_arquivo_configuracao(caminho_arquivo):
    try:
        with open(caminho_arquivo, 'r', encoding='utf-8') as arquivo:
            linhas = arquivo.readlines()
    except FileNotFoundError:
        print(f"Erro: O arquivo '{caminho_arquivo}' não foi encontrado.")
        return None

    linhas = [linha.strip() for linha in linhas if linha.strip()]

    if len(linhas) < 2:
        print("Erro: O arquivo de configuracao deve ter pelo menos 2 linhas.")
        return None

    config_sistema = linhas[0].split(';')

    # Lê cada campo da primeira linha, usando o valor padrão se estiver ausente ou vazio.
    algoritmo = config_sistema[0].strip().upper() if len(
        config_sistema) > 0 and config_sistema[0].strip() else PADRAO_ALGORITMO

    try:
        quantum = int(config_sistema[1].strip()) if len(
            config_sistema) > 1 and config_sistema[1].strip() else PADRAO_QUANTUM
    except ValueError:
        print(f"Aviso: quantum inválido, usando padrão ({PADRAO_QUANTUM}).")
        quantum = PADRAO_QUANTUM

    try:
        qtde_cpus = int(config_sistema[2].strip()) if len(
            config_sistema) > 2 and config_sistema[2].strip() else PADRAO_CPUS
    except ValueError:
        print(f"Aviso: qtde_cpus inválido, usando padrão ({PADRAO_CPUS}).")
        qtde_cpus = PADRAO_CPUS

    # Req. Geral 2: o sistema deve ter no mínimo 2 CPUs.
    # Se o valor informado for menor que 2, corrige para o mínimo em vez de abortar.
    if qtde_cpus < 2:
        print(
            f"Aviso: qtde_cpus={qtde_cpus} é menor que o mínimo. Usando {PADRAO_CPUS} CPUs.")
        qtde_cpus = PADRAO_CPUS

    # Alpha é opcional — usado apenas no Projeto B (PRIOPEnv).
    try:
        alpha = int(config_sistema[3].strip()) if len(
            config_sistema) > 3 and config_sistema[3].strip() else None
    except ValueError:
        alpha = None

    tarefas_criadas = []

    for i, linha in enumerate(linhas[1:], start=2):
        dados = linha.split(';')

        # ID é obrigatório — sem ele não tem como identificar a tarefa.
        if not dados[0].strip():
            print(f"Aviso: linha {i} sem ID, ignorada.")
            continue
        id_tarefa = dados[0].strip()

        # Cor: usa padrão cinza se ausente ou vazia.
        cor = dados[1].strip().upper() if len(
            dados) > 1 and dados[1].strip() else PADRAO_COR

        # Ingresso: usa 0 como padrão (tarefa já disponível desde o início).
        try:
            ingresso = int(dados[2].strip()) if len(
                dados) > 2 and dados[2].strip() else 0
        except ValueError:
            print(f"Aviso: ingresso inválido na linha {i}, usando 0.")
            ingresso = 0

        # Duração: usa 1 como padrão mínimo se ausente ou inválida.
        try:
            duracao = int(dados[3].strip()) if len(
                dados) > 3 and dados[3].strip() else 1
        except ValueError:
            print(f"Aviso: duracao inválida na linha {i}, usando 1.")
            duracao = 1

        # Prioridade: usa o padrão se ausente.
        try:
            prioridade = int(dados[4].strip()) if len(
                dados) > 4 and dados[4].strip() else PADRAO_PRIORIDADE
        except ValueError:
            print(
                f"Aviso: prioridade inválida na linha {i}, usando {PADRAO_PRIORIDADE}.")
            prioridade = PADRAO_PRIORIDADE

        # Lista de eventos: vazia por padrão (processada no Projeto B).
        lista_eventos = dados[5].strip() if len(dados) > 5 else ""

        nova_tarefa = Task(id_tarefa, cor, ingresso,
                           duracao, prioridade, lista_eventos)
        tarefas_criadas.append(nova_tarefa)

    return {
        "algoritmo": algoritmo,
        "quantum": quantum,
        "cpus": qtde_cpus,
        "alpha": alpha,
        "tarefas": tarefas_criadas
    }
