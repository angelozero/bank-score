from langchain.agents import create_agent

from src.agent.agent_base_model import AgentResponse
from src.service.generate_prompt import generate_prompt
from src.service.get_embedding_service import get_embedding
from src.service.upload_files import upload_files_execute
from src.service.get_chat_model import get_chat_model
from src.service.get_credit_analysis_prompt import get_credit_analysis_prompt
from src.service.find_data_by_similarity_relevance_scores import (
    find_data_by_similarity_relevance_scores,
)


def execute(query_question):
    print("Executing RAG service...")

    query = query_question or "Quais são as categorias da TABELA DE SCORE DE CRÉDITO?"

    embedding = get_embedding()
    
    results = find_data_by_similarity_relevance_scores(
        embeddings=embedding, query=query, k=3
    )

    if not results or results[0][1] < 0.2:
        print(f"\n\nNão foi possível encontrar resultados relevantes.\n\n")
        return

    context_text = "\n\n---\n\n".join([doc.page_content for doc, _score in results])

    prompt = generate_prompt(context_text, query)
    data = get_chat_model()
    response = data.invoke(prompt)

    print(f"\Response:\n{response.content}\n\n")
    return {"Response": response}