from fastapi import FastAPI
from app.api.routes import router
from app.db.sqlite import init_db

init_db()

app = FastAPI()

app.include_router(router)