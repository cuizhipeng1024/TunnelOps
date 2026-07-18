import { Button, Card, Form, Input, Radio, Space, Typography, message } from 'antd';
import { useEffect, useRef, useState } from 'react';
import { Terminal } from 'xterm';
import { FitAddon } from 'xterm-addon-fit';
import 'xterm/css/xterm.css';
import { Agent } from '../api';

interface TerminalPanelProps {
  agent: Agent;
  active: boolean;
}

export default function TerminalPanel({ agent, active }: TerminalPanelProps) {
  const containerRef = useRef<HTMLDivElement>(null);
  const wsRef = useRef<WebSocket | null>(null);
  const termRef = useRef<Terminal | null>(null);
  const fitRef = useRef<FitAddon | null>(null);
  const [authType, setAuthType] = useState<'password' | 'key'>('password');
  const [connecting, setConnecting] = useState(false);
  const [connected, setConnected] = useState(false);
  const [form] = Form.useForm();

  useEffect(() => {
    return () => {
      wsRef.current?.close();
      termRef.current?.dispose();
      termRef.current = null;
      fitRef.current = null;
    };
  }, []);

  useEffect(() => {
    if (active && connected && fitRef.current && containerRef.current) {
      fitRef.current.fit();
    }
  }, [active, connected]);

  const connect = async () => {
    const values = await form.validateFields();
    setConnecting(true);

    const token = localStorage.getItem('token');
    const protocol = window.location.protocol === 'https:' ? 'wss' : 'ws';
    const ws = new WebSocket(
      `${protocol}://${window.location.host}/api/shell/ws/${agent.id}?token=${token}`,
    );
    wsRef.current = ws;

    ws.onopen = () => {
      ws.send(
        JSON.stringify({
          auth_type: authType,
          username: values.username || agent.ssh_user,
          password: authType === 'password' ? values.password : undefined,
        }),
      );
    };

    ws.onmessage = (event) => {
      if (typeof event.data === 'string') {
        const msg = JSON.parse(event.data);
        if (msg.type === 'error') {
          message.error(`[${agent.name}] ${msg.message}`);
          setConnecting(false);
          ws.close();
          return;
        }
        if (msg.type === 'connected') {
          setConnected(true);
          setConnecting(false);
          message.success(`[${agent.name}] ${msg.message}`);
          initTerminal(ws);
        }
      } else if (termRef.current && event.data instanceof Blob) {
        event.data.arrayBuffer().then((buf) => {
          termRef.current?.write(new Uint8Array(buf));
        });
      } else if (termRef.current && event.data instanceof ArrayBuffer) {
        termRef.current.write(new Uint8Array(event.data));
      }
    };

    ws.onerror = () => {
      message.error(`[${agent.name}] 连接失败`);
      setConnecting(false);
    };

    ws.onclose = () => {
      setConnected(false);
      setConnecting(false);
    };
  };

  const initTerminal = (ws: WebSocket) => {
    if (!containerRef.current) return;
    const term = new Terminal({
      cursorBlink: true,
      fontSize: 14,
      theme: { background: '#1e1e1e' },
    });
    const fitAddon = new FitAddon();
    term.loadAddon(fitAddon);
    term.open(containerRef.current);
    fitAddon.fit();
    termRef.current = term;
    fitRef.current = fitAddon;

    term.onData((data) => {
      if (ws.readyState === WebSocket.OPEN) {
        ws.send(new TextEncoder().encode(data));
      }
    });
    term.onResize(({ cols, rows }) => {
      if (ws.readyState === WebSocket.OPEN) {
        ws.send(JSON.stringify({ type: 'resize', cols, rows }));
      }
    });
  };

  return (
    <div style={{ height: '100%', display: 'flex', flexDirection: 'column' }}>
      {!connected && (
        <Card style={{ marginBottom: 16, maxWidth: 480 }}>
          <Typography.Paragraph type="secondary">
            设备: {agent.name} · {agent.status === 'online' ? '在线' : '离线'}
          </Typography.Paragraph>
          <Form form={form} layout="vertical" initialValues={{ username: agent.ssh_user }}>
            <Form.Item label="认证方式">
              <Radio.Group value={authType} onChange={(e) => setAuthType(e.target.value)}>
                <Radio.Button value="password">密码</Radio.Button>
                <Radio.Button value="key">密钥</Radio.Button>
              </Radio.Group>
            </Form.Item>
            <Form.Item name="username" label="SSH 用户名">
              <Input />
            </Form.Item>
            {authType === 'password' && (
              <Form.Item name="password" label="SSH 密码" rules={[{ required: true }]}>
                <Input.Password />
              </Form.Item>
            )}
            <Button
              type="primary"
              loading={connecting}
              onClick={connect}
              disabled={agent.status !== 'online'}
            >
              建立连接
            </Button>
          </Form>
        </Card>
      )}
      <div
        ref={containerRef}
        className="terminal-container"
        style={{
          display: connected ? 'block' : 'none',
          flex: 1,
          height: connected ? 'calc(100vh - 220px)' : 0,
          minHeight: connected ? 400 : 0,
        }}
      />
    </div>
  );
}
