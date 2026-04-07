export const typeTextMap = {
  image: '图片检测',
  video: '视频检测'
};

export const taskStatusTextMap = {
  pending: '待处理',
  running: '处理中',
  completed: '已完成',
  failed: '失败',
  cancelled: '已取消'
};

export const taskResultTextMap = {
  wearing: '已佩戴安全带',
  not_wearing: '未佩戴安全带',
  uncertain: '结果不确定'
};

export const resultTextMap = {
  wear: '已佩戴安全带',
  no_wear: '未佩戴安全带',
  processing: '检测中',
  finished: '检测完成',
  success: '检测成功',
  failed: '检测失败',
  pending: '待处理',
  running: '处理中',
  completed: '已完成',
  cancelled: '已取消'
};

export const riskTextMap = {
  low: '低风险',
  medium: '中风险',
  high: '高风险'
};

export const violationStatusTextMap = {
  0: '检测完成',
  1: '申请待审核',
  2: '申请审核通过',
  3: '申请审核驳回'
};

export const roleTextMap = {
  user: '普通用户',
  auditor: '审核员',
  admin: '管理员'
};

export const objectTypeTextMap = {
  vehicle: '车辆',
  person: '人员',
  seatbelt: '安全带',
  license_plate: '车牌'
};

export const resultTagTypeMap = {
  wear: 'success',
  no_wear: 'danger',
  wearing: 'success',
  not_wearing: 'danger',
  uncertain: 'warning',
  processing: 'warning',
  finished: 'success',
  completed: 'success',
  failed: 'danger',
  cancelled: 'info',
  pending: 'info',
  running: 'warning',
  low: 'info',
  medium: 'warning',
  high: 'danger',
  0: 'info',
  1: 'warning',
  2: 'success',
  3: 'danger',
  admin: 'danger',
  auditor: 'warning',
  user: 'info'
};

export const formatTypeText = (type) => typeTextMap[type] || type || '-';
export const formatTaskStatusText = (value) => taskStatusTextMap[value] || value || '-';
export const formatTaskResultText = (value) => taskResultTextMap[value] || resultTextMap[value] || value || '-';
export const formatViolationStatusText = (value) => {
  if (value === undefined || value === null || value === '') {
    return '-';
  }

  return violationStatusTextMap[value] || String(value);
};
export const formatRiskText = (riskLevel) => riskTextMap[riskLevel] || riskLevel || '-';
export const formatRoleText = (role) => roleTextMap[role] || role || '-';
export const formatObjectTypeText = (type) => objectTypeTextMap[type] || type || '-';
export const getResultTagType = (value) => resultTagTypeMap[value] || 'info';

export const formatResultText = (record) => {
  if (!record) {
    return '-';
  }

  if (record.result_text) {
    return record.result_text;
  }

  if (record.task_result) {
    return formatTaskResultText(record.task_result);
  }

  if (record.violation_type === 'no_seatbelt') {
    return '未系安全带';
  }

  if (record.violation_no && (record.status === 0 || record.status === 1 || record.status === 2 || record.status === 3)) {
    return formatViolationStatusText(record.status);
  }

  if (record.risk_level) {
    return formatRiskText(record.risk_level);
  }

  if (record.status && taskStatusTextMap[record.status]) {
    return formatTaskStatusText(record.status);
  }

  return resultTextMap[record.result] || record.result || '-';
};

export const resolveApiUrl = (url) => {
  if (!url) {
    return '';
  }

  if (/^https?:\/\//i.test(url)) {
    return url;
  }

  const apiBaseURL = import.meta.env.VITE_API_BASE_URL || window.location.origin;
  const safeUrl = url.startsWith('/') ? url : `/${url}`;
  return `${apiBaseURL}${safeUrl}`;
};

export const resolveMediaUrl = (url) => {
  if (!url) {
    return '';
  }

  if (/^https?:\/\//i.test(url)) {
    return url;
  }

  const fileBaseURL = import.meta.env.VITE_FILE_BASE_URL || window.location.origin;
  const safeUrl = url.startsWith('/') ? url : `/${url}`;
  return `${fileBaseURL}${safeUrl}`;
};

export const getListData = (payload) => {
  if (Array.isArray(payload)) {
    return payload;
  }

  return payload?.results || payload?.items || payload?.list || payload?.data || [];
};

export const getListTotal = (payload, fallback = 0) => {
  if (Array.isArray(payload)) {
    return payload.length;
  }

  return payload?.count || payload?.total || getListData(payload).length || fallback;
};

export const getLatestResult = (task) => {
  if (!task?.results?.length) {
    return null;
  }

  return [...task.results].sort((a, b) => {
    const indexGap = Number(b.result_index || 0) - Number(a.result_index || 0);
    if (indexGap !== 0) {
      return indexGap;
    }
    return String(b.created_at || '').localeCompare(String(a.created_at || ''));
  })[0];
};

export const formatDuration = (durationMs) => {
  if (durationMs === undefined || durationMs === null || Number.isNaN(Number(durationMs))) {
    return '-';
  }

  const totalSeconds = Math.floor(Number(durationMs) / 1000);
  const minutes = Math.floor(totalSeconds / 60);
  const seconds = totalSeconds % 60;
  return `${minutes}分${seconds}秒`;
};

export const formatPercent = (value, digits = 2) => {
  if (value === undefined || value === null || Number.isNaN(Number(value))) {
    return '-';
  }

  return `${(Number(value) * 100).toFixed(digits)}%`;
};

export const formatDateTime = (value) => {
  if (!value) {
    return '-';
  }

  const date = new Date(value);
  if (Number.isNaN(date.getTime())) {
    return value;
  }

  const pad = (num) => String(num).padStart(2, '0');
  return `${date.getFullYear()}-${pad(date.getMonth() + 1)}-${pad(date.getDate())} ${pad(date.getHours())}:${pad(date.getMinutes())}:${pad(date.getSeconds())}`;
};
