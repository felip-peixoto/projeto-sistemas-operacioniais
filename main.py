from parser_config import ler_arquivo_configuracao
from simulador import Simulador


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
    print("="*45)


def main():
    print("Iniciando o Sistema Operacional...")
    config = ler_arquivo_configuracao("teste.txt")
    if not config:
        return

    motor = Simulador(config)

    while True:
        # Agora imprimimos o Gantt e depois as filas
        imprimir_gantt(motor)
        imprimir_estado_atual(motor)

        comando = input(
            "\n[ENTER] Avançar | [V] Voltar | [S] Sair: ").strip().upper()

        if comando == 'S':
            break
        elif comando == 'V':
            if motor.retroceder_tick():
                print("\n⏪ Voltando no tempo...")
        else:
            motor.avancar_tick()
            print("\n⏩ Avançando 1 tick...")


if __name__ == "__main__":
    main()
