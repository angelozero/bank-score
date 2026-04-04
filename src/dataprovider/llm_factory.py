import os
from dotenv import load_dotenv
from langchain.chat_models import init_chat_model
from langchain.embeddings import init_embeddings

# Load environment variables from .env file
load_dotenv()

# Configuration constants retrieved from environment
MODEL_NAME = os.getenv("MODEL_NAME")
API_KEY = os.getenv("API_KEY")
BASE_URL = os.getenv("BASE_URL")


def chat_model():
    print("[XX] - Inicializando LLM para serviço de chat...")
    """
    Initializes and returns the Chat Model (LLM) instance.
    Uses LiteLLM proxy via OpenAI-compatible interface.
    """
    return init_chat_model(
        model=MODEL_NAME,
        model_provider="openai",
        api_key=API_KEY,
        base_url=BASE_URL,
    )


def get_embedding():
    print("[03] - Inicializando LLM para serviço de embeddings...")
    """
    Initializes and returns the Embeddings instance.
    Configured to handle float encoding format for Ollama compatibility.
    """
    return init_embeddings(
        model=MODEL_NAME,
        provider="openai",
        api_key=API_KEY,
        base_url=BASE_URL,
        # Force float encoding to avoid LiteLLM/Ollama base64 errors
        model_kwargs={"encoding_format": "float"},
    )
