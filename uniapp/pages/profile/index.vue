<template>
	<view class="page">
		<view class="page-header">
			<text class="page-title">个人信息</text>
		</view>

		<view class="profile-card">
			<view class="profile-main">
				<view class="avatar">{{ avatarText }}</view>
				<view class="profile-copy">
					<text class="profile-name">{{ userInfo.username || '微信用户' }}</text>
					<text class="profile-sub">手机号：{{ userInfo.phone || '未绑定' }}</text> 
				</view>
			</view>
		</view>

		<view class="group-card stats-card">
			<view class="stats-item">
				<text class="stats-value">{{ plates.length }}</text>
				<text class="stats-label">绑定车牌号</text>
			</view>
			<view class="stats-divider"></view>
			<view class="stats-item">
				<text class="stats-value">{{ violationTotal }}</text>
				<text class="stats-label">违法总数</text>
			</view>
		</view>

		<view class="group-card menu-card">
			<view class="cell cell-head">
				<view class="cell-main">
					<text class="cell-title">已绑定车牌</text>
					<text class="cell-desc">{{ plates.length ? `共 ${plates.length} 个` : '当前还没有绑定车牌' }}</text>
				</view>
				<button class="refresh-button" :disabled="loading" @click="bootstrap">
					{{ loading ? '加载中...' : '刷新' }}
				</button>
			</view>
			<view v-if="plates.length" class="plate-list">
				<view v-for="plate in plates" :key="plate.id" class="plate-item">
					<text class="plate-text">{{ plate.plate_text }}</text>
				</view>
			</view>
		</view>

		<button class="logout-button" @click="handleLogout">退出登录</button>
	</view>
</template>

<script>
import { clearSession, isAuthenticated, saveSession } from '../../utils/auth'
import { fetchCurrentUser, fetchViolations, listPlates } from '../../utils/api'

export default {
	data() {
		return {
			userInfo: {},
			plates: [],
			violationTotal: 0,
			loading: false
		}
	},
	computed: {
		avatarText() {
			const source = this.userInfo.username || this.userInfo.phone || 'U'
			return String(source).slice(0, 1).toUpperCase()
		}
	},
	onShow() {
		if (!isAuthenticated()) {
			this.redirectToAuth()
			return
		}
		this.bootstrap()
	},
	onPullDownRefresh() {
		if (!isAuthenticated()) {
			uni.stopPullDownRefresh()
			this.redirectToAuth()
			return
		}
		this.bootstrap(true)
	},
	methods: {
		redirectToAuth() {
			uni.reLaunch({ url: '/pages/auth/index' })
		},
		async bootstrap(fromPullDown) {
			const isPullDown = fromPullDown === true
			this.loading = true
			try {
				const [profile, plates, violations] = await Promise.all([
					fetchCurrentUser(),
					listPlates(),
					fetchViolations({
						page: 1,
						page_size: 1
					})
				])
				this.userInfo = profile.user || profile || {}
				this.plates = plates || profile.bound_plates || []
				this.violationTotal = violations.total || 0
				saveSession({
					...(profile.user || profile || {}),
					bound_plates: profile.bound_plates || plates || []
				})
			} catch (error) {
				this.notify(error.message || '加载个人信息失败')
			} finally {
				this.loading = false
				if (isPullDown) {
					uni.stopPullDownRefresh()
				}
			}
		},
		handleLogout() {
			uni.showModal({
				title: '退出登录',
				content: '退出后需要重新登录，是否继续？',
				success: (result) => {
					if (!result.confirm) {
						return
					}
					clearSession()
					this.redirectToAuth()
				}
			})
		},
		notify(message) {
			uni.showToast({
				title: message,
				icon: 'none'
			})
		}
	}
}
</script>

