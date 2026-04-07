<template>
  <div>
    <PageHeader
      title="仪表盘"
      :description="dashboardDescription"
    />

    <el-row :gutter="20" class="stat-grid">
      <el-col :xs="24" :sm="12" :lg="6" v-for="item in statCards" :key="item.label">
        <el-card shadow="hover" class="stat-card">
          <div class="stat-card__icon" :class="item.theme">
            <el-icon><component :is="item.icon" /></el-icon>
          </div>
          <div class="stat-card__content">
            <div class="stat-card__label">{{ item.label }}</div>
            <div class="stat-card__value">{{ item.value }}</div>
            <div class="stat-card__foot">{{ item.description }}</div>
          </div>
        </el-card>
      </el-col>
    </el-row>

    <el-row :gutter="20">
      <el-col :xs="24" :xl="14">
        <el-card shadow="never" class="panel-card">
          <template #header>
            <div class="panel-card__header">
              <span>佩戴情况对比</span>
              <el-tag type="info" effect="plain">ECharts</el-tag>
            </div>
          </template>
          <div ref="chartRef" class="dashboard-chart"></div>
        </el-card>
      </el-col>

      <el-col :xs="24" :xl="10">
        <el-card shadow="never" class="panel-card">
          <template #header>
            <div class="panel-card__header">
              <span>数据概览</span>
              <el-tag type="success" effect="light">实时统计</el-tag>
            </div>
          </template>

          <div class="insight-list">
            <div class="insight-item">
              <span>总检测任务数</span>
              <strong>{{ totalTaskCount }}</strong>
            </div>
            <div class="insight-item">
              <span>已佩戴占比</span>
              <strong>{{ wearRate }}</strong>
            </div>
            <div class="insight-item">
              <span>待复核违规</span>
              <strong>{{ pendingViolationCount }}</strong>
            </div>
            <div class="insight-item">
              <span>当日总检测数</span>
              <strong>{{ todayCount }}</strong>
            </div>
          </div>
        </el-card>
      </el-col>
    </el-row>

    <el-card shadow="never" class="panel-card mt-20">
      <template #header>
        <div class="panel-card__header">
          <span>最近识别任务</span>
          <el-button text type="primary" @click="goHistory">查看全部</el-button>
        </div>
      </template>

      <el-table :data="recentTasks" v-loading="loading" stripe>
        <el-table-column prop="task_no" label="任务编号" min-width="140" />
        <el-table-column prop="source_name" label="文件名" min-width="180" show-overflow-tooltip />
        <el-table-column label="类型" width="110">
          <template #default="{ row }">
            <el-tag effect="light">{{ formatTypeText(row.task_type) }}</el-tag>
          </template>
        </el-table-column>
        <el-table-column label="状态" width="110">
          <template #default="{ row }">
            <el-tag :type="getResultTagType(row.status)" effect="light">{{ formatTaskStatusText(row.status) }}</el-tag>
          </template>
        </el-table-column>
        <el-table-column label="结果" min-width="150">
          <template #default="{ row }">
            {{ formatTaskResultText(row.task_result) }}
          </template>
        </el-table-column>
        <el-table-column label="时间" min-width="170">
          <template #default="{ row }">
            {{ formatDateTime(row.created_at) }}
          </template>
        </el-table-column>
      </el-table>

      <el-empty v-if="!recentTasks.length && !loading" description="暂无最近识别任务" />
    </el-card>
  </div>
</template>

<script setup>
import { computed, nextTick, onBeforeUnmount, onMounted, ref } from 'vue';
import { useRouter } from 'vue-router';
import * as echarts from 'echarts';

import { getDashboardData } from '@/api/dashboard';
import PageHeader from '@/components/PageHeader.vue';
import {
  formatDateTime,
  formatTaskResultText,
  formatTaskStatusText,
  formatTypeText,
  getResultTagType
} from '@/utils/format';
import { getStoredRole } from '@/utils/permission';

const router = useRouter();
const role = getStoredRole();
const loading = ref(false);
const chartRef = ref(null);
const chartInstance = ref(null);
const dashboard = ref({});

const dashboardDescription = computed(() => (
  role === 'admin'
    ? '查看全系统检测概况，统计口径包含总检测任务数、当日总检测数、待复核和违规总数。'
    : '查看当前账号的检测概况，统计口径包含本人总检测任务数、本人当日总检测数、待复核和违规总数。'
));

const getNumberValue = (...values) => {
  const match = values.find((item) => item !== undefined && item !== null && item !== '');
  return Number(match || 0);
};

