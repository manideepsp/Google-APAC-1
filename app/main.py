from fastapi import FastAPI
from fastapi.staticfiles import StaticFiles
from app.api.routes import router
from app.db.alloydb import init_alloydb
from app.db.sqlite import init_db

init_db()
init_alloydb()

app = FastAPI()


@app.middleware("http")
async def add_no_cache_headers(request, call_next):
	response = await call_next(request)

	if request.method == "GET":
		content_type = response.headers.get("content-type", "")
		if any(
			media_type in content_type
			for media_type in (
				"text/html",
				"text/css",
				"application/javascript",
				"text/javascript",
			)
		):
			response.headers["Cache-Control"] = "no-store, max-age=0"
			response.headers["Pragma"] = "no-cache"
			response.headers["Expires"] = "0"

	return response


app.include_router(router)
app.mount("/", StaticFiles(directory="ui", html=True), name="ui")