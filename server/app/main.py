import asyncio
from contextlib import asynccontextmanager
from pathlib import Path

from fastapi import FastAPI, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import FileResponse
from fastapi.staticfiles import StaticFiles

from app.auth import get_user_by_username, hash_password, log_audit
from app.config import settings
from app.database import async_session, init_db
from app.models import AuditAction, User, UserRole
from app.routers import api, shell, tunnel


@asynccontextmanager
async def lifespan(app: FastAPI):
    await init_db()
    async with async_session() as db:
        admin = await get_user_by_username(db, "admin")
        if not admin:
            admin = User(
                username="admin",
                password_hash=hash_password("admin123"),
                role=UserRole.admin,
            )
            db.add(admin)
            await db.commit()
            await log_audit(
                db,
                AuditAction.user_create,
                user_id=None,
                target="admin",
                detail="Default admin created (password: admin123)",
            )
    yield


app = FastAPI(title=settings.app_name, lifespan=lifespan)

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

app.include_router(api.router)
app.include_router(tunnel.router)
app.include_router(shell.router)

static_dir = Path(__file__).resolve().parent.parent / "static"
static_dir.mkdir(exist_ok=True)
(static_dir / "agent").mkdir(exist_ok=True)
app.mount("/static", StaticFiles(directory=str(static_dir)), name="static")

web_dir = static_dir / "web"
if web_dir.exists():
    app.mount("/assets", StaticFiles(directory=str(web_dir / "assets")), name="assets")

    @app.get("/{full_path:path}")
    async def spa_fallback(full_path: str, request: Request):
        if full_path.startswith("api/"):
            from fastapi import HTTPException

            raise HTTPException(status_code=404)
        index = web_dir / "index.html"
        if index.exists():
            return FileResponse(index)
        return {"message": "Web UI not built. Run: cd web && npm install && npm run build"}


@app.get("/api/health")
async def health():
    return {"status": "ok", "service": settings.app_name}


if __name__ == "__main__":
    import uvicorn

    logging.basicConfig(
        level=logging.INFO,
        format="%(asctime)s %(levelname)s [%(name)s] %(message)s",
    )

    uvicorn.run(
        "app.main:app",
        host=settings.server_host,
        port=settings.server_port,
        reload=True,
    )
