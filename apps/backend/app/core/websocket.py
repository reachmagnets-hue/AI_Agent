from fastapi import WebSocket

class ConnectionManager:
    def __init__(self):
        self.active_connections: list[WebSocket] = []

    async def connect(self, websocket: WebSocket):
        await websocket.accept()
        self.active_connections.append(websocket)

    def disconnect(self, websocket: WebSocket):
        if websocket in self.active_connections:
            self.active_connections.remove(websocket)

    async def broadcast(self, message: dict):
        import asyncio
        for connection in self.active_connections:
            async def send_safe(conn):
                try:
                    await asyncio.wait_for(conn.send_json(message), timeout=2.0)
                except Exception:
                    pass
            asyncio.create_task(send_safe(connection))

websocket_manager = ConnectionManager()
