import grpc
from concurrent import futures

from app.services.youtube_helper import fetch_trending_videos
import app.services.youtube_pb2 as pb2
import app.services.youtube_pb2_grpc as pb2_grpc


class YouTubeService(pb2_grpc.YouTubeServiceServicer):


    def GetTrending(self, request, context):
        try:
            data = fetch_trending_videos()

            return pb2.TrendingResponse(
                titles=data["titles"],
                topics=data["channels"]  # using channels as topics proxy
            )

        except Exception as e:
            context.set_details(str(e))
            context.set_code(grpc.StatusCode.INTERNAL)
            return pb2.TrendingResponse()

    def GetChannelAnalytics(self, request, context):
        return pb2.AnalyticsResponse(
            growth="increasing",
            top_videos=[
                "AI tools video",
                "Automation tutorial"
            ]
        )


def serve():
    server = grpc.server(futures.ThreadPoolExecutor(max_workers=10))
    pb2_grpc.add_YouTubeServiceServicer_to_server(YouTubeService(), server)
    
    server.add_insecure_port("[::]:50051")
    server.start()
    
    print("YouTube gRPC server running on port 50051")
    server.wait_for_termination()


if __name__ == "__main__":
    serve()