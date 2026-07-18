import { BrowserRouter, Navigate, Route, Routes } from 'react-router-dom';
import { useEffect, useState } from 'react';
import { Spin } from 'antd';
import Layout from './components/Layout';
import Login from './pages/Login';
import Agents from './pages/Agents';
import Terminal from './pages/Terminal';
import Users from './pages/Users';
import AuditLogs from './pages/AuditLogs';
import Settings from './pages/Settings';
import { getMe, User } from './api';

function PrivateRoute({ children, user }: { children: React.ReactNode; user: User | null }) {
  if (!localStorage.getItem('token')) return <Navigate to="/login" replace />;
  if (!user) return <Spin fullscreen />;
  return <>{children}</>;
}

export default function App() {
  const [user, setUser] = useState<User | null>(null);
  const [loading, setLoading] = useState(!!localStorage.getItem('token'));

  useEffect(() => {
    if (!localStorage.getItem('token')) {
      setLoading(false);
      return;
    }
    getMe()
      .then(setUser)
      .catch(() => localStorage.removeItem('token'))
      .finally(() => setLoading(false));
  }, []);

  if (loading) return <Spin fullscreen />;

  return (
    <BrowserRouter>
      <Routes>
        <Route path="/login" element={<Login onLogin={setUser} />} />
        <Route
          path="/"
          element={
            <PrivateRoute user={user}>
              <Layout user={user!} onLogout={() => setUser(null)} />
            </PrivateRoute>
          }
        >
          <Route index element={<Navigate to="/agents" replace />} />
          <Route path="agents" element={<Agents />} />
          <Route path="terminal/:agentId" element={<Terminal />} />
          <Route path="users" element={<Users user={user!} />} />
          <Route path="audit" element={<AuditLogs />} />
          <Route path="settings" element={<Settings user={user!} onUpdate={setUser} />} />
        </Route>
      </Routes>
    </BrowserRouter>
  );
}
