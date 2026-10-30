import axios from 'axios'

const api = axios.create({
  baseURL: '/api',
  headers: { 'Content-Type': 'application/json' },
})

// ── Scenes ────────────────────────────────────────────────────────────────────

export const getScenes = () => api.get('/scenes').then(r => r.data)

export const getScene = (id) => api.get(`/scenes/${id}`).then(r => r.data)

export const createScene = (name) =>
  api.post('/scenes', { name }).then(r => r.data)

// ── POIs ──────────────────────────────────────────────────────────────────────

export const getPOIs = (sceneId) =>
  api.get(`/scenes/${sceneId}/pois`).then(r => r.data)

export const createPOI = (sceneId, { name, description, x, y, z }) =>
  api.post(`/scenes/${sceneId}/pois`, { name, description, x, y, z }).then(r => r.data)

export const updatePOI = (poiId, data) =>
  api.put(`/pois/${poiId}`, data).then(r => r.data)

export const deletePOI = (poiId) =>
  api.delete(`/pois/${poiId}`)

export const searchPOIs = (sceneId, q) =>
  api.get(`/scenes/${sceneId}/search`, { params: { q } }).then(r => r.data)

// ── Navigation ────────────────────────────────────────────────────────────────

export const getPath = (sceneId, fromPoiId, toPoiId) =>
  api.get(`/scenes/${sceneId}/path`, {
    params: { from_poi: fromPoiId, to_poi: toPoiId },
  }).then(r => r.data)

export const getGridMeta = (sceneId) =>
  api.get(`/scenes/${sceneId}/grid`).then(r => r.data)

export default api
