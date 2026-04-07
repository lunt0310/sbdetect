import request from '@/utils/request';

export const getDashboardData = (params) => request({
  url: '/api/dashboard/',
  method: 'get',
  params
});
