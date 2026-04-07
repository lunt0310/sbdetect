<template>
  <div>
    <PageHeader
      title="视频检测"
      description="上传视频后调用统一检测接口，返回任务结果后展示帧统计和违规信息。"
    />

    <el-row :gutter="20">
      <el-col :xs="24" :xl="10">
        <el-card shadow="never" class="panel-card">
          <template #header>
            <div class="panel-card__header">
              <span>上传视频</span>
              <el-tag type="warning" effect="plain">MP4 / AVI / MOV</el-tag>
            </div>
          </template>

          <el-upload
            ref="uploadRef"
            class="upload-block"
            drag
            :auto-upload="false"
            :limit="1"
            :file-list="fileList"
            :show-file-list="false"
            :on-change="handleFileChange"
            :on-remove="handleRemove"
            :on-exceed="handleExceed"
            accept=".mp4,.avi,.mov"
          >
            <el-icon class="el-icon--upload"><VideoCameraFilled /></el-icon>
            <div class="el-upload__text">将视频拖到此处，或 <em>点击上传</em></div>
            <template #tip>
              <div class="el-upload__tip">仅支持 mp4 / avi / mov，文件大小不超过 100MB</div>
            </template>
          </el-upload>

          <div class="preview-box">
            <div class="preview-box__title">上传预览</div>
            <div v-if="previewUrl" class="preview-box__video preview-box__media">
              <video :src="previewUrl" controls />
            </div>
            <el-empty v-else description="请选择待检测视频" />
          </div>

          <div class="file-summary">
            <div class="file-summary__title">文件信息</div>
            <div v-if="selectedFile" class="file-summary__content">
              <div class="file-summary__item">
                <span>文件名</span>
                <strong>{{ selectedFile.name }}</strong>
              </div>
              <div class="file-summary__item">
                <span>文件大小</span>
                <strong>{{ fileSizeText }}</strong>
              </div>
              <div class="file-summary__item">
                <span>检测状态</span>
                <el-tag :type="statusTagType">{{ statusText }}</el-tag>
              </div>
            </div>
            <el-empty v-else description="请选择待检测视频" />
          </div>

          <el-steps :active="stepActive" finish-status="success" simple class="video-steps">
            <el-step title="选择文件" />
            <el-step title="提交任务" />
            <el-step title="识别处理" />
            <el-step title="结果展示" />
          </el-steps>

          <div class="action-row">
            <el-button type="primary" :loading="loading" @click="handleDetect">开始检测</el-button>
            <el-button @click="resetAll">重置</el-button>
          </div>
        </el-card>
      </el-col>

      <el-col :xs="24" :xl="14">
        <ResultCard
          title="视频检测结果"
          :loading="loading"
          :status="displayStatus"
          :items="resultItems"
          :tag-text="resultTagText"
          :tag-type="statusTagType"
          empty-text="上传视频并提交后，系统会在这里显示检测结果"
          error-text="视频检测失败，请检查文件或稍后重试"
        >
          <template #media>
            <div v-if="videoUrl" class="detect-media">
              <video :src="videoUrl" controls />
            </div>
          </template>
        </ResultCard>
      </el-col>
    </el-row>
  </div>
</template>

<script setup>
import { computed, onBeforeUnmount, ref } from 'vue';
import { ElMessage } from 'element-plus';

import { createDetection } from '@/api/detect';
import PageHeader from '@/components/PageHeader.vue';
import ResultCard from '@/components/ResultCard.vue';
import {
  formatDateTime,
  formatDuration,
  formatTaskResultText,
  formatTaskStatusText,
  getResultTagType,
  resolveMediaUrl
} from '@/utils/format';

const MAX_FILE_SIZE = 100;

const uploadRef = ref(null);
const fileList = ref([]);
const selectedFile = ref(null);
const previewUrl = ref('');
const loading = ref(false);
const detectStatus = ref('idle');
const task = ref(null);

const validateVideoFile = (file) => {
  const validTypes = ['video/mp4', 'video/avi', 'video/quicktime', 'video/x-msvideo'];
  const extensionValid = /\.(mp4|avi|mov)$/i.test(file.name);
  const typeValid = validTypes.includes(file.type) || !file.type || extensionValid;
  const sizeValid = file.size / 1024 / 1024 <= MAX_FILE_SIZE;

  if (!typeValid) {
    ElMessage.warning('仅支持 MP4、AVI、MOV 格式的视频');
    return false;
  }

  if (!sizeValid) {
    ElMessage.warning(`视频大小不能超过 ${MAX_FILE_SIZE}MB`);
    return false;
  }

  return true;
};

