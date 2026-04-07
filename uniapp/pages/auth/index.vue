<template>
	<view class="page">
		<view class="top-bar">
			<view class="top-copy">
				<text class="page-title">违法记录查询</text>
				<text class="page-desc">登录后查看车辆个人记录、处理进度</text>
			</view>
			<button class="top-action" @click="goToRegister">注册</button>
		</view>

		<view class="section">
			<view class="form">
				<view class="field">
					<text class="label">账号</text>
					<input
						v-model.trim="loginForm.account"
						class="input"
						placeholder="请输入手机号或用户名"
						placeholder-class="input-placeholder"
					/>
				</view>

				<view class="field">
					<text class="label">密码</text>
					<input
						v-model="loginForm.password"
						class="input"
						type="password"
						password
						placeholder="请输入登录密码"
						placeholder-class="input-placeholder"
					/>
				</view>

				<button class="primary-button" :disabled="submitting" @click="handleLogin">
					{{ submitting ? '登录中...' : '立即登录' }}
				</button>
			</view>
		</view>

		<!-- #ifdef MP-WEIXIN -->
		<view class="section section-gap">
			<view class="section-head compact">
				<text class="section-tip">首次登录可直接使用微信授权</text>
			</view>
			<view class="wechat-grid">
				<button class="wechat-button solid" :disabled="submitting || bindingSubmitting" @click="handleWechatAuth('login')">
					{{ submitting ? '处理中...' : '微信快捷登录' }}
				</button>
			</view>
		</view>
		<!-- #endif -->

		<!-- #ifdef MP-WEIXIN -->
		<view v-if="bindPhoneVisible" class="mask"></view>
		<view v-if="bindPhoneVisible" class="bind-dialog">
			<view class="dialog-head">
				<view>
					<text class="dialog-title">完成注册</text>
				</view>
				
			</view>


			<view class="bind-user-card">
				<text class="bind-user-label">当前账号</text>
				<text class="bind-user-value">{{ pendingWechatUser.username || '微信用户' }}</text>
			</view>

			<view class="field field-gap-none">
				<text class="label">设置密码</text>
				<input
					v-model="bindPhoneForm.password"
					class="input"
					type="password"
					password
					placeholder="至少 6 位密码"
					placeholder-class="input-placeholder"
				/>
			</view>

			<view class="field field-gap">
				<text class="label">确认密码</text>
				<input
					v-model="bindPhoneForm.confirm_password"
					class="input"
					type="password"
					password
					placeholder="请再次输入密码"
					placeholder-class="input-placeholder"
				/>
			</view>

			<button class="dialog-cancel" :disabled="bindingSubmitting" @click="skipPendingWechatBind">跳过并进入首页</button>
			<button
				class="dialog-confirm"
				open-type="getPhoneNumber"
				:disabled="!canSubmitWechatBind"
				@getphonenumber="handleGetPhoneNumber"
			>
				{{ bindingSubmitting ? '绑定中...' : '微信授权手机号并完成绑定' }}
			</button>
		</view>
		<!-- #endif -->
	</view>
</template>

<script>
import { getSession, hasPendingWechatBind, isAuthenticated, saveSession } from '../../utils/auth'
import { bindMiniappPhone, loginMiniapp, wxMiniappLogin } from '../../utils/api'

const defaultLoginForm = () => ({
	account: '',
	password: ''
})

const defaultBindPhoneForm = () => ({
	password: '',
	confirm_password: ''
})

