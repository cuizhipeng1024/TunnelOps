def format_shell_error(exc: Exception, host: str, port: int) -> str:
    msg = str(exc).strip()
    if "Name or service not known" in msg or "getaddrinfo failed" in msg:
        return (
            f"无法解析 SSH 目标地址「{host}」。"
            f"请在「设备管理 → 编辑」中将 SSH 目标地址改为 Agent 本机可访问的 IP，"
            f"Agent 与 SSH 在同一台机器时填 127.0.0.1（当前端口 {port}）。"
        )
    if "Connection refused" in msg:
        return (
            f"SSH 连接被拒绝（{host}:{port}）。"
            f"请确认目标机器 SSH 服务已启动，且端口正确。"
        )
    if "Tunnel open timeout" in msg:
        return f"隧道建立超时，Agent 无法连接 {host}:{port}，请检查 Agent 是否在线及 SSH 目标地址。"
    if "Agent offline" in msg:
        return "Agent 离线。请确认内网 Agent 服务正在运行。"
    return msg or "连接失败"
