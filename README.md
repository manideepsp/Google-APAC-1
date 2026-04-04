# Google-APAC-1

## Run Entire App With One Command

Start all required services in one terminal (YouTube gRPC, Sheets gRPC, and FastAPI UI/API):

```powershell
poetry run python -m app.startup
```

After startup:

- UI: http://127.0.0.1:8000/
- Health: http://127.0.0.1:8000/health

Press `Ctrl+C` in that same terminal to stop everything together.
