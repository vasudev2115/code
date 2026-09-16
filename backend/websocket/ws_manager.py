"""
WebSocket connection manager with a typed event envelope.

Per the code review's suggested shape:
    {"type": "telemetry", "timestamp": "...", "data": {...}}
    {"type": "detection", "timestamp": "...", "data": {...}}

This lets the React client reliably distinguish message types instead
of guessing from the payload shape. Event types match the roadmap's
Phase 9 list: telemetry | detection | alert | mission_status | system_status
"""

import json
from datetime import datetime, timezone
from typing import List

from fastapi import WebSocket


class ConnectionManager:
    def __init__(self):
        self.active_connections: List[WebSocket] = []

    async def connect(self, websocket: WebSocket):
        await websocket.accept()
        self.active_connections.append(websocket)

    def disconnect(self, websocket: WebSocket):
        if websocket in self.active_connections:
            self.active_connections.remove(websocket)

    async def broadcast(self, event_type: str, data: dict):
        """Send a typed envelope to every connected client.

        Dead connections are pruned automatically -- a slow/disconnected
        client never blocks broadcasting to the others.
        """
        envelope = {
            "type": event_type,
            "timestamp": datetime.now(timezone.utc).isoformat(),
            "data": data,
        }
        message = json.dumps(envelope)

        dead_connections = []
        for connection in self.active_connections:
            try:
                await connection.send_text(message)
            except Exception:
                dead_connections.append(connection)

        for dead in dead_connections:
            self.disconnect(dead)


manager = ConnectionManager()
