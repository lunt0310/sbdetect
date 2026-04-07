import { getDetectionDetail, getDetectionList } from '@/api/detect';

export const getHistoryList = (params) => getDetectionList(params);
export const getHistoryDetail = (id) => getDetectionDetail(id);
export const deleteHistory = () => Promise.reject(new Error('当前后端未提供删除历史接口'));
