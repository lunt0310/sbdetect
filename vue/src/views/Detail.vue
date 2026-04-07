<template>
  <div>
    <PageHeader
      title="检测详情"
      description="查看单条检测任务的完整信息，包括结果图、对象列表和违规记录。"
    >
      <template #extra>
        <el-button @click="router.push('/history')">返回识别记录</el-button>
      </template>
    </PageHeader>

    <el-row :gutter="20">
      <el-col :xs="24" :xl="9">
        <el-card shadow="never" class="panel-card">
          <template #header>
            <div class="panel-card__header">
              <span>媒体预览</span>
              <el-tag :type="getResultTagType(detail.task_result || detail.status)" effect="light">
                {{ formatTaskResultText(detail.task_result) }}
              </el-tag>
            </div>
          </template>

          <div v-loading="loading" class="detail-media-wrap">
            <div v-if="isImage && imageUrl" class="detail-media">
              <img :src="imageUrl" alt="检测图片" />
            </div>
            <div v-else-if="isVideo && videoUrl" class="detail-media">
              <video :src="videoUrl" controls />
            </div>
            <el-empty v-else description="暂无可预览的媒体资源" />
          </div>
        </el-card>
      </el-col>

      <el-col :xs="24" :xl="15">
        <el-card shadow="never" class="panel-card">
          <template #header>
            <div class="panel-card__header">
              <span>基础信息</span>
              <el-tag type="info" effect="plain">Task Detail</el-tag>
            </div>
          </template>

          <el-descriptions
            v-loading="loading"
            :column="2"
            border
            class="detail-descriptions"
          >
            <el-descriptions-item label="任务 ID">{{ detail.id || '-' }}</el-descriptions-item>
            <el-descriptions-item label="任务编号">{{ detail.task_no || '-' }}</el-descriptions-item>
            <el-descriptions-item label="文件名">{{ detail.source_name || '-' }}</el-descriptions-item>
            <el-descriptions-item label="任务类型">{{ formatTypeText(detail.task_type) }}</el-descriptions-item>
            <el-descriptions-item label="任务状态">{{ formatTaskStatusText(detail.status) }}</el-descriptions-item>
            <el-descriptions-item label="检测结果">{{ formatTaskResultText(detail.task_result) }}</el-descriptions-item>
            <el-descriptions-item label="任务进度">{{ `${Number(detail.progress || 0)}%` }}</el-descriptions-item>
            <el-descriptions-item label="违规数量">{{ detail.violation_count ?? 0 }}</el-descriptions-item>
            <el-descriptions-item label="总帧数">{{ detail.total_frames ?? 0 }}</el-descriptions-item>
            <el-descriptions-item label="已处理帧数">{{ detail.processed_frames ?? 0 }}</el-descriptions-item>
            <el-descriptions-item label="执行时长">{{ formatDuration(detail.duration_ms) }}</el-descriptions-item>
            <el-descriptions-item label="创建时间">{{ formatDateTime(detail.created_at) }}</el-descriptions-item>
            <el-descriptions-item label="开始时间">{{ formatDateTime(detail.started_at) }}</el-descriptions-item>
            <el-descriptions-item label="完成时间">{{ formatDateTime(detail.finished_at) }}</el-descriptions-item>
            <el-descriptions-item label="创建用户">{{ detail.user || '-' }}</el-descriptions-item>
            <el-descriptions-item label="备注">{{ detail.notes || '暂无备注' }}</el-descriptions-item>
            <el-descriptions-item label="错误信息">{{ detail.error_message || '-' }}</el-descriptions-item>
          </el-descriptions>

          <div class="detail-extra">
            <div class="detail-extra__item">
              <span>结果图片</span>
              <strong>{{ latestResult?.result_image_url || '-' }}</strong>
            </div>
            <div class="detail-extra__item">
              <span>原始文件地址</span>
              <strong>{{ detail.file_url || '-' }}</strong>
            </div>
            <div class="detail-extra__item">
              <span>结果数量</span>
              <strong>{{ detail.result_count ?? 0 }}</strong>
            </div>
          </div>
        </el-card>
      </el-col>
    </el-row>

    <el-row :gutter="20" class="mt-20">
      <el-col :xs="24" :xl="14">
        <el-card shadow="never" class="panel-card">
          <template #header>
            <div class="panel-card__header">
              <span>识别对象</span>
              <el-tag type="info" effect="light">{{ objectList.length }} 个</el-tag>
            </div>
          </template>

          <el-table :data="objectList" v-loading="loading" stripe>
            <el-table-column prop="id" label="ID" width="80" />
            <el-table-column label="对象类型" width="110">
              <template #default="{ row }">
                {{ formatObjectTypeText(row.object_type) }}
              </template>
            </el-table-column>
            <el-table-column prop="object_label" label="对象标签" min-width="120" />
            <el-table-column prop="plate_text" label="车牌" width="120" />
            <el-table-column label="置信度" width="110">
              <template #default="{ row }">
                {{ formatPercent(row.confidence) }}
              </template>
            </el-table-column>
            <el-table-column prop="seatbelt_status" label="安全带状态" min-width="120" />
            <el-table-column label="违规" width="90">
              <template #default="{ row }">
                <el-tag :type="row.is_violation ? 'danger' : 'success'" effect="light">
                  {{ row.is_violation ? '是' : '否' }}
                </el-tag>
              </template>
            </el-table-column>
          </el-table>

          <el-empty v-if="!objectList.length && !loading" description="暂无识别对象" />
        </el-card>
      </el-col>

      <el-col :xs="24" :xl="10">
        <el-card shadow="never" class="panel-card">
          <template #header>
            <div class="panel-card__header">
              <span>关联违规</span>
              <el-tag type="danger" effect="light">{{ violationList.length }} 条</el-tag>
            </div>
          </template>

          <div class="insight-list" v-if="violationList.length">
            <div v-for="item in violationList" :key="item.id" class="insight-item">
              <div>
                <div>{{ item.violation_no || `违规 #${item.id}` }}</div>
                <small>{{ item.plate_text || item.username || '-' }}</small>
              </div>
              <el-tag :type="getResultTagType(item.status)" effect="light">
                {{ formatViolationStatusText(item.status) }}
              </el-tag>
            </div>
          </div>
          <el-empty v-else-if="!loading" description="暂无关联违规" />
        </el-card>
      </el-col>
    </el-row>
  </div>
