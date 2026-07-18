import asyncio
import threading

import paramiko
from paramiko import SSHClient

from app.ssh_keys import load_private_key

from app.tunnel import TunnelManager, TunnelSession


class TunnelSocket:
    """Socket-like wrapper over reverse tunnel for Paramiko."""

    def __init__(self, session: TunnelSession, manager: TunnelManager, loop: asyncio.AbstractEventLoop):
        self.session = session
        self.manager = manager
        self.loop = loop
        self._buffer = bytearray()
        self._closed = False
        self._recv_event = threading.Event()
        self._reader_task = loop.create_task(self._read_loop())

    async def _read_loop(self) -> None:
        while not self._closed and not self.session.closed.is_set():
            try:
                msg = await asyncio.wait_for(self.session.queue.get(), timeout=30.0)
            except asyncio.TimeoutError:
                continue
            if msg.get("type") == "tunnel_data":
                data = bytes.fromhex(msg["data"])
                self._buffer.extend(data)
                self._recv_event.set()
            elif msg.get("type") == "tunnel_closed":
                self._closed = True
                self._recv_event.set()
                break

    def recv(self, nbytes: int) -> bytes:
        while True:
            if self._buffer:
                data = bytes(self._buffer[:nbytes])
                del self._buffer[: len(data)]
                return data
            if self._closed or self.session.closed.is_set():
                return b""
            self._recv_event.clear()
            self._recv_event.wait(timeout=30.0)

    def send(self, data: bytes) -> int:
        if self._closed:
            return 0
        future = asyncio.run_coroutine_threadsafe(
            self.manager.relay_data(self.session, data), self.loop
        )
        future.result(timeout=10.0)
        return len(data)

    def sendall(self, data: bytes) -> None:
        self.send(data)

    def close(self) -> None:
        if self._closed:
            return
        self._closed = True
        future = asyncio.run_coroutine_threadsafe(
            self.manager.close_tunnel(self.session), self.loop
        )
        try:
            future.result(timeout=5.0)
        except Exception:
            pass
        self._reader_task.cancel()

    def settimeout(self, timeout: float | None) -> None:
        pass

    def getsockname(self) -> tuple[str, int]:
        return ("127.0.0.1", 0)

    def getpeername(self) -> tuple[str, int]:
        return ("127.0.0.1", 22)

    def fileno(self) -> int:
        raise NotImplementedError

    def makefile(self, *args, **kwargs):
        raise NotImplementedError


async def connect_ssh_via_tunnel(
    manager: TunnelManager,
    agent_id: int,
    host: str,
    port: int,
    username: str,
    *,
    password: str | None = None,
    private_key: str | None = None,
) -> SSHClient:
    loop = asyncio.get_running_loop()
    session = await manager.open_tunnel(agent_id, host, port)

    def _connect() -> SSHClient:
        sock = TunnelSocket(session, manager, loop)
        client = SSHClient()
        client.set_missing_host_key_policy(paramiko.AutoAddPolicy())
        pkey = None
        if private_key:
            pkey = load_private_key(private_key)
        client.connect(
            hostname="127.0.0.1",
            port=22,
            username=username,
            password=password,
            pkey=pkey,
            sock=sock,
            allow_agent=False,
            look_for_keys=False,
            timeout=15,
        )
        return client

    try:
        return await asyncio.to_thread(_connect)
    except Exception:
        await manager.close_tunnel(session)
        raise
