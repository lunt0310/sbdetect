<template>
	<view class="page">
		<view class="fixed-panel">
			<view class="top-bar">
				<view>
					<text class="page-title">车辆违法记录查询</text>
				</view>
				<button class="plus-button" @click="openBindCard">+</button>
			</view>

			<view class="filter-card">
				<picker
					class="filter-picker"
					mode="selector"
					:range="plateFilterOptions"
					range-key="label"
					:value="selectedPlateIndex"
					@change="onPlateFilterChange"
				>
					<view class="filter-item">
						<text class="filter-name">车牌</text>
						<view class="filter-value-row">
							<text class="filter-value">{{ selectedPlateLabel }}</text>
							<text class="filter-arrow">∨</text>
						</view>
					</view>
				</picker>

				<picker
					class="filter-picker"
					mode="selector"
					:range="violationStatusOptions"
					range-key="label"
					:value="selectedStatusIndex"
					@change="onStatusFilterChange"
				>
					<view class="filter-item no-border">
						<text class="filter-name">状态</text>
						<view class="filter-value-row">
							<text class="filter-value">{{ selectedStatusLabel }}</text>
							<text class="filter-arrow">∨</text>
						</view>
					</view>
				</picker>
			</view>

			<view class="section-header">
				<text class="section-title">违法记录</text>
				<text class="section-total">共 {{ total }} 条</text>
			</view>
		</view>

		<scroll-view class="list-scroll" scroll-y show-scrollbar="false">
			<view v-if="violations.length" class="violation-list">
				<view v-for="item in violations" :key="item.id" class="violation-card" @click="goToDetail(item.id)">
					<view class="violation-head">
						<text class="plate-text">{{ item.plate_text }}</text>
						<text class="status-text" :class="statusClass(getStatusValue(item))">
							{{ getDisplayStatus(item) }}
						</text>
					</view>
					<text class="violation-no">{{ item.violation_no }}</text>
					<view class="info-row">
						<text class="info-label">违法类型</text>
						<text class="info-value">{{ getTypeLabel(item.violation_type) }}</text>
					</view>
					<view class="info-row">
						<text class="info-label">任务号</text>
						<text class="info-value">{{ item.task_no || '--' }}</text>
					</view>
					<view class="info-row">
						<text class="info-label">创建时间</text>
						<text class="info-value">{{ formatDateTime(item.created_at) }}</text>
					</view>
				</view>
			</view>
			<view v-else class="empty-list-card">
				<text class="empty-list-title">暂无违法记录</text>
				<text class="empty-list-desc">切换筛选条件后再试试。</text>
			</view>
		</scroll-view>

		<view v-if="bindCardVisible" class="mask" @click="closeBindCard"></view>
		<view v-if="bindCardVisible" class="bind-dialog">
			<view class="dialog-head">
				<text class="dialog-title">绑定车牌</text>
				<button class="dialog-close" @click="closeBindCard">关闭</button>
			</view>
			<input
				class="plate-input"
				:value="bindPlateForm.plate_text"
				placeholder="请输入车牌号，例如：浙A12345"
				placeholder-class="input-placeholder"
				maxlength="8"
				@input="onPlateInput"
			/>
			<view class="dialog-actions">
				<button class="dialog-cancel" @click="closeBindCard">取消</button>
				<button class="dialog-confirm" :disabled="plateSubmitting" @click="handleBindPlate">
					{{ plateSubmitting ? '绑定中...' : '确认绑定' }}
				</button>
			</view>
		</view>
	</view>
</template>

<script>
import { isAuthenticated, saveSession } from '../../utils/auth'
import {
	bindPlate,
	fetchCurrentUser,
	fetchViolations,
	listPlates
} from '../../utils/api'
import {
	getViolationStatusLabel,
	getViolationRecordStatusLabel,
	getViolationTypeLabel,
	VIOLATION_STATUS_OPTIONS
} from '../../utils/dicts'
import { formatDateTime } from '../../utils/format'

const defaultBindPlateForm = () => ({
	plate_text: ''
})

const PLATE_PATTERN = /^[\u4e00-\u9fa5][A-Z][A-Z0-9港澳学警领挂]{5,6}$/

