from langchain_text_splitters import RecursiveCharacterTextSplitter

def generate_chunks(documents):
    spliter = RecursiveCharacterTextSplitter(
        chunk_size=2000, chunk_overlap=500, length_function=len, add_start_index=True
    )
    chunks = spliter.split_documents(documents)
    return chunks