"""Frontend do simulador de escalonamento.

Este script faz apenas a leitura inicial do arquivo config.txt e transforma
seu conteúdo em estruturas simples para validação no terminal.

Regras atendidas:
- Uso apenas de bibliotecas built-in do Python.
- Leitura com csv usando delimitador ';'.
- Tratamento de espaços em branco.
- Normalização do nome do algoritmo para minúsculas.
- Criação de um TCB simples para cada tarefa.
- Impressão da configuração final e da lista de tarefas.
"""

from __future__ import annotations

import csv
import os
from dataclasses import dataclass, asdict
from pathlib import Path
from pprint import pprint
from typing import Any, List


@dataclass
class TCB:
    """Task Control Block simplificado para representar uma tarefa."""

    id: str
    cor: str
    ingresso: int
    duracao: int
    prioridade: int
    lista_eventos: List[str]


def limpar_texto(valor: str) -> str:
    """Remove espaços em branco das pontas de uma string."""

    return valor.strip()


def normalizar_algoritmo(valor: str) -> str:
    """Padroniza o nome do algoritmo para comparação case-insensitive."""

    return limpar_texto(valor).lower()


def converter_inteiro(valor: str, nome_campo: str) -> int:
    """Converte um campo textual para inteiro com mensagem de erro clara."""

    texto = limpar_texto(valor)
    try:
        return int(texto)
    except ValueError as exc:
        raise ValueError(f"Campo '{nome_campo}' inválido: {valor!r}") from exc


def parse_lista_eventos(valor: str) -> List[str]:
    """Converte a lista de eventos em uma lista Python.

    O formato esperado é uma sequência textual separada por vírgulas.
    Exemplo: CPU,IO,CPU
    """

    texto = limpar_texto(valor)
    if not texto:
        return []

    eventos = [limpar_texto(item) for item in texto.split(",")]
    return [item for item in eventos if item]


def ler_configuracao(caminho_arquivo: str = "config.txt") -> dict:
    """Lê o arquivo de configuração e devolve um dicionário pronto para uso."""

    caminho = Path(caminho_arquivo)
    if not caminho.exists():
        raise FileNotFoundError(f"Arquivo não encontrado: {caminho.resolve()}")

    tarefas: List[TCB] = []

    with caminho.open(mode="r", encoding="utf-8", newline="") as arquivo:
        leitor = csv.reader(arquivo, delimiter=";")
        linhas = [linha for linha in leitor if any(campo.strip() for campo in linha)]

    if not linhas:
        raise ValueError("O arquivo de configuração está vazio.")

    if len(linhas[0]) < 3:
        raise ValueError(
            "A primeira linha deve conter: algoritmo; quantum; qtde_cpus"
        )

    algoritmo, quantum, qtde_cpus = linhas[0][:3]
    configuracao_sistema = {
        "algoritmo": normalizar_algoritmo(algoritmo),
        "quantum": converter_inteiro(quantum, "quantum"),
        "qtde_cpus": converter_inteiro(qtde_cpus, "qtde_cpus"),
    }

    for numero_linha, linha in enumerate(linhas[1:], start=2):
        if len(linha) < 6:
            raise ValueError(
                f"A linha {numero_linha} deve conter: id; cor; ingresso; duracao; prioridade; lista_eventos"
            )

        id_tarefa = limpar_texto(linha[0])
        cor = limpar_texto(linha[1])
        ingresso = converter_inteiro(linha[2], f"ingresso (linha {numero_linha})")
        duracao = converter_inteiro(linha[3], f"duracao (linha {numero_linha})")
        prioridade = converter_inteiro(linha[4], f"prioridade (linha {numero_linha})")
        lista_eventos = parse_lista_eventos(linha[5])

        tarefas.append(
            TCB(
                id=id_tarefa,
                cor=cor,
                ingresso=ingresso,
                duracao=duracao,
                prioridade=prioridade,
                lista_eventos=lista_eventos,
            )
        )

    return {
        "sistema": configuracao_sistema,
        "tarefas": [asdict(tarefa) for tarefa in tarefas],
    }


def imprimir_resultado(dados: dict) -> None:
    """Exibe o conteúdo carregado de forma fácil de validar no terminal."""

    print("=== CONFIGURAÇÃO DO SISTEMA ===")
    pprint(dados["sistema"], sort_dicts=False)
    print()
    print("=== LISTA DE TAREFAS (TCB) ===")
    for indice, tarefa in enumerate(dados["tarefas"], start=1):
        print(f"Tarefa {indice}:")
        pprint(tarefa, sort_dicts=False)
        print()


def exibir_estado_sistema(
    tick_atual: int,
    estado_cpus: Any,
    estado_tarefas: Any,
) -> str:
    """Limpa o terminal e mostra o estado atual do simulador.

    A função foi pensada para ser chamada a cada tick do escalonador.
    Ela exibe:
    - o tick atual;
    - quais tarefas estão rodando em cada CPU;
    - o estado das demais tarefas;
    - uma pausa para o usuário decidir se quer continuar.

    Retorna o comando digitado pelo usuário.
    """

    os.system("cls" if os.name == "nt" else "clear")

    print("=" * 70)
    print(f"TICK ATUAL: {tick_atual}")
    print("=" * 70)
    print()

    print("CPUs em execução:")
    if isinstance(estado_cpus, dict):
        for cpu, tarefa in estado_cpus.items():
            tarefa_exibida = tarefa if tarefa else "Ociosa"
            print(f"- {cpu}: {tarefa_exibida}")
    elif isinstance(estado_cpus, list):
        for indice, tarefa in enumerate(estado_cpus):
            tarefa_exibida = tarefa if tarefa else "Ociosa"
            print(f"- CPU {indice}: {tarefa_exibida}")
    else:
        pprint(estado_cpus, sort_dicts=False)

    print()
    print("Estado das outras tarefas:")
    if not estado_tarefas:
        print("- Nenhuma tarefa para exibir")
    elif isinstance(estado_tarefas, dict):
        for nome, info in estado_tarefas.items():
            print(f"- {nome}: {info}")
    else:
        for tarefa in estado_tarefas:
            if isinstance(tarefa, dict):
                identificador = tarefa.get("id", "?")
                estado = tarefa.get("estado", "indefinido")
                print(f"- {identificador}: {estado}")
            else:
                print(f"- {tarefa}")

    print()
    print("-" * 70)
    return input(
        "Pressione Enter para avançar para o próximo Tick ou digite um comando: "
    )


def main() -> None:
    """Ponto de entrada do frontend."""
    # Loop falso simulando o tempo passando só para testar a sua interface hoje
    for tick in range(1, 4):
        # Dados de mentira simulando o que o motor do Backend vai te mandar depois
        cpus_falsas = {"CPU 1": "P1", "CPU 2": "Ociosa"} 
        tarefas_falsas = {
            "P1": "Executando", 
            "P2": "Pronta", 
            "P3": "Suspensa"
        }
        
        # Chama a função nova que limpa a tela e pede o Enter
        exibir_estado_sistema(tick, cpus_falsas, tarefas_falsas)

if __name__ == "__main__":
    main()