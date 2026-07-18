import json
from datetime import datetime, timezone

from fastapi import APIRouter, Depends, WebSocket, WebSocketDisconnect, status
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.auth import decode_token, log_audit
from app.database import async_session
from app.models import Agent, AgentStatus, AuditAction, AuditLog, User
from app.tunnel import tunnel_manager

router = APIRouter(prefix="/api/tunnel")


@router.websocket("/ws")
async def agent_tunnel(websocket: WebSocket):
    await websocket.accept()
    token = websocket.query_params.get("token")
    if not token:
        await websocket.close(code=status.WS_1008_POLICY_VIOLATION)
        return

    async with async_session() as db:
        result = await db.execute(select(Agent).where(Agent.token == token))
        agent = result.scalar_one_or_none()
        if not agent:
            await websocket.close(code=status.WS_1008_POLICY_VIOLATION)
            return
        agent_id = agent.id
        agent.status = AgentStatus.online
        agent.last_seen = datetime.now(timezone.utc)
        await db.commit()

    await tunnel_manager.register_agent(agent_id, token, websocket)

    try:
        while True:
            raw = await websocket.receive_text()
            await tunnel_manager.handle_agent_message(agent_id, raw)
    except WebSocketDisconnect:
        pass
    finally:
        await tunnel_manager.unregister_agent(agent_id, token)
        async with async_session() as db:
            agent = await db.get(Agent, agent_id)
            if agent:
                agent.status = AgentStatus.offline
                agent.last_seen = datetime.now(timezone.utc)
                await db.commit()
