import json
from channels.generic.websocket import AsyncWebsocketConsumer
from channels.db import database_sync_to_async
from celery.result import AsyncResult

class FileUploadConsumer(AsyncWebsocketConsumer):
    async def connect(self):
        print("WebSocket connection established")
        await self.channel_layer.group_add("file_upload", self.channel_name)
        await self.accept()

    async def disconnect(self, close_code):
        await self.channel_layer.group_discard("file_upload", self.channel_name)

    async def receive(self, text_data):
        # Optional: Handle incoming messages
        pass

    @database_sync_to_async
    def get_task_status(self, task_id):
        task_result = AsyncResult(task_id)
        return task_result.state

    async def send_task_update(self, task_id, status, file_name=None):
        await self.channel_layer.group_send(
            "file_upload",
            {
                "type": "task_update",
                "task_id": task_id,
                "status": status,
                "file_name": file_name
            }
        )

    async def task_update(self, event):
        print(f"Sending task update: {event}")
        await self.send(text_data=json.dumps({
            'task_id': event['task_id'],
            'status': event['status'],
            'file_name': event.get('file_name')
        }))