import request from '@/utils/request';

export function getHealthStatus() {
  return request.get('/api/health/');
}
