<template>
  <div>
    <PageHeader
      title="用户管理"
      description="仅管理员可见。支持查询用户、创建用户、修改用户信息和重置密码。"
    >
      <template #extra>
        <el-button @click="loadUsers">刷新列表</el-button>
        <el-button type="primary" @click="openCreateDialog">创建用户</el-button>
      </template>
    </PageHeader>

    <el-row :gutter="20" class="stat-grid">
      <el-col :xs="24" :sm="8">
        <el-card shadow="hover" class="stat-card">
          <div class="stat-card__icon theme-blue"><el-icon><UserFilled /></el-icon></div>
          <div class="stat-card__content">
            <div class="stat-card__label">用户总数</div>
            <div class="stat-card__value">{{ users.length }}</div>
            <div class="stat-card__foot">系统用户接口返回的全部用户</div>
          </div>
        </el-card>
      </el-col>
      <el-col :xs="24" :sm="8">
        <el-card shadow="hover" class="stat-card">
          <div class="stat-card__icon theme-green"><el-icon><CircleCheckFilled /></el-icon></div>
          <div class="stat-card__content">
            <div class="stat-card__label">启用用户</div>
            <div class="stat-card__value">{{ users.filter((item) => item.is_active).length }}</div>
            <div class="stat-card__foot">可正常登录系统的账号数量</div>
          </div>
        </el-card>
      </el-col>
      <el-col :xs="24" :sm="8">
        <el-card shadow="hover" class="stat-card">
          <div class="stat-card__icon theme-orange"><el-icon><Management /></el-icon></div>
          <div class="stat-card__content">
            <div class="stat-card__label">管理员 / 审核员</div>
            <div class="stat-card__value">{{ users.filter((item) => ['admin', 'auditor'].includes(item.role)).length }}</div>
            <div class="stat-card__foot">具备后台管理能力的账号数量</div>
          </div>
        </el-card>
      </el-col>
    </el-row>

    <el-card shadow="never" class="panel-card filter-card">
      <el-form :inline="true" :model="filters" class="filter-form">
        <el-form-item label="用户名">
          <el-input v-model="filters.username" placeholder="按用户名筛选" clearable style="width: 180px" />
        </el-form-item>
        <el-form-item label="角色">
          <el-select v-model="filters.role" clearable placeholder="全部角色" style="width: 160px">
            <el-option label="普通用户" value="user" />
            <el-option label="审核员" value="auditor" />
            <el-option label="管理员" value="admin" />
          </el-select>
        </el-form-item>
        <el-form-item label="状态">
          <el-select v-model="filters.is_active" clearable placeholder="全部状态" style="width: 160px">
            <el-option label="启用" :value="true" />
            <el-option label="停用" :value="false" />
          </el-select>
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
      <el-table :data="pagedUsers" v-loading="loading" stripe>
        <el-table-column prop="id" label="ID" width="80" />
        <el-table-column prop="username" label="用户名" width="140" />
        <el-table-column prop="phone" label="手机号" width="150" />
        <el-table-column prop="email" label="邮箱" min-width="180" />
        <el-table-column label="角色" width="120">
          <template #default="{ row }">
            <el-tag :type="getResultTagType(row.role)" effect="light">{{ formatRoleText(row.role) }}</el-tag>
          </template>
        </el-table-column>
        <el-table-column label="状态" width="100">
          <template #default="{ row }">
            <el-tag :type="row.is_active ? 'success' : 'danger'" effect="light">{{ row.is_active ? '启用' : '停用' }}</el-tag>
          </template>
        </el-table-column>
        <el-table-column label="创建时间" min-width="170">
          <template #default="{ row }">
            {{ formatDateTime(row.date_joined || row.created_at) }}
          </template>
        </el-table-column>
        <el-table-column label="操作" min-width="280" fixed="right">
          <template #default="{ row }">
            <el-button text type="primary" @click="openEditDialog(row)">修改</el-button>
            <el-button text type="warning" @click="toggleStatus(row)">{{ row.is_active ? '停用' : '启用' }}</el-button>
            <el-button text type="danger" @click="resetPassword(row)">重置密码</el-button>
          </template>
        </el-table-column>
      </el-table>

      <el-empty v-if="!filteredUsers.length && !loading" description="暂无用户数据" />

      <div class="table-footer">
        <div class="table-footer__count">共 {{ filteredUsers.length }} 位用户</div>
        <el-pagination
          background
          layout="total, sizes, prev, pager, next, jumper"
          :total="filteredUsers.length"
          :page-size="pagination.pageSize"
          :current-page="pagination.page"
          :page-sizes="[10, 20, 50]"
          @current-change="handlePageChange"
          @size-change="handleSizeChange"
        />
      </div>
    </el-card>

    <el-dialog v-model="dialogVisible" :title="dialogMode === 'create' ? '创建用户' : '修改用户'" width="520px">
      <el-form ref="formRef" :model="form" :rules="rules" label-width="90px">
        <el-form-item label="用户名" prop="username">
          <el-input v-model="form.username" :disabled="dialogMode === 'edit'" />
        </el-form-item>
        <el-form-item label="手机号" prop="phone">
          <el-input v-model="form.phone" />
        </el-form-item>
        <el-form-item label="邮箱" prop="email">
          <el-input v-model="form.email" />
        </el-form-item>
        <el-form-item label="角色" prop="role">
          <el-select v-model="form.role" style="width: 100%">
            <el-option label="普通用户" value="user" />
            <el-option label="审核员" value="auditor" />
            <el-option label="管理员" value="admin" />
          </el-select>
        </el-form-item>
        <el-form-item label="状态" prop="is_active">
          <el-switch v-model="form.is_active" />
        </el-form-item>
        <el-form-item v-if="dialogMode === 'create'" label="初始密码" prop="password">
          <el-input v-model="form.password" type="password" show-password />
        </el-form-item>
      </el-form>
      <template #footer>
        <el-button @click="dialogVisible = false">取消</el-button>
        <el-button type="primary" @click="submitForm">确定</el-button>
      </template>
    </el-dialog>
  </div>
