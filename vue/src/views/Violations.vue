<template>
  <div>
    <PageHeader
      title="违规记录"
      description="查看后端返回的违规记录，并支持审核员和管理员进行违规复核。"
    >
      <template #extra>
        <el-button @click="resetFilters">重置筛选</el-button>
        <el-button type="primary" @click="fetchViolationData">刷新记录</el-button>
      </template>
    </PageHeader>

    <el-card shadow="never" class="panel-card filter-card">
      <el-form :inline="true" :model="filters" class="filter-form">
        <el-form-item v-if="role !== 'user'" label="用户">
          <el-input v-model="filters.username" clearable placeholder="按用户名筛选" style="width: 160px" />
        </el-form-item>
        <el-form-item label="车牌">
          <el-input v-model="filters.plate_text" clearable placeholder="按车牌筛选" style="width: 160px" />
        </el-form-item>
        <el-form-item label="违规状态">
          <el-select v-model="filters.status" clearable placeholder="全部状态" style="width: 160px">
            <el-option label="检测完成" :value="0" />
            <el-option label="申请待复核" :value="1" />
            <el-option label="申请复核通过" :value="2" />
            <el-option label="申请复核驳回" :value="3" />
          </el-select>
        </el-form-item>
        <el-form-item label="日期范围">
          <el-date-picker
            v-model="filters.dateRange"
            type="daterange"
            range-separator="至"
            start-placeholder="开始日期"
            end-placeholder="结束日期"
            value-format="YYYY-MM-DD"
          />
        </el-form-item>
      </el-form>
    </el-card>

    <el-card shadow="never" class="panel-card">
      <el-table :data="pagedData" v-loading="loading" stripe>
        <el-table-column prop="id" label="ID" width="80" />
        <el-table-column prop="violation_no" label="违规编号" min-width="150" />
        <el-table-column prop="task_no" label="任务编号" min-width="150" />
        <el-table-column prop="username" label="用户" width="120" />
        <el-table-column prop="plate_text" label="车牌号" width="140" />
        <el-table-column label="违规类型" width="120">
          <template #default="{ row }">
            {{ row.violation_type === 'no_seatbelt' ? '未系安全带' : row.violation_type }}
          </template>
        </el-table-column>
        <el-table-column label="状态" width="120">
          <template #default="{ row }">
            <el-tag :type="getResultTagType(row.status)" effect="light">
              {{ formatViolationStatusText(row.status) }}
            </el-tag>
          </template>
        </el-table-column>
        <el-table-column prop="auditor" label="复核人" width="120" />
        <el-table-column label="创建时间" min-width="170">
          <template #default="{ row }">
            {{ formatDateTime(row.created_at) }}
          </template>
        </el-table-column>
        <el-table-column label="操作" min-width="180" fixed="right">
          <template #default="{ row }">
            <el-button type="primary" text @click="viewDetail(row.id)">查看详情</el-button>
            <el-button
              v-if="canReview"
              type="warning"
              text
              @click="openReviewDialog(row)"
            >
              复核
            </el-button>
          </template>
        </el-table-column>
      </el-table>

      <el-empty v-if="!filteredData.length && !loading" description="暂无违规记录" />

      <div class="table-footer">
        <div class="table-footer__count">共 {{ filteredData.length }} 条记录</div>
        <el-pagination
          background
          layout="total, sizes, prev, pager, next, jumper"
          :total="filteredData.length"
          :page-size="pagination.pageSize"
          :current-page="pagination.page"
          :page-sizes="[10, 20, 50]"
          @current-change="handlePageChange"
          @size-change="handleSizeChange"
        />
      </div>
    </el-card>

    <el-drawer v-model="detailVisible" title="违规详情" size="520px">
      <el-descriptions v-if="currentDetail" :column="1" border>
        <el-descriptions-item label="违规编号">{{ currentDetail.violation_no || '-' }}</el-descriptions-item>
        <el-descriptions-item label="任务编号">{{ currentDetail.task_no || '-' }}</el-descriptions-item>
        <el-descriptions-item label="用户名">{{ currentDetail.username || '-' }}</el-descriptions-item>
        <el-descriptions-item label="车牌号">{{ currentDetail.plate_text || '-' }}</el-descriptions-item>
        <el-descriptions-item label="违规状态">{{ formatViolationStatusText(currentDetail.status) }}</el-descriptions-item>
        <el-descriptions-item label="复核人">{{ currentDetail.auditor || '-' }}</el-descriptions-item>
        <el-descriptions-item label="复核时间">{{ formatDateTime(currentDetail.audit_time) }}</el-descriptions-item>
        <el-descriptions-item label="复核备注">{{ currentDetail.audit_remark || '-' }}</el-descriptions-item>
        <el-descriptions-item label="处理备注">{{ currentDetail.handled_remark || '-' }}</el-descriptions-item>
        <el-descriptions-item label="创建时间">{{ formatDateTime(currentDetail.created_at) }}</el-descriptions-item>
      </el-descriptions>
    </el-drawer>

    <el-dialog v-model="reviewVisible" title="违规复核" width="520px">
      <el-form ref="reviewFormRef" :model="reviewForm" :rules="reviewRules" label-width="90px">
        <el-form-item label="复核结果" prop="status">
          <el-select v-model="reviewForm.status" style="width: 100%">
            <el-option label="复核通过" :value="2" />
            <el-option label="复核驳回" :value="3" />
          </el-select>
        </el-form-item>
        <el-form-item label="复核备注" prop="audit_remark">
          <el-input v-model="reviewForm.audit_remark" type="textarea" :rows="3" />
        </el-form-item>
        <el-form-item label="处理备注" prop="handled_remark">
          <el-input v-model="reviewForm.handled_remark" type="textarea" :rows="3" />
        </el-form-item>
      </el-form>
      <template #footer>
        <el-button @click="reviewVisible = false">取消</el-button>
        <el-button type="primary" :loading="reviewSubmitting" @click="submitReview">提交复核</el-button>
      </template>
    </el-dialog>
  </div>
