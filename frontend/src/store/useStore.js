import { create } from 'zustand'
import { DEFAULT_SCENES } from '../api/scenesData.js'

// Default to Ultra-HD Ex4 scene with 856k splats (original showcase scene)
const initialScene = DEFAULT_SCENES.find((s) => s.name?.includes('Ex4')) || DEFAULT_SCENES[0]

const useStore = create((set, get) => ({
  // ── Scene & Tour State ───────────────────────────────────────────────────────
  currentScene: initialScene,        // Scene object from API / fallback
  scenes: DEFAULT_SCENES,            // List of available 3D rooms / scenes
  tourData: null,            // TourManifest from tour.json
  activeNodeId: null,        // Current panorama node ID (e.g. 'n000')
  tourMode: 'photosphere',   // 'photosphere' | 'freeroam' | 'dollhouse' | 'splat'
  
  // ── Navigation & POI State ──────────────────────────────────────────────────
  pois: [],                  // Array of POI objects
  selectedPOI: null,         // Currently focused POI
  navigationPath: null,      // Array of [x, y, z] world coords, or null
  mode: 'roam',              // 'roam' | 'navigate' | 'poi-select'
  
  // ── Player & Collision State ────────────────────────────────────────────────
  collisionEnabled: true,    // Clamped by three-pathfinding navmesh
  isAutoWalking: false,      // Video-game style guidance along path
  playerPosition: [0, 1.65, 0],
  playerYaw: 0,
  minimapOpen: false,        // Corner overlay vs full floorplan
  isLoading: false,

  // ── Actions ────────────────────────────────────────────────────────────────
  setScene: (scene) => set({ currentScene: scene }),
  setScenes: (scenes) => set({ scenes }),
  setTourData: (tourData) => {
    const firstNode = tourData?.nodes?.[0]?.id || null
    set({
      tourData,
      activeNodeId: tourData?.default_node || firstNode,
    })
  },
  setActiveNodeId: (activeNodeId) => set({ activeNodeId }),
  setTourMode: (tourMode) => set({ tourMode }),
  
  setPOIs: (pois) => set({ pois }),
  addPOI: (poi) => set((state) => ({ pois: [...state.pois, poi] })),
  selectPOI: (poi) => set({ selectedPOI: poi }),
  
  setPath: (path) => set({ navigationPath: path }),
  setMode: (mode) => {
    const updates = { mode }
    if (mode !== 'navigate') updates.navigationPath = null
    set(updates)
  },
  
  setCollisionEnabled: (collisionEnabled) => set({ collisionEnabled }),
  setIsAutoWalking: (isAutoWalking) => set({ isAutoWalking }),
  setPlayerPosition: (playerPosition) => set({ playerPosition }),
  setPlayerYaw: (playerYaw) => set({ playerYaw }),
  toggleMinimap: () => set((s) => ({ minimapOpen: !s.minimapOpen })),
  setMinimapOpen: (minimapOpen) => set({ minimapOpen }),

  setLoading: (isLoading) => set({ isLoading }),
  clearSelection: () => set({ selectedPOI: null, navigationPath: null, isAutoWalking: false }),
}))

export default useStore
