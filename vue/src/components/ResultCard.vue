<template>
  <el-card class="result-card" shadow="never">
    <template #header>
      <div class="result-card__header">
        <span>{{ title }}</span>
        <el-tag v-if="tagText" :type="tagType" effect="light">{{ tagText }}</el-tag>
      </div>
    </template>

    <div v-if="loading" class="result-card__loading">
      <el-skeleton :rows="6" animated />
    </div>

    <el-empty
      v-else-if="status === 'empty'"
      :description="emptyText"
    />

    <el-empty
      v-else-if="status === 'error'"
      :description="errorText"
    />

    <div v-else class="result-card__body">
      <div v-if="$slots.media" class="result-card__media">
        <slot name="media" />
      </div>

      <div class="result-card__grid">
        <div
          v-for="item in items"
          :key="item.label"
          class="result-item"
        >
          <div class="result-item__label">{{ item.label }}</div>
          <div class="result-item__value">{{ item.value || '-' }}</div>
        </div>
      </div>

      <div v-if="$slots.footer" class="result-card__footer">
        <slot name="footer" />
      </div>
    </div>
  </el-card>
</template>

<script setup>
defineProps({
  title: {
    type: String,
    default: '结果展示'
  },
  loading: {
    type: Boolean,
    default: false
  },
  status: {
    type: String,
    default: 'empty'
  },
  items: {
    type: Array,
    default: () => []
  },
  tagText: {
    type: String,
    default: ''
  },
  tagType: {
    type: String,
    default: 'info'
  },
  emptyText: {
    type: String,
    default: '暂无检测结果'
  },
  errorText: {
    type: String,
    default: '检测失败，请重新尝试'
  }
});
</script>
