import axios from 'axios'

const api = axios.create({
  baseURL: import.meta.env.VITE_API_URL || 'http://localhost:8000',
})

api.interceptors.request.use((config) => {
  const token = localStorage.getItem('esg_token')
  if (token) {
    config.headers['Authorization'] = `Token ${token}`
  }
  return config
})

export function login(username, password) {
  return api.post('/api/auth/login/', { username, password })
}

export function getMe() {
  return api.get('/api/auth/me/')
}

export function getStats() {
  return api.get('/api/stats/')
}

export function getIngestions() {
  return api.get('/api/ingestions/')
}

export function uploadFile(sourceType, file, onProgress) {
  const formData = new FormData()
  formData.append('file', file)
  return api.post(`/api/upload/${sourceType}/`, formData, {
    headers: { 'Content-Type': 'multipart/form-data' },
    onUploadProgress: (progressEvent) => {
      if (onProgress && progressEvent.total) {
        const pct = Math.round((progressEvent.loaded * 100) / progressEvent.total)
        onProgress(pct)
      }
    },
  })
}

export function getRecords(params) {
  return api.get('/api/records/', { params })
}

export function getRecord(id) {
  return api.get(`/api/records/${id}/`)
}

export function approveRecord(id, reviewNote) {
  return api.post(`/api/records/${id}/approve/`, { review_note: reviewNote })
}

export function rejectRecord(id, reviewNote) {
  return api.post(`/api/records/${id}/reject/`, { review_note: reviewNote })
}

export function bulkApprove(recordIds) {
  return api.post('/api/records/bulk-approve/', { record_ids: recordIds })
}

export default api
