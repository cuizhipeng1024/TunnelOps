import { Button, Form, Input, Modal, Select, Space, Table, Tag, message } from 'antd';
import { PlusOutlined } from '@ant-design/icons';
import { useEffect, useState } from 'react';
import { User, createUser, deleteUser, listUsers, updateUser } from '../api';

export default function Users({ user }: { user: User }) {
  const [users, setUsers] = useState<User[]>([]);
  const [loading, setLoading] = useState(false);
  const [modalOpen, setModalOpen] = useState(false);
  const [form] = Form.useForm();

  const load = async () => {
    setLoading(true);
    try {
      setUsers(await listUsers());
    } finally {
      setLoading(false);
    }
  };

  useEffect(() => {
    load();
  }, []);

  if (user.role !== 'admin') {
    return <div>无权限</div>;
  }

  const columns = [
    { title: 'ID', dataIndex: 'id', width: 60 },
    { title: '用户名', dataIndex: 'username' },
    {
      title: '角色',
      dataIndex: 'role',
      render: (r: string) => <Tag color={r === 'admin' ? 'red' : 'blue'}>{r}</Tag>,
    },
    {
      title: 'SSH 密钥',
      dataIndex: 'has_ssh_key',
      render: (v: boolean) => (v ? '已配置' : '未配置'),
    },
    { title: '创建时间', dataIndex: 'created_at' },
    {
      title: '操作',
      render: (_: unknown, record: User) => (
        <Space>
          <Button
            size="small"
            onClick={() => {
              form.setFieldsValue({ username: record.username, role: record.role });
              Modal.confirm({
                title: '修改用户',
                content: (
                  <Form form={form} layout="vertical" style={{ marginTop: 16 }}>
                    <Form.Item name="password" label="新密码（留空则不修改）">
                      <Input.Password />
                    </Form.Item>
                    <Form.Item name="role" label="角色">
                      <Select options={[{ value: 'admin', label: 'admin' }, { value: 'user', label: 'user' }]} />
                    </Form.Item>
                  </Form>
                ),
                onOk: async () => {
                  const values = form.getFieldsValue();
                  await updateUser(record.id, {
                    password: values.password || undefined,
                    role: values.role,
                  });
                  message.success('已更新');
                  load();
                },
              });
            }}
          >
            编辑
          </Button>
          <Button
            size="small"
            danger
            disabled={record.id === user.id}
            onClick={async () => {
              await deleteUser(record.id);
              message.success('已删除');
              load();
            }}
          >
            删除
          </Button>
        </Space>
      ),
    },
  ];

  return (
    <>
      <div style={{ display: 'flex', justifyContent: 'space-between', marginBottom: 16 }}>
        <h3 style={{ margin: 0 }}>用户管理</h3>
        <Button
          type="primary"
          icon={<PlusOutlined />}
          onClick={() => {
            form.resetFields();
            setModalOpen(true);
          }}
        >
          添加用户
        </Button>
      </div>
      <Table rowKey="id" loading={loading} columns={columns} dataSource={users} />

      <Modal
        title="添加用户"
        open={modalOpen}
        onOk={async () => {
          const values = await form.validateFields();
          await createUser(values);
          message.success('用户已创建');
          setModalOpen(false);
          load();
        }}
        onCancel={() => setModalOpen(false)}
      >
        <Form form={form} layout="vertical">
          <Form.Item name="username" label="用户名" rules={[{ required: true }]}>
            <Input />
          </Form.Item>
          <Form.Item name="password" label="密码" rules={[{ required: true, min: 6 }]}>
            <Input.Password />
          </Form.Item>
          <Form.Item name="role" label="角色" initialValue="user">
            <Select options={[{ value: 'admin', label: 'admin' }, { value: 'user', label: 'user' }]} />
          </Form.Item>
        </Form>
      </Modal>
    </>
  );
}
