<template>
	<view class="page">
		<view v-if="detail.id" class="detail-card">
			<view class="head">
				<view>
					<text class="headline">{{ detail.violation_no }}</text>
					<text class="subline">{{ detail.plate_text }} · {{ getTypeLabel(detail.violation_type) }}</text>
				</view>
				<text class="status-badge" :class="reviewStatusClass(detail.status)">
					{{ getRecordStatusLabel(detail) }}
				</text>
			</view>

			<view class="grid">
				<view class="cell">
					<text class="cell-label">任务号</text>
					<text class="cell-value">{{ detail.task_no || '--' }}</text>
				</view>
				<view class="cell">
					<text class="cell-label">申请状态</text>
					<text class="cell-value">{{ getRecordStatusLabel(detail) }}</text>
				</view>
				<view class="cell">
					<text class="cell-label">创建时间</text>
					<text class="cell-value">{{ formatDateTime(detail.created_at) }}</text>
				</view>
				<view class="cell">
					<text class="cell-label">更新时间</text>
					<text class="cell-value">{{ formatDateTime(detail.updated_at) }}</text>
				</view>
				<view class="cell">
					<text class="cell-label">审核时间</text>
					<text class="cell-value">{{ formatDateTime(detail.audit_time) }}</text>
				</view>
				<view class="cell">
					<text class="cell-label">处理时间</text>
					<text class="cell-value">{{ formatDateTime(detail.handled_time) }}</text>
				</view>
			</view>

			<view class="remark-group">
				<view class="remark-card">
					<text class="remark-title">审核备注</text>
					<text class="remark-text">{{ detail.audit_remark || '暂无审核备注' }}</text>
				</view>
				<view class="remark-card">
					<text class="remark-title">处理备注</text>
					<text class="remark-text">{{ detail.handled_remark || '暂无处理备注' }}</text>
				</view>
			</view>

			<view v-if="previewUrls.length" class="images-panel">
				<text class="section-title">违法图片</text>
				<view class="image-grid">
					<image
						v-for="url in previewUrls"
						:key="url"
						class="evidence-image"
						:src="url"
						mode="aspectFill"
						@click="preview(url)"
					/>
				</view>
			</view>

			<view class="action-group">
				<button
					v-if="canApplyReview(detail)"
					class="review-button"
					:disabled="reviewSubmitting"
					@click="handleApplyReview"
				>
					{{ reviewSubmitting ? '申请中...' : '申请复核' }}
				</button>
				<button class="primary-button" :disabled="loading" @click="loadDetail">
					{{ loading ? '刷新中...' : '刷新详情' }}
				</button>
			</view>
		</view>

		<view v-else class="empty-state">
			<text class="empty-title">正在加载违法详情</text>
			<text class="empty-desc">如果长时间没有结果，请检查登录状态或详情 ID 是否正确。</text>
		</view>
	</view>
</template>

<script>
import { isAuthenticated } from '../../utils/auth'
import { fetchViolationDetail, submitViolationReview } from '../../utils/api'
import { loadProtectedImage } from '../../utils/media'
import { getViolationRecordStatusLabel, getViolationTypeLabel } from '../../utils/dicts'
import { formatDateTime } from '../../utils/format'

