<template>
	<view class="page">
		<view class="top-bar">
			<view class="top-copy">
				<text class="page-title">用户注册</text>
			</view>
			<button class="top-action" @click="goToLogin">返回登录</button>
		</view>

		<view class="section">

			<view class="form">
				<view class="field">
					<text class="label">手机号</text>
					<input
						v-model.trim="registerForm.phone"
						class="input"
						type="number"
						placeholder="请输入 11 位手机号"
						placeholder-class="input-placeholder"
					/>
				</view>

				<view class="field">
					<text class="label">密码</text>
					<input
						v-model="registerForm.password"
						class="input"
						type="password"
						password
						placeholder="至少 6 位密码"
						placeholder-class="input-placeholder"
					/>
				</view>

				<view class="field">
					<text class="label">确认密码</text>
					<input
						v-model="registerForm.confirm_password"
						class="input"
						type="password"
						password
						placeholder="请再次输入密码"
						placeholder-class="input-placeholder"
					/>
				</view>

				<button class="primary-button" :disabled="submitting" @click="handleRegister">
					{{ submitting ? '注册中...' : '注册并登录' }}
				</button>
			</view>
		</view>

	
	</view>
</template>

<script>
import { isAuthenticated, saveSession } from '../../utils/auth'
import { registerMiniapp } from '../../utils/api'

const defaultRegisterForm = () => ({
	phone: '',
	password: '',
	confirm_password: ''
})

export default {
	data() {
		return {
			submitting: false,
			registerForm: defaultRegisterForm()
		}
	},
	onShow() {
		if (isAuthenticated()) {
			this.goHome()
		}
	},
	methods: {
		validateRegister() {
			if (!/^1\d{10}$/.test(this.registerForm.phone)) {
				return '请输入正确的手机号'
			}
			if (!this.registerForm.password || this.registerForm.password.length < 6) {
				return '密码长度至少 6 位'
			}
			if (this.registerForm.password !== this.registerForm.confirm_password) {
				return '两次输入的密码不一致'
			}
			return ''
		},
		async handleRegister() {
			const error = this.validateRegister()
			if (error) {
				this.notify(error)
				return
			}
			this.submitting = true
			try {
				const data = await registerMiniapp(this.registerForm)
				saveSession(data)
				this.notify('注册成功')
				this.registerForm = defaultRegisterForm()
				this.goHome()
			} catch (requestError) {
				this.notify(requestError.message || '注册失败')
			} finally {
				this.submitting = false
			}
		},
		goToLogin() {
			const pages = getCurrentPages()
			if (pages.length > 1) {
				uni.navigateBack()
				return
			}
			uni.redirectTo({
				url: '/pages/auth/index'
			})
		},
		notify(message) {
			uni.showToast({
				title: message,
				icon: 'none'
			})
		},
		goHome() {
			uni.reLaunch({
				url: '/pages/index/index'
			})
		}
	}
}
</script>

<style scoped>
	.page {
		--primary: #2e5b9a;
		--primary-light: #5e89c4;
		--warning: #d49b3d;
		--warning-light: #e3b45d;
		--text: #24324b;
		--subtext: #66758f;
		--bg-page: #f4f7fb;
		--bg-soft: rgba(244, 247, 251, 0.95);
		--border-soft: rgba(68, 93, 140, 0.12);
		min-height: 100vh;
		padding: 32rpx 28rpx calc(156rpx + env(safe-area-inset-bottom));
		background: var(--bg-page);
	}

	.top-bar {
		display: flex;
		align-items: flex-start;
		justify-content: space-between;
		gap: 24rpx;
		padding: 22rpx 8rpx 36rpx;
	}

	.top-copy {
		flex: 1;
	}

	.page-title {
		display: block;
		font-size: 44rpx;
		font-weight: 700;
		color: var(--text);
	}

	.page-desc,
	.section-tip,
	.section-desc {
		font-size: 26rpx;
		line-height: 1.7;
		color: var(--subtext);
	}

	.page-desc {
		margin-top: 12rpx;
	}

	.top-action {
		display: inline-flex;
		align-items: center;
		justify-content: center;
		height: 72rpx;
		padding: 0 28rpx;
		border-radius: 18rpx;
		background: transparent;
		border: 1rpx solid var(--border-soft);
		font-size: 28rpx;
		font-weight: 600;
		color: var(--primary);
	}

	.section {
		padding: 0 10rpx;
	}

	.section-gap {
		margin-top: 36rpx;
	}

	.section-head {
		display: flex;
		align-items: center;
		justify-content: space-between;
		gap: 18rpx;
		margin-bottom: 28rpx;
	}

	.section-title,
	.label {
		font-size: 32rpx;
		font-weight: 600;
		color: var(--text);
	}

	.form,
	.field {
		display: flex;
		flex-direction: column;
	}

	.form {
		gap: 24rpx;
	}

	.field {
		gap: 14rpx;
	}

	.input {
		height: 94rpx;
		padding: 0 28rpx;
		border-radius: 18rpx;
		background: var(--bg-soft);
		border: 1rpx solid transparent;
		font-size: 30rpx;
		color: var(--text);
	}

	.input-placeholder {
		color: var(--subtext);
	}

	.primary-button {
		display: flex;
		align-items: center;
		justify-content: center;
		height: 94rpx;
		border-radius: 18rpx;
		font-size: 30rpx;
		font-weight: 600;
		line-height: 1;
		text-align: center;
		background: linear-gradient(145deg, var(--warning), var(--warning-light));
		color: #ffffff;
	}

	.primary-button[disabled],
	.top-action[disabled] {
		opacity: 0.6;
	}

	@media screen and (max-width: 420px) {
		.top-bar,
		.section-head {
			flex-direction: column;
			align-items: stretch;
		}

		.top-action {
			width: 100%;
		}
	}
</style>


