import { clearSession, getAccessToken } from './auth'
import { buildApiUrl, MINIAPP_API_PREFIX } from './config'

function toQueryString(params = {}) {
	const search = Object.keys(params)
		.filter((key) => params[key] !== '' && params[key] !== undefined && params[key] !== null)
		.map((key) => `${encodeURIComponent(key)}=${encodeURIComponent(params[key])}`)
		.join('&')
	return search ? `?${search}` : ''
}

function redirectToAuth() {
	const pages = getCurrentPages()
	const current = pages[pages.length - 1]
	if (current && current.route === 'pages/auth/index') {
		return
	}
	uni.reLaunch({
		url: '/pages/auth/index'
	})
}

function request({
	url,
	method = 'GET',
	data,
	withAuth = true
}) {
	return new Promise((resolve, reject) => {
		const headers = {}
		if (withAuth && getAccessToken()) {
			headers.Authorization = `Bearer ${getAccessToken()}`
		}
		uni.request({
			url: buildApiUrl(url),
			method,
			data,
			header: headers,
			success: (response) => {
				const body = response.data || {}
				const message = body.message || `请求失败(${response.statusCode})`
				if (response.statusCode === 401 && withAuth) {
					clearSession()
					redirectToAuth()
					reject(new Error(body.message || '登录已失效'))
					return
				}
				if (response.statusCode < 200 || response.statusCode >= 300) {
					reject(new Error(message))
					return
				}
				if (typeof body.code === 'number' && body.code !== 0) {
					if (body.code === 401 && withAuth) {
						clearSession()
						redirectToAuth()
					}
					reject(new Error(message))
					return
				}
				resolve(typeof body.data === 'undefined' ? body : body.data)
			},
			fail: (error) => {
				reject(new Error(error.errMsg || '网络请求失败'))
			}
		})
	})
}

export function registerMiniapp(payload) {
	return request({
		url: `${MINIAPP_API_PREFIX}/auth/register/`,
		method: 'POST',
		data: payload,
		withAuth: false
	})
}

export function loginMiniapp(payload) {
	return request({
		url: `${MINIAPP_API_PREFIX}/auth/login/`,
		method: 'POST',
		data: payload,
		withAuth: false
	})
}

export function wxMiniappLogin(payload) {
	return request({
		url: `${MINIAPP_API_PREFIX}/auth/wx-login/`,
		method: 'POST',
		data: payload,
		withAuth: false
	})
}

export function bindMiniappPhone(payload) {
	return request({
		url: `${MINIAPP_API_PREFIX}/auth/bind-phone/`,
		method: 'POST',
		data: payload,
		withAuth: true
	})
}

export function fetchCurrentUser() {
	return request({
		url: `${MINIAPP_API_PREFIX}/me/`
	})
}

export function listPlates() {
	return request({
		url: `${MINIAPP_API_PREFIX}/plates/`
	})
}

export function bindPlate(payload) {
	return request({
		url: `${MINIAPP_API_PREFIX}/plates/`,
		method: 'POST',
		data: payload
	})
}

export function unbindPlate(id) {
	return request({
		url: `${MINIAPP_API_PREFIX}/plates/${id}/`,
		method: 'DELETE'
	})
}

export function fetchViolations(params) {
	return request({
		url: `${MINIAPP_API_PREFIX}/violations/${toQueryString(params)}`
	})
}

export function fetchViolationDetail(id) {
	return request({
		url: `${MINIAPP_API_PREFIX}/violations/${id}/`
	})
}

export function submitViolationReview(id) {
	return request({
		url: `${MINIAPP_API_PREFIX}/violations/${id}/review/`,
		method: 'POST',
		data: {}
	})
}