<style scoped>
	.page {
		--primary: #2e5b9a;
		--primary-light: #5e89c4;
		--success: #2f7d67;
		--success-light: #58aa8c;
		--danger: #d95d39;
		--danger-light: #de7351;
		--text: #24324b;
		--subtext: #66758f;
		--bg-page: #f4f7fb;
		--bg-card: rgba(255, 255, 255, 0.9);
		--bg-soft: rgba(244, 247, 251, 0.8);
		--border-soft: rgba(68, 93, 140, 0.12);
		min-height: 100vh;
		padding: 34rpx 28rpx calc(176rpx + env(safe-area-inset-bottom));
		background: var(--bg-page);
	}

	.page-header {
		padding: 12rpx 10rpx 30rpx;
	}

	.page-title {
		display: block;
		font-size: 48rpx;
		font-weight: 700;
		line-height: 1.45;
		color: var(--text);
	}

	.profile-card,
	.group-card {
		background: var(--bg-card);
		border: 1rpx solid var(--border-soft);
		border-radius: 28rpx;
		box-shadow: 0 12rpx 36rpx rgba(46, 91, 154, 0.08);
	}

	.profile-card {
		display: flex;
		align-items: center;
		justify-content: space-between;
		gap: 24rpx;
		padding: 34rpx 28rpx;
	}

	.profile-main,
	.cell,
	.plate-item {
		display: flex;
		align-items: center;
		justify-content: space-between;
		gap: 20rpx;
	}

	.profile-main {
		justify-content: flex-start;
		flex: 1;
	}

	.avatar {
		width: 124rpx;
		height: 124rpx;
		border-radius: 30rpx;
		background: linear-gradient(145deg, var(--primary), var(--primary-light));
		display: flex;
		align-items: center;
		justify-content: center;
		font-size: 48rpx;
		font-weight: 700;
		color: #ffffff;
	}

	.profile-copy {
		display: flex;
		flex-direction: column;
		gap: 12rpx;
	}

	.profile-name,
	.cell-title,
	.stats-value,
	.plate-text {
		font-size: 36rpx;
		font-weight: 600;
		line-height: 1.55;
		color: var(--text);
	}

	.profile-sub,
	.cell-desc,
	.cell-value,
	.stats-label {
		font-size: 28rpx;
		line-height: 1.75;
		color: var(--subtext);
	}

	.stats-card,
	.menu-card {
		margin-top: 28rpx;
	}

	.stats-card {
		display: grid;
		grid-template-columns: repeat(3, auto);
		align-items: center;
		padding: 24rpx 12rpx;
	}

	.stats-item {
		padding: 18rpx 0;
		display: flex;
		flex-direction: column;
		align-items: center;
		gap: 10rpx;
	}

	.stats-divider {
		width: 1rpx;
		height: 86rpx;
		background: var(--border-soft);
	}

	.cell {
		padding: 32rpx 28rpx;
		border-bottom: 1rpx solid rgba(68, 93, 140, 0.08);
	}

	.cell:last-child {
		border-bottom: none;
	}

	.cell-main {
		min-width: 0;
		flex: 1;
		display: flex;
		flex-direction: column;
		gap: 10rpx;
	}

	.cell-head {
		align-items: flex-start;
	}

	.refresh-button {
		display: inline-flex;
		align-items: center;
		justify-content: center;
		min-width: 124rpx;
		height: 72rpx;
		padding: 0 28rpx;
		line-height: 1;
		text-align: center;
		border-radius: 20rpx;
		background: linear-gradient(145deg, rgba(46, 91, 154, 0.08), rgba(94, 137, 196, 0.16));
		font-size: 28rpx;
		font-weight: 600;
		color: var(--primary);
	}

	.refresh-button[disabled] {
		opacity: 0.55;
	}

	.plate-list {
		display: flex;
		flex-direction: column;
	}

	.plate-item {
		padding: 0 28rpx 28rpx;
	}

	.plate-item:first-child {
		padding-top: 10rpx;
	}

	.logout-button {
		display: flex;
		align-items: center;
		justify-content: center;
		margin-top: 36rpx;
		height: 100rpx;
		padding: 0 28rpx;
		line-height: 1;
		text-align: center;
		border-radius: 28rpx;
		background: linear-gradient(145deg, var(--danger), var(--danger-light));
		font-size: 34rpx;
		font-weight: 700;
		color: #ffffff;
	}

	@media screen and (max-width: 420px) {
		.profile-card {
			align-items: flex-start;
		}

		.cell-head {
			flex-direction: column;
			align-items: stretch;
		}

		.refresh-button {
			width: 100%;
		}
	}
</style>