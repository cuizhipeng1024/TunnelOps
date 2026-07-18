import asyncio
import json
import logging
import secrets
import uuid
from dataclasses import dataclass, field
from datetime import datetime, timezone

from fastapi import WebSocket


logger = logging.getLogger("tunnelops.tunnel")


@dataclass
class TunnelSession:
    session_id: str
    agent_id: int
    queue: asyncio.Queue = field(default_factory=asyncio.Queue)
    closed: asyncio.Event = field(default_factory=asyncio.Event)


@dataclass
class ConnectedAgent:
    agent_id: int
    websocket: WebSocket
    connected_at: datetime = field(default_factory=lambda: datetime.now(timezone.utc))
    pending_sessions: dict[str, TunnelSession] = field(default_factory=dict)


class TunnelManager:
    def __init__(self) -> None:
        self._agents: dict[int, ConnectedAgent] = {}
        self._token_map: dict[str, int] = {}
        self._lock = asyncio.Lock()

    def generate_token(self) -> str:
        return secrets.token_urlsafe(32)

    async def register_agent(self, agent_id: int, token: str, websocket: WebSocket) -> None:
        async with self._lock:
            old = self._agents.get(agent_id)
            if old:
                try:
                    await old.websocket.close()
                except Exception:
                    pass
            self._agents[agent_id] = ConnectedAgent(agent_id=agent_id, websocket=websocket)
            self._token_map[token] = agent_id

    async def unregister_agent(self, agent_id: int, token: str) -> None:
        async with self._lock:
            self._agents.pop(agent_id, None)
            self._token_map.pop(token, None)

    def is_online(self, agent_id: int) -> bool:
        return agent_id in self._agents

    def get_agent(self, agent_id: int) -> ConnectedAgent | None:
        return self._agents.get(agent_id)

    async def send_to_agent(self, agent_id: int, message: dict) -> None:
        agent = self._agents.get(agent_id)
        if not agent:
            raise ConnectionError("Agent offline")
        await agent.websocket.send_text(json.dumps(message))

    async def open_tunnel(
        self, agent_id: int, host: str, port: int, timeout: float = 10.0
    ) -> TunnelSession:
        session_id = str(uuid.uuid4())
        session = TunnelSession(session_id=session_id, agent_id=agent_id)
        agent = self._agents.get(agent_id)
        if not agent:
            raise ConnectionError("Agent offline")
        agent.pending_sessions[session_id] = session
        await self.send_to_agent(
            agent_id,
            {
                "type": "open_tunnel",
                "session_id": session_id,
                "host": host,
                "port": port,
            },
        )
        try:
            msg = await asyncio.wait_for(session.queue.get(), timeout=timeout)
        except asyncio.TimeoutError as exc:
            agent.pending_sessions.pop(session_id, None)
            logger.error("Tunnel open timeout agent_id=%s host=%s port=%s", agent_id, host, port)
            raise ConnectionError("Tunnel open timeout") from exc
        if msg.get("type") != "tunnel_ready":
            agent.pending_sessions.pop(session_id, None)
            error = msg.get("error", "Tunnel open failed")
            logger.error("Tunnel open failed agent_id=%s host=%s port=%s error=%s", agent_id, host, port, error)
            raise ConnectionError(error)
        return session

    async def close_tunnel(self, session: TunnelSession) -> None:
        agent = self._agents.get(session.agent_id)
        if agent:
            agent.pending_sessions.pop(session.session_id, None)
            try:
                await self.send_to_agent(
                    session.agent_id,
                    {"type": "close_tunnel", "session_id": session.session_id},
                )
            except Exception:
                pass
        session.closed.set()

    async def relay_data(self, session: TunnelSession, data: bytes) -> None:
        await self.send_to_agent(
            session.agent_id,
            {
                "type": "tunnel_data",
                "session_id": session.session_id,
                "data": data.hex(),
            },
        )

    async def handle_agent_message(self, agent_id: int, raw: str) -> None:
        message = json.loads(raw)
        msg_type = message.get("type")
        session_id = message.get("session_id")
        agent = self._agents.get(agent_id)
        if not agent:
            return

        if msg_type in ("tunnel_ready", "tunnel_error"):
            session = agent.pending_sessions.get(session_id)
            if session:
                await session.queue.put(message)
        elif msg_type == "tunnel_data":
            session = agent.pending_sessions.get(session_id)
            if session:
                await session.queue.put(message)
        elif msg_type == "tunnel_closed":
            session = agent.pending_sessions.get(session_id)
            if session:
                session.closed.set()


tunnel_manager = TunnelManager()
