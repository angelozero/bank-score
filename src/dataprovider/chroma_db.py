import os
from dotenv import load_dotenv
from langchain_chroma.vectorstores import Chroma
from langchain_ollama import embeddings

load_dotenv()

CHUNKS_DB_PATH = os.getenv("CHUNKS_DB_PATH")


def persist_data_to_chroma_db(chunks, embeddings):
    Chroma.from_documents(chunks, embeddings, persist_directory=CHUNKS_DB_PATH)
    print("Chunk Data Base persisted with success")

def similarity_search_with_relevance_scores(embeddings, query, k):
    print("Performing similarity search with relevance scores...")
    database = __get_data_from_chroma_db(embeddings)
    return database.similarity_search_with_relevance_scores(query, k=k)


def __get_data_from_chroma_db(embeddings):
    print("Getting data from Chroma DB...")
    return Chroma(persist_directory=CHUNKS_DB_PATH, embedding_function=embeddings)