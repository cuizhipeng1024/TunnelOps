import { Button, Card, Form, Input, Radio, Space, Typography, message } from 'antd';
import { ArrowLeftOutlined } from '@ant-design/icons';
import { useEffect, useRef, useState } from 'react';
import { useLocation, useNavigate, useParams } from 'react-router-dom';
import { Terminal } from 'xterm';
import { FitAddon } from 'xterm-addon-fit';
import 'xterm/css/xterm.css';
import { Agent, listAgents } from '../api';

export default function TerminalPage() {
  const { agentId } = useParams();
  const navigate = useNavigate();
  const location = useLocation();
  const termRef = useRef<HTMLDivElement>(null);
  const xtermRef = useRef<Terminal | null>(null);
  const wsRef = useRef<WebSocket | null>(null);
  const [agent, setAgent] = useState<Agent | null>((location.state as { agent?: Agent })?.agent ?? null);
  const [authType, setAuthType] = useState<'password' | 'key'>('password');
  const [connecting, setConnecting] = useState(false);
  const [connected, setConnected] = useState(false);
  const [form] = Form.useForm();

  useEffect(() => {
    if (!agent && agentId) {
      listAgents().then((list) => setAgent(list.find((a) => a.id === Number(agentId)) ?? null));
    }
  }, [agent, agentId]);

  useEffect(() => {
    return () => {
      wsRef.current?.close();
      xtermRef.current?.dispose();
    };
  }, []);

  const connect = async () => {
    const values = await form.validateFields();
    if (!agent) return;

    setConnecting(true);
    const token = localStorage.getItem('token');
    const protocol = window.location.protocol === 'https:' ? 'wss' : 'ws';
    const ws = new WebSocket(`${protocol}://${window.location.host}/api/shell/ws/${agent.id}?token=${token}`);
    wsRef.current = ws;

    ws.onopen = () => {
      ws.send(JSON.stringify({
        auth_type: authType,
        username: values.username || agent.ssh_user,
        password: authType === 'password' ? values.password : undefined,
      }));
    };

    ws.onmessage = (event) => {
      if (typeof event.data === 'string') {
        const msg = JSON.parse(event.data);
        if (msg.type === 'error') {
          message.error(msg.message);
          setConnecting(false);
          ws.close();
          return;
        }
        if (msg.type === 'connected') {
          setConnected(true);
          setConnecting(false);
          message.success(msg.message);
          initTerminal(ws);
        }
      } else if (xtermRef.current && event.data instanceof Blob) {
        event.data.arrayBuffer().then((buf) => {
          xtermRef.current?.write(new Uint8Array(buf));
        });
      } else if (xtermRef.current && event.data instanceof ArrayBuffer) {
        xtermRef.current.write(new Uint8Array(event.data));
      }
    };

    ws.onerror = () => {
      message.error('连接失败');
      setConnecting(false);
    };

    ws.onclose = () => {
      setConnected(false);
      setConnecting(false);
    };
  };

  const initTerminal = (ws: WebSocket) => {
    if (!termRef.current) return;
    const term = new Terminal({
      cursorBlink: true,
      fontSize: 14,
      theme: { background: '#1e1e1e' },
    });
    const fitAddon = new FitAddon();
    term.loadAddon(fitAddon);
    term.open(termRef.current);
    fitAddon.fit();
    xtermRef.current = term;

    term.onData((data) => ws.send(new TextEncoder().encode(data)));
    term.onResize(({ cols, rows }) => {
      ws.send(JSON.stringify({ type: 'resize', cols, rows }));
    });

    window.addEventListener('resize', () => fitAddon.fit());
  };

  if (!agent) {
    return <Typography.Text>设备不存在</Typography.Text>;
  }

  return (
    <div>
      <Space style={{ marginBottom: 16 }}>
        <Button icon={<ArrowLeftOutlined />} onClick={() => navigate('/agents')}>
          返回
        </Button>
        <Typography.Title level={4} style={{ margin: 0 }}>
          连接: {agent.name}
        </Typography.Title>
        <Typography.Text type="secondary">
          {agent.status === 'online' ? '在线' : '离线'}
        </Typography.Text>
      </Space>

      {!connected && (
        <Card style={{ marginBottom: 16, maxWidth: 480 }}>
          <Form form={form} layout="vertical" initialValues={{ username: agent.ssh_user }}>
            <Form.Item label="认证方式">
              <Radio.Group value={authType} onChange={(e) => setAuthType(e.target.value)}>
                <Radio.Button value="password">密码</Radio.Button>
                <Radio.Button value="key">密钥（使用个人设置中的私钥）</Radio.Button>
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
            <Button type="primary" loading={connecting} onClick={connect} disabled={agent.status !== 'online'}>
              建立连接
            </Button>
          </Form>
        </Card>
      )}

      <div className="terminal-container" ref={termRef} style={{ display: connected ? 'block' : 'none' }} />
    </div>
  );
}
