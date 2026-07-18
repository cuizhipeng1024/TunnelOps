from datetime import datetime, timezone

from fastapi import APIRouter, Depends, HTTPException, Query, Request, status
from fastapi.security import OAuth2PasswordRequestForm
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.auth import (
    create_access_token,
    get_user_by_username,
    hash_password,
    log_audit,
    verify_password,
)
from app.database import get_db
from app.deps import client_ip, get_admin_user, get_current_user
from app.models import Agent, AgentStatus, AuditAction, AuditLog, User, UserRole
from app.ssh_keys import load_private_key, public_key_line
from app.schemas import (
    AgentCreate,
    AgentResponse,
    AgentUpdate,
    AuditLogResponse,
    DeployScriptResponse,
    SshKeyUpdate,
    Token,
    UserCreate,
    UserResponse,
    UserUpdate,
)
from app.tunnel import tunnel_manager

router = APIRouter(prefix="/api")


@router.get("/health")
async def health():
    from app.config import settings

    return {"status": "ok", "service": settings.app_name}


@router.post("/auth/login", response_model=Token)
async def login(
    request: Request,
    form: OAuth2PasswordRequestForm = Depends(),
    db: AsyncSession = Depends(get_db),
):
    user = await get_user_by_username(db, form.username)
    if not user or not verify_password(form.password, user.password_hash):
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Invalid credentials")
    token = create_access_token({"sub": str(user.id), "role": user.role.value})
    await log_audit(
        db,
        AuditAction.login,
        user_id=user.id,
        target=user.username,
        ip_address=client_ip(request),
    )
    return Token(access_token=token)


@router.get("/auth/me", response_model=UserResponse)
async def me(user: User = Depends(get_current_user)):
    return UserResponse(
        id=user.id,
        username=user.username,
        role=user.role,
        has_ssh_key=bool(user.ssh_private_key),
        created_at=user.created_at,
    )


