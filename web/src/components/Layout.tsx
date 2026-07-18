import { Layout as AntLayout, Menu, Button, Typography } from 'antd';
import {
  CloudServerOutlined,
  UserOutlined,
  AuditOutlined,
  SettingOutlined,
  LogoutOutlined,
} from '@ant-design/icons';
import { Outlet, useLocation, useNavigate } from 'react-router-dom';
import { User } from '../api';

const { Header, Sider, Content } = AntLayout;

export default function Layout({ user, onLogout }: { user: User; onLogout: () => void }) {
  const navigate = useNavigate();
  const location = useLocation();

  const items = [
    { key: '/agents', icon: <CloudServerOutlined />, label: '设备管理' },
    { key: '/audit', icon: <AuditOutlined />, label: '审计日志' },
    { key: '/settings', icon: <SettingOutlined />, label: '个人设置' },
  ];

  if (user.role === 'admin') {
    items.splice(1, 0, { key: '/users', icon: <UserOutlined />, label: '用户管理' });
  }

  return (
    <AntLayout style={{ minHeight: '100vh' }}>
      <Sider breakpoint="lg" collapsedWidth="0">
        <div style={{ color: '#fff', padding: 16, fontSize: 18, fontWeight: 600 }}>TunnelOps</div>
        <Menu
          theme="dark"
          mode="inline"
          selectedKeys={[location.pathname.startsWith('/terminal') ? '/agents' : location.pathname]}
          items={items}
          onClick={({ key }) => navigate(key)}
        />
      </Sider>
      <AntLayout>
        <Header
          style={{
            background: '#fff',
            padding: '0 24px',
            display: 'flex',
            alignItems: 'center',
            justifyContent: 'space-between',
          }}
        >
          <Typography.Text type="secondary">内网设备反向隧道运维平台</Typography.Text>
          <div>
            <Typography.Text style={{ marginRight: 16 }}>{user.username}</Typography.Text>
            <Button
              icon={<LogoutOutlined />}
              onClick={() => {
                localStorage.removeItem('token');
                onLogout();
                navigate('/login');
              }}
            >
              退出
            </Button>
          </div>
        </Header>
        <Content style={{ margin: 24 }}>
          <Outlet />
        </Content>
      </AntLayout>
    </AntLayout>
  );
}
