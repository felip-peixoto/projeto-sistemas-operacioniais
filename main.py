from frontend import iniciar_servidor_web


def main():
    print("Iniciando o Sistema Operacional...")

    # Sobe o servidor sem nenhum cenário carregado.
    # O usuário escolhe o arquivo .txt pela interface web.
    print("\n🌐 Iniciando servidor Web para controle da simulação...")
    print("➡️ Acesse no seu navegador: http://127.0.0.1:8000")

    iniciar_servidor_web(None, host='127.0.0.1', port=8000)


if __name__ == "__main__":
    main()
