<template>
  <div>
    <PageHeader
      title="用户中心"
      description="查看当前登录用户信息，并支持在线修改密码。"
    />

    <el-row :gutter="20">
      <el-col :xs="24" :xl="9">
        <el-card shadow="never" class="panel-card profile-card">
          <div class="profile-card__head">
            <el-avatar :size="72">{{ userInitial }}</el-avatar>
            <div>
              <h3>{{ userInfo.username || '未命名用户' }}</h3>
              <p>{{ roleText }}</p>
            </div>
          </div>

          <div class="profile-card__body">
            <div class="profile-meta">
              <span>用户 ID</span>
              <strong>{{ userInfo.id || '-' }}</strong>
            </div>
            <div class="profile-meta">
              <span>用户名</span>
              <strong>{{ userInfo.username || '-' }}</strong>
            </div>
            <div class="profile-meta">
              <span>手机号</span>
              <strong>{{ userInfo.phone || '-' }}</strong>
            </div>
            <div class="profile-meta">
              <span>邮箱</span>
              <strong>{{ userInfo.email || '-' }}</strong>
            </div>
            <div class="profile-meta">
              <span>角色</span>
              <strong>{{ roleText }}</strong>
            </div>
            <div class="profile-meta">
              <span>注册时间</span>
              <strong>{{ formatDateTime(userInfo.date_joined || userInfo.created_at) }}</strong>
            </div>
          </div>
        </el-card>
      </el-col>

      <el-col :xs="24" :xl="15">
        <el-card shadow="never" class="panel-card">
          <template #header>
            <div class="panel-card__header">
              <span>修改密码</span>
              <el-tag type="warning" effect="plain">Password Update</el-tag>
            </div>
          </template>

          <el-form
            ref="formRef"
            :model="passwordForm"
            :rules="rules"
            label-width="110px"
            class="password-form"
          >
            <el-form-item label="原密码" prop="old_password">
              <el-input v-model="passwordForm.old_password" type="password" show-password />
            </el-form-item>
            <el-form-item label="新密码" prop="new_password">
              <el-input v-model="passwordForm.new_password" type="password" show-password />
            </el-form-item>
            <el-form-item label="确认密码" prop="confirm_password">
              <el-input v-model="passwordForm.confirm_password" type="password" show-password />
            </el-form-item>
            <el-form-item>
              <el-button type="primary" :loading="submitting" @click="handleSubmit">保存修改</el-button>
              <el-button @click="resetForm">重置表单</el-button>
            </el-form-item>
          </el-form>
        </el-card>
      </el-col>
    </el-row>
  </div>
</template>

<script setup>
import { computed, onMounted, reactive, ref } from 'vue';
import { storeToRefs } from 'pinia';
import { ElMessage } from 'element-plus';

import { changePassword } from '@/api/user';
import PageHeader from '@/components/PageHeader.vue';
import { useUserStore } from '@/store/user';
import { formatDateTime, formatRoleText } from '@/utils/format';

const userStore = useUserStore();
const { user } = storeToRefs(userStore);
const formRef = ref(null);
const submitting = ref(false);

const passwordForm = reactive({
  old_password: '',
  new_password: '',
  confirm_password: ''
});

const validateConfirmPassword = (rule, value, callback) => {
  if (!value) {
    callback(new Error('请再次输入新密码'));
    return;
  }

  if (value !== passwordForm.new_password) {
    callback(new Error('两次输入的新密码不一致'));
    return;
  }

  callback();
};

const rules = {
  old_password: [
    { required: true, message: '请输入原密码', trigger: 'blur' }
  ],
  new_password: [
    { required: true, message: '请输入新密码', trigger: 'blur' },
    { min: 6, message: '新密码长度不能少于 6 位', trigger: 'blur' }
  ],
  confirm_password: [
    { validator: validateConfirmPassword, trigger: 'blur' }
  ]
};

const userInfo = computed(() => user.value || {});
const userInitial = computed(() => (userInfo.value.username || 'U').slice(0, 1).toUpperCase());
const roleText = computed(() => formatRoleText(userInfo.value.role));

const resetForm = () => {
  passwordForm.old_password = '';
  passwordForm.new_password = '';
  passwordForm.confirm_password = '';
  formRef.value?.clearValidate();
};

const handleSubmit = async () => {
  if (!formRef.value) {
    return;
  }

  await formRef.value.validate();
  submitting.value = true;

  try {
    const data = await changePassword({
      old_password: passwordForm.old_password,
      new_password: passwordForm.new_password,
      confirm_password: passwordForm.confirm_password
    });
    userStore.setAuth(data || {});
    ElMessage.success('密码修改成功，登录状态已同步更新');
    resetForm();
  } finally {
    submitting.value = false;
  }
};

onMounted(() => {
  if (!user.value) {
    userStore.fetchUserInfo().catch(() => {});
  }
});
</script>
