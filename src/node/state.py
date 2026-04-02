import re

from typing import Annotated, Literal, TypedDict
from langgraph.graph import END, START, StateGraph, add_messages
from langgraph.checkpoint.memory import MemorySaver

class CreditState(TypedDict):
    # add_messages faz o "merge" automático das listas (histórico)
    messages: Annotated[list[str], add_messages]
    cpf_original: str
    cpf_masked: str
    amount: float
    is_approved: bool
    analysis_report: str

# ----- #
# Nodes #
# ----- # 
def guardrails_node(state: CreditState):
    """Mascara o CPF antes de qualquer processamento com LLM."""
    cpf = state["cpf_original"]
    masked = re.sub(r"(\d{3})\.(\d{3})\.(\d{3})-(\d{2})", r"\1.***.***-\4", cpf)
    return {"cpf_masked": masked, "messages": [f"CPF detectado e mascarado: {masked}"]}

def analysis_node(state: CreditState):
    """
    Simula a chamada ao LiteLLM + RAG.
    Aqui você usaria o seu prompt de 'Analista Sênior'.
    """
    amount = state["amount"]
    # Simulando lógica baseada no PDF de Política
    report = f"Análise para R$ {amount}: "
    if amount > 5000:
        report += "Valor excede limite automático. Requer Gerente."
    else:
        report += "Perfil elegível para aprovação automática."
        
    return {"analysis_report": report, "messages": [report]}

def manager_node(state: CreditState):
    """
    Nó de pausa. O grafo vai parar ANTES de entrar aqui.
    Quando o gerente aprova, o estado 'is_approved' é atualizado.
    """
    print("\n[Aguardando interação do Gerente no Banco de Dados...]")
    return state # O nó apenas retorna o estado atualizado após o 'resume'

# ----------- #
# Condicional #
# ----------- #
def route_request(state: CreditState) -> Literal["automatic", "manual"]:
    if state["amount"] > 5000:
        return "manual"
    return "automatic"

# ----- #
# GRAFO #
# ----- #
builder = StateGraph(CreditState)

builder.add_node("guardrails", guardrails_node)
builder.add_node("analysis", analysis_node)
builder.add_node("manager_approval", manager_node)
builder.add_node("auto_approve", lambda s: {"is_approved": True, "messages": ["Aprovado automaticamente"]})

builder.add_edge(START, "guardrails")
builder.add_edge("guardrails", "analysis")

# Roteamento Inteligente
builder.add_conditional_edges("analysis", route_request, {
    "manual": "manager_approval",
    "automatic": "auto_approve"
})

builder.add_edge("manager_approval", END)
builder.add_edge("auto_approve", END)

# 5. Compilação com Checkpointer e Interrupção
memory = MemorySaver()
graph = builder.compile(
    checkpointer=memory, 
    interrupt_before=["manager_approval"] # PAUSA
)

if __name__ == "__main__":
    try:
        graph.get_graph().draw_mermaid_png(output_file_path='graph.png')
        print("Grafo gerado com sucesso!")
    except Exception as e:
        print(f"Erro ao gerar imagem: {e}")