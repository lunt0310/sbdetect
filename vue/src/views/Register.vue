<template>
  <div class="login-page">
    <div class="login-hero register-hero">
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
          <h2>注册账号</h2>
          <p>请填写基础信息完成注册</p>
        </div>

        <el-form
          ref="formRef"
          :model="form"
          :rules="rules"
          label-position="top"
          size="large"
        >
          <el-form-item label="用户名" prop="username">
            <el-input v-model="form.username" placeholder="请输入用户名" :prefix-icon="User" clearable />
          </el-form-item>

          <el-form-item label="手机号" prop="phone">
            <el-input v-model="form.phone" placeholder="请输入手机号" :prefix-icon="Iphone" clearable />
          </el-form-item>

          <el-form-item label="邮箱" prop="email">
            <el-input v-model="form.email" placeholder="请输入邮箱" :prefix-icon="Message" clearable />
          </el-form-item>

          <el-form-item label="密码" prop="password">
            <el-input
              v-model="form.password"
              type="password"
              placeholder="请输入密码"
              :prefix-icon="Lock"
              show-password
              clearable
            />
          </el-form-item>

          <el-form-item label="确认密码" prop="confirmPassword">
            <el-input
              v-model="form.confirmPassword"
              type="password"
              placeholder="请再次输入密码"
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
              注册并进入系统
            </el-button>
          </el-form-item>
        </el-form>

        <div class="auth-switch">
          已有账号？
          <router-link to="/login">立即登录</router-link>
        </div>
      </el-card>
    </div>
  </div>
</template>

<script setup>
import { Iphone, Lock, Message, User } from '@element-plus/icons-vue';
import { reactive, ref } from 'vue';
import { useRouter } from 'vue-router';
import { ElMessage } from 'element-plus';

import { useUserStore } from '@/store/user';

const router = useRouter();
const formRef = ref(null);
const loading = ref(false);
const userStore = useUserStore();

const form = reactive({
  username: '',
  password: '',
  confirmPassword: '',
  phone: '',
  email: ''
});

const validateConfirmPassword = (rule, value, callback) => {
  if (!value) {
    callback(new Error('请再次输入密码'));
    return;
  }

  if (value !== form.password) {
    callback(new Error('两次输入的密码不一致'));
    return;
  }

  callback();
};

const rules = {
  username: [
    { required: true, message: '请输入用户名', trigger: 'blur' },
    { min: 3, message: '用户名长度不能少于 3 位', trigger: 'blur' }
  ],
  phone: [
    { required: true, message: '请输入手机号', trigger: 'blur' },
    { pattern: /^1\\d{10}$/, message: '请输入正确的手机号', trigger: 'blur' }
  ],
  email: [
    { type: 'email', message: '请输入正确的邮箱格式', trigger: 'blur' }
  ],
  password: [
    { required: true, message: '请输入密码', trigger: 'blur' },
    { min: 6, message: '密码长度不能少于 6 位', trigger: 'blur' }
  ],
  confirmPassword: [
    { validator: validateConfirmPassword, trigger: 'blur' }
  ]
};

const handleSubmit = async () => {
  if (!formRef.value) {
    return;
  }

  await formRef.value.validate();
  loading.value = true;

  try {
    const payload = {
      username: form.username,
      password: form.password,
      confirm_password: form.confirmPassword,
      phone: form.phone
    };

    if (form.email) {
      payload.email = form.email;
    }

    await userStore.registerAction(payload);
    ElMessage.success('注册成功，已自动登录');
    router.push('/dashboard');
  } finally {
    loading.value = false;
  }
};
</script>
