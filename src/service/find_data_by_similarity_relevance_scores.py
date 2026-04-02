from src.dataprovider.chroma_db import similarity_search_with_relevance_scores

def find_data_by_similarity_relevance_scores(embeddings, query, k):
    return similarity_search_with_relevance_scores(embeddings, query, k)