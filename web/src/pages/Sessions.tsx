import { PlusOutlined } from '@ant-design/icons';
import { Button, Modal, Select, Space, Tabs, Typography, message } from 'antd';
import { useCallback, useEffect, useMemo, useState } from 'react';
import { useNavigate, useSearchParams } from 'react-router-dom';
import { Agent, listAgents } from '../api';
import TerminalPanel from '../components/TerminalPanel';

interface SessionTab {
  key: string;
  agentId: number;
  agent: Agent;
  label: string;
}

let tabCounter = 0;

function makeTabKey(agentId: number) {
  tabCounter += 1;
  return `${agentId}-${tabCounter}-${Date.now()}`;
}

export default function Sessions() {
  const [agents, setAgents] = useState<Agent[]>([]);
  const [tabs, setTabs] = useState<SessionTab[]>([]);
  const [activeKey, setActiveKey] = useState<string>();
  const [pickerOpen, setPickerOpen] = useState(false);
  const [pickAgentId, setPickAgentId] = useState<number | null>(null);
  const [searchParams, setSearchParams] = useSearchParams();
  const navigate = useNavigate();

  const loadAgents = useCallback(async () => {
    setAgents(await listAgents());
  }, []);

  useEffect(() => {
    loadAgents();
    const timer = setInterval(loadAgents, 10000);
    return () => clearInterval(timer);
  }, [loadAgents]);

  const addTab = useCallback(
    (agent: Agent) => {
      const key = makeTabKey(agent.id);
      const tab: SessionTab = {
        key,
        agentId: agent.id,
        agent,
        label: agent.name,
      };
      setTabs((prev) => [...prev, tab]);
      setActiveKey(key);
      return key;
    },
    [],
  );

  useEffect(() => {
    const agentId = searchParams.get('agent');
    if (!agentId || agents.length === 0) return;

    const agent = agents.find((a) => a.id === Number(agentId));
    if (!agent) return;

    addTab(agent);
    setSearchParams({}, { replace: true });
  }, [agents, searchParams, setSearchParams, addTab]);

  useEffect(() => {
    setTabs((prev) =>
      prev.map((tab) => {
        const latest = agents.find((a) => a.id === tab.agentId);
        return latest ? { ...tab, agent: latest, label: latest.name } : tab;
      }),
    );
  }, [agents]);

  const openPicker = () => {
    const online = agents.filter((a) => a.status === 'online');
    if (online.length === 0) {
      message.warning('当前没有在线设备');
      return;
    }
    setPickAgentId(online[0].id);
    setPickerOpen(true);
  };

  const confirmPicker = () => {
    const agent = agents.find((a) => a.id === pickAgentId);
    if (!agent) return;
    addTab(agent);
    setPickerOpen(false);
  };

  const tabItems = useMemo(
    () =>
      tabs.map((tab) => ({
        key: tab.key,
        label: (
          <Space size={4}>
            <span
              style={{
                display: 'inline-block',
                width: 8,
                height: 8,
                borderRadius: '50%',
                background: tab.agent.status === 'online' ? '#52c41a' : '#d9d9d9',
              }}
            />
            {tab.label}
          </Space>
        ),
        children: <TerminalPanel agent={tab.agent} active={activeKey === tab.key} />,
        closable: true,
      })),
    [tabs, activeKey],
  );

  return (
    <div>
      <Space style={{ marginBottom: 16, width: '100%', justifyContent: 'space-between' }}>
        <Typography.Title level={4} style={{ margin: 0 }}>
          终端会话
        </Typography.Title>
        <Space>
          <Button type="primary" icon={<PlusOutlined />} onClick={openPicker}>
            新建连接
          </Button>
          <Button onClick={() => navigate('/agents')}>设备管理</Button>
        </Space>
      </Space>

      {tabs.length === 0 ? (
        <Typography.Paragraph type="secondary">
          点击「新建连接」同时打开多台设备，或在设备列表点击「连接」/「新标签连接」。同一设备也可打开多个会话。
        </Typography.Paragraph>
      ) : (
        <Tabs
          type="editable-card"
          hideAdd
          activeKey={activeKey}
          onChange={setActiveKey}
          onEdit={(targetKey, action) => {
            if (action !== 'remove' || typeof targetKey !== 'string') return;
            setTabs((prev) => {
              const next = prev.filter((t) => t.key !== targetKey);
              if (activeKey === targetKey) {
                setActiveKey(next[next.length - 1]?.key);
              }
              return next;
            });
          }}
          items={tabItems}
          destroyInactiveTabPane={false}
        />
      )}

      <Modal
        title="选择设备"
        open={pickerOpen}
        onOk={confirmPicker}
        onCancel={() => setPickerOpen(false)}
      >
        <Select
          style={{ width: '100%' }}
          value={pickAgentId ?? undefined}
          onChange={setPickAgentId}
          options={agents.map((a) => ({
            value: a.id,
            label: `${a.name} (${a.status === 'online' ? '在线' : '离线'})`,
            disabled: a.status !== 'online',
          }))}
        />
      </Modal>
    </div>
  );
}
