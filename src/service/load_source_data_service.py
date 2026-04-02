import os
from dotenv import load_dotenv
from langchain_community.document_loaders import PyPDFDirectoryLoader

load_dotenv()

BASE_PATH_FILES = os.getenv("BASE_PATH_FILES")

def load_source_data():
    loader_source = PyPDFDirectoryLoader(BASE_PATH_FILES)
    documents = loader_source.load()
    return documents