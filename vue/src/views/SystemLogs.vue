<template>
  <div>
    <PageHeader
      title="系统日志"
      description="审核员和管理员可在这里查看查询日志与操作日志。"
    >
      <template #extra>
        <el-button @click="resetFilters">重置筛选</el-button>
        <el-button type="primary" @click="loadLogs">刷新日志</el-button>
      </template>
    </PageHeader>

    <el-card shadow="never" class="panel-card filter-card">
      <el-form :inline="true" :model="filters" class="filter-form">
        <el-form-item label="日志类型">
          <el-select v-model="filters.source" clearable placeholder="全部类型" style="width: 160px">
            <el-option label="查询日志" value="query" />
            <el-option label="操作日志" value="operation" />
          </el-select>
        </el-form-item>
        <el-form-item label="用户名">
          <el-input v-model="filters.username" clearable placeholder="按用户名筛选" style="width: 160px" />
        </el-form-item>
        <el-form-item label="模块/类型">
          <el-input v-model="filters.keyword" clearable placeholder="查询模块 / 操作类型" style="width: 220px" />
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
      <el-table :data="pagedLogs" v-loading="loading" stripe>
        <el-table-column prop="id" label="ID" width="80" />
        <el-table-column label="日志类型" width="120">
          <template #default="{ row }">
            <el-tag :type="row.source === 'operation' ? 'warning' : 'info'" effect="light">
              {{ row.source === 'operation' ? '操作日志' : '查询日志' }}
            </el-tag>
          </template>
        </el-table-column>
        <el-table-column prop="username" label="用户" width="140" />
        <el-table-column prop="module" label="模块 / 类型" min-width="160" />
        <el-table-column prop="target" label="目标 / 参数" min-width="220" show-overflow-tooltip />
        <el-table-column prop="detail" label="日志内容" min-width="260" show-overflow-tooltip />
        <el-table-column label="时间" min-width="170">
          <template #default="{ row }">
            {{ formatDateTime(row.created_at) }}
          </template>
        </el-table-column>
      </el-table>

      <el-empty v-if="!filteredLogs.length && !loading" description="暂无日志数据" />

      <div class="table-footer">
        <div class="table-footer__count">共 {{ filteredLogs.length }} 条日志</div>
        <el-pagination
          background
          layout="total, sizes, prev, pager, next, jumper"
          :total="filteredLogs.length"
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

import { getOperationLogs, getQueryLogs } from '@/api/logs';
import PageHeader from '@/components/PageHeader.vue';
import { formatDateTime, getListData } from '@/utils/format';

const logs = ref([]);
const loading = ref(false);
const filters = reactive({
  source: '',
  username: '',
  keyword: '',
  dateRange: []
});

const pagination = reactive({
  page: 1,
  pageSize: 10
});

const stringifyValue = (value) => {
  if (!value) {
    return '-';
  }

  if (typeof value === 'string') {
    return value;
  }

  try {
    return JSON.stringify(value);
  } catch (error) {
    return '-';
  }
};

const normalizeQueryLog = (item) => ({
  id: item.id,
  source: 'query',
  username: item.username || '-',
  module: item.query_module || '-',
  target: stringifyValue(item.query_params),
  detail: `返回 ${item.result_count ?? 0} 条记录`,
  created_at: item.created_at
});

const normalizeOperationLog = (item) => ({
  id: item.id,
  source: 'operation',
  username: item.username || '-',
  module: item.operation_type || '-',
  target: `${item.target_type || '-'}${item.target_id ? ` #${item.target_id}` : ''}`,
  detail: `${item.request_method || ''} ${item.request_path || ''} ${item.detail || ''}`.trim(),
  created_at: item.created_at
});

const filteredLogs = computed(() => logs.value.filter((item) => {
  if (filters.source && item.source !== filters.source) {
    return false;
  }

  if (filters.username && !String(item.username || '').includes(filters.username.trim())) {
    return false;
  }

  if (filters.keyword) {
    const keyword = filters.keyword.trim();
    if (!`${item.module} ${item.target} ${item.detail}`.includes(keyword)) {
      return false;
    }
  }

  if (filters.dateRange?.length === 2) {
    const createdAt = String(item.created_at || '');
    if (createdAt < filters.dateRange[0] || createdAt > `${filters.dateRange[1]} 23:59:59`) {
      return false;
    }
  }

  return true;
}));

const pagedLogs = computed(() => {
  const start = (pagination.page - 1) * pagination.pageSize;
  return filteredLogs.value.slice(start, start + pagination.pageSize);
});

const buildQueryParams = () => {
  const [startDate, endDate] = filters.dateRange || [];
  return {
    username: filters.username || undefined,
    query_module: filters.source === 'query' ? filters.keyword || undefined : undefined,
    operation_type: filters.source === 'operation' ? filters.keyword || undefined : undefined,
    date_from: startDate || undefined,
    date_to: endDate || undefined
  };
};

const loadLogs = async () => {
  loading.value = true;
  try {
    const params = buildQueryParams();
    const [queryLogs, operationLogs] = await Promise.all([
      getQueryLogs({
        username: params.username,
        query_module: params.query_module,
        date_from: params.date_from,
        date_to: params.date_to
      }),
      getOperationLogs({
        username: params.username,
        operation_type: params.operation_type,
        date_from: params.date_from,
        date_to: params.date_to
      })
    ]);

    logs.value = [
      ...getListData(operationLogs).map(normalizeOperationLog),
      ...getListData(queryLogs).map(normalizeQueryLog)
    ].sort((a, b) => String(b.created_at).localeCompare(String(a.created_at)));
    pagination.page = 1;
  } finally {
    loading.value = false;
  }
};

const resetFilters = () => {
  filters.source = '';
  filters.username = '';
  filters.keyword = '';
  filters.dateRange = [];
  pagination.page = 1;
  loadLogs();
};

const handlePageChange = (page) => {
  pagination.page = page;
};

const handleSizeChange = (pageSize) => {
  pagination.pageSize = pageSize;
  pagination.page = 1;
};

onMounted(() => {
  loadLogs();
});
</script>
