import uvicorn
from fastapi import FastAPI
from src.service.rag_service import execute as rag_execute
app = FastAPI()

@app.get("/")
def root():
    response = rag_execute()
    return {"response": response}

if __name__ == "__main__":
    uvicorn.run(app, host="0.0.0.0", port=8000)