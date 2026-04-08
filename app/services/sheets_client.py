import os

import grpc
from app.services import sheets_pb2, sheets_pb2_grpc


_DEFAULT_TIMEOUT_SECONDS = float(os.getenv("SHEETS_GRPC_TIMEOUT_SECONDS", "3.0"))
TaskRequest = getattr(sheets_pb2, "TaskRequest")
Empty = getattr(sheets_pb2, "Empty")


def get_client():
    host = str(os.getenv("SHEETS_GRPC_HOST", "localhost")).strip() or "localhost"
    port = str(os.getenv("SHEETS_GRPC_PORT", "50052")).strip() or "50052"
    channel = grpc.insecure_channel(f"{host}:{port}")
    return sheets_pb2_grpc.SheetsServiceStub(channel)


def add_task(task, status, priority, day):
    client = get_client()

    return client.AddTask(
        TaskRequest(
            task=task,
            status=status,
            priority=priority,
            day=day
        ),
        timeout=_DEFAULT_TIMEOUT_SECONDS,
    )


def clear_tasks():
    client = get_client()
    return client.ClearTasks(Empty(), timeout=_DEFAULT_TIMEOUT_SECONDS)