import axios from 'axios';

// Same-origin by default: nginx (AWS) and the Vite dev proxy both forward /api to FastAPI.
const api = axios.create({
  baseURL: import.meta.env.VITE_API_URL || '/api',
});

api.interceptors.request.use((config) => {
  const token = localStorage.getItem('token');
  if (token) {
    config.headers.Authorization = `Bearer ${token}`;
  }
  return config;
});

// crypto.randomUUID only exists on HTTPS/localhost; fall back for plain-HTTP pages.
export function newKey() {
  if (globalThis.crypto?.randomUUID) return globalThis.crypto.randomUUID();
  return 'k-' + Date.now().toString(36) + '-' + Math.random().toString(36).slice(2, 12);
}

export default api;
