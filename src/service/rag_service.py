from src.service.get_llm_with_tools import get_llm_with_tools
from src.service.get_client_analysis_risk_descritpion import (
    get_client_analysis_risk_descritpion,
)
from src.service.get_context_by_results import get_context_by_results
from src.service.get_results_by_relevance_score import get_results_by_relevance_score
from src.agent.agent_langgraph_model import LangGraphSource, LangGraphAgentResponse
from src.service.get_risk_analysis_prompt import get_risk_analysis_prompt
from src.tools.validate_credit_policy_tool import validate_credit_policy


def execute(cpf, amount):
    print(f"\n[01] - Executing RAG service...")

    query = (
        f"Realize a auditoria de crédito para o valor de R$ {amount} "
        f"e CPF {cpf}. Verifique o enquadramento nas faixas de score, "
        "possíveis fatores de impedimento do Item 3 e regras de 'Geographic Override' do Item 7. "
        "Retorne o padrão do cliente e o relatório conforme o protocolo do Item 10."
    )

    results = get_results_by_relevance_score(query)

    context = get_context_by_results(results)

    analysis_risk_description = get_client_analysis_risk_descritpion(context, query)

    prompt = get_risk_analysis_prompt(cpf, amount, analysis_risk_description)

    llm = get_llm_with_tools(validate_credit_policy)

    try:
        response = llm.invoke(prompt["messages"])

        return {"data": response}

    except Exception as e:
        print(f"Erro ao processar resposta estruturada: {e}")
        return None
