import asyncio
import json
import logging

from fastapi import APIRouter, WebSocket, WebSocketDisconnect, status

from app.auth import decode_token, log_audit
from app.database import async_session
from app.models import Agent, AuditAction, User
from app.ssh_bridge import connect_ssh_via_tunnel
from app.tunnel import tunnel_manager

logger = logging.getLogger("tunnelops.shell")
router = APIRouter(prefix="/api/shell")


async def _authenticate_ws(websocket: WebSocket) -> tuple[int, str] | None:
    token = websocket.query_params.get("token")
    if not token:
        return None
    payload = decode_token(token)
    if not payload or "sub" not in payload:
        return None
    return int(payload["sub"]), payload.get("role", "user")


@router.websocket("/ws/{agent_id}")
async def shell_session(websocket: WebSocket, agent_id: int):
    await websocket.accept()
    auth = await _authenticate_ws(websocket)
    if not auth:
        logger.warning("Shell unauthorized agent_id=%s", agent_id)
        await websocket.send_json({"type": "error", "message": "Unauthorized"})
        await websocket.close(code=status.WS_1008_POLICY_VIOLATION)
        return
    user_id, _ = auth

    try:
        init_msg = await websocket.receive_text()
        config = json.loads(init_msg)
        auth_type = config.get("auth_type", "password")
        username = config.get("username")
        password = config.get("password")
    except Exception as exc:
        logger.warning("Shell invalid init agent_id=%s error=%s", agent_id, exc)
        await websocket.send_json({"type": "error", "message": "Invalid init message"})
        await websocket.close()
        return

    async with async_session() as db:
        agent = await db.get(Agent, agent_id)
        user = await db.get(User, user_id)
        if not agent:
            logger.warning("Shell agent not found agent_id=%s", agent_id)
            await websocket.send_json({"type": "error", "message": "Agent not found"})
            await websocket.close()
            return
        if not tunnel_manager.is_online(agent_id):
            logger.warning(
                "Shell agent offline agent_id=%s (若使用 uvicorn --workers >1，请改为 --workers 1)",
                agent_id,
            )
            await websocket.send_json({"type": "error", "message": "Agent offline"})
            await websocket.close()
            return

        ssh_user = username or agent.ssh_user
        private_key = None
        if auth_type == "key":
            if not user or not user.ssh_private_key:
                await websocket.send_json({"type": "error", "message": "No SSH key configured"})
                await websocket.close()
                return
            private_key = user.ssh_private_key
        elif not password:
            logger.warning("Shell password required agent_id=%s user=%s", agent_id, ssh_user)
            await websocket.send_json({"type": "error", "message": "Password required"})
            await websocket.close()
            return

        host = agent.host or "127.0.0.1"
        try:
            ssh_client = await connect_ssh_via_tunnel(
                tunnel_manager,
                agent_id,
                host,
                agent.ssh_port,
                ssh_user,
                password=password if auth_type == "password" else None,
                private_key=private_key,
            )
        except Exception as exc:
            logger.exception(
                "Shell connect failed agent_id=%s user=%s auth=%s host=%s port=%s",
                agent_id,
                ssh_user,
                auth_type,
                host,
                agent.ssh_port,
            )
            await websocket.send_json({"type": "error", "message": str(exc)})
            await websocket.close()
            return

        await log_audit(
            db,
            AuditAction.shell_connect,
            user_id=user_id,
            target=agent.name,
            detail=f"user={ssh_user}, auth={auth_type}",
        )

    logger.info("Shell connected agent_id=%s user=%s auth=%s", agent_id, ssh_user, auth_type)

    channel = ssh_client.invoke_shell(term="xterm-256color")
    channel.settimeout(0.0)

    await websocket.send_json({"type": "connected", "message": f"Connected to {agent.name}"})

    async def read_ssh():
        while True:
            if channel.recv_ready():
                data = channel.recv(4096)
                if not data:
                    break
                await websocket.send_bytes(data)
            elif channel.exit_status_ready():
                break
            else:
                await asyncio.sleep(0.02)

    read_task = asyncio.create_task(read_ssh())

    try:
        while True:
            msg = await websocket.receive()
            if msg.get("type") == "websocket.disconnect":
                break
            if "bytes" in msg and msg["bytes"]:
                channel.send(msg["bytes"])
            elif "text" in msg and msg["text"]:
                data = json.loads(msg["text"])
                if data.get("type") == "resize":
                    channel.resize_pty(width=data["cols"], height=data["rows"])
    except WebSocketDisconnect:
        pass
    finally:
        read_task.cancel()
        channel.close()
        ssh_client.close()
        async with async_session() as db:
            agent = await db.get(Agent, agent_id)
            await log_audit(
                db,
                AuditAction.shell_disconnect,
                user_id=user_id,
                target=agent.name if agent else str(agent_id),
            )
