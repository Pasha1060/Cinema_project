import json
from urllib.parse import parse_qs

from asgiref.sync import sync_to_async
from channels.generic.websocket import AsyncWebsocketConsumer

from .seat_locks import (
    clear_expired_locks,
    get_locked_seats,
    lock_seat,
    release_seat,
    release_seats_by_client,
)


class SeatConsumer(AsyncWebsocketConsumer):
    async def connect(self):
        self.session_id = self.scope['url_route']['kwargs']['session_id']
        self.room_group_name = f'session_{self.session_id}'

        query_params = parse_qs(self.scope['query_string'].decode())
        self.client_id = query_params.get('client_id', [self.channel_name])[0]

        await self.channel_layer.group_add(
            self.room_group_name,
            self.channel_name
        )

        await self.accept()
        expired_locks = await sync_to_async(clear_expired_locks)(self.session_id)

        for lock_data in expired_locks:
            await self.channel_layer.group_send(
                self.room_group_name,
                {
                    'type': 'seat_status_message',
                    'event_type': 'seat_released',
                    'seat_id': lock_data.get('seat_id'),
                    'row': lock_data.get('row'),
                    'number': lock_data.get('number'),
                    'status': 'free',
                    'sender_channel_name': None,
                }
            )
        #released_locks = await sync_to_async(release_seats_by_client)(
        #    self.session_id,
        #   self.client_id
        #)

        #for lock_data in released_locks:
        #    await self.channel_layer.group_send(
        #        self.room_group_name,
        #        {
        #            'type': 'seat_status_message',
        #            'event_type': 'seat_released',
        #            'seat_id': lock_data.get('seat_id'),
        #            'row': lock_data.get('row'),
        #            'number': lock_data.get('number'),
        #            'status': 'free',
        #            'sender_channel_name': None,
        #        }
        #    )
        locked_seats = await sync_to_async(get_locked_seats)(self.session_id)

        await self.send(text_data=json.dumps({
            'type': 'initial_locked_seats',
            'locked_seats': locked_seats,
        }))

    async def disconnect(self, close_code):
        released_locks = await sync_to_async(release_seats_by_client)(
            self.session_id,
            self.client_id
        )

        await self.channel_layer.group_discard(
            self.room_group_name,
            self.channel_name
        )

        for lock_data in released_locks:
            await self.channel_layer.group_send(
                self.room_group_name,
                {
                    'type': 'seat_status_message',
                    'event_type': 'seat_released',
                    'seat_id': lock_data.get('seat_id'),
                    'row': lock_data.get('row'),
                    'number': lock_data.get('number'),
                    'status': 'free',
                    'sender_channel_name': None,
                }
            )

    async def receive(self, text_data):
        data = json.loads(text_data)

        event_type = data.get('type')
        seat_id = data.get('seat_id')
        row = data.get('row')
        number = data.get('number')
        status = data.get('status')
        client_id = data.get('client_id', self.client_id)

        if event_type == 'seat_selected':
            is_locked = await sync_to_async(lock_seat)(
                self.session_id,
                seat_id,
                client_id,
                row,
                number
            )

            if not is_locked:
                await self.send(text_data=json.dumps({
                    'type': 'seat_lock_failed',
                    'seat_id': seat_id,
                    'message': 'Место уже выбрано другим пользователем.',
                }))
                return

        if event_type == 'seat_released':
            await sync_to_async(release_seat)(
                self.session_id,
                seat_id,
                client_id
            )

        await self.channel_layer.group_send(
            self.room_group_name,
            {
                'type': 'seat_status_message',
                'event_type': event_type,
                'seat_id': seat_id,
                'row': row,
                'number': number,
                'status': status,
                'sender_channel_name': self.channel_name,
            }
        )

    async def seat_status_message(self, event):
        if event.get('sender_channel_name') == self.channel_name:
            return

        await self.send(text_data=json.dumps({
            'type': event.get('event_type'),
            'seat_id': event.get('seat_id'),
            'row': event.get('row'),
            'number': event.get('number'),
            'status': event.get('status'),
        }))