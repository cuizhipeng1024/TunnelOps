import axios from 'axios';

const api = axios.create({ baseURL: '/api' });

api.interceptors.request.use((config) => {
  const token = localStorage.getItem('token');
  if (token) {
    config.headers.Authorization = `Bearer ${token}`;
  }
  return config;
});

api.interceptors.response.use(
  (res) => res,
  (err) => {
    if (err.response?.status === 401) {
      localStorage.removeItem('token');
      if (!window.location.pathname.includes('/login')) {
        window.location.href = '/login';
      }
    }
    return Promise.reject(err);
  }
);

export interface User {
  id: number;
  username: string;
  role: 'admin' | 'user';
  has_ssh_key: boolean;
  created_at: string;
}

export interface Agent {
  id: number;
  name: string;
  description: string | null;
  token: string;
  host: string | null;
  ssh_port: number;
  ssh_user: string;
  status: 'online' | 'offline';
  last_seen: string | null;
  created_at: string;
}

export interface AuditLog {
  id: number;
  user_id: number | null;
  username: string | null;
  action: string;
  target: string | null;
  detail: string | null;
  ip_address: string | null;
  created_at: string;
}

export async function login(username: string, password: string) {
  const form = new URLSearchParams();
  form.append('username', username);
  form.append('password', password);
  const { data } = await api.post('/auth/login', form, {
    headers: { 'Content-Type': 'application/x-www-form-urlencoded' },
  });
  return data;
}

export async function getMe() {
  const { data } = await api.get<User>('/auth/me');
  return data;
}

export async function updateSshKey(privateKey: string) {
  await api.put('/auth/ssh-key', { private_key: privateKey });
}

export async function deleteSshKey() {
  await api.delete('/auth/ssh-key');
}

export async function listAgents() {
  const { data } = await api.get<Agent[]>('/agents');
  return data;
}

export async function createAgent(payload: {
  name: string;
  description?: string;
  host?: string;
  ssh_port?: number;
  ssh_user?: string;
}) {
  const { data } = await api.post<Agent>('/agents', payload);
  return data;
}

export async function updateAgent(id: number, payload: Partial<Agent>) {
  const { data } = await api.put<Agent>(`/agents/${id}`, payload);
  return data;
}

export async function deleteAgent(id: number) {
  await api.delete(`/agents/${id}`);
}

export async function regenerateToken(id: number) {
  const { data } = await api.post<Agent>(`/agents/${id}/regenerate-token`);
  return data;
}

export async function getDeployScript(id: number, serverUrl: string) {
  const { data } = await api.get<{ script: string; token: string }>(`/agents/${id}/deploy`, {
    params: { server_url: serverUrl },
  });
  return data;
}

export async function listUsers() {
  const { data } = await api.get<User[]>('/users');
  return data;
}

export async function createUser(payload: { username: string; password: string; role: string }) {
  const { data } = await api.post<User>('/users', payload);
  return data;
}

export async function updateUser(id: number, payload: { password?: string; role?: string }) {
  const { data } = await api.put<User>(`/users/${id}`, payload);
  return data;
}

export async function deleteUser(id: number) {
  await api.delete(`/users/${id}`);
}

export async function listAuditLogs(limit = 100) {
  const { data } = await api.get<AuditLog[]>('/audit-logs', { params: { limit } });
  return data;
}

export default api;
