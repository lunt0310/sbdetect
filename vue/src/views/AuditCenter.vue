<template>
  <div>
    <PageHeader
      :title="isAdminRole ? '复核' : '复核中心'"
      :description="pageDescription"
    >
      <template #extra>
        <el-button @click="fetchData">刷新列表</el-button>
      </template>
    </PageHeader>

    <el-alert
      :title="alertText"
      type="info"
      :closable="false"
      show-icon
      class="mb-20"
    />

    <el-row :gutter="20" class="stat-grid">
      <el-col :xs="24" :sm="8">
        <el-card shadow="hover" class="stat-card">
          <div class="stat-card__icon theme-orange">
            <el-icon><Bell /></el-icon>
          </div>
          <div class="stat-card__content">
            <div class="stat-card__label">待复核</div>
            <div class="stat-card__value">{{ pendingViolations.length }}</div>
            <div class="stat-card__foot">当前等待处理的违规记录数量</div>
          </div>
        </el-card>
      </el-col>
      <el-col :xs="24" :sm="8">
        <el-card shadow="hover" class="stat-card">
          <div class="stat-card__icon theme-green">
            <el-icon><CircleCheck /></el-icon>
          </div>
          <div class="stat-card__content">
            <div class="stat-card__label">复核通过</div>
            <div class="stat-card__value">{{ confirmedCount }}</div>
            <div class="stat-card__foot">已撤销违规的记录数量</div>
          </div>
        </el-card>
      </el-col>
      <el-col :xs="24" :sm="8">
        <el-card shadow="hover" class="stat-card">
          <div class="stat-card__icon theme-red">
            <el-icon><CloseBold /></el-icon>
          </div>
          <div class="stat-card__content">
            <div class="stat-card__label">复核驳回</div>
            <div class="stat-card__value">{{ rejectedCount }}</div>
            <div class="stat-card__foot">已驳回违规的记录数量</div>
          </div>
        </el-card>
      </el-col>
    </el-row>

    <el-row :gutter="20">
      <el-col :xs="24" :xl="8">
        <el-card shadow="never" class="panel-card audit-list-card">
          <template #header>
            <div class="panel-card__header">
              <span>待复核列表</span>
              <el-tag type="danger" effect="light">{{ pendingViolations.length }}</el-tag>
            </div>
          </template>

          <div v-loading="loading" class="audit-list">
            <div
              v-for="item in pendingViolations"
              :key="item.id"
              class="audit-list__item"
              :class="{ 'is-active': selectedViolation?.id === item.id }"
              @click="selectViolation(item)"
            >
              <div class="audit-list__top">
                <strong>{{ item.violation_no || `违规 #${item.id}` }}</strong>
                <el-tag :type="getResultTagType(item.status)" effect="light">
                  {{ formatViolationStatusText(item.status) }}
                </el-tag>
              </div>
              <div class="audit-list__meta">任务编号：{{ item.task_no || '-' }}</div>
              <div class="audit-list__meta">车牌号：{{ item.plate_text || '-' }}</div>
              <div class="audit-list__meta">提交时间：{{ formatDateTime(item.created_at) }}</div>
            </div>

            <el-empty v-if="!pendingViolations.length && !loading" description="暂无待复核记录" />
          </div>
        </el-card>
      </el-col>

      <el-col :xs="24" :xl="16">
        <el-card shadow="never" class="panel-card">
          <template #header>
            <div class="panel-card__header">
              <span>复核详情</span>
              <el-tag v-if="selectedViolation" :type="getResultTagType(selectedViolation.status)" effect="light">
                {{ formatViolationStatusText(selectedViolation.status) }}
              </el-tag>
            </div>
          </template>

          <div v-if="selectedViolation" v-loading="detailLoading">
            <div class="audit-preview">
              <div class="audit-preview__media">
                <div v-if="annotatedImageUrl" class="detail-media">
                  <img :src="annotatedImageUrl" alt="标注结果图" />
                </div>
                <el-empty v-else description="暂无标注图片" />
              </div>

              <div class="audit-preview__info">
                <div class="detail-extra">
                  <div class="detail-extra__item">
                    <span>违规编号</span>
                    <strong>{{ selectedViolation.violation_no || '-' }}</strong>
                  </div>
                  <div class="detail-extra__item">
                    <span>任务编号</span>
                    <strong>{{ selectedViolation.task_no || '-' }}</strong>
                  </div>
                  <div class="detail-extra__item">
                    <span>用户名</span>
                    <strong>{{ selectedViolation.username || '-' }}</strong>
                  </div>
                  <div class="detail-extra__item">
                    <span>车牌号</span>
                    <strong>{{ selectedViolation.plate_text || '-' }}</strong>
                  </div>
                  <div class="detail-extra__item">
                    <span>违规类型</span>
                    <strong>{{ selectedViolation.violation_type === 'no_seatbelt' ? '未系安全带' : selectedViolation.violation_type }}</strong>
                  </div>
                  <div class="detail-extra__item">
                    <span>提交时间</span>
                    <strong>{{ formatDateTime(selectedViolation.created_at) }}</strong>
                  </div>
                  <div class="detail-extra__item">
                    <span>对象标签</span>
                    <strong>{{ selectedObject?.object_label || '-' }}</strong>
                  </div>
                  <div class="detail-extra__item">
                    <span>安全带状态</span>
                    <strong>{{ selectedObject?.seatbelt_status || '-' }}</strong>
                  </div>
                  <div class="detail-extra__item">
                    <span>置信度</span>
                    <strong>{{ formatPercent(selectedObject?.confidence) }}</strong>
                  </div>
                  <div class="detail-extra__item">
                    <span>备注信息</span>
                    <strong>{{ selectedResult?.notes || selectedTask?.notes || '-' }}</strong>
                  </div>
                </div>
              </div>
            </div>

            <el-form class="audit-review-form" label-position="top">
              <el-form-item label="复核回复">
                <el-input
                  v-model="reviewForm.audit_remark"
                  type="textarea"
                  :rows="4"
                  placeholder="请输入复核回复，说明通过或驳回原因"
                />
              </el-form-item>

              <div class="action-row">
                <el-button
                  type="success"
                  :loading="reviewSubmitting === 2"
                  @click="submitReview(2)"
                >
                  复核通过
                </el-button>
                <el-button
                  type="danger"
                  :loading="reviewSubmitting === 3"
                  @click="submitReview(3)"
                >
                  复核驳回
                </el-button>
              </div>
            </el-form>
          </div>

          <el-empty v-else description="请先从左侧选择一条待复核记录" />
        </el-card>
      </el-col>
    </el-row>
  </div>
