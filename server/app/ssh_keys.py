import io

import paramiko
from paramiko import ECDSAKey, Ed25519Key, PKey, RSAKey

KEY_CLASSES: tuple[type[PKey], ...] = (Ed25519Key, RSAKey, ECDSAKey)


def load_private_key(key_text: str, password: str | None = None) -> PKey:
    """Load PEM/OpenSSH private key (Ed25519, RSA, ECDSA)."""
    stripped = key_text.strip()
    if not stripped:
        raise ValueError("私钥内容为空")

    buffer = io.StringIO(stripped)
    errors: list[str] = []
    for key_class in KEY_CLASSES:
        try:
            buffer.seek(0)
            return key_class.from_private_key(buffer, password=password)
        except Exception as exc:
            errors.append(f"{key_class.__name__}: {exc}")

    raise ValueError(
        "不支持的私钥格式。请使用 OpenSSH 或 PEM 格式的 Ed25519 / RSA / ECDSA 私钥。"
        f" ({errors[0] if errors else 'unknown'})"
    )


def public_key_line(key: PKey) -> str:
    return f"{key.get_name()} {key.get_base64()}"
