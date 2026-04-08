import grpc
from concurrent import futures
import os

from app.services.youtube_helper import fetch_trending_videos
from app.services.youtube_helper import fetch_channel_analytics
import app.services.youtube_pb2 as pb2
import app.services.youtube_pb2_grpc as pb2_grpc

TrendingResponse = getattr(pb2, "TrendingResponse")
AnalyticsResponse = getattr(pb2, "AnalyticsResponse")


class YouTubeService(pb2_grpc.YouTubeServiceServicer):


    def GetTrending(self, request, context):
        try:
            data = fetch_trending_videos()

            return TrendingResponse(
                titles=data["titles"],
                topics=data["channels"]  # using channels as topics proxy
            )

        except Exception as e:
            context.set_details(str(e))
            context.set_code(grpc.StatusCode.INTERNAL)
            return TrendingResponse()

    def GetChannelAnalytics(self, request, context):
        try:
            channel_id = request.channel_id

            data = fetch_channel_analytics(channel_id)

            return AnalyticsResponse(
                growth=f"Subscribers: {data['subscriber_count']}",
                top_videos=[
                    video["title"] for video in data["top_videos"]
                ]
            )

        except Exception as e:
            context.set_details(str(e))
            context.set_code(grpc.StatusCode.INTERNAL)
            return AnalyticsResponse()


def serve():
    port = int(str(os.getenv("YOUTUBE_GRPC_PORT", "50051")).strip() or "50051")
    server = grpc.server(futures.ThreadPoolExecutor(max_workers=10))
    pb2_grpc.add_YouTubeServiceServicer_to_server(YouTubeService(), server)
    
    server.add_insecure_port(f"[::]:{port}")
    server.start()
    
    print(f"YouTube gRPC server running on port {port}")
    server.wait_for_termination()


if __name__ == "__main__":
    serve()