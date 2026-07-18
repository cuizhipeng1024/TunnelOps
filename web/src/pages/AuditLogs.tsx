import { Table, Tag } from 'antd';
import { useEffect, useState } from 'react';
import { AuditLog, listAuditLogs } from '../api';

const actionLabels: Record<string, string> = {
  login: '登录',
  logout: '退出',
  agent_create: '创建设备',
  agent_update: '更新设备',
  agent_delete: '删除设备',
  shell_connect: 'Shell 连接',
  shell_disconnect: 'Shell 断开',
  user_create: '创建用户',
  user_update: '更新用户',
  user_delete: '删除用户',
  key_update: '更新密钥',
};

export default function AuditLogs() {
  const [logs, setLogs] = useState<AuditLog[]>([]);
  const [loading, setLoading] = useState(false);

  useEffect(() => {
    setLoading(true);
    listAuditLogs(200)
      .then(setLogs)
      .finally(() => setLoading(false));
  }, []);

  const columns = [
    { title: '时间', dataIndex: 'created_at', width: 180 },
    { title: '用户', dataIndex: 'username', width: 120 },
    {
      title: '操作',
      dataIndex: 'action',
      width: 120,
      render: (a: string) => <Tag>{actionLabels[a] || a}</Tag>,
    },
    { title: '目标', dataIndex: 'target', ellipsis: true },
    { title: '详情', dataIndex: 'detail', ellipsis: true },
    { title: 'IP', dataIndex: 'ip_address', width: 140 },
  ];

  return (
    <>
      <h3 style={{ marginBottom: 16 }}>审计日志</h3>
      <Table rowKey="id" loading={loading} columns={columns} dataSource={logs} pagination={{ pageSize: 20 }} />
    </>
  );
}
