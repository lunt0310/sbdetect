export const API_BASE_URL = 'http://127.0.0.1:8000'
export const MINIAPP_API_PREFIX = '/api/miniapp'

function stripTrailingSlash(value) {
	return (value || '').replace(/\/+$/, '')
}

function isAbsoluteUrl(value) {
	return /^https?:\/\//i.test(value || '')
}

export function buildApiUrl(path) {
	if (!path) {
		return stripTrailingSlash(API_BASE_URL)
	}
	if (isAbsoluteUrl(path)) {
		return path
	}
	const normalizedPath = path.startsWith('/') ? path : `/${path}`
	return `${stripTrailingSlash(API_BASE_URL)}${normalizedPath}`
}

export function resolveAssetUrl(url) {
	if (!url) {
		return ''
	}
	if (isAbsoluteUrl(url)) {
		return url
	}
	return `${stripTrailingSlash(API_BASE_URL)}${url.startsWith('/') ? url : `/${url}`}` //添加/
}
