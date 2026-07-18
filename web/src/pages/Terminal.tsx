import { useEffect, useState } from 'react';
import { useNavigate, useParams } from 'react-router-dom';
import { Spin } from 'antd';
import { Agent, listAgents } from '../api';

/** 兼容旧链接 /terminal/:agentId，跳转到多会话工作区 */
export default function TerminalRedirect() {
  const { agentId } = useParams();
  const navigate = useNavigate();
  const [, setReady] = useState(false);

  useEffect(() => {
    if (!agentId) {
      navigate('/sessions', { replace: true });
      return;
    }
    listAgents()
      .then((list) => {
        const agent = list.find((a) => a.id === Number(agentId));
        if (agent) {
          navigate(`/sessions?agent=${agent.id}`, { replace: true });
        } else {
          navigate('/sessions', { replace: true });
        }
      })
      .finally(() => setReady(true));
  }, [agentId, navigate]);

  return <Spin fullscreen tip="正在打开终端..." />;
}
