import request from '@/utils/request';

export const getViolations = (params) => request({
  url: '/api/violations/',
  method: 'get',
  params
});

export const getViolationDetail = (id) => request({
  url: `/api/violations/${id}/`,
  method: 'get'
});

export const reviewViolation = (id, data) => request({
  url: `/api/violations/${id}/review/`,
  method: 'post',
  data
});
