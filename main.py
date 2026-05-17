from frontend import iniciar_servidor_web


def main():
    # Aqui iniciamos o sistema e deixamos o frontend web cuidar da simulacao.
    print("Iniciando o Sistema Operacional...")

    print("\nIniciando servidor web para controle da simulacao...")
    print("Acesse no navegador: http://127.0.0.1:8000")

    iniciar_servidor_web(None, host='127.0.0.1', port=8000)


if __name__ == "__main__":
    main()
