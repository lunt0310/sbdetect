const SESSION_KEY = 'miniapp_session'

export function getSession() {
	return uni.getStorageSync(SESSION_KEY) || {}
}

export function saveSession(session) {
	const current = getSession()
	uni.setStorageSync(SESSION_KEY, {
		...current,
		...(session || {})
	})
}

export function clearSession() {
	uni.removeStorageSync(SESSION_KEY)
}

export function getAccessToken() {
	return getSession().access_token || ''
}

export function hasPendingWechatBind() {
	const session = getSession()
	return Boolean(session.access_token) && session.need_bind_phone === true && session.is_password_set === false
}

export function isAuthenticated() {
	return Boolean(getAccessToken())
}
