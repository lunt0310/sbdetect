const USER_LIST_KEY = 'mock_user_list';
const LOG_LIST_KEY = 'mock_system_logs';
const USER_INFO_KEY = 'user_info';

const parseJSON = (value, fallback) => {
  try {
    return JSON.parse(value);
  } catch (error) {
    return fallback;
  }
};

const nowText = () => new Date().toLocaleString('zh-CN', { hour12: false });

const buildSeedUsers = () => {
  const currentUser = parseJSON(localStorage.getItem(USER_INFO_KEY) || 'null', null);
  const defaultUsers = [
    {
      id: 1,
      username: 'admin',
      phone: '13800000000',
      email: 'admin@test.com',
      role: 'admin',
      is_active: true,
      date_joined: nowText()
    },
    {
      id: 2,
      username: 'auditor01',
      phone: '13900000001',
      email: 'auditor@test.com',
      role: 'auditor',
      is_active: true,
      date_joined: nowText()
    },
    {
      id: 3,
      username: 'user01',
      phone: '13700000002',
      email: 'user@test.com',
      role: 'user',
      is_active: true,
      date_joined: nowText()
    }
  ];

  if (!currentUser?.username) {
    return defaultUsers;
  }

  const merged = [
    {
      id: currentUser.id || 99,
      username: currentUser.username,
      phone: currentUser.phone || '',
      email: currentUser.email || '',
      role: currentUser.role || 'user',
      is_active: currentUser.is_active !== false,
      date_joined: currentUser.date_joined || nowText()
    },
    ...defaultUsers.filter((item) => item.username !== currentUser.username)
  ];

  return merged;
};

export const getMockUsers = () => {
  const stored = parseJSON(localStorage.getItem(USER_LIST_KEY) || 'null', null);
  if (stored?.length) {
    return stored;
  }

  const seed = buildSeedUsers();
  localStorage.setItem(USER_LIST_KEY, JSON.stringify(seed));
  return seed;
};

export const saveMockUsers = (users) => {
  localStorage.setItem(USER_LIST_KEY, JSON.stringify(users));
};

export const getSystemLogs = () => {
  const stored = parseJSON(localStorage.getItem(LOG_LIST_KEY) || 'null', null);
  if (stored?.length) {
    return stored;
  }

  const seedLogs = [
    {
      id: 1,
      action: 'login',
      operator: 'system',
      target: '安全带检测系统',
      detail: '系统初始化日志',
      created_at: nowText(),
      level: 'info'
    },
    {
      id: 2,
      action: 'audit',
      operator: 'auditor01',
      target: '违规记录',
      detail: '审核员查看了全量检测记录',
      created_at: nowText(),
      level: 'warning'
    }
  ];

  localStorage.setItem(LOG_LIST_KEY, JSON.stringify(seedLogs));
  return seedLogs;
};

export const saveSystemLogs = (logs) => {
  localStorage.setItem(LOG_LIST_KEY, JSON.stringify(logs));
};

export const appendSystemLog = ({ action, operator, target, detail, level = 'info' }) => {
  const logs = getSystemLogs();
  const nextId = logs.length ? Math.max(...logs.map((item) => Number(item.id) || 0)) + 1 : 1;
  const newLog = {
    id: nextId,
    action,
    operator,
    target,
    detail,
    created_at: nowText(),
    level
  };

  const merged = [newLog, ...logs];
  saveSystemLogs(merged);
  return newLog;
};

export const createMockUser = (payload, operator) => {
  const users = getMockUsers();
  const nextId = users.length ? Math.max(...users.map((item) => Number(item.id) || 0)) + 1 : 1;
  const newUser = {
    id: nextId,
    username: payload.username,
    phone: payload.phone,
    email: payload.email,
    role: payload.role,
    is_active: payload.is_active !== false,
    date_joined: nowText()
  };

  const merged = [newUser, ...users];
  saveMockUsers(merged);
  appendSystemLog({
    action: 'create_user',
    operator,
    target: payload.username,
    detail: `创建用户 ${payload.username}，角色 ${payload.role}`,
    level: 'success'
  });
  return newUser;
};

export const updateMockUser = (id, payload, operator) => {
  const users = getMockUsers();
  const merged = users.map((item) => (Number(item.id) === Number(id)
    ? {
        ...item,
        ...payload
      }
    : item));

  saveMockUsers(merged);
  appendSystemLog({
    action: 'update_user',
    operator,
    target: payload.username || `ID:${id}`,
    detail: `修改用户信息 ${payload.username || id}`,
    level: 'warning'
  });
  return merged.find((item) => Number(item.id) === Number(id));
};

export const toggleMockUserStatus = (id, operator) => {
  const users = getMockUsers();
  let changedUser = null;
  const merged = users.map((item) => {
    if (Number(item.id) !== Number(id)) {
      return item;
    }

    changedUser = {
      ...item,
      is_active: !item.is_active
    };
    return changedUser;
  });

  saveMockUsers(merged);

  if (changedUser) {
    appendSystemLog({
      action: changedUser.is_active ? 'enable_user' : 'disable_user',
      operator,
      target: changedUser.username,
      detail: `${changedUser.is_active ? '启用' : '停用'}用户 ${changedUser.username}`,
      level: changedUser.is_active ? 'success' : 'danger'
    });
  }

  return changedUser;
};

export const resetMockUserPassword = (id, operator) => {
  const users = getMockUsers();
  const targetUser = users.find((item) => Number(item.id) === Number(id));
  const newPassword = `Pass@${String(id).padStart(4, '0')}`;

  if (targetUser) {
    appendSystemLog({
      action: 'reset_password',
      operator,
      target: targetUser.username,
      detail: `重置用户 ${targetUser.username} 的密码`,
      level: 'warning'
    });
  }

  return {
    user: targetUser,
    newPassword
  };
};