export default {
	data() {
		return {
			id: '',
			loading: false,
			reviewSubmitting: false,
			detail: {},
			detailPreviewUrls: []
		}
	},
	computed: {
		previewUrls() {
			return this.detailPreviewUrls
		}
	},
	onLoad(options) {
		if (!isAuthenticated()) {
			uni.reLaunch({ url: '/pages/auth/index' })
			return
		}
		this.id = options.id || ''
		if (!this.id) {
			this.notify('缺少违法记录 ID')
			setTimeout(() => {
				uni.navigateBack()
			}, 300)
			return
		}
		this.loadDetail()
	},
	methods: {
		formatDateTime,
		getTypeLabel(type) {
			return getViolationTypeLabel(type)
		},
		getRecordStatusLabel(record) {
			return getViolationRecordStatusLabel(Number(record.status))
		},
		reviewStatusClass(status) {
			return {
				ready: Number(status) === 0,
				pending: Number(status) === 1,
				approved: Number(status) === 2,
				rejected: Number(status) === 3
			}
		},
		canApplyReview(record) {
			return Number(record.status) === 0
		},
		async loadDetail() {
			if (!this.id) {
				return
			}
			this.loading = true
			try {
				this.detail = await fetchViolationDetail(this.id)
				await this.hydrateDetailImages()
			} catch (error) {
				this.notify(error.message || '加载详情失败')
			} finally {
				this.loading = false
			}
		},
		async handleApplyReview() {
			this.reviewSubmitting = true
			try {
				await submitViolationReview(this.id)
				this.notify('复核申请已提交')
				await this.loadDetail()
			} catch (error) {
				this.notify(error.message || '提交复核申请失败')
			} finally {
				this.reviewSubmitting = false
			}
		},
		async hydrateDetailImages() {
			const urls = [this.detail.result_image_url, this.detail.object_image_url].filter(
				(url) => typeof url === 'string' && url.trim()
			)
			if (!urls.length) {
				this.detailPreviewUrls = []
				return
			}
			const images = await Promise.all(
				urls.map(async (url) => {
					try {
						return await loadProtectedImage(url)
					} catch (error) {
						return ''
					}
				})
			)
			this.detailPreviewUrls = images.filter(Boolean)
		},
		preview(current) {
			if (!this.previewUrls.length) {
				return
			}
			uni.previewImage({
				current,
				urls: this.previewUrls
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
		min-height: 100vh;
		padding: 28rpx;
		background:
			radial-gradient(circle at top right, rgba(0, 0, 0, 0.08), transparent 28%),
			linear-gradient(180deg, #f4f4f4 0%, #ebebeb 100%);
	}

	.detail-card,
	.remark-card {
		border-radius: 28rpx;
		box-shadow: 0 20rpx 60rpx rgba(0, 0, 0, 0.08);
	}

	.detail-card {
		padding: 30rpx;
		background: rgba(255, 255, 255, 0.94);
	}

	.head {
		display: flex;
		align-items: flex-start;
		justify-content: space-between;
		gap: 20rpx;
		margin-bottom: 24rpx;
	}

	.headline {
		display: block;
		font-size: 42rpx;
		font-weight: 700;
		line-height: 1.5;
		color: #111111;
	}

	.subline,
	.cell-label,
	.remark-title,
	.empty-desc {
		font-size: 32rpx;
		color: #666666;
	}

	.subline {
		display: block;
		margin-top: 10rpx;
	}

	.status-badge {
		padding: 12rpx 18rpx;
		border-radius: 999rpx;
		font-size: 26rpx;
		font-weight: 600;
		background: #ececec;
		color: #333333;
	}

	.status-badge.ready {
		background: #ececec;
		color: #333333;
	}

	.status-badge.pending {
		background: #dedede;
		color: #222222;
	}

	.status-badge.approved {
		background: #111111;
		color: #ffffff;
	}

	.status-badge.rejected {
		background: #cfcfcf;
		color: #111111;
	}

	.grid {
		display: grid;
		grid-template-columns: repeat(2, minmax(0, 1fr));
		gap: 18rpx;
	}

	.cell {
		padding: 22rpx;
		border-radius: 22rpx;
		background: #f2f2f2;
	}

	.cell-label {
		display: block;
		margin-bottom: 10rpx;
	}

	.cell-value,
	.remark-text,
	.empty-title {
		font-size: 32rpx;
		line-height: 1.75;
		color: #111111;
	}

	.remark-group {
		display: flex;
		flex-direction: column;
		gap: 18rpx;
		margin-top: 24rpx;
	}

	.remark-card {
		padding: 24rpx;
		background: #f3f3f3;
	}

	.remark-title {
		display: block;
		margin-bottom: 12rpx;
		font-weight: 600;
	}

	.images-panel {
		margin-top: 24rpx;
	}

	.section-title {
		display: block;
		margin-bottom: 16rpx;
		font-size: 34rpx;
		font-weight: 700;
		color: #111111;
	}

	.image-grid {
		display: grid;
		grid-template-columns: repeat(2, minmax(0, 1fr));
		gap: 16rpx;
	}

	.evidence-image {
		height: 240rpx;
		border-radius: 22rpx;
		background: #e8e8e8;
	}

	.action-group {
		display: flex;
		flex-direction: column;
		gap: 16rpx;
		margin-top: 30rpx;
	}

	.primary-button,
	.review-button {
		display: flex;
		align-items: center;
		justify-content: center;
		height: 94rpx;
		border-radius: 22rpx;
		font-size: 32rpx;
		font-weight: 700;
	}

	.primary-button {
		background: linear-gradient(135deg, #111111 0%, #2f2f2f 100%);
		color: #ffffff;
	}

	.review-button {
		background: #ffffff;
		border: 2rpx solid #111111;
		color: #111111;
	}

	.primary-button[disabled],
	.review-button[disabled] {
		opacity: 0.65;
	}

	.empty-state {
		padding: 120rpx 40rpx;
		text-align: center;
	}

	.empty-title {
		display: block;
		margin-bottom: 12rpx;
		font-weight: 700;
	}

	@media screen and (max-width: 420px) {
		.head {
			flex-direction: column;
		}

		.grid,
		.image-grid {
			grid-template-columns: 1fr;
		}
	}
</style>