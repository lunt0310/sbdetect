export const VIOLATION_STATUS_OPTIONS = [
	{ label: '全部状态', value: '' },
	{ label: '待审核', value: 'pending_review' },
	{ label: '已确认', value: 'confirmed' },
	{ label: '已处理', value: 'handled' },
	{ label: '已驳回', value: 'rejected' }
]

export const VIOLATION_STATUS_LABELS = {
	pending_review: '待审核',
	confirmed: '已确认',
	handled: '已处理',
	rejected: '已驳回'
}

export const VIOLATION_RECORD_STATUS_LABELS = {
	0: '检测完成',
	1: '申请待审核',
	2: '申请审核通过',
	3: '申请审核驳回'
}

export const VIOLATION_TYPE_LABELS = {
	no_seatbelt: '未系安全带'
}

export function getViolationStatusLabel(status) {
	return VIOLATION_STATUS_LABELS[status] || status || '未知状态'
}

export function getViolationRecordStatusLabel(status) {
	return VIOLATION_RECORD_STATUS_LABELS[status] || '未知状态'
}

export function getViolationTypeLabel(type) {
	return VIOLATION_TYPE_LABELS[type] || type || '未知类型'
}