@router.put("/auth/ssh-key")
async def update_ssh_key(
    body: SshKeyUpdate,
    request: Request,
    user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    try:
        key = load_private_key(body.private_key)
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc
    user.ssh_private_key = body.private_key.strip()
    user.ssh_public_key = public_key_line(key)
    await db.commit()
    await log_audit(
        db,
        AuditAction.key_update,
        user_id=user.id,
        target=user.username,
        ip_address=client_ip(request),
    )
    return {"message": "SSH key updated"}


@router.delete("/auth/ssh-key")
async def delete_ssh_key(
    request: Request,
    user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    user.ssh_private_key = None
    user.ssh_public_key = None
    await db.commit()
    await log_audit(
        db,
        AuditAction.key_update,
        user_id=user.id,
        target=user.username,
        detail="Key removed",
        ip_address=client_ip(request),
    )
    return {"message": "SSH key removed"}


@router.get("/users", response_model=list[UserResponse])
async def list_users(
    _: User = Depends(get_admin_user),
    db: AsyncSession = Depends(get_db),
):
    result = await db.execute(select(User).order_by(User.id))
    users = result.scalars().all()
    return [
        UserResponse(
            id=u.id,
            username=u.username,
            role=u.role,
            has_ssh_key=bool(u.ssh_private_key),
            created_at=u.created_at,
        )
        for u in users
    ]


@router.post("/users", response_model=UserResponse, status_code=201)
async def create_user(
    body: UserCreate,
    request: Request,
    admin: User = Depends(get_admin_user),
    db: AsyncSession = Depends(get_db),
):
    existing = await get_user_by_username(db, body.username)
    if existing:
        raise HTTPException(status_code=400, detail="Username exists")
    user = User(
        username=body.username,
        password_hash=hash_password(body.password),
        role=body.role,
    )
    db.add(user)
    await db.commit()
    await db.refresh(user)
    await log_audit(
        db,
        AuditAction.user_create,
        user_id=admin.id,
        target=body.username,
        ip_address=client_ip(request),
    )
    return UserResponse(
        id=user.id,
        username=user.username,
        role=user.role,
        has_ssh_key=False,
        created_at=user.created_at,
    )


@router.put("/users/{user_id}", response_model=UserResponse)
async def update_user(
    user_id: int,
    body: UserUpdate,
    request: Request,
    admin: User = Depends(get_admin_user),
    db: AsyncSession = Depends(get_db),
):
    user = await db.get(User, user_id)
    if not user:
        raise HTTPException(status_code=404, detail="User not found")
    if body.password:
        user.password_hash = hash_password(body.password)
    if body.role:
        user.role = body.role
    await db.commit()
    await db.refresh(user)
    await log_audit(
        db,
        AuditAction.user_update,
        user_id=admin.id,
        target=user.username,
        ip_address=client_ip(request),
    )
    return UserResponse(
        id=user.id,
        username=user.username,
        role=user.role,
        has_ssh_key=bool(user.ssh_private_key),
        created_at=user.created_at,
    )


@router.delete("/users/{user_id}")
async def delete_user(
    user_id: int,
    request: Request,
    admin: User = Depends(get_admin_user),
    db: AsyncSession = Depends(get_db),
):
    user = await db.get(User, user_id)
    if not user:
        raise HTTPException(status_code=404, detail="User not found")
    if user.id == admin.id:
        raise HTTPException(status_code=400, detail="Cannot delete yourself")
    username = user.username
    await db.delete(user)
    await db.commit()
    await log_audit(
        db,
        AuditAction.user_delete,
        user_id=admin.id,
        target=username,
        ip_address=client_ip(request),
    )
    return {"message": "User deleted"}


@router.get("/agents", response_model=list[AgentResponse])
async def list_agents(
    _: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    result = await db.execute(select(Agent).order_by(Agent.id))
    agents = result.scalars().all()
    responses = []
    for agent in agents:
        if tunnel_manager.is_online(agent.id):
            agent.status = AgentStatus.online
        else:
            agent.status = AgentStatus.offline
        responses.append(AgentResponse.model_validate(agent))
    return responses


@router.post("/agents", response_model=AgentResponse, status_code=201)
async def create_agent(
    body: AgentCreate,
    request: Request,
    user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    agent = Agent(
        name=body.name,
        description=body.description,
        host=body.host or "127.0.0.1",
        ssh_port=body.ssh_port,
        ssh_user=body.ssh_user,
        token=tunnel_manager.generate_token(),
        status=AgentStatus.offline,
    )
    db.add(agent)
    await db.commit()
    await db.refresh(agent)
    await log_audit(
        db,
        AuditAction.agent_create,
        user_id=user.id,
        target=agent.name,
        detail=f"agent_id={agent.id}",
        ip_address=client_ip(request),
    )
    return AgentResponse.model_validate(agent)


@router.put("/agents/{agent_id}", response_model=AgentResponse)
async def update_agent(
    agent_id: int,
    body: AgentUpdate,
    request: Request,
    user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    agent = await db.get(Agent, agent_id)
    if not agent:
        raise HTTPException(status_code=404, detail="Agent not found")
    for field, value in body.model_dump(exclude_unset=True).items():
        setattr(agent, field, value)
    await db.commit()
    await db.refresh(agent)
    await log_audit(
        db,
        AuditAction.agent_update,
        user_id=user.id,
        target=agent.name,
        ip_address=client_ip(request),
    )
    agent.status = AgentStatus.online if tunnel_manager.is_online(agent.id) else AgentStatus.offline
    return AgentResponse.model_validate(agent)


@router.delete("/agents/{agent_id}")
async def delete_agent(
    agent_id: int,
    request: Request,
    user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    agent = await db.get(Agent, agent_id)
    if not agent:
        raise HTTPException(status_code=404, detail="Agent not found")
    name = agent.name
    await db.delete(agent)
    await db.commit()
    await log_audit(
        db,
        AuditAction.agent_delete,
        user_id=user.id,
        target=name,
        ip_address=client_ip(request),
    )
    return {"message": "Agent deleted"}


@router.post("/agents/{agent_id}/regenerate-token", response_model=AgentResponse)
async def regenerate_token(
    agent_id: int,
    user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    agent = await db.get(Agent, agent_id)
    if not agent:
        raise HTTPException(status_code=404, detail="Agent not found")
    agent.token = tunnel_manager.generate_token()
    await db.commit()
    await db.refresh(agent)
    agent.status = AgentStatus.online if tunnel_manager.is_online(agent.id) else AgentStatus.offline
    return AgentResponse.model_validate(agent)


@router.get("/agents/{agent_id}/deploy", response_model=DeployScriptResponse)
async def get_deploy_script(
    agent_id: int,
    server_url: str = Query(..., description="Public server URL, e.g. https://tunnel.example.com"),
    user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    agent = await db.get(Agent, agent_id)
    if not agent:
        raise HTTPException(status_code=404, detail="Agent not found")
    ws_url = server_url.rstrip("/").replace("https://", "wss://").replace("http://", "ws://")
    ws_url = f"{ws_url}/api/tunnel/ws"
    script = f"""#!/bin/bash
set -euo pipefail
SERVER_URL="{server_url.rstrip('/')}"
AGENT_TOKEN="{agent.token}"
AGENT_NAME="{agent.name}"
INSTALL_DIR="/opt/tunnelops-agent"
VENV_DIR="$INSTALL_DIR/venv"

echo "==> Installing TunnelOps Agent for $AGENT_NAME"

if ! command -v python3 &>/dev/null; then
  echo "ERROR: python3 is required"
  exit 1
fi
if ! command -v curl &>/dev/null; then
  echo "ERROR: curl is required"
  exit 1
fi

if ! python3 -c "import venv" 2>/dev/null; then
  echo "==> Installing python3-venv..."
  sudo apt-get update -qq
  sudo apt-get install -y python3-venv curl
fi

sudo mkdir -p "$INSTALL_DIR"

echo "==> Downloading agent..."
sudo curl -fsSL "$SERVER_URL/static/agent/agent.py" -o "$INSTALL_DIR/agent.py"

echo "==> Creating Python virtual environment..."
if [ ! -d "$VENV_DIR" ]; then
  sudo python3 -m venv "$VENV_DIR"
fi

echo "==> Installing dependencies..."
sudo "$VENV_DIR/bin/pip" install --upgrade pip -q
sudo "$VENV_DIR/bin/pip" install "websockets>=14.1" -q

echo "==> Creating systemd service..."
sudo tee /etc/systemd/system/tunnelops-agent.service > /dev/null << EOF
[Unit]
Description=TunnelOps Agent - $AGENT_NAME
After=network-online.target
Wants=network-online.target

[Service]
Type=simple
WorkingDirectory=$INSTALL_DIR
Environment=PYTHONUNBUFFERED=1
Environment=TUNNELOPS_SERVER=$SERVER_URL
Environment=TUNNELOPS_TOKEN=$AGENT_TOKEN
Environment=TUNNELOPS_NAME=$AGENT_NAME
ExecStart=$VENV_DIR/bin/python $INSTALL_DIR/agent.py
Restart=always
RestartSec=5
StandardOutput=journal
StandardError=journal

[Install]
WantedBy=multi-user.target
EOF

sudo systemctl daemon-reload
sudo systemctl enable tunnelops-agent
sudo systemctl restart tunnelops-agent

echo "==> Done! Agent is running."
echo "    Status: sudo systemctl status tunnelops-agent"
echo "    Logs:   sudo journalctl -u tunnelops-agent -f"
"""
    return DeployScriptResponse(script=script, token=agent.token)


@router.get("/audit-logs", response_model=list[AuditLogResponse])
async def list_audit_logs(
    limit: int = Query(100, le=500),
    _: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    result = await db.execute(
        select(AuditLog, User.username)
        .outerjoin(User, AuditLog.user_id == User.id)
        .order_by(AuditLog.id.desc())
        .limit(limit)
    )
    rows = result.all()
    return [
        AuditLogResponse(
            id=log.id,
            user_id=log.user_id,
            username=username,
            action=log.action,
            target=log.target,
            detail=log.detail,
            ip_address=log.ip_address,
            created_at=log.created_at,
        )
        for log, username in rows
    ]