</template>

<script setup>
import { Bell, CircleCheck, CloseBold } from '@element-plus/icons-vue';
import { computed, onMounted, reactive, ref } from 'vue';
import { ElMessage } from 'element-plus';

import { getDetectionDetail } from '@/api/detect';
import { getViolationDetail, getViolations, reviewViolation } from '@/api/violations';
import PageHeader from '@/components/PageHeader.vue';
import {
  formatDateTime,
  formatPercent,
  formatViolationStatusText,
  getResultTagType,
  resolveMediaUrl
} from '@/utils/format';
import { isAdmin, getStoredRole } from '@/utils/permission';

const role = getStoredRole();
const isAdminRole = isAdmin(role);
const loading = ref(false);
const detailLoading = ref(false);
const reviewSubmitting = ref(null);
const violations = ref([]);
const selectedViolation = ref(null);
const selectedTask = ref(null);
const selectedResult = ref(null);
const selectedObject = ref(null);

const reviewForm = reactive({
  audit_remark: ''
});

const pageDescription = computed(() => (
  isAdminRole
    ? '管理员端仅保留仪表盘和复核页面，当前页面用于处理待复核记录。'
    : '审核员可在这里查看待复核记录，核对标注图片后提交复核结果。'
));

const alertText = computed(() => (
  isAdminRole
    ? '当前为管理员复核工作台，仅保留违规复核相关功能。'
    : '当前为复核中心，可查看待复核记录并提交复核回复。'
));

const pendingViolations = computed(() => violations.value.filter((item) => Number(item.status) === 1));
const confirmedCount = computed(() => violations.value.filter((item) => Number(item.status) === 2).length);
const rejectedCount = computed(() => violations.value.filter((item) => Number(item.status) === 3).length);

const annotatedImageUrl = computed(() => resolveMediaUrl(
  selectedResult.value?.result_image_url || selectedTask.value?.file_url
));

const resolveTaskDetail = async (violation) => {
  detailLoading.value = true;

  try {
    const [violationDetail, taskDetail] = await Promise.all([
      getViolationDetail(violation.id),
      getDetectionDetail(violation.task_id)
    ]);

    selectedViolation.value = violationDetail || violation;
    selectedTask.value = taskDetail || null;
    selectedResult.value = taskDetail?.results?.find((item) => Number(item.id) === Number(violationDetail?.result_id || violation.result_id)) || null;
    selectedObject.value = selectedResult.value?.objects?.find((item) => Number(item.id) === Number(violationDetail?.object_id || violation.object_id)) || null;
    reviewForm.audit_remark = violationDetail?.audit_remark || '';
  } finally {
    detailLoading.value = false;
  }
};

const fetchData = async () => {
  loading.value = true;

  try {
    const data = await getViolations();
    violations.value = Array.isArray(data) ? data : (data?.results || data?.data || []);

    if (pendingViolations.value.length) {
      const currentId = selectedViolation.value?.id;
      const nextTarget = pendingViolations.value.find((item) => item.id === currentId) || pendingViolations.value[0];
      await resolveTaskDetail(nextTarget);
    } else {
      selectedViolation.value = null;
      selectedTask.value = null;
      selectedResult.value = null;
      selectedObject.value = null;
      reviewForm.audit_remark = '';
    }
  } finally {
    loading.value = false;
  }
};

const selectViolation = async (item) => {
  await resolveTaskDetail(item);
};

const submitReview = async (status) => {
  if (!selectedViolation.value) {
    return;
  }

  const currentId = selectedViolation.value.id;
  const currentIndex = pendingViolations.value.findIndex((item) => Number(item.id) === Number(currentId));
  reviewSubmitting.value = status;

  try {
    await reviewViolation(selectedViolation.value.id, {
      status,
      audit_remark: reviewForm.audit_remark || undefined
    });
    ElMessage.success(status === 2 ? '复核通过已提交' : '复核驳回已提交');

    loading.value = true;
    try {
      const data = await getViolations();
      violations.value = Array.isArray(data) ? data : (data?.results || data?.data || []);

      if (pendingViolations.value.length) {
        const nextTarget = pendingViolations.value[currentIndex] || pendingViolations.value[currentIndex - 1] || pendingViolations.value[0];
        await resolveTaskDetail(nextTarget);
      } else {
        selectedViolation.value = null;
        selectedTask.value = null;
        selectedResult.value = null;
        selectedObject.value = null;
        reviewForm.audit_remark = '';
      }
    } finally {
      loading.value = false;
    }
  } finally {
    reviewSubmitting.value = null;
  }
};

onMounted(() => {
  fetchData();
});
</script>
