import grpc
from app.services import sheets_pb2, sheets_pb2_grpc
from app.services.sheets_pb2 import Empty


def get_client():
    channel = grpc.insecure_channel("localhost:50052")
    return sheets_pb2_grpc.SheetsServiceStub(channel)


def add_task(task, status, priority, day):
    client = get_client()

    return client.AddTask(
        sheets_pb2.TaskRequest(
            task=task,
            status=status,
            priority=priority,
            day=day
        )
    )


def clear_tasks():
    client = get_client()
    return client.ClearTasks(Empty())