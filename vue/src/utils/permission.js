export const ROLE_USER = 'user';
export const ROLE_AUDITOR = 'auditor';
export const ROLE_ADMIN = 'admin';

export const USER_INFO_KEY = 'user_info';

export const getStoredUserInfo = () => {
  try {
    return JSON.parse(localStorage.getItem(USER_INFO_KEY) || 'null');
  } catch (error) {
    return null;
  }
};

export const getStoredRole = () => getStoredUserInfo()?.role || ROLE_USER;

export const hasAnyRole = (roles = [], currentRole = getStoredRole()) => {
  if (!roles?.length) {
    return true;
  }

  return roles.includes(currentRole);
};

export const isAuditor = (role = getStoredRole()) => [ROLE_AUDITOR, ROLE_ADMIN].includes(role);
export const isAdmin = (role = getStoredRole()) => role === ROLE_ADMIN;
