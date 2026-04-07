import { getAccessToken } from './auth'
import { resolveAssetUrl } from './config'

const imageTaskCache = {}

export function loadProtectedImage(url) {
	if (!url) {
		return Promise.resolve('')
	}

	const absoluteUrl = resolveAssetUrl(url)
	if (imageTaskCache[absoluteUrl]) {
		return imageTaskCache[absoluteUrl]
	}

	imageTaskCache[absoluteUrl] = new Promise((resolve, reject) => {
		const header = {}
		const accessToken = getAccessToken()
		if (accessToken) {
			header.Authorization = `Bearer ${accessToken}`
		}

		uni.downloadFile({
			url: absoluteUrl,
			header,
			success: (response) => {
				if (response.statusCode >= 200 && response.statusCode < 300 && response.tempFilePath) {
					resolve(response.tempFilePath)
					return
				}
				delete imageTaskCache[absoluteUrl]
				reject(new Error(`Image load failed (${response.statusCode})`))
			},
			fail: (error) => {
				delete imageTaskCache[absoluteUrl]
				reject(new Error(error.errMsg || 'Image load failed'))
			}
		})
	})

	return imageTaskCache[absoluteUrl]
}