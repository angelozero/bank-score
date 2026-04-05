import re
import os
import sys

sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), "../..")))

from typing import Annotated, Literal, TypedDict
from urllib import response
from langgraph.graph import END, START, StateGraph, add_messages
from langgraph.checkpoint.memory import MemorySaver
from src.service.rag_service import execute as rag_execute


class CreditState(TypedDict):
    messages: Annotated[list[str], add_messages]
    cpf_original: str
    cpf_masked: str
    amount: float
    is_approved: bool
    analysis_report: str
    # Campo para a classificação da IA
    client_pattern: Literal["CONSERVADOR", "RISCO", "EXCECAO", "BLOQUEIO"]


# ----- #
# Nodes #
# ----- #
def guardrails_node(state: CreditState):
    """
    Agora este nó apenas limpa o estado ou prepara os dados,
    pois o LiteLLM cuidará do mascaramento.
    """
    print(f"\nCPF Original: {state['cpf_original']}\n")
    return {"cpf_masked": state["cpf_original"]}


def analysis_node(state: CreditState):
    """
    Nó de Auditoria Cognitiva (Simulando LiteLLM + RAG).
    A IA agora identifica o padrão baseado na política (itens 2, 7, 8 e 10).
    """
    amount = state["amount"]
    raw_cpf = state["cpf_original"]

    # --- SIMULAÇÃO DE CHAMADA RAG/LLM ---
    result = rag_execute(raw_cpf, amount)

    try:
        agent_response = result["response"]
        response_text = agent_response.answer
        masked_cpf = state["cpf_masked"]

    except (KeyError, AttributeError):
        response_text = "ERRO: Resposta da IA em formato inválido."

    print(f"\nCPF Mascarado: {state['cpf_masked']}\n")
    return {"analysis_report": response_text, "cpf": masked_cpf}


def manager_node(state: CreditState):
    """Nó de pausa para o Gerente."""
    print(f"\n[ALERTA] Gerente, analise o relatório: {state['analysis_report']}")
    return state


# ----------- #
# CONDICIONAL #
# ----------- #
def route_request(state: CreditState) -> Literal["to_manager", "to_auto_check"]:
    """
    Roteamento baseado no 'insight' da IA e não apenas no valor bruto.
    """
    pattern = state.get("client_pattern")

    # De acordo com sua nova estratégia, se for RISCO ou valor alto, vai para o Gerente
    if pattern == "RISCO" or state["amount"] > 5000:
        return "to_manager"

    return "to_auto_check"


# ----- #
# GRAFO #
# ----- #
builder = StateGraph(CreditState)

builder.add_node("guardrails", guardrails_node)
builder.add_node("analysis", analysis_node)
builder.add_node("manager_approval", manager_node)
# Nó final de sucesso (Simulando uma aprovação que ainda passa por check final)
builder.add_node(
    "auto_approve",
    lambda s: {
        "is_approved": True,
        "messages": ["SISTEMA: Processo concluído com aprovação."],
    },
)
builder.add_edge(START, "guardrails")
builder.add_edge("guardrails", "analysis")

# A lógica de decisão agora lê o 'client_pattern' gerado pela IA
builder.add_conditional_edges(
    "analysis",
    route_request,
    {"to_manager": "manager_approval", "to_auto_check": "auto_approve"},
)

builder.add_edge("manager_approval", END)
builder.add_edge("auto_approve", END)

# O grafo vai pausar SEMPRE que o destino for 'manager_approval'
memory = MemorySaver()
graph = builder.compile(checkpointer=memory, interrupt_before=["manager_approval"])

if __name__ == "__main__":
    try:
        graph.get_graph().draw_mermaid_png(output_file_path="graph.png")
        print("Grafo gerado com sucesso!")
    except Exception as e:
        print(f"Erro ao gerar imagem: {e}")
