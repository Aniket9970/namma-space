import { useState, useEffect, useCallback } from 'react'
import Viewer3D from './components/Viewer3D.jsx'
import Sidebar from './components/Sidebar.jsx'
import POIForm from './components/POIForm.jsx'
import useStore from './store/useStore.js'
import usePOIs from './hooks/usePOIs.js'
import { getScenes, createScene } from './api/index.js'
import { DEFAULT_SCENES } from './api/scenesData.js'

export default function App() {
  const { currentScene, mode, setScene, setScenes: setStoreScenes, isLoading } = useStore()
  const { fetchPOIs, submitPOI } = usePOIs()

  // POI placement state
  const [pendingPosition, setPendingPosition] = useState(null)

  // Mobile viewport detection
  const [isMobile, setIsMobile] = useState(() => {
    if (typeof window === 'undefined') return false
    return window.innerWidth < 768 || /Android|iPhone|iPad|iPod|Mobile/i.test(navigator.userAgent)
  })
  const [sidebarOpen, setSidebarOpen] = useState(false)

  useEffect(() => {
    const handleResize = () => {
      const mobile = window.innerWidth < 768 || /Android|iPhone|iPad|iPod|Mobile/i.test(navigator.userAgent)
      setIsMobile(mobile)
    }
    window.addEventListener('resize', handleResize)
    return () => window.removeEventListener('resize', handleResize)
  }, [])

  // Scene picker state (pre-populate with default scenes so UI is instant)
  const [scenes, setScenes] = useState(DEFAULT_SCENES)
  const [showScenePicker, setShowScenePicker] = useState(false)
  const [newSceneName, setNewSceneName] = useState('')
  const [creating, setCreating] = useState(false)

  // Load live scenes on mount
  useEffect(() => {
    getScenes()
      .then((data) => {
        if (data && data.length > 0) {
          setScenes(data)
          setStoreScenes(data)
        }
      })
      .catch((e) => console.error('Failed to load scenes:', e))
  }, [setStoreScenes])

  // Load POIs when scene changes
  useEffect(() => {
    if (currentScene) fetchPOIs()
  }, [currentScene, fetchPOIs])

  // Auto-select Ex4 scene if available and none selected
  useEffect(() => {
    if (!currentScene && scenes.length > 0) {
      const defaultScene = scenes.find((s) => s.name?.includes('Ex4')) || scenes[0]
      setScene(defaultScene)
    }
    if (scenes.length === 0 && !currentScene) {
      setShowScenePicker(true)
    }
  }, [scenes, currentScene, setScene])

  // Handle POI placement from 3D viewer
  const handlePOIPlace = useCallback((position) => {
    if (mode !== 'poi-select') return
    setPendingPosition(position)
  }, [mode])

  const handlePOISubmit = useCallback(async (data) => {
    await submitPOI(data)
    setPendingPosition(null)
  }, [submitPOI])

  const handleCreateScene = async (e) => {
    e.preventDefault()
    if (!newSceneName.trim()) return
    setCreating(true)
    try {
      const scene = await createScene(newSceneName.trim())
      setScenes((prev) => [scene, ...prev])
      setScene(scene)
      setShowScenePicker(false)
      setNewSceneName('')
    } catch (err) {
      console.error('Failed to create scene:', err)
    } finally {
      setCreating(false)
    }
  }

  return (
    <div style={styles.root}>
      {/* Desktop Sidebar */}
      {!isMobile && (
        <div style={{ width: 280, minWidth: 280, height: '100%' }}>
          <Sidebar />
        </div>
      )}

      {/* Mobile Sidebar Drawer Modal */}
      {isMobile && sidebarOpen && (
        <div style={styles.mobileDrawerOverlay} onClick={() => setSidebarOpen(false)}>
          <div style={styles.mobileDrawerPanel} onClick={(e) => e.stopPropagation()}>
            <Sidebar onClose={() => setSidebarOpen(false)} />
          </div>
        </div>
      )}

      {/* 3D Viewer */}
      <div style={styles.canvasWrapper}>
        <Viewer3D onPOIPlace={handlePOIPlace} isMobile={isMobile} />

        {/* Top bar */}
        <div style={{
          ...styles.topBar,
          top: isMobile ? 8 : 12,
          right: isMobile ? 8 : 12,
          gap: isMobile ? 4 : 8,
          maxWidth: isMobile ? 'calc(100vw - 150px)' : 'calc(100vw - 24px)',
        }}>
          {isMobile && (
            <button
              onClick={() => setSidebarOpen(true)}
              style={{
                ...styles.mobileMenuBtn,
                padding: '5px 8px',
                fontSize: 11,
              }}
            >
              ☰ POIs
            </button>
          )}

          <button
            onClick={() => setShowScenePicker(true)}
            style={{
              ...styles.topBarBtn,
              padding: isMobile ? '5px 8px' : '7px 14px',
              fontSize: isMobile ? 11 : 13,
            }}
          >
            🗂 {currentScene ? currentScene.name : 'Select Scene'}
          </button>
          {mode === 'poi-select' && (
            <div style={{ ...styles.modeBadge, padding: isMobile ? '5px 8px' : '7px 14px', fontSize: isMobile ? 10 : 12 }}>
              {isMobile ? '📍 Tap POI' : '📍 Double-click to place POI'}
            </div>
          )}
          {mode === 'navigate' && (
            <div style={{ ...styles.modeBadge, background: '#1a3010', borderColor: '#4caf50', padding: isMobile ? '5px 8px' : '7px 14px', fontSize: isMobile ? 10 : 12 }}>
              🧭 Nav
            </div>
          )}
          {isLoading && <div style={{ ...styles.loadingBadge, padding: isMobile ? '5px 8px' : '7px 14px', fontSize: isMobile ? 10 : 12 }}>⏳ Loading…</div>}
        </div>
      </div>

      {/* POI Form modal */}
      {pendingPosition && (
        <POIForm
          position={pendingPosition}
          onSubmit={handlePOISubmit}
          onCancel={() => setPendingPosition(null)}
        />
      )}

      {/* Scene Picker modal */}
      {showScenePicker && (
        <div style={styles.overlay} onClick={() => setShowScenePicker(false)}>
          <div style={styles.modal} onClick={(e) => e.stopPropagation()}>
            <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center' }}>
              <h3 style={styles.modalTitle}>🏠 Namma Space</h3>
              <button
                onClick={() => setShowScenePicker(false)}
                style={{ background: 'none', border: 'none', color: '#888', fontSize: 18, cursor: 'pointer', padding: 4 }}
              >
                ✕
              </button>
            </div>
            <p style={styles.modalSub}>Select or create a scene</p>

            {scenes.length > 0 && (
              <ul style={styles.sceneList}>
                {scenes.map((s) => {
                  const isActive = currentScene?.id === s.id
                  return (
                    <li
                      key={s.id}
                      style={{
                        ...styles.sceneItem,
                        border: isActive ? '1px solid #00bfff' : '1px solid transparent',
                        background: isActive ? '#142c44' : '#1a2233',
                      }}
                      onClick={() => { setScene(s); setShowScenePicker(false) }}
                    >
                      <span style={{ fontWeight: isActive ? 700 : 500, color: isActive ? '#00bfff' : '#e0e0e0' }}>
                        {isActive ? '✓ ' : ''}{s.name}
                      </span>
                      <span style={styles.sceneDate}>
                        {new Date(s.created_at).toLocaleDateString()}
                      </span>
                    </li>
                  )
                })}
              </ul>
            )}

            <div style={styles.divider}>— or create new —</div>

            <form onSubmit={handleCreateScene} style={styles.form}>
              <input
                value={newSceneName}
                onChange={(e) => setNewSceneName(e.target.value)}
                placeholder="Scene name…"
                style={styles.input}
                autoFocus
                required
              />
              <button
                type="submit"
                style={styles.createBtn}
                disabled={creating || !newSceneName.trim()}
              >
                {creating ? 'Creating…' : 'Create Scene'}
              </button>
            </form>
          </div>
        </div>
      )}
    </div>
  )
}

