import axios from 'axios'

const api = axios.create({
  baseURL: '/api',
  headers: { 'Content-Type': 'application/json' },
})

// ── Scenes ────────────────────────────────────────────────────────────────────

const FALLBACK_SCENES = [
  {
    id: 10,
    name: 'Ex4 Scene (Showcase Room)',
    glb_path: '/static/models/ex4.glb',
    splat_path: '/static/models/ex4.splat',
    grid_path: '/static/navigation/ex4_grid.npy',
    grid_meta_json: JSON.stringify({ origin: [-10.0, -10.0], cell_size: 0.05, rows: 200, cols: 200 })
  },
  {
    id: 5,
    name: 'Sample Scene',
    glb_path: '/static/models/sample_scene.glb',
    splat_path: '/static/models/sample_scene.splat',
    grid_path: '/static/navigation/sample_scene_grid.npy',
    grid_meta_json: JSON.stringify({ origin: [-5.0, -5.0], cell_size: 0.05, rows: 100, cols: 100 })
  }
]

export const getScenes = () =>
  api.get('/scenes')
    .then(r => r.data)
    .catch((err) => {
      console.warn('Backend API /scenes unreachable, using static fallback scenes:', err.message)
      return FALLBACK_SCENES
    })

export const getScene = (id) =>
  api.get(`/scenes/${id}`)
    .then(r => r.data)
    .catch(() => FALLBACK_SCENES.find(s => s.id === Number(id)) || FALLBACK_SCENES[0])

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