const clearPreview = () => {
  if (previewUrl.value) {
    URL.revokeObjectURL(previewUrl.value);
    previewUrl.value = '';
  }
};

const replaceCurrentFile = (rawFile) => {
  clearPreview();
  task.value = null;
  detectStatus.value = rawFile ? 'ready' : 'idle';
  selectedFile.value = rawFile;
  fileList.value = rawFile
    ? [{
        name: rawFile.name,
        size: rawFile.size,
        status: 'ready',
        raw: rawFile
      }]
    : [];
  previewUrl.value = rawFile ? URL.createObjectURL(rawFile) : '';
};

const handleFileChange = (uploadFile) => {
  const rawFile = uploadFile.raw;

  if (!rawFile || !validateVideoFile(rawFile)) {
    replaceCurrentFile(null);
    uploadRef.value?.clearFiles();
    return;
  }

  uploadRef.value?.clearFiles();
  replaceCurrentFile(rawFile);
};

const handleExceed = (files) => {
  const rawFile = files[0];

  if (!rawFile || !validateVideoFile(rawFile)) {
    return;
  }

  uploadRef.value?.clearFiles();
  replaceCurrentFile(rawFile);
};

const handleRemove = () => {
  replaceCurrentFile(null);
};

const handleDetect = async () => {
  if (!selectedFile.value) {
    ElMessage.warning('请先选择一个视频文件');
    return;
  }

  const formData = new FormData();
  formData.append('file', selectedFile.value);
  loading.value = true;
  detectStatus.value = 'uploading';
  task.value = null;

  try {
    const data = await createDetection(formData);
    task.value = data || null;
    detectStatus.value = task.value?.status === 'completed' ? 'finished' : 'processing';
    ElMessage.success('视频检测任务已返回结果');
  } catch (error) {
    task.value = error.apiData || null;
    detectStatus.value = 'failed';
  } finally {
    loading.value = false;
  }
};

const resetAll = () => {
  replaceCurrentFile(null);
  loading.value = false;
  uploadRef.value?.clearFiles();
};

const fileSizeText = computed(() => {
  if (!selectedFile.value) {
    return '-';
  }

  return `${(selectedFile.value.size / 1024 / 1024).toFixed(2)} MB`;
});

const statusText = computed(() => {
  if (task.value?.status) {
    return formatTaskStatusText(task.value.status);
  }

  const map = {
    idle: '未开始',
    ready: '待提交',
    uploading: '上传中',
    processing: '处理中',
    finished: '已完成',
    failed: '失败'
  };

  return map[detectStatus.value] || detectStatus.value;
});

const statusTagType = computed(() => getResultTagType(task.value?.status || detectStatus.value));

const stepActive = computed(() => {
  const map = {
    idle: 0,
    ready: 1,
    uploading: 2,
    processing: 3,
    finished: 4,
    failed: 2
  };

  if (task.value?.status === 'completed') {
    return 4;
  }

  if (task.value?.status === 'running' || task.value?.status === 'pending') {
    return 3;
  }

  return map[detectStatus.value] || 0;
});

const displayStatus = computed(() => {
  if (detectStatus.value === 'failed') {
    return 'error';
  }

  if (task.value || loading.value) {
    return 'success';
  }

  return 'empty';
});

const resultTagText = computed(() => {
  if (!task.value) {
    return '';
  }

  return `${formatTaskStatusText(task.value.status)} / ${formatTaskResultText(task.value.task_result)}`;
});

const videoUrl = computed(() => resolveMediaUrl(
  task.value?.metadata?.result_video_url
  || task.value?.metadata?.video_url
  || task.value?.file_url
));

const resultItems = computed(() => {
  if (!task.value) {
    return [];
  }

  return [
    { label: '任务编号', value: task.value.task_no || '-' },
    { label: '文件名', value: task.value.source_name || '-' },
    { label: '任务状态', value: formatTaskStatusText(task.value.status) },
    { label: '检测结果', value: formatTaskResultText(task.value.task_result) },
    { label: '任务进度', value: `${Number(task.value.progress || 0)}%` },
    { label: '总帧数', value: task.value.total_frames ?? 0 },
    { label: '已处理帧数', value: task.value.processed_frames ?? 0 },
    { label: '违规数量', value: task.value.violation_count ?? 0 },
    { label: '任务时长', value: formatDuration(task.value.duration_ms) },
    { label: '开始时间', value: formatDateTime(task.value.started_at || task.value.created_at) },
    { label: '完成时间', value: formatDateTime(task.value.finished_at) }
  ];
});

onBeforeUnmount(() => {
  clearPreview();
});
</script>