// ── Styles ────────────────────────────────────────────────────────────────────
const styles = {
  root: {
    display: 'flex',
    width: '100%',
    height: '100dvh',
    overflow: 'hidden',
    background: '#0a0a1a',
    position: 'relative',
  },
  canvasWrapper: {
    flex: 1,
    width: '100%',
    height: '100%',
    position: 'relative',
    overflow: 'hidden',
  },
  mobileDrawerOverlay: {
    position: 'fixed',
    inset: 0,
    background: 'rgba(0, 0, 0, 0.72)',
    backdropFilter: 'blur(8px)',
    zIndex: 999,
    display: 'flex',
    justifyContent: 'flex-start',
  },
  mobileDrawerPanel: {
    width: 'min(320px, 86vw)',
    height: '100%',
    background: '#0d1117',
    borderRight: '1px solid #1e3a5f',
    boxShadow: '4px 0 24px rgba(0,0,0,0.8)',
    display: 'flex',
    flexDirection: 'column',
    overflowY: 'auto',
  },
  mobileMenuBtn: {
    background: 'rgba(0, 229, 255, 0.15)',
    border: '1px solid #00e5ff',
    borderRadius: 7,
    color: '#00e5ff',
    padding: '7px 12px',
    fontSize: 12,
    fontWeight: 700,
    cursor: 'pointer',
    backdropFilter: 'blur(8px)',
  },
  topBar: {
    position: 'absolute',
    top: 12,
    right: 12,
    display: 'flex',
    gap: 8,
    alignItems: 'center',
    zIndex: 10,
    maxWidth: 'calc(100vw - 24px)',
    flexWrap: 'wrap',
    justifyContent: 'flex-end',
  },
  topBarBtn: {
    background: 'rgba(13,17,23,0.85)',
    border: '1px solid #1e3a5f',
    borderRadius: 7,
    color: '#00bfff',
    padding: '7px 14px',
    fontSize: 13,
    cursor: 'pointer',
    backdropFilter: 'blur(8px)',
    fontWeight: 600,
  },
  modeBadge: {
    background: 'rgba(13,30,50,0.9)',
    border: '1px solid #1e4080',
    borderRadius: 7,
    color: '#ffdd00',
    padding: '7px 14px',
    fontSize: 12,
    backdropFilter: 'blur(8px)',
  },
  loadingBadge: {
    background: 'rgba(13,17,23,0.85)',
    border: '1px solid #333',
    borderRadius: 7,
    color: '#aaa',
    padding: '7px 14px',
    fontSize: 12,
  },
  overlay: {
    position: 'fixed',
    inset: 0,
    background: 'rgba(0,0,0,0.8)',
    display: 'flex',
    alignItems: 'center',
    justifyContent: 'center',
    zIndex: 2000,
    backdropFilter: 'blur(6px)',
  },
  modal: {
    background: '#111827',
    border: '1px solid #1e4080',
    borderRadius: 14,
    padding: '28px 32px',
    minWidth: 360,
    maxWidth: 460,
    width: '90vw',
    boxShadow: '0 24px 80px rgba(0,0,0,0.8)',
  },
  modalTitle: {
    color: '#00bfff',
    fontSize: 22,
    fontWeight: 800,
    marginBottom: 4,
  },
  modalSub: {
    color: '#666',
    fontSize: 13,
    marginBottom: 18,
  },
  sceneList: {
    listStyle: 'none',
    maxHeight: 200,
    overflowY: 'auto',
    marginBottom: 16,
    display: 'flex',
    flexDirection: 'column',
    gap: 4,
  },
  sceneItem: {
    display: 'flex',
    justifyContent: 'space-between',
    alignItems: 'center',
    padding: '10px 14px',
    background: '#1a2233',
    borderRadius: 7,
    cursor: 'pointer',
    fontSize: 14,
    color: '#e0e0e0',
    border: '1px solid #2a3a5a',
    transition: 'border-color 0.15s',
  },
  sceneDate: {
    fontSize: 11,
    color: '#556',
  },
  divider: {
    textAlign: 'center',
    color: '#334',
    fontSize: 12,
    margin: '14px 0',
  },
  form: {
    display: 'flex',
    gap: 8,
  },
  input: {
    flex: 1,
    background: '#1a2233',
    border: '1px solid #2a3a5a',
    borderRadius: 7,
    color: '#e0e0e0',
    padding: '10px 12px',
    fontSize: 14,
    outline: 'none',
  },
  createBtn: {
    background: '#0d3060',
    border: '1px solid #00bfff',
    borderRadius: 7,
    color: '#00bfff',
    padding: '10px 18px',
    fontSize: 13,
    fontWeight: 700,
    cursor: 'pointer',
  },
}
