from parser_config import ler_arquivo_configuracao
from simulador import Simulador
from frontend import iniciar_servidor_web


def imprimir_gantt(motor):
    """Lê o histórico e desenha o Gráfico de Gantt no terminal."""
    print("\n📊 GRÁFICO DE GANTT (Linha do Tempo):")

    # Desenha a régua de tempo em cima (00, 01, 02...)
    regua = "Tempo:  "
    for tick in range(motor.relogio + 1):
        regua += f" {tick:02d} "
    print(regua)

    # Desenha a linha de cada processador
    for i in range(len(motor.cpus)):
        linha = f"CPU {i}:  "

        # 1. Lê o que aconteceu no passado (histórico)
        for estado in motor.historico_estados:
            cpu_passado = estado["cpus"][i]
            if cpu_passado.tarefa_atual:
                linha += f"[{cpu_passado.tarefa_atual.id}] "
            else:
                linha += "[--] "  # Ociosa

        # 2. Lê o que está acontecendo no exato momento presente
        cpu_agora = motor.cpus[i]
        if cpu_agora.tarefa_atual:
            linha += f"[{cpu_agora.tarefa_atual.id}] "
        else:
            linha += "[--] "

        print(linha)


def imprimir_estado_atual(motor):
    """Mostra os bastidores das filas."""
    print(f"\n{'='*45}")
    print(f"🕒 BASTIDORES - TICK: {motor.relogio}")
    print(f"{'='*45}")
    print(f"📦 Fila de Novas: {[t.id for t in motor.fila_novas]}")
    print(f"⏳ Fila de Prontas: {[t.id for t in motor.fila_prontas]}")
    print(f"✅ Fila de Concluídas: {[t.id for t in motor.fila_concluidas]}")
    print(
        f"🎲 Houve Sorteio? {'SIM' if motor.houve_sorteio_neste_tick else 'NÃO'}")
    print("="*45)


def modificar_tarefa_manualmente(motor):
    """Requisito 3.4 e 1.5.2: Modificação manual do estado/propriedades da tarefa."""
    todas_tarefas = motor.fila_novas + motor.fila_prontas + motor.fila_concluidas
    for cpu in motor.cpus:
        if cpu.tarefa_atual:
            todas_tarefas.append(cpu.tarefa_atual)

    print("\n--- MODIFICAR TAREFA ---")
    print(f"Tarefas no sistema: {[t.id for t in todas_tarefas]}")
    id_alvo = input(
        "Digite o ID da tarefa que deseja alterar (ou ENTER para cancelar): ").strip()

    tarefa_encontrada = next(
        (t for t in todas_tarefas if t.id == id_alvo), None)
    if not tarefa_encontrada:
        print("Tarefa não encontrada.")
        return

    print(f"Editando Tarefa {tarefa_encontrada.id} | Duração: {tarefa_encontrada.duracao} | Prioridade: {tarefa_encontrada.prioridade} | Estado: {tarefa_encontrada.estado}")
    nova_duracao = input("Nova Duração (ENTER para manter): ").strip()
    nova_prioridade = input("Nova Prioridade (ENTER para manter): ").strip()
    novo_estado = input(
        "Forçar Estado [Suspensa, Pronta, Nova] (ENTER para manter): ").strip()

    if nova_duracao:
        tarefa_encontrada.duracao = int(nova_duracao)
    if nova_prioridade:
        tarefa_encontrada.prioridade = int(nova_prioridade)
    if novo_estado:
        tarefa_encontrada.estado = novo_estado
        print("Aviso: Mover a tarefa manualmente entre filas na interface do terminal é complexo, seu Frontend cuidará disso melhor. Status alterado na memória.")
    if novo_estado.lower() == "suspensa":
        # Procurar onde a tarefa está e remover
        if tarefa_encontrada in motor.fila_prontas:
            motor.fila_prontas.remove(tarefa_encontrada)

        for cpu in motor.cpus:
            if cpu.tarefa_atual == tarefa_encontrada:
                cpu.tarefa_atual = None

        tarefa_encontrada.estado = "Suspensa"
        motor.fila_suspensas.append(tarefa_encontrada)
        print(
            f"Tarefa {tarefa_encontrada.id} movida para a Fila de Suspensas.")
    print("Modificação aplicada!\n")


def executar_passo_a_passo(motor):
    """Modo 1: Com intervenção humana."""
    total_tarefas = len(motor.fila_novas)
    while len(motor.fila_concluidas) < motor.total_tarefas_sistema:
        imprimir_gantt(motor)
        imprimir_estado_atual(motor)

        comando = input(
            "\n[ENTER] Avançar | [V] Voltar | [M] Modificar Tarefa | [S] Sair: ").strip().upper()

        if comando == 'S':
            break
        elif comando == 'V':
            if motor.retroceder_tick():
                print("\n⏪ Voltando no tempo...")
        elif comando == 'M':
            modificar_tarefa_manualmente(motor)
        else:
            motor.avancar_tick()

    print("\n--- FIM DA SIMULAÇÃO PASSO A PASSO ---")
    imprimir_relatorio_ociosidade(motor)


def executar_completo(motor):
    """Modo 2: Execução direta (Requisito 1.5)."""
    print("\nRodando Execução Completa...")
    total_tarefas = len(motor.fila_novas)

    while len(motor.fila_concluidas) < total_tarefas:
        motor.avancar_tick()

        # Trava de segurança (opcional)
        if motor.relogio > 200:
            print("Abordado por limite de segurança de ticks.")
            break

    imprimir_gantt(motor)
    print("\n--- FIM DA SIMULAÇÃO COMPLETA ---")
    imprimir_relatorio_ociosidade(motor)


def imprimir_relatorio_ociosidade(motor):
    """Requisito 1.2: Relatório de CPU Ociosa."""
    print("\n📊 RELATÓRIO DE OCIOSIDADE DOS PROCESSADORES:")
    for cpu in motor.cpus:
        print(f"CPU {cpu.id}: Desligada/Ociosa por {cpu.tempo_desligada} ticks.")
    print("="*45)


def main():
    print("Iniciando o Sistema Operacional...")
    config = ler_arquivo_configuracao("teste.txt")
    if not config:
        return

    motor = Simulador(config)

    # escolha inicial: modo dev (CLI) ou web
    print("\nEscolha modo de inicialização:")
    print("1 - Modo Dev (CLI)")
    print("2 - Modo Web (HTTP)")
    modo = input("Opção (1/2) [1]: ").strip() or '1'

    if modo == '2':
        print("\nIniciando servidor web para controle da simulação (abra no navegador)...")
        iniciar_servidor_web(motor, host='127.0.0.1', port=8000)
        return

    print("\nSelecione o Modo de Execução (Req 1.5):")
    print("1 - Modo Passo a Passo (com controle manual)")
    print("2 - Execução Completa (resultado direto)")
    escolha = input("Opção: ").strip()

    if escolha == '2':
        executar_completo(motor)
    else:
        executar_passo_a_passo(motor)


if __name__ == "__main__":
    main()