</template>

<script setup>
import { computed, onMounted, ref, watch } from 'vue';
import { useRoute, useRouter } from 'vue-router';

import { getDetectionDetail } from '@/api/detect';
import PageHeader from '@/components/PageHeader.vue';
import {
  formatDateTime,
  formatDuration,
  formatObjectTypeText,
  formatPercent,
  formatTaskResultText,
  formatTaskStatusText,
  formatTypeText,
  formatViolationStatusText,
  getLatestResult,
  getResultTagType,
  resolveMediaUrl
} from '@/utils/format';

const route = useRoute();
const router = useRouter();
const loading = ref(false);
const detail = ref({});

const fetchDetail = async () => {
  loading.value = true;

  try {
    const data = await getDetectionDetail(route.params.id);
    detail.value = data || {};
  } finally {
    loading.value = false;
  }
};

const latestResult = computed(() => getLatestResult(detail.value));
const objectList = computed(() => latestResult.value?.objects || []);
const violationList = computed(() => latestResult.value?.violations || []);
const isImage = computed(() => detail.value.task_type === 'image');
const isVideo = computed(() => detail.value.task_type === 'video');
const imageUrl = computed(() => resolveMediaUrl(latestResult.value?.result_image_url || detail.value.file_url));
const videoUrl = computed(() => resolveMediaUrl(
  detail.value.metadata?.result_video_url
  || detail.value.metadata?.video_url
  || detail.value.file_url
));

watch(() => route.params.id, fetchDetail);

onMounted(() => {
  fetchDetail();
});
</script>
