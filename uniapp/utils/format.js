export function formatDateTime(value) {
	if (!value) {
		return '--'
	}
	return String(value).replace('T', ' ').replace(/\.\d+Z?$/, '').replace(/([+-]\d{2}:\d{2})$/, ' $1')
}

export function formatRole(role) {
	if (!role) {
		return '--'
	}
	if (role === 'user') {
		return '普通用户'
	}
	if (role === 'admin') {
		return '管理员'
	}
	return role
}
