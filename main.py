from parser_config import ler_arquivo_configuracao
from simulador import Simulador
from frontend import iniciar_servidor_web


def main():
    print("Iniciando o Sistema Operacional...")

    # 1. Lê as configurações
    config = ler_arquivo_configuracao("config.txt")
    if not config:
        print("Erro: Não foi possível carregar o arquivo de configuração.")
        return

    # 2. Inicializa o motor do Sistema Operacional
    motor = Simulador(config)

    # 3. Trava a execução iniciando o Servidor Web
    print("\n🌐 Iniciando servidor Web para controle da simulação...")
    print("➡️ Acesse no seu navegador: http://127.0.0.1:8000")

    iniciar_servidor_web(motor, host='127.0.0.1', port=8000)


if __name__ == "__main__":
    main()
