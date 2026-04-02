from src.service.generate_prompt import generate_prompt
from src.service.get_embedding_service import get_embedding
from src.service.upload_files import upload_files_execute
from src.service.get_chat_model import get_chat_model
from src.service.find_data_by_similarity_relevance_scores import find_data_by_similarity_relevance_scores

def execute():
    print("Executing RAG service...")
    # Executar este trecho apenas uma vez para carregar os dados e persistir no banco de dados Chroma
    # upload_files_execute()
    
    # query = input(f"\nDigite sua pergunta: ")
    # if not query:
    #     print("Nenhuma pergunta fornecida.")
    #     return
    
    query = "Quais são as categorias da TABELA DE SCORE DE CRÉDITO?"
    embedding = get_embedding()
    
    results = find_data_by_similarity_relevance_scores(embeddings=embedding, query=query, k=3)
    
    if not results or results[0][1] < 0.2:
        print(f"\n\nNão foi possível encontrar resultados relevantes.\n\n")
        return
    
    context_text = "\n\n---\n\n".join([doc.page_content for doc, _score in results])
    
    prompt = generate_prompt(context_text, query)
    data = get_chat_model()
    response = data.invoke(prompt)
    
    print(f"\nResposta:\n{response.content}\n\n")