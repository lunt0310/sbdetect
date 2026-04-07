<template>
  <div>
    <PageHeader
      title="识别记录"
      :description="pageDescription"
    >
      <template #extra>
        <el-button @click="resetFilters">重置筛选</el-button>
        <el-button type="primary" @click="fetchTableData">查询记录</el-button>
      </template>
    </PageHeader>

    <el-alert
      :title="scopeText"
      type="info"
      :closable="false"
      show-icon
      class="mb-20"
    />

    <el-card shadow="never" class="panel-card filter-card">
      <el-form :inline="true" :model="filters" class="filter-form">
        <el-form-item label="任务编号">
          <el-input v-model="filters.task_no" placeholder="输入任务编号" clearable style="width: 180px" />
        </el-form-item>

        <el-form-item label="文件名">
          <el-input v-model="filters.source_name" placeholder="输入文件名" clearable style="width: 200px" />
        </el-form-item>

        <el-form-item label="检测类型">
          <el-select v-model="filters.task_type" placeholder="全部类型" clearable style="width: 150px">
            <el-option label="图片检测" value="image" />
            <el-option label="视频检测" value="video" />
          </el-select>
        </el-form-item>

        <el-form-item label="任务状态">
          <el-select v-model="filters.status" placeholder="全部状态" clearable style="width: 150px">
            <el-option label="待处理" value="pending" />
            <el-option label="处理中" value="running" />
            <el-option label="已完成" value="completed" />
            <el-option label="失败" value="failed" />
            <el-option label="已取消" value="cancelled" />
          </el-select>
        </el-form-item>

        <el-form-item label="违规状态">
          <el-select v-model="filters.has_violation" placeholder="全部" clearable style="width: 150px">
            <el-option label="有违规" :value="true" />
            <el-option label="无违规" :value="false" />
          </el-select>
        </el-form-item>

        <el-form-item v-if="role !== 'user'" label="用户">
          <el-input v-model="filters.username" placeholder="按用户名筛选" clearable style="width: 180px" />
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
        <el-table-column prop="task_no" label="任务编号" min-width="140" />
        <el-table-column prop="source_name" label="文件名" min-width="180" show-overflow-tooltip />
        <el-table-column label="类型" width="110">
          <template #default="{ row }">
            <el-tag effect="light">{{ formatTypeText(row.task_type) }}</el-tag>
          </template>
        </el-table-column>
        <el-table-column label="用户" width="120">
          <template #default="{ row }">
            {{ row.user || '-' }}
          </template>
        </el-table-column>
        <el-table-column label="状态" width="110">
          <template #default="{ row }">
            <el-tag :type="getResultTagType(row.status)" effect="light">
              {{ formatTaskStatusText(row.status) }}
            </el-tag>
          </template>
        </el-table-column>
        <el-table-column label="检测结果" min-width="160">
          <template #default="{ row }">
            <el-tag :type="getResultTagType(row.task_result)" effect="light">
              {{ formatTaskResultText(row.task_result) }}
            </el-tag>
          </template>
        </el-table-column>
        <el-table-column label="违规数" width="100">
          <template #default="{ row }">
            {{ row.violation_count ?? 0 }}
          </template>
        </el-table-column>
        <el-table-column label="进度" width="120">
          <template #default="{ row }">
            {{ `${Number(row.progress || 0)}%` }}
          </template>
        </el-table-column>
        <el-table-column label="创建时间" min-width="170">
          <template #default="{ row }">
            {{ formatDateTime(row.created_at) }}
          </template>
        </el-table-column>
        <el-table-column label="操作" width="120" fixed="right">
          <template #default="{ row }">
            <el-button type="primary" text @click="viewDetail(row.id)">查看详情</el-button>
          </template>
        </el-table-column>
      </el-table>

      <el-empty v-if="!filteredData.length && !loading" description="暂无识别记录" />

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
  </div>
</template>

<script setup>
import { computed, onMounted, reactive, ref } from 'vue';
import { useRouter } from 'vue-router';

import { getDetectionList } from '@/api/detect';
import PageHeader from '@/components/PageHeader.vue';
import {
  formatDateTime,
  formatTaskResultText,
  formatTaskStatusText,
  formatTypeText,
  getListData,
  getResultTagType
} from '@/utils/format';
import { getStoredRole } from '@/utils/permission';

const router = useRouter();
const role = getStoredRole();
const loading = ref(false);
const rawData = ref([]);
const filters = reactive({
  task_no: '',
  source_name: '',
  task_type: '',
  status: '',
  username: '',
  has_violation: '',
  dateRange: []
});
const pagination = reactive({
  page: 1,
  pageSize: 10
});

const pageDescription = computed(() => {
  if (role === 'user') {
    return '普通用户仅查看自己的识别记录；违规信息请在“违规记录”页查看。';
  }
  return '审核员和管理员可查看当前权限范围内的全量识别任务，并进入详情页查看识别结果。';
});

const scopeText = computed(() => (
  role === 'user'
    ? '当前账号为普通用户，识别记录应由后端按用户维度返回。'
    : '当前账号具备审计权限，页面会展示后端返回的全量识别记录。'
));

const filteredData = computed(() => rawData.value.filter((item) => {
  if (filters.task_no && !String(item.task_no || '').includes(filters.task_no.trim())) {
    return false;
  }

  if (filters.source_name && !String(item.source_name || '').includes(filters.source_name.trim())) {
    return false;
  }

  if (filters.task_type && item.task_type !== filters.task_type) {
    return false;
  }

  if (filters.status && item.status !== filters.status) {
    return false;
  }

  if (filters.username && !String(item.user || '').includes(filters.username.trim())) {
    return false;
  }

  if (filters.has_violation !== '' && Boolean(item.has_violation) !== filters.has_violation) {
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
    status: filters.status || undefined,
    task_type: filters.task_type || undefined,
    username: filters.username || undefined,
    has_violation: filters.has_violation === '' ? undefined : filters.has_violation,
    task_no: filters.task_no || undefined,
    source_name: filters.source_name || undefined,
    date_from: startDate || undefined,
    date_to: endDate || undefined
  };
};

const fetchTableData = async () => {
  loading.value = true;

  try {
    const data = await getDetectionList(buildParams());
    rawData.value = getListData(data);
    pagination.page = 1;
  } finally {
    loading.value = false;
  }
};

const resetFilters = () => {
  filters.task_no = '';
  filters.source_name = '';
  filters.task_type = '';
  filters.status = '';
  filters.username = '';
  filters.has_violation = '';
  filters.dateRange = [];
  pagination.page = 1;
  fetchTableData();
};

const viewDetail = (id) => {
  router.push(`/history/${id}`);
};

const handlePageChange = (page) => {
  pagination.page = page;
};

const handleSizeChange = (pageSize) => {
  pagination.pageSize = pageSize;
  pagination.page = 1;
};

onMounted(() => {
  fetchTableData();
});
</script>
