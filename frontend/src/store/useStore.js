import { create } from 'zustand'

const useStore = create((set, get) => ({
  // ── State ──────────────────────────────────────────────────────────────────
  currentScene: null,    // Scene object from API
  pois: [],              // Array of POI objects
  selectedPOI: null,     // Currently focused POI
  navigationPath: null,  // Array of [x, y, z] world coords, or null
  mode: 'roam',          // 'roam' | 'navigate' | 'poi-select'
  isLoading: false,

  // ── Actions ────────────────────────────────────────────────────────────────
  setScene: (scene) => set({ currentScene: scene }),

  setPOIs: (pois) => set({ pois }),

  addPOI: (poi) => set((state) => ({ pois: [...state.pois, poi] })),

  selectPOI: (poi) => set({ selectedPOI: poi }),

  setPath: (path) => set({ navigationPath: path }),

  setMode: (mode) => {
    const updates = { mode }
    // Clear path when leaving navigate mode
    if (mode !== 'navigate') updates.navigationPath = null
    set(updates)
  },

  setLoading: (isLoading) => set({ isLoading }),

  clearSelection: () => set({ selectedPOI: null, navigationPath: null }),
}))

export default useStore
