<template>
  <div class="login-page">
    <div class="login-hero">
      <h1>安全带检测管理系统</h1>

      <div class="hero-points">
        <div class="hero-point">
          <strong>实时检测</strong>
          <span>上传图片或视频后直观查看检测结果</span>
        </div>
        <div class="hero-point">
          <strong>可视化统计</strong>
          <span>仪表盘集中展示关键数据</span>
        </div>
        <div class="hero-point">
          <strong>记录追踪</strong>
          <span>识别记录、违规记录、日志与用户管理按角色开放</span>
        </div>
      </div>
    </div>

    <div class="login-panel">
      <el-card class="login-card" shadow="never">
        <div class="login-card__title">
          <h2>欢迎登录</h2>
          <p>请输入账号密码进入系统</p>
        </div>

        <el-form
          ref="formRef"
          :model="form"
          :rules="rules"
          label-position="top"
          size="large"
        >
          <el-form-item label="用户名" prop="username">
            <el-input
              v-model="form.username"
              placeholder="请输入用户名"
              :prefix-icon="User"
              clearable
            />
          </el-form-item>

          <el-form-item label="密码" prop="password">
            <el-input
              v-model="form.password"
              type="password"
              placeholder="请输入密码"
              :prefix-icon="Lock"
              show-password
              clearable
              @keyup.enter="handleSubmit"
            />
          </el-form-item>

          <el-form-item>
            <el-button
              type="primary"
              class="login-submit"
              :loading="loading"
              @click="handleSubmit"
            >
              登录系统
            </el-button>
          </el-form-item>
        </el-form>

        <div class="auth-switch">
          还没有账号？
          <router-link to="/register">立即注册</router-link>
        </div>
      </el-card>
    </div>
  </div>
</template>

<script setup>
import { Lock, User } from '@element-plus/icons-vue';
import { reactive, ref } from 'vue';
import { useRoute, useRouter } from 'vue-router';
import { ElMessage } from 'element-plus';

import { useUserStore } from '@/store/user';

const formRef = ref(null);
const route = useRoute();
const router = useRouter();
const userStore = useUserStore();
const loading = ref(false);

const form = reactive({
  username: '',
  password: ''
});

const rules = {
  username: [
    { required: true, message: '请输入用户名', trigger: 'blur' }
  ],
  password: [
    { required: true, message: '请输入密码', trigger: 'blur' },
    { min: 6, message: '密码长度不能少于 6 位', trigger: 'blur' }
  ]
};

const handleSubmit = async () => {
  if (!formRef.value) {
    return;
  }

  await formRef.value.validate();

  loading.value = true;

  try {
    await userStore.loginAction(form);
    ElMessage.success('登录成功');
    router.push(route.query.redirect || '/dashboard');
  } finally {
    loading.value = false;
  }
};
</script>