export default {
	data() {
		return {
			plates: [],
			bindCardVisible: false,
			plateSubmitting: false,
			loadingViolations: false,
			total: 0,
			violations: [],
			filters: {
				plate_text: '',
				violation_status: ''
			},
			violationStatusOptions: VIOLATION_STATUS_OPTIONS,
			requestPageSize: 100
		}
	},
	computed: {
		plateFilterOptions() {
			return [{ label: '全部车牌', value: '' }].concat(
				this.plates.map((plate) => ({
					label: plate.plate_text,
					value: plate.plate_text
				}))
			)
		},
		selectedPlateIndex() {
			const index = this.plateFilterOptions.findIndex((item) => item.value === this.filters.plate_text)
			return index === -1 ? 0 : index
		},
		selectedStatusIndex() {
			const index = this.violationStatusOptions.findIndex((item) => item.value === this.filters.violation_status)
			return index === -1 ? 0 : index
		},
		selectedPlateLabel() {
			const option = this.plateFilterOptions[this.selectedPlateIndex]
			return option ? option.label : '全部车牌'
		},
		selectedStatusLabel() {
			const option = this.violationStatusOptions[this.selectedStatusIndex]
			return option ? option.label : '全部状态'
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
		formatDateTime,
		getStatusValue(item) {
			if (item.status !== undefined && item.status !== null && item.status !== '') {
				return item.status
			}
			return item.violation_status || item.violation_status_value || ''
		},
		getDisplayStatus(item) {
			const rawStatus = this.getStatusValue(item)
			if (rawStatus !== '' && !Number.isNaN(Number(rawStatus))) {
				return getViolationRecordStatusLabel(Number(rawStatus))
			}
			return (
				item.violation_status_label ||
				item.violation_status_display ||
				item.status_label ||
				item.status_text ||
				getViolationStatusLabel(rawStatus)
			)
		},
		getTypeLabel(type) {
			return getViolationTypeLabel(type)
		},
		statusClass(status) {
			const numericStatus = Number(status)
			if (!Number.isNaN(numericStatus)) {
				return {
					pending: numericStatus === 1,
					rejected: numericStatus === 3,
					processed: numericStatus === 0 || numericStatus === 2
				}
			}
			return {
				pending: status === 'pending_review',
				rejected: status === 'rejected',
				processed: status === 'handled' || status === 'confirmed'
			}
		},
		redirectToAuth() {
			uni.reLaunch({ url: '/pages/auth/index' })
		},
		async bootstrap(fromPullDown) {
			const isPullDown = fromPullDown === true
			try {
				await this.loadProfile()
				await this.loadViolations()
			} finally {
				if (isPullDown) {
					uni.stopPullDownRefresh()
				}
			}
		},
		async loadProfile() {
			try {
				const [profile, plates] = await Promise.all([fetchCurrentUser(), listPlates()])
				this.plates = plates || []
				if (!this.plates.some((plate) => plate.plate_text === this.filters.plate_text)) {
					this.filters.plate_text = ''
				}
				saveSession({
					...(profile.user || {}),
					bound_plates: profile.bound_plates || plates || []
				})
			} catch (error) {
				this.notify(error.message || '加载用户信息失败')
			}
		},
		async loadViolations() {
			this.loadingViolations = true
			try {
				const baseFilters = {
					plate_text: this.filters.plate_text,
					violation_status: this.filters.violation_status
				}
				const firstPage = await fetchViolations({
					...baseFilters,
					page: 1,
					page_size: this.requestPageSize
				})
				const allItems = [].concat(firstPage.items || [])
				const total = Number(firstPage.total || 0)
				const totalPages = Math.max(1, Math.ceil(total / this.requestPageSize))

				for (let page = 2; page <= totalPages; page += 1) {
					const nextPage = await fetchViolations({
						...baseFilters,
						page,
						page_size: this.requestPageSize
					})
					allItems.push(...(nextPage.items || []))
				}

				this.violations = allItems
				this.total = total
			} catch (error) {
				this.notify(error.message || '加载违法记录失败')
			} finally {
				this.loadingViolations = false
			}
		},
		onPlateFilterChange(event) {
			const option = this.plateFilterOptions[Number(event.detail.value)] || this.plateFilterOptions[0]
			this.filters.plate_text = option.value
			this.loadViolations()
		},
		onStatusFilterChange(event) {
			const option = this.violationStatusOptions[Number(event.detail.value)] || this.violationStatusOptions[0]
			this.filters.violation_status = option.value
			this.loadViolations()
		},
		goToDetail(id) {
			uni.navigateTo({
				url: `/pages/violation/detail?id=${id}`
			})
		},
		openBindCard() {
			this.bindCardVisible = true
		},
		closeBindCard() {
			this.bindCardVisible = false
			this.bindPlateForm = defaultBindPlateForm()
		},
		onPlateInput(event) {
			const normalized = String(event.detail.value || '')
				.replace(/\s+/g, '')
				.toUpperCase()
				.match(/[\u4e00-\u9fa5A-Z0-9港澳学警领挂]/g)
			this.bindPlateForm.plate_text = (normalized || []).join('').slice(0, 8)
		},
		async handleBindPlate() {
			const plateText = this.bindPlateForm.plate_text
			if (!PLATE_PATTERN.test(plateText)) {
				this.notify('请输入正确的车牌号')
				return
			}
			this.plateSubmitting = true
			try {
				await bindPlate({ plate_text: plateText })
				this.notify('车牌绑定成功')
				this.closeBindCard()
				await Promise.all([this.loadProfile(), this.loadViolations()])
			} catch (error) {
				this.notify(error.message || '绑定失败')
			} finally {
				this.plateSubmitting = false
			}
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
		height: 100vh;
		padding: 32rpx 28rpx calc(28rpx + env(safe-area-inset-bottom));
		background: #f7f7f7;
		box-sizing: border-box;
		display: flex;
		flex-direction: column;
		overflow: hidden;
	}

	.fixed-panel {
		flex-shrink: 0;
	}

	.top-bar {
		display: flex;
		align-items: flex-start;
		justify-content: space-between;
		gap: 24rpx;
		padding: 22rpx 8rpx 30rpx;
	}

	.page-title {
		display: block;
		font-size: 46rpx;
		font-weight: 700;
		line-height: 1.45;
		color: #191919;
	}

	.page-desc,
	.filter-name,
	.section-total,
	.info-label,
	.dialog-tip,
	.empty-bind-desc,
	.empty-list-desc {
		font-size: 28rpx;
		line-height: 1.75;
		color: #8c8c8c;
	}

	.page-desc {
		margin-top: 12rpx;
	}

	.plus-button {
		display: flex;
		align-items: center;
		justify-content: center;
		width: 72rpx;
		min-width: 72rpx;
		height: 72rpx;
		border-radius: 18rpx;
		background: #ffffff;
		border: 1rpx solid #e6e6e6;
		font-size: 44rpx;
		line-height: 1;
		color: #191919;
		box-shadow: 0 8rpx 24rpx rgba(0, 0, 0, 0.04);
	}

	.filter-card,
	.empty-bind-card,
	.violation-card,
	.empty-list-card,
	.bind-dialog {
		background: #ffffff;
		border-radius: 24rpx;
	}

	.filter-card,
	.empty-bind-card,
	.empty-list-card {
		padding: 0 28rpx;
	}

	.filter-item {
		padding: 28rpx 0;
		border-bottom: 1rpx solid #f0f0f0;
	}

	.filter-item.no-border {
		border-bottom: none;
	}

	.filter-value-row,
	.info-row,
	.violation-head,
	.section-header,
	.dialog-head {
		display: flex;
		align-items: center;
		justify-content: space-between;
		gap: 18rpx;
	}

	.filter-value {
		font-size: 34rpx;
		font-weight: 500;
		line-height: 1.6;
		color: #191919;
	}

	.filter-arrow {
		font-size: 28rpx;
		color: #b2b2b2;
	}

	.empty-bind-card,
	.empty-list-card {
		margin-top: 0;
		padding-top: 30rpx;
		padding-bottom: 30rpx;
	}

	.empty-bind-title,
	.empty-list-title,
	.section-title,
	.plate-text {
		display: block;
		font-size: 34rpx;
		font-weight: 600;
		line-height: 1.6;
		color: #191919;
	}

	.section-header {
		margin: 34rpx 6rpx 24rpx;
	}

	.list-scroll {
		flex: 1;
		min-height: 0;
	}

	.violation-list {
		display: flex;
		flex-direction: column;
		gap: 24rpx;
		padding-bottom: calc(128rpx + env(safe-area-inset-bottom));
	}

	.violation-card {
		padding: 28rpx;
	}

	.status-text {
		font-size: 28rpx;
		font-weight: 500;
		line-height: 1.6;
		color: #07c160;
	}

	.status-text.pending {
		color: #faad14;
	}

	.status-text.rejected {
		color: #ee0a24;
	}

	.status-text.processed {
		color: #07c160;
	}

	.violation-no {
		display: block;
		margin: 20rpx 0 22rpx;
		font-size: 32rpx;
		line-height: 1.65;
		color: #4c4c4c;
	}

	.info-row {
		padding: 10rpx 0;
	}

	.info-label,
	.info-value {
		font-size: 30rpx;
		line-height: 1.7;
	}

	.info-value {
		color: #191919;
		text-align: right;
	}

	.mask {
		position: fixed;
		inset: 0;
		background: rgba(0, 0, 0, 0.32);
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
	}

	.dialog-title {
		font-size: 36rpx;
		font-weight: 600;
		line-height: 1.6;
		color: #191919;
	}

	.dialog-close {
		font-size: 28rpx;
		line-height: 1.6;
		color: #8c8c8c;
	}

	.plate-input {
		height: 94rpx;
		margin-top: 26rpx;
		padding: 0 28rpx;
		border-radius: 18rpx;
		background: #f7f7f7;
		font-size: 34rpx;
		color: #191919;
	}

	.input-placeholder {
		color: #b2b2b2;
	}

	.dialog-tip {
		display: block;
		margin-top: 16rpx;
	}

	.dialog-actions {
		display: grid;
		grid-template-columns: repeat(2, minmax(0, 1fr));
		gap: 18rpx;
		margin-top: 30rpx;
	}

	.dialog-cancel,
	.dialog-confirm {
		display: flex;
		align-items: center;
		justify-content: center;
		height: 88rpx;
		border-radius: 18rpx;
		font-size: 32rpx;
		font-weight: 600;
		line-height: 1;
	}

	.dialog-cancel {
		background: #f5f5f5;
		color: #191919;
	}

	.dialog-confirm {
		background: #07c160;
		color: #ffffff;
	}

	.dialog-confirm[disabled] {
		opacity: 0.6;
	}

	@media screen and (max-width: 420px) {
		.dialog-actions {
			grid-template-columns: 1fr;
		}
	}
</style>