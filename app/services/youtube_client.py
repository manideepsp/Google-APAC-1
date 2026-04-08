import os

import grpc
from app.services import youtube_pb2 as pb2
from app.services import youtube_pb2_grpc as pb2_grpc


def get_youtube_client():
    host = str(os.getenv("YOUTUBE_GRPC_HOST", "localhost")).strip() or "localhost"
    port = str(os.getenv("YOUTUBE_GRPC_PORT", "50051")).strip() or "50051"
    channel = grpc.insecure_channel(f"{host}:{port}")
    return pb2_grpc.YouTubeServiceStub(channel)


def get_trending():
    client = get_youtube_client()
    return client.GetTrending(pb2.Empty())


def get_channel_analytics(channel_id: str):
    client = get_youtube_client()
    return client.GetChannelAnalytics(
        pb2.ChannelRequest(channel_id=channel_id)
    )