</template>

<script setup>
import { computed, onMounted, reactive, ref } from 'vue';
import { ElMessage } from 'element-plus';

import { getViolationDetail, getViolations, reviewViolation } from '@/api/violations';
import PageHeader from '@/components/PageHeader.vue';
import {
  formatDateTime,
  formatViolationStatusText,
  getListData,
  getResultTagType
} from '@/utils/format';
import { getStoredRole } from '@/utils/permission';

const role = getStoredRole();
const canReview = ['auditor', 'admin'].includes(role);
const loading = ref(false);
const rawData = ref([]);
const detailVisible = ref(false);
const reviewVisible = ref(false);
const reviewSubmitting = ref(false);
const currentDetail = ref(null);
const currentReviewId = ref(null);
const reviewFormRef = ref(null);

const filters = reactive({
  username: '',
  plate_text: '',
  status: '',
  dateRange: []
});

const pagination = reactive({
  page: 1,
  pageSize: 10
});

const reviewForm = reactive({
  status: 2,
  audit_remark: '',
  handled_remark: ''
});

const reviewRules = {
  status: [
    { required: true, message: '请选择复核结果', trigger: 'change' }
  ]
};

const filteredData = computed(() => rawData.value.filter((item) => {
  if (filters.username && !String(item.username || '').includes(filters.username.trim())) {
    return false;
  }

  if (filters.plate_text && !String(item.plate_text || '').includes(filters.plate_text.trim())) {
    return false;
  }

  if (filters.status !== '' && Number(item.status) !== Number(filters.status)) {
    return false;
  }

  if (filters.dateRange?.length === 2) {
    const createdAt = String(item.created_at || '');
    if (createdAt < filters.dateRange[0] || createdAt > `${filters.dateRange[1]} 23:59:59`) {
      return false;
    }
  }

  return true;
}));

const pagedData = computed(() => {
  const start = (pagination.page - 1) * pagination.pageSize;
  return filteredData.value.slice(start, start + pagination.pageSize);
});

const buildParams = () => {
  const [startDate, endDate] = filters.dateRange || [];
  return {
    username: filters.username || undefined,
    plate_text: filters.plate_text || undefined,
    status: filters.status === '' ? undefined : filters.status,
    date_from: startDate || undefined,
    date_to: endDate || undefined
  };
};

const fetchViolationData = async () => {
  loading.value = true;
  try {
    const data = await getViolations(buildParams());
    rawData.value = getListData(data);
    pagination.page = 1;
  } finally {
    loading.value = false;
  }
};

const resetFilters = () => {
  filters.username = '';
  filters.plate_text = '';
  filters.status = '';
  filters.dateRange = [];
  pagination.page = 1;
  fetchViolationData();
};

const viewDetail = async (id) => {
  const data = await getViolationDetail(id);
  currentDetail.value = data || null;
  detailVisible.value = true;
};

const openReviewDialog = (row) => {
  currentReviewId.value = row.id;
  reviewForm.status = Number(row.status) === 1 ? 2 : Number(row.status || 2);
  reviewForm.audit_remark = row.audit_remark || '';
  reviewForm.handled_remark = row.handled_remark || '';
  reviewVisible.value = true;
};

const submitReview = async () => {
  await reviewFormRef.value.validate();
  reviewSubmitting.value = true;

  try {
    await reviewViolation(currentReviewId.value, {
      status: reviewForm.status,
      audit_remark: reviewForm.audit_remark || undefined,
      handled_remark: reviewForm.handled_remark || undefined
    });
    ElMessage.success('违规复核已提交');
    reviewVisible.value = false;
    fetchViolationData();
  } finally {
    reviewSubmitting.value = false;
  }
};

const handlePageChange = (page) => {
  pagination.page = page;
};

const handleSizeChange = (pageSize) => {
  pagination.pageSize = pageSize;
  pagination.page = 1;
};

onMounted(() => {
  fetchViolationData();
});
</script>
