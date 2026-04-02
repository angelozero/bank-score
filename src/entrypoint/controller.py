from fastapi import FastAPI

app = FastAPI()

@app.get("/")
def home():
    return {"status": "online", "framework": "FastAPI", "manager": "uv"}