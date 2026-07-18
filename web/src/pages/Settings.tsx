import { Button, Card, Form, Input, Space, Typography, message } from 'antd';
import { User, deleteSshKey, getMe, updateSshKey } from '../api';

export default function Settings({
  user,
  onUpdate,
}: {
  user: User;
  onUpdate: (user: User) => void;
}) {
  const [form] = Form.useForm();

  const saveKey = async () => {
    try {
      const values = await form.validateFields();
      await updateSshKey(values.private_key);
      message.success('SSH 私钥已保存');
      onUpdate(await getMe());
    } catch (err: unknown) {
      const detail =
        (err as { response?: { data?: { detail?: string } } })?.response?.data?.detail ||
        (err as Error)?.message ||
        '保存失败';
      message.error(typeof detail === 'string' ? detail : '保存失败');
    }
  };

  const removeKey = async () => {
    await deleteSshKey();
    message.success('SSH 私钥已删除');
    form.resetFields();
    onUpdate(await getMe());
  };

  return (
    <Space direction="vertical" size="large" style={{ width: '100%', maxWidth: 640 }}>
      <Card title="账号信息">
        <Typography.Paragraph>用户名: {user.username}</Typography.Paragraph>
        <Typography.Paragraph>角色: {user.role}</Typography.Paragraph>
        <Typography.Paragraph>
          SSH 密钥: {user.has_ssh_key ? '已配置（连接设备时可选择密钥登录）' : '未配置'}
        </Typography.Paragraph>
      </Card>

      <Card title="通用 SSH 私钥">
        <Typography.Paragraph type="secondary">
          设置后，在连接内网设备时可选择「密钥」认证方式，无需每次输入密码。支持 OpenSSH / PEM 格式的 Ed25519、RSA、ECDSA 私钥。
        </Typography.Paragraph>
        <Form form={form} layout="vertical">
          <Form.Item
            name="private_key"
            label="私钥内容"
            rules={[{ required: true, message: '请粘贴私钥' }]}
          >
            <Input.TextArea
              rows={10}
              placeholder={'-----BEGIN OPENSSH PRIVATE KEY-----\n...\n-----END OPENSSH PRIVATE KEY-----'}
              style={{ fontFamily: 'monospace' }}
            />
          </Form.Item>
          <Space>
            <Button type="primary" onClick={saveKey}>
              保存私钥
            </Button>
            {user.has_ssh_key && (
              <Button danger onClick={removeKey}>
                删除私钥
              </Button>
            )}
          </Space>
        </Form>
      </Card>
    </Space>
  );
}
