import grpc
from concurrent import futures

from app.services.sheets_helper import get_sheet
from app.services import sheets_pb2, sheets_pb2_grpc

TaskResponse = getattr(sheets_pb2, "TaskResponse")
Empty = getattr(sheets_pb2, "Empty")


class SheetsService(sheets_pb2_grpc.SheetsServiceServicer):

    def AddTask(self, request, context):
        print("Received task:", request.task)
        sheet = get_sheet()
        worksheet = sheet.worksheet("Tasks")

        print("Appending:", request.task)

        worksheet.append_row([
            request.task,
            request.status,
            request.priority,
            request.day
        ])

        print("Row appended")

        return TaskResponse(message="Task added")

    def ClearTasks(self, request, context):
        sheet = get_sheet()
        worksheet = sheet.worksheet("Tasks")
        worksheet.batch_clear(["A:D"])
        return Empty()


def serve():
    server = grpc.server(futures.ThreadPoolExecutor(max_workers=10))
    sheets_pb2_grpc.add_SheetsServiceServicer_to_server(
        SheetsService(), server
    )

    server.add_insecure_port("[::]:50052")
    server.start()

    print("Sheets gRPC running on 50052")
    server.wait_for_termination()


if __name__ == "__main__":
    serve()