from fastapi import FastAPI
from fastapi.staticfiles import StaticFiles
from app.api.routes import router
from app.db.sqlite import init_db

init_db()

app = FastAPI()

app.include_router(router)
app.mount("/", StaticFiles(directory="ui", html=True), name="ui")