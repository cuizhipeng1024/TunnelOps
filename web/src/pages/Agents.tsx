import {
  Button,
  Form,
  Input,
  InputNumber,
  Modal,
  Popconfirm,
  Space,
  Table,
  Tag,
  message,
  Typography,
} from 'antd';
import { PlusOutlined, CodeOutlined, ReloadOutlined, ConsoleSqlOutlined } from '@ant-design/icons';
import { useEffect, useState } from 'react';
import { useNavigate } from 'react-router-dom';
import {
  Agent,
  createAgent,
  deleteAgent,
  getDeployScript,
  listAgents,
  regenerateToken,
  updateAgent,
} from '../api';

export default function Agents() {
  const [agents, setAgents] = useState<Agent[]>([]);
  const [loading, setLoading] = useState(false);
  const [modalOpen, setModalOpen] = useState(false);
  const [deployOpen, setDeployOpen] = useState(false);
  const [deployScript, setDeployScript] = useState('');
  const [editing, setEditing] = useState<Agent | null>(null);
  const [form] = Form.useForm();
  const [serverUrl, setServerUrl] = useState(window.location.origin);
  const navigate = useNavigate();

  const load = async () => {
    setLoading(true);
    try {
      setAgents(await listAgents());
    } finally {
      setLoading(false);
    }
  };

  useEffect(() => {
    load();
    const timer = setInterval(load, 10000);
    return () => clearInterval(timer);
  }, []);

  const openCreate = () => {
    setEditing(null);
    form.resetFields();
    form.setFieldsValue({ ssh_port: 22, ssh_user: 'root', host: '127.0.0.1' });
    setModalOpen(true);
  };

  const openEdit = (agent: Agent) => {
    setEditing(agent);
    form.setFieldsValue(agent);
    setModalOpen(true);
  };

  const handleSubmit = async () => {
    const values = await form.validateFields();
    if (editing) {
      await updateAgent(editing.id, values);
      message.success('设备已更新');
    } else {
      await createAgent(values);
      message.success('设备已创建');
    }
    setModalOpen(false);
    load();
  };

  const handleDeploy = async (agent: Agent) => {
    const data = await getDeployScript(agent.id, serverUrl);
    setDeployScript(data.script);
    setDeployOpen(true);
  };

  const columns = [
    { title: '名称', dataIndex: 'name', key: 'name' },
    { title: '描述', dataIndex: 'description', key: 'description', ellipsis: true },
    {
      title: '状态',
      dataIndex: 'status',
      key: 'status',
      render: (s: string) => (
        <Tag color={s === 'online' ? 'green' : 'default'}>{s === 'online' ? '在线' : '离线'}</Tag>
      ),
    },
    { title: 'SSH 用户', dataIndex: 'ssh_user', key: 'ssh_user' },
    { title: 'SSH 端口', dataIndex: 'ssh_port', key: 'ssh_port' },
    { title: '目标主机', dataIndex: 'host', key: 'host' },
    {
      title: '操作',
      key: 'action',
      render: (_: unknown, record: Agent) => (
        <Space wrap>
          <Button
            type="primary"
            size="small"
            icon={<ConsoleSqlOutlined />}
            disabled={record.status !== 'online'}
            onClick={() => navigate(`/terminal/${record.id}`, { state: { agent: record } })}
          >
            连接
          </Button>
          <Button size="small" onClick={() => openEdit(record)}>
            编辑
          </Button>
          <Button size="small" icon={<CodeOutlined />} onClick={() => handleDeploy(record)}>
            部署
          </Button>
          <Popconfirm title="重新生成 Token？旧 Agent 将断开" onConfirm={async () => {
            await regenerateToken(record.id);
            message.success('Token 已更新');
            load();
          }}>
            <Button size="small" icon={<ReloadOutlined />}>
              重置Token
            </Button>
          </Popconfirm>
          <Popconfirm title="确认删除？" onConfirm={async () => {
            await deleteAgent(record.id);
            message.success('已删除');
            load();
          }}>
            <Button size="small" danger>
              删除
            </Button>
          </Popconfirm>
        </Space>
      ),
    },
  ];

  return (
    <>
      <div style={{ display: 'flex', justifyContent: 'space-between', marginBottom: 16 }}>
        <Typography.Title level={4} style={{ margin: 0 }}>
          Agent 设备
        </Typography.Title>
        <Button type="primary" icon={<PlusOutlined />} onClick={openCreate}>
          添加设备
        </Button>
      </div>
      <Table rowKey="id" loading={loading} columns={columns} dataSource={agents} />

      <Modal
        title={editing ? '编辑设备' : '添加设备'}
        open={modalOpen}
        onOk={handleSubmit}
        onCancel={() => setModalOpen(false)}
        destroyOnClose
      >
        <Form form={form} layout="vertical">
          <Form.Item name="name" label="名称" rules={[{ required: true }]}>
            <Input />
          </Form.Item>
          <Form.Item name="description" label="描述">
            <Input.TextArea rows={2} />
          </Form.Item>
          <Form.Item name="host" label="SSH 目标地址（Agent 本机视角）">
            <Input placeholder="127.0.0.1" />
          </Form.Item>
          <Form.Item name="ssh_port" label="SSH 端口">
            <InputNumber min={1} max={65535} style={{ width: '100%' }} />
          </Form.Item>
          <Form.Item name="ssh_user" label="默认 SSH 用户">
            <Input />
          </Form.Item>
        </Form>
      </Modal>

      <Modal
        title="一键部署脚本"
        open={deployOpen}
        onCancel={() => setDeployOpen(false)}
        width={720}
        footer={[
          <Button key="copy" type="primary" onClick={() => {
            navigator.clipboard.writeText(deployScript);
            message.success('已复制到剪贴板');
          }}>
            复制脚本
          </Button>,
        ]}
      >
        <Form layout="vertical" style={{ marginBottom: 16 }}>
          <Form.Item label="公网 Server 地址">
            <Input value={serverUrl} onChange={(e) => setServerUrl(e.target.value)} />
          </Form.Item>
        </Form>
        <Input.TextArea value={deployScript} rows={16} readOnly style={{ fontFamily: 'monospace' }} />
        <Typography.Paragraph type="secondary" style={{ marginTop: 8 }}>
          在内网设备上执行此脚本即可安装并启动 Agent（需要 root 权限和 python3）。
        </Typography.Paragraph>
      </Modal>
    </>
  );
}
