from datetime import datetime
from typing import Literal

from pydantic import BaseModel, Field

from app.models import AgentStatus, AuditAction, UserRole


class Token(BaseModel):
    access_token: str
    token_type: str = "bearer"


class UserCreate(BaseModel):
    username: str = Field(min_length=3, max_length=64)
    password: str = Field(min_length=6)
    role: UserRole = UserRole.user


class UserUpdate(BaseModel):
    password: str | None = Field(default=None, min_length=6)
    role: UserRole | None = None


class UserResponse(BaseModel):
    id: int
    username: str
    role: UserRole
    has_ssh_key: bool
    created_at: datetime

    model_config = {"from_attributes": True}


class SshKeyUpdate(BaseModel):
    private_key: str = Field(min_length=32)


class AgentCreate(BaseModel):
    name: str = Field(min_length=1, max_length=128)
    description: str | None = None
    host: str | None = None
    ssh_port: int = 22
    ssh_user: str = "root"


class AgentUpdate(BaseModel):
    name: str | None = Field(default=None, min_length=1, max_length=128)
    description: str | None = None
    host: str | None = None
    ssh_port: int | None = None
    ssh_user: str | None = None


class AgentResponse(BaseModel):
    id: int
    name: str
    description: str | None
    token: str
    host: str | None
    ssh_port: int
    ssh_user: str
    status: AgentStatus
    last_seen: datetime | None
    created_at: datetime

    model_config = {"from_attributes": True}


class ShellConnectRequest(BaseModel):
    auth_type: Literal["password", "key"] = "password"
    password: str | None = None
    username: str | None = None


class AuditLogResponse(BaseModel):
    id: int
    user_id: int | None
    username: str | None = None
    action: AuditAction
    target: str | None
    detail: str | None
    ip_address: str | None
    created_at: datetime

    model_config = {"from_attributes": True}


class DeployScriptResponse(BaseModel):
    script: str
    token: str
