from src.dataprovider.chroma_db import persist_data_to_chroma_db

def save_data_db(chunks, embeddings):
    persist_data_to_chroma_db(chunks, embeddings)