export default {
	data() {
		return {
			submitting: false,
			bindingSubmitting: false,
			bindPhoneVisible: false,
			loginForm: defaultLoginForm(),
			bindPhoneForm: defaultBindPhoneForm(),
			pendingWechatUser: {}
		}
	},
	computed: {
		canSubmitWechatBind() {
			return (
				!this.bindingSubmitting &&
				this.bindPhoneForm.password.length >= 6 &&
				this.bindPhoneForm.password === this.bindPhoneForm.confirm_password
			)
		}
	},
	onShow() {
		if (isAuthenticated()) {
			this.goHome()
			return
		}
		this.syncPendingWechatBind()
	},
	methods: {
		validateLogin() {
			if (!this.loginForm.account) {
				return '请输入手机号或用户名'
			}
			if (!this.loginForm.password) {
				return '请输入密码'
			}
			return ''
		},
		validateBindPhoneForm() {
			if (!this.bindPhoneForm.password || this.bindPhoneForm.password.length < 6) {
				return '密码长度至少 6 位'
			}
			if (this.bindPhoneForm.password !== this.bindPhoneForm.confirm_password) {
				return '两次输入的密码不一致'
			}
			return ''
		},
		syncPendingWechatBind() {
			if (!hasPendingWechatBind()) {
				this.bindPhoneVisible = false
				this.pendingWechatUser = {}
				this.bindPhoneForm = defaultBindPhoneForm()
				return
			}
			const session = getSession()
			this.pendingWechatUser = {
				username: session.username || '',
				wx_openid: session.wx_openid || ''
			}
			this.bindPhoneVisible = true
		},
		async handleLogin() {
			const error = this.validateLogin()
			if (error) {
				this.notify(error)
				return
			}
			this.submitting = true
			try {
				const data = await loginMiniapp(this.loginForm)
				saveSession(data)
				this.notify('登录成功')
				this.loginForm = defaultLoginForm()
				this.goHome()
			} catch (requestError) {
				this.notify(requestError.message || '登录失败')
			} finally {
				this.submitting = false
			}
		},
		async handleWechatAuth(mode) {
			this.submitting = true
			try {
				const loginResult = await new Promise((resolve, reject) => {
					uni.login({
						provider: 'weixin',
						success: resolve,
						fail: reject
					})
				})
				if (!loginResult.code) {
					throw new Error('未获取到微信登录 code')
				}
				const data = await wxMiniappLogin({ code: loginResult.code })
				saveSession(data)
				if (data.need_bind_phone === true && data.is_password_set === false) {
					this.syncPendingWechatBind()
					this.notify(mode === 'register' ? '微信授权成功，可先跳过绑定' : '微信登录成功，可先跳过绑定')
					return
				}
				this.notify(mode === 'register' ? '微信快捷注册成功' : '微信登录成功')
				this.goHome()
			} catch (requestError) {
				const fallbackMessage = mode === 'register' ? '微信快捷注册失败' : '微信登录失败'
				this.notify(requestError.message || fallbackMessage)
			} finally {
				this.submitting = false
			}
		},
		async handleGetPhoneNumber(event) {
			const error = this.validateBindPhoneForm()
			if (error) {
				this.notify(error)
				return
			}
			const phoneCode = event.detail && event.detail.code
			if (!phoneCode) {
				this.notify('请先同意手机号授权')
				return
			}
			this.bindingSubmitting = true
			try {
				const data = await bindMiniappPhone({
					phone_code: phoneCode,
					password: this.bindPhoneForm.password,
					confirm_password: this.bindPhoneForm.confirm_password
				})
				saveSession(data)
				this.bindPhoneForm = defaultBindPhoneForm()
				this.bindPhoneVisible = false
				this.notify('绑定成功')
				this.goHome()
			} catch (requestError) {
				this.notify(requestError.message || '绑定失败')
			} finally {
				this.bindingSubmitting = false
			}
		},
		skipPendingWechatBind() {
			this.bindPhoneVisible = false
			this.bindPhoneForm = defaultBindPhoneForm()
			this.notify('已跳过绑定，可稍后再设置')
			this.goHome()
		},
		goToRegister() {
			uni.navigateTo({
				url: '/pages/auth/register'
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
		--success: #2f7d67;
		--success-light: #58aa8c;
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
		font-size: 50rpx;
		font-weight: 700;
		color: var(--text);
	}

	.page-desc,
	.section-tip,
	.section-desc,
	.dialog-desc,
	.bind-user-label {
		font-size: 34rpx;
		line-height: 1.7;
		color: var(--subtext);
	}

	.page-desc {
		margin-top: 12rpx;
	}

	.top-action,
	.dialog-close {
		display: inline-flex;
		align-items: center;
		justify-content: center;
		height: 72rpx;
		padding: 0 28rpx;
		border-radius: 18rpx;
		background: transparent;
		border: 1rpx solid var(--border-soft);
		font-size: 36rpx;
		font-weight: 600;
		color: var(--primary);
	}

	.section {
		padding: 0 10rpx;
	}

	.section-gap {
		margin-top: 36rpx;
	}

	.section-head,
	.dialog-head {
		display: flex;
		align-items: center;
		justify-content: space-between;
		gap: 18rpx;
		margin-bottom: 28rpx;
	}

	.section-head.compact {
		align-items: flex-start;
	}

	.section-title,
	.label,
	.dialog-title,
	.bind-user-value {
		font-size: 36rpx;
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

	.field-gap-none {
		margin-top: 0;
	}

	.field-gap {
		margin-top: 24rpx;
	}

	.input {
		height: 94rpx;
		padding: 0 28rpx;
		border-radius: 18rpx;
		background: var(--bg-soft);
		border: 1rpx solid transparent;
		font-size: 34rpx;
		color: var(--text);
	}

	.input-placeholder {
		color: var(--subtext);
	}

	.primary-button,
	.secondary-button,
	.wechat-button,
	.dialog-cancel,
	.dialog-confirm {
		display: flex;
		align-items: center;
		justify-content: center;
		height: 94rpx;
		border-radius: 18rpx;
		font-size: 34rpx;
		font-weight: 600;
		line-height: 1;
		text-align: center;
	}

	.primary-button {
		background: linear-gradient(145deg, var(--primary), var(--primary-light));
		color: #ffffff;
	}

	.wechat-button.solid,
	.dialog-confirm {
		background: linear-gradient(145deg, var(--success), var(--success-light));
		color: #ffffff;
	}

	.wechat-button.light,
	.secondary-button,
	.dialog-cancel {
		background: rgba(46, 91, 154, 0.08);
		color: var(--primary);
	}

	.wechat-grid {
		display: grid;
		grid-template-columns: repeat(2, minmax(0, 1fr));
		gap: 18rpx;
	}

	.section-desc {
		display: block;
		margin-top: 18rpx;
	}

	.primary-button[disabled],
	.secondary-button[disabled],
	.wechat-button[disabled],
	.dialog-cancel[disabled],
	.dialog-confirm[disabled],
	.dialog-close[disabled],
	.top-action[disabled] {
		opacity: 0.6;
	}

	.mask {
		position: fixed;
		inset: 0;
		background: rgba(36, 50, 75, 0.3);
		z-index: 40;
	}

	.bind-dialog {
		position: fixed;
		left: 32rpx;
		right: 32rpx;
		top: 50%;
		transform: translateY(-50%);
		padding: 32rpx;
		z-index: 41;
		background: rgba(255, 255, 255, 0.96);
		border-radius: 24rpx;
	}

	.bind-user-card {
		padding: 24rpx;
		margin-bottom: 24rpx;
		background: rgba(244, 247, 251, 0.95);
		border-radius: 18rpx;
	}

	.bind-user-value {
		display: block;
		margin-top: 12rpx;
	}

	.dialog-cancel {
		margin-top: 28rpx;
	}

	.dialog-confirm {
		margin-top: 18rpx;
	}

	@media screen and (max-width: 420px) {
		.wechat-grid {
			grid-template-columns: 1fr;
		}

		.top-bar,
		.section-head,
		.dialog-head {
			flex-direction: column;
			align-items: stretch;
		}

		.top-action,
		.dialog-close {
			width: 100%;
		}
	}
</style>