from estruturas import Task


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

    algoritmo = config_sistema[0].strip().upper()
    quantum = int(config_sistema[1].strip())
    qtde_cpus = int(config_sistema[2].strip())

    alpha = int(config_sistema[3].strip()) if len(config_sistema) > 3 else None

    tarefas_criadas = []

    for linha in linhas[1:]:
        dados = linha.split(';')

        id_tarefa = dados[0].strip()
        cor = dados[1].strip().upper()
        ingresso = dados[2].strip()
        duracao = dados[3].strip()
        prioridade = dados[4].strip()

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


# TESTE SE O CODIGO ESTÀ FUNCIONANDO
if __name__ == "__main__":
    with open("teste.txt", "w") as f:
        f.write("PrioP; 2; 4\n")
        f.write("T1; FF0000; 0; 10; 1; \n")
        f.write("T2; 00FF00; 2; 5; 2; ML01:03\n")

    resultado = ler_arquivo_configuracao("teste.txt")

    print("--- DADOS DO SISTEMA ---")
    print(f"Algoritmo: {resultado['algoritmo']}")
    print(f"Quantum: {resultado['quantum']}")
    print(f"CPUs: {resultado['cpus']}")

    print("\n--- TAREFAS CARREGADAS ---")
    for t in resultado['tarefas']:
        print(
            f"ID: {t.id} | Cor: {t.cor} | T_inicial: {t.ingresso} | Duração: {t.duracao}")
