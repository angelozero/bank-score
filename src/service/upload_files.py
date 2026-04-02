from src.service.load_source_data_service import load_source_data
from src.service.generate_chunks_service import generate_chunks
from src.service.get_embedding_service import get_embedding
from src.service.save_data_db import save_data_db


def upload_files_execute():
    print("Executing upload files service...")
    documents = load_source_data()
    chunks = generate_chunks(documents)
    embeddinds = get_embedding()
    save_data_db(chunks, embeddinds)