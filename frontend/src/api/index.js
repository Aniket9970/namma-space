import axios from 'axios'
import { DEFAULT_SCENES, DEFAULT_POIS } from './scenesData.js'

const api = axios.create({
  baseURL: '/api',
  headers: { 'Content-Type': 'application/json' },
  timeout: 3000,
})

// Local storage key for offline/standalone POIs
const LOCAL_POIS_KEY = 'namma_space_custom_pois'
const getLocalPOIs = () => {
  try {
    return JSON.parse(localStorage.getItem(LOCAL_POIS_KEY) || '[]')
  } catch {
    return []
  }
}
const saveLocalPOIs = (pois) => {
  try {
    localStorage.setItem(LOCAL_POIS_KEY, JSON.stringify(pois))
  } catch {}
}

// ── Scenes ────────────────────────────────────────────────────────────────────

export const getScenes = async () => {
  try {
    const r = await api.get('/scenes')
    if (r.data && Array.isArray(r.data) && r.data.length > 0) {
      return r.data
    }
  } catch (err) {
    console.info('[Namma Space] Using bundled scenes (standalone mode).')
  }
  return DEFAULT_SCENES
}

export const getScene = async (id) => {
  try {
    const r = await api.get(`/scenes/${id}`)
    if (r.data) return r.data
  } catch {}
  return DEFAULT_SCENES.find((s) => s.id === Number(id)) || DEFAULT_SCENES[0]
}

export const createScene = async (name) => {
  try {
    const r = await api.post('/scenes', { name })
    return r.data
  } catch {
    const newScene = {
      id: Date.now(),
      name,
      glb_path: '/static/models/scene.glb',
      splat_path: '/static/models/scene.splat',
      grid_path: '/static/navigation/grid.npy',
      grid_meta_json: null,
      tour_path: '/static/panoramas/sample_scene/tour.json',
      created_at: new Date().toISOString(),
    }
    return newScene
  }
}

// ── POIs ──────────────────────────────────────────────────────────────────────

export const getPOIs = async (sceneId) => {
  try {
    const r = await api.get(`/scenes/${sceneId}/pois`)
    if (r.data && Array.isArray(r.data)) return r.data
  } catch {}

  const basePois = DEFAULT_POIS.filter((p) => p.scene_id === Number(sceneId))
  const localPois = getLocalPOIs().filter((p) => p.scene_id === Number(sceneId))
  return [...basePois, ...localPois]
}

export const createPOI = async (sceneId, { name, description, x, y, z }) => {
  try {
    const r = await api.post(`/scenes/${sceneId}/pois`, { name, description, x, y, z })
    return r.data
  } catch {
    const newPoi = {
      id: Date.now(),
      scene_id: Number(sceneId),
      name,
      description: description || '',
      x: Number(x) || 0,
      y: Number(y) || 0,
      z: Number(z) || 0,
      grid_row: null,
      grid_col: null,
    }
    const current = getLocalPOIs()
    saveLocalPOIs([...current, newPoi])
    return newPoi
  }
}

export const updatePOI = async (poiId, data) => {
  try {
    const r = await api.put(`/pois/${poiId}`, data)
    return r.data
  } catch {
    const current = getLocalPOIs()
    const updated = current.map((p) => (p.id === poiId ? { ...p, ...data } : p))
    saveLocalPOIs(updated)
    return { id: poiId, ...data }
  }
}

export const deletePOI = async (poiId) => {
  try {
    await api.delete(`/pois/${poiId}`)
  } catch {
    const current = getLocalPOIs()
    saveLocalPOIs(current.filter((p) => p.id !== poiId))
  }
}

export const searchPOIs = async (sceneId, q) => {
  try {
    const r = await api.get(`/scenes/${sceneId}/search`, { params: { q } })
    return r.data
  } catch {
    const all = await getPOIs(sceneId)
    if (!q) return all.slice(0, 5)
    return all.filter((p) => p.name.toLowerCase().includes(q.toLowerCase())).slice(0, 5)
  }
}

// ── Navigation ────────────────────────────────────────────────────────────────

export const getPath = async (sceneId, fromPoiId, toPoiId) => {
  try {
    const r = await api.get(`/scenes/${sceneId}/path`, {
      params: { from_poi: fromPoiId, to_poi: toPoiId },
    })
    return r.data
  } catch {
    return { path: [] }
  }
}

export const getGridMeta = async (sceneId) => {
  try {
    const r = await api.get(`/scenes/${sceneId}/grid`)
    return r.data
  } catch {
    return null
  }
}

export default api

