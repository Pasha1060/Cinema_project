from django.urls import path

from . import consumers

websocket_urlpatterns = [
    path('ws/sessions/<int:session_id>/seats/', consumers.SeatConsumer.as_asgi()),
]