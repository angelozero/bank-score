from langchain.agents import create_agent

from src.agent.agent_langgraph_model import LangGraphSource, LangGraphAgentResponse
from src.service.get_chat_model import get_chat_model
from src.service.get_risk_analysis_prompt import get_risk_analysis
from src.service.get_embedding_service import get_embedding
from src.service.find_data_by_similarity_relevance_scores import (
    find_data_by_similarity_relevance_scores,
)
from src.tools.validate_credit_policy_tool import validate_credit_policy


def execute(cpf, amount):
    print("Executing RAG LANGGGRAPH service...")

    query = (
        f"Realize a auditoria de crédito para o valor de R$ {amount} "
        f"e CPF {cpf}. Verifique o enquadramento nas faixas de score, "
        "possíveis fatores de impedimento do Item 3 e regras de 'Geographic Override' do Item 7. "
        "Retorne o padrão do cliente e o relatório conforme o protocolo do Item 10."
    )

    # --- #
    # RAG #
    # --- #
    embedding = get_embedding()
    results = find_data_by_similarity_relevance_scores(
        embeddings=embedding, query=query, k=3
    )

    if not results or results[0][1] < 0.2:
        print(f"\n\nNão foi possível encontrar resultados relevantes.\n\n")
        return

    context_text = "\n".join([doc.page_content for doc, _score in results])

    model = get_chat_model()
    
    llm = model.bind_tools([validate_credit_policy])

    structured_llm = llm.with_structured_output(LangGraphAgentResponse)

    prompt = get_risk_analysis(cpf, amount, context_text)

    try:
        response = structured_llm.invoke(prompt["messages"])

        if isinstance(response, LangGraphAgentResponse):
            response.sources = [
                LangGraphSource(
                    url=doc.metadata.get("url", "N/A"),
                    title=doc.metadata.get("title", "Documento"),
                    relevance_score=float(score),
                )
                for doc, score in results
            ]

            print(f"\nResposta Estruturada:\n{response.answer}")
            return response.answer

    except Exception as e:
        print(f"Erro ao processar resposta estruturada: {e}")
        return None
