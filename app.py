
from pydantic import BaseModel
import uvicorn
from fastapi import FastAPI
from src.service.upload_files import upload_files_execute
from src.service.rag_service import execute as rag_execute
from service.rag_service import execute as rag_langgraph_execute


app = FastAPI()

class SolicitacaoRAG(BaseModel):
    cpf: str
    valor: float

@app.get("/")
def root():
    # upload_files_execute()
    
    # query = input(f"\nDigite sua pergunta: ")
    # if not query:
    #     print("Nenhuma pergunta fornecida.")
    #     return
    
    # rag_execute(query)
    response = rag_langgraph_execute("123.456.789-00", 10000.0)
    return {"response": response}

@app.post("/")
def root(dados: SolicitacaoRAG):
    # O FastAPI extrai o JSON e transforma no objeto 'dados'
    # Você acessa os valores como atributos do objeto
    response = rag_langgraph_execute(dados.cpf, dados.valor)
    
    return {
        "status": "sucesso",
        "response": response
    }

if __name__ == "__main__":
    uvicorn.run(app, host="0.0.0.0", port=8000)