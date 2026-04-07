import request from '@/utils/request';

export const getDetectionList = (params) => request({
  url: '/api/detections/',
  method: 'get',
  params
});

export const createDetection = (data) => request({
  url: '/api/detections/',
  method: 'post',
  data,
  headers: {
    'Content-Type': 'multipart/form-data'
  }
});

export const getDetectionDetail = (id) => request({
  url: `/api/detections/${id}/`,
  method: 'get'
});

export const getObjectImageBlob = (id) => request({
  url: `/api/objects/${id}/image/`,
  method: 'get',
  responseType: 'blob'
});
