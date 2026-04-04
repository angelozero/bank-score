from src.service.get_embedding_service import get_embedding
from src.service.find_data_by_similarity_relevance_scores import (
    find_data_by_similarity_relevance_scores,
)

def get_results_by_relevance_score(query):
    print("[02] - Buscando resultados por pontuação de relevância...")
    embedding = get_embedding()
    return find_data_by_similarity_relevance_scores(
        embeddings=embedding, query=query, k=3
    )