</template>

<script setup>
import { CircleCheckFilled, Management, UserFilled } from '@element-plus/icons-vue';
import { computed, reactive, ref } from 'vue';
import { ElMessage, ElMessageBox } from 'element-plus';

import { createSystemUser, getSystemUsers, resetSystemUserPassword, updateSystemUser } from '@/api/system';
import PageHeader from '@/components/PageHeader.vue';
import { formatDateTime, formatRoleText, getListData, getResultTagType } from '@/utils/format';

const users = ref([]);
const loading = ref(false);
const dialogVisible = ref(false);
const dialogMode = ref('create');
const currentEditId = ref(null);
const formRef = ref(null);

const filters = reactive({
  username: '',
  role: '',
  is_active: '',
  dateRange: []
});

const pagination = reactive({
  page: 1,
  pageSize: 10
});

const form = reactive({
  username: '',
  phone: '',
  email: '',
  role: 'user',
  is_active: true,
  password: ''
});

const rules = {
  username: [
    { required: true, message: '请输入用户名', trigger: 'blur' }
  ],
  phone: [
    { required: true, message: '请输入手机号', trigger: 'blur' }
  ],
  email: [
    { required: true, message: '请输入邮箱', trigger: 'blur' },
    { type: 'email', message: '请输入正确的邮箱格式', trigger: 'blur' }
  ],
  role: [
    { required: true, message: '请选择角色', trigger: 'change' }
  ],
  password: [
    { required: true, message: '请输入初始密码', trigger: 'blur' },
    { min: 6, message: '密码至少 6 位', trigger: 'blur' }
  ]
};

const filteredUsers = computed(() => users.value.filter((item) => {
  if (filters.username && !String(item.username || '').includes(filters.username.trim())) {
    return false;
  }

  if (filters.role && item.role !== filters.role) {
    return false;
  }

  if (filters.is_active !== '' && Boolean(item.is_active) !== filters.is_active) {
    return false;
  }

  if (filters.dateRange?.length === 2) {
    const dateValue = String(item.date_joined || item.created_at || '');
    if (dateValue < filters.dateRange[0] || dateValue > `${filters.dateRange[1]} 23:59:59`) {
      return false;
    }
  }

  return true;
}));

const pagedUsers = computed(() => {
  const start = (pagination.page - 1) * pagination.pageSize;
  return filteredUsers.value.slice(start, start + pagination.pageSize);
});

const resetForm = () => {
  form.username = '';
  form.phone = '';
  form.email = '';
  form.role = 'user';
  form.is_active = true;
  form.password = '';
  currentEditId.value = null;
  formRef.value?.clearValidate();
};

const buildParams = () => {
  const [startDate, endDate] = filters.dateRange || [];
  return {
    username: filters.username || undefined,
    role: filters.role || undefined,
    is_active: filters.is_active === '' ? undefined : filters.is_active,
    date_from: startDate || undefined,
    date_to: endDate || undefined
  };
};

const loadUsers = async () => {
  loading.value = true;
  try {
    const data = await getSystemUsers(buildParams());
    users.value = getListData(data);
    pagination.page = 1;
  } finally {
    loading.value = false;
  }
};

const openCreateDialog = () => {
  dialogMode.value = 'create';
  resetForm();
  dialogVisible.value = true;
};

const openEditDialog = (row) => {
  dialogMode.value = 'edit';
  currentEditId.value = row.id;
  form.username = row.username;
  form.phone = row.phone || '';
  form.email = row.email || '';
  form.role = row.role || 'user';
  form.is_active = row.is_active !== false;
  form.password = '';
  dialogVisible.value = true;
};

const submitForm = async () => {
  await formRef.value.validate();

  const payload = {
    phone: form.phone,
    email: form.email,
    role: form.role,
    is_active: form.is_active
  };

  if (dialogMode.value === 'create') {
    await createSystemUser({
      username: form.username,
      password: form.password,
      confirm_password: form.password,
      ...payload
    });
    ElMessage.success('创建用户成功');
  } else {
    await updateSystemUser(currentEditId.value, payload);
    ElMessage.success('修改用户成功');
  }

  dialogVisible.value = false;
  loadUsers();
};

const toggleStatus = async (row) => {
  try {
    await ElMessageBox.confirm(`确认${row.is_active ? '停用' : '启用'}用户 ${row.username} 吗？`, '状态变更', {
      type: 'warning'
    });
  } catch (error) {
    return;
  }

  await updateSystemUser(row.id, {
    phone: row.phone,
    email: row.email,
    role: row.role,
    is_active: !row.is_active
  });
  ElMessage.success('用户状态已更新');
  loadUsers();
};

const resetPassword = async (row) => {
  let password = '';

  try {
    const result = await ElMessageBox.prompt(`请输入用户 ${row.username} 的新密码`, '重置密码', {
      confirmButtonText: '确定',
      cancelButtonText: '取消',
      inputType: 'password',
      inputPattern: /^.{6,}$/,
      inputErrorMessage: '密码至少 6 位'
    });
    password = result.value;
  } catch (error) {
    return;
  }

  await resetSystemUserPassword(row.id, {
    new_password: password,
    confirm_password: password
  });
  ElMessage.success('密码已重置');
};

const handlePageChange = (page) => {
  pagination.page = page;
};

const handleSizeChange = (pageSize) => {
  pagination.pageSize = pageSize;
  pagination.page = 1;
};

loadUsers();
</script>
