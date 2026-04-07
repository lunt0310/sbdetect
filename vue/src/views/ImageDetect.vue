<template>
  <div>
    <PageHeader
      title="图片检测"
      description="上传单张图片进行安全带识别，前端直接对接统一检测接口并展示任务结果。"
    />

    <el-row :gutter="20">
      <el-col :xs="24" :xl="10">
        <el-card shadow="never" class="panel-card">
          <template #header>
            <div class="panel-card__header">
              <span>上传图片</span>
              <el-tag type="info" effect="plain">JPG / PNG / WEBP</el-tag>
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
            accept=".jpg,.jpeg,.png,.webp"
          >
            <el-icon class="el-icon--upload"><UploadFilled /></el-icon>
            <div class="el-upload__text">将图片拖到此处，或 <em>点击上传</em></div>
            <template #tip>
              <div class="el-upload__tip">仅支持 jpg / jpeg / png / webp，文件大小不超过 5MB</div>
            </template>
          </el-upload>

          <div class="preview-box">
            <div class="preview-box__title">上传预览</div>
            <div v-if="previewUrl" class="preview-box__image preview-box__media">
              <img :src="previewUrl" alt="图片预览" />
            </div>
            <el-empty v-else description="请选择待检测图片" />
          </div>

          <div class="action-row">
            <el-button type="primary" :loading="loading" @click="handleDetect">开始检测</el-button>
            <el-button @click="resetAll">清空结果</el-button>
          </div>
        </el-card>
      </el-col>

      <el-col :xs="24" :xl="14">
        <ResultCard
          title="检测结果"
          :loading="loading"
          :status="resultStatus"
          :items="resultItems"
          :tag-text="resultTagText"
          :tag-type="resultTagType"
          empty-text="上传图片后点击“开始检测”查看结果"
          error-text="检测失败，请检查图片格式或稍后再试"
        >
          <template #media>
            <div v-if="processedImageUrl" class="detect-media">
              <img :src="processedImageUrl" alt="检测结果图" />
            </div>
          </template>

          <template #footer>
            <el-alert
              v-if="task"
              :title="footerText"
              :type="resultStatus === 'error' ? 'warning' : 'success'"
              :closable="false"
              show-icon
            />
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
  formatPercent,
  formatTaskResultText,
  formatTaskStatusText,
  getLatestResult,
  getResultTagType,
  resolveMediaUrl
} from '@/utils/format';

const uploadRef = ref(null);
const fileList = ref([]);
const selectedFile = ref(null);
const previewUrl = ref('');
const loading = ref(false);
const resultStatus = ref('empty');
const task = ref(null);

const validateImageFile = (file) => {
  const validTypes = ['image/jpeg', 'image/png', 'image/webp'];
  const isValidType = validTypes.includes(file.type);
  const isValidSize = file.size / 1024 / 1024 <= 5;

  if (!isValidType) {
    ElMessage.warning('仅支持 JPG、PNG、WEBP 格式的图片');
    return false;
  }

  if (!isValidSize) {
    ElMessage.warning('图片大小不能超过 5MB');
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

const latestResult = computed(() => getLatestResult(task.value));
const processedImageUrl = computed(() => resolveMediaUrl(latestResult.value?.result_image_url));

const resultTagText = computed(() => {
  if (!task.value) {
    return '';
  }
  return formatTaskResultText(task.value.task_result);
});

const resultTagType = computed(() => getResultTagType(task.value?.task_result || task.value?.status));

const footerText = computed(() => {
  if (!task.value) {
    return '';
  }

  if (resultStatus.value === 'error') {
    return task.value.error_message || '后端已返回任务信息，但本次检测未成功完成。';
  }

  return task.value.has_violation
    ? '检测完成，已识别到违规目标，可进入详情页查看对象列表与违规详情。'
    : '检测完成，当前图片未发现违规目标。';
});

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
    { label: '违规数量', value: task.value.violation_count ?? 0 },
    { label: '目标数量', value: latestResult.value?.object_count ?? 0 },
    { label: '最高置信度', value: formatPercent(latestResult.value?.max_confidence) },
    { label: '检测时间', value: formatDateTime(task.value.created_at) },
    { label: '结果图片', value: latestResult.value?.result_image_url || '后端未返回结果图' }
  ];
});

const replaceCurrentFile = (rawFile) => {
  clearPreview();
  task.value = null;
  resultStatus.value = 'empty';
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

  if (!rawFile || !validateImageFile(rawFile)) {
    replaceCurrentFile(null);
    uploadRef.value?.clearFiles();
    return;
  }

  uploadRef.value?.clearFiles();
  replaceCurrentFile(rawFile);
};

const handleExceed = (files) => {
  const rawFile = files[0];

  if (!rawFile || !validateImageFile(rawFile)) {
    return;
  }

  uploadRef.value?.clearFiles();
  replaceCurrentFile(rawFile);
};

const handleRemove = () => {
  selectedFile.value = null;
  fileList.value = [];
  clearPreview();
};

const resetAll = () => {
  task.value = null;
  resultStatus.value = 'empty';
  selectedFile.value = null;
  fileList.value = [];
  clearPreview();
  uploadRef.value?.clearFiles();
};

const handleDetect = async () => {
  if (!selectedFile.value) {
    ElMessage.warning('请先选择一张图片');
    return;
  }

  const formData = new FormData();
  formData.append('file', selectedFile.value);
  loading.value = true;
  resultStatus.value = 'empty';

  try {
    const data = await createDetection(formData);
    task.value = data || null;
    resultStatus.value = 'success';
    ElMessage.success('图片检测完成');
  } catch (error) {
    task.value = error.apiData || null;
    resultStatus.value = 'error';
  } finally {
    loading.value = false;
  }
};

onBeforeUnmount(() => {
  clearPreview();
});
</script>
