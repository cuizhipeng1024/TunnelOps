#!/usr/bin/env python3
"""TunnelOps Agent - reverse tunnel client for internal devices."""

import asyncio
import json
import os
import sys

try:
    import websockets
except ImportError:
    print("Please install: pip install websockets")
    sys.exit(1)

SERVER = os.environ.get("TUNNELOPS_SERVER", "http://localhost:8080").rstrip("/")
TOKEN = os.environ.get("TUNNELOPS_TOKEN", "")
NAME = os.environ.get("TUNNELOPS_NAME", "agent")

WS_URL = SERVER.replace("https://", "wss://").replace("http://", "ws://")
WS_URL = f"{WS_URL}/api/tunnel/ws?token={TOKEN}"

tunnel_connections: dict[str, "TunnelConnection"] = {}


class TunnelConnection:
    def __init__(self, session_id: str, host: str, port: int, ws):
        self.session_id = session_id
        self.host = host
        self.port = port
        self.ws = ws
        self.reader = None
        self.writer = None

    async def start(self):
        self.reader, self.writer = await asyncio.open_connection(self.host, self.port)
        asyncio.create_task(self._read_loop())

    async def _read_loop(self):
        try:
            while True:
                data = await self.reader.read(4096)
                if not data:
                    break
                await self.ws.send(
                    json.dumps(
                        {
                            "type": "tunnel_data",
                            "session_id": self.session_id,
                            "data": data.hex(),
                        }
                    )
                )
        except Exception:
            pass
        finally:
            await self.ws.send(json.dumps({"type": "tunnel_closed", "session_id": self.session_id}))
            tunnel_connections.pop(self.session_id, None)
            if self.writer:
                self.writer.close()

    async def write(self, data: bytes):
        if self.writer:
            self.writer.write(data)
            await self.writer.drain()


async def handle_message(message: dict, ws) -> None:
    msg_type = message.get("type")
    session_id = message.get("session_id")

    if msg_type == "open_tunnel":
        host = message.get("host", "127.0.0.1")
        port = int(message.get("port", 22))
        try:
            conn = TunnelConnection(session_id, host, port, ws)
            await conn.start()
            tunnel_connections[session_id] = conn
            await ws.send(json.dumps({"type": "tunnel_ready", "session_id": session_id}))
        except Exception as exc:
            err = str(exc)
            await ws.send(
                json.dumps({"type": "tunnel_error", "session_id": session_id, "error": err})
            )

    elif msg_type == "tunnel_data":
        conn = tunnel_connections.get(session_id)
        if conn:
            data = bytes.fromhex(message["data"])
            await conn.write(data)

    elif msg_type == "close_tunnel":
        conn = tunnel_connections.pop(session_id, None)
        if conn and conn.writer:
            conn.writer.close()


async def run_agent() -> None:
    if not TOKEN:
        print("TUNNELOPS_TOKEN is required")
        sys.exit(1)

    print(f"TunnelOps Agent [{NAME}] connecting to {SERVER}")

    while True:
        try:
            async with websockets.connect(WS_URL, ping_interval=20, ping_timeout=60) as ws:
                print("Connected to server")
                async for raw in ws:
                    message = json.loads(raw)
                    await handle_message(message, ws)
        except Exception as exc:
            print(f"Connection lost: {exc}, reconnecting in 5s...")
            await asyncio.sleep(5)


if __name__ == "__main__":
    asyncio.run(run_agent())
