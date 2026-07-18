from pydantic_settings import BaseSettings


class Settings(BaseSettings):
    app_name: str = "TunnelOps"
    secret_key: str = "change-me-in-production-use-openssl-rand-hex-32"
    database_url: str = "sqlite+aiosqlite:///./tunnelops.db"
    access_token_expire_minutes: int = 60 * 24
    server_host: str = "0.0.0.0"
    server_port: int = 8080
    tunnel_path: str = "/api/tunnel/ws"

    class Config:
        env_file = ".env"


settings = Settings()