const totalTaskCount = computed(() => getNumberValue(
  dashboard.value.total_count,
  dashboard.value.total_tasks,
  dashboard.value.task_count
));

const wearCount = computed(() => getNumberValue(
  dashboard.value.wear_count,
  dashboard.value.wearing_count,
  dashboard.value.safe_count
));

const noWearCount = computed(() => getNumberValue(
  dashboard.value.no_wear_count,
  dashboard.value.not_wearing_count,
  dashboard.value.violation_task_count
));

const todayCount = computed(() => getNumberValue(
  dashboard.value.today_count,
  dashboard.value.today_tasks,
  dashboard.value.today_task_count
));

const pendingViolationCount = computed(() => getNumberValue(
  dashboard.value.pending_violation_count,
  dashboard.value.pending_review_count,
  dashboard.value.pending_count
));

const violationTotalCount = computed(() => getNumberValue(
  dashboard.value.violation_count,
  dashboard.value.total_violation_count,
  dashboard.value.violations_count,
  dashboard.value.no_wear_count,
  dashboard.value.not_wearing_count
));

const recentTasks = computed(() => (
  dashboard.value.recent_tasks
  || dashboard.value.recent_records
  || dashboard.value.latest_tasks
  || []
));

const recentViolations = computed(() => (
  dashboard.value.recent_violations
  || dashboard.value.latest_violations
  || []
));

const pendingViolationCountByList = computed(() => recentViolations.value.filter((item) => Number(item.status) === 1).length);
const violationTotalByList = computed(() => recentViolations.value.length);

const wearRate = computed(() => {
  if (!totalTaskCount.value) {
    return '0%';
  }
  return `${((wearCount.value / totalTaskCount.value) * 100).toFixed(1)}%`;
});

const statCards = computed(() => [
  {
    label: '总检测任务数',
    value: totalTaskCount.value,
    description: role === 'admin' ? '全系统累计处理的检测任务数量' : '当前账号累计处理的检测任务数量',
    icon: 'DataAnalysis',
    theme: 'theme-blue'
  },
  {
    label: '当日总检测数',
    value: todayCount.value,
    description: role === 'admin' ? '全系统今日新提交的检测任务数量' : '当前账号今日新提交的检测任务数量',
    icon: 'Calendar',
    theme: 'theme-green'
  },
  {
    label: '待复核',
    value: pendingViolationCount.value || pendingViolationCountByList.value,
    description: role === 'admin' ? '全系统等待 auditor / admin 处理的复核申请' : '当前账号待复核的申请记录',
    icon: 'Monitor',
    theme: 'theme-orange'
  },
  {
    label: '违规总数',
    value: violationTotalCount.value || violationTotalByList.value,
    description: role === 'admin' ? '全系统累计识别出的违规记录数量' : '当前账号累计识别出的违规记录数量',
    icon: 'WarningFilled',
    theme: 'theme-red'
  }
]);

const renderChart = () => {
  if (!chartRef.value) {
    return;
  }

  if (!chartInstance.value) {
    chartInstance.value = echarts.init(chartRef.value);
  }

  chartInstance.value.setOption({
    tooltip: {
      trigger: 'axis'
    },
    grid: {
      top: 30,
      left: 20,
      right: 20,
      bottom: 20,
      containLabel: true
    },
    xAxis: {
      type: 'category',
      data: ['已佩戴', '未佩戴'],
      axisLine: {
        lineStyle: {
          color: '#b7c1d8'
        }
      }
    },
    yAxis: {
      type: 'value',
      splitLine: {
        lineStyle: {
          type: 'dashed'
        }
      }
    },
    series: [
      {
        type: 'bar',
        barWidth: 48,
        data: [
          {
            value: wearCount.value,
            itemStyle: {
              color: '#2f7d67',
              borderRadius: [12, 12, 0, 0]
            }
          },
          {
            value: noWearCount.value,
            itemStyle: {
              color: '#d95d39',
              borderRadius: [12, 12, 0, 0]
            }
          }
        ]
      }
    ]
  });
};

const fetchDashboard = async () => {
  loading.value = true;

  try {
    const data = await getDashboardData({ limit: 6 });
    dashboard.value = data || {};
    await nextTick();
    renderChart();
  } finally {
    loading.value = false;
  }
};

const handleResize = () => {
  chartInstance.value?.resize();
};

const goHistory = () => {
  router.push('/history');
};

onMounted(() => {
  fetchDashboard();
  window.addEventListener('resize', handleResize);
});

onBeforeUnmount(() => {
  window.removeEventListener('resize', handleResize);
  chartInstance.value?.dispose();
});
</script>
