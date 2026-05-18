from estruturas import Task

PADRAO_ALGORITMO = "SRTF"
PADRAO_QUANTUM = 2
PADRAO_CPUS = 2
PADRAO_PRIORIDADE = 1
PADRAO_COR = "AAAAAA"


def _ler_campo_int(campos, indice, padrao, nome, linha=None):
    """Lê um campo inteiro de uma lista de strings, retornando o padrão se ausente/inválido."""
    try:
        return int(campos[indice].strip()) if len(campos) > indice and campos[indice].strip() else padrao
    except ValueError:
        prefixo = f"linha {linha}: " if linha else ""
        print(f"Aviso: {prefixo}{nome} inválido, usando {padrao}.")
        return padrao


def ler_arquivo_configuracao(caminho_arquivo):
    try:
        with open(caminho_arquivo, 'r', encoding='utf-8') as f:
            linhas = [l.strip() for l in f if l.strip()]
    except FileNotFoundError:
        print(f"Erro: arquivo '{caminho_arquivo}' não encontrado.")
        return None

    if len(linhas) < 2:
        print("Erro: o arquivo deve ter pelo menos 2 linhas.")
        return None

    cfg = linhas[0].split(';')

    algoritmo = cfg[0].strip().upper() if cfg[0].strip() else PADRAO_ALGORITMO
    quantum = _ler_campo_int(cfg, 1, PADRAO_QUANTUM,   "quantum")
    qtde_cpus = _ler_campo_int(cfg, 2, PADRAO_CPUS,      "qtde_cpus")
    alpha = _ler_campo_int(cfg, 3, None,              "alpha")  # Projeto B

    # Req. Geral 2: mínimo de 2 CPUs.
    if qtde_cpus is not None and qtde_cpus < 2:
        print(
            f"Aviso: qtde_cpus={qtde_cpus} menor que o mínimo. Usando {PADRAO_CPUS}.")
        qtde_cpus = PADRAO_CPUS

    # --- Linhas seguintes: uma tarefa por linha ---
    tarefas = []
    for i, linha in enumerate(linhas[1:], start=2):
        dados = linha.split(';')

        if not dados[0].strip():
            print(f"Aviso: linha {i} sem ID, ignorada.")
            continue

        id_tarefa = dados[0].strip()
        cor = dados[1].strip().upper() if len(
            dados) > 1 and dados[1].strip() else PADRAO_COR
        ingresso = _ler_campo_int(dados, 2, 0,                "ingresso",  i)
        duracao = _ler_campo_int(dados, 3, 1,                "duracao",   i)
        prioridade = _ler_campo_int(
            dados, 4, PADRAO_PRIORIDADE, "prioridade", i)
        lista_eventos = dados[5].strip() if len(dados) > 5 else ""

        tarefas.append(Task(id_tarefa, cor, ingresso,
                       duracao, prioridade, lista_eventos))

    return {
        "algoritmo": algoritmo,
        "quantum":   quantum,
        "cpus":      qtde_cpus,
        "alpha":     alpha,
        "tarefas":   tarefas
    }
