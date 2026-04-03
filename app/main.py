from fastapi import FastAPI

app = FastAPI()

@app.get("/")
def root():
    return {"message": "YouTube AI Agent running"}