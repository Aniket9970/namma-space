import { useState, useCallback, useRef, useEffect } from 'react'
import { searchPOIs } from '../api/index.js'
import useStore from '../store/useStore.js'
import useNavigation from '../hooks/useNavigation.js'

// ── Debounce helper ───────────────────────────────────────────────────────────
function useDebounce(fn, delay) {
  const timerRef = useRef(null)
  return useCallback(
    (...args) => {
      if (timerRef.current) clearTimeout(timerRef.current)
      timerRef.current = setTimeout(() => fn(...args), delay)
    },
    [fn, delay],
  )
}

// ── SearchBar ─────────────────────────────────────────────────────────────────
export function SearchBar({ sceneId }) {
  const [query, setQuery] = useState('')
  const [results, setResults] = useState([])
  const [open, setOpen] = useState(false)
  const { selectPOI } = useStore()
  const { navigate } = useNavigation()
  const selectedPOI = useStore((s) => s.selectedPOI)

  const doSearch = useCallback(
    async (q) => {
      if (!sceneId || !q.trim()) { setResults([]); return }
      try {
        const data = await searchPOIs(sceneId, q)
        setResults(data)
        setOpen(data.length > 0)
      } catch {
        setResults([])
      }
    },
    [sceneId],
  )

  const debouncedSearch = useDebounce(doSearch, 300)

  const handleChange = (e) => {
    setQuery(e.target.value)
    debouncedSearch(e.target.value)
  }

  const handleSelect = (poi) => {
    selectPOI(poi)
    setQuery(poi.name)
    setOpen(false)
    // If we already have a selected POI, navigate to the clicked one
    if (selectedPOI && selectedPOI.id !== poi.id) {
      navigate(selectedPOI.id, poi.id)
    }
  }

  return (
    <div style={{ position: 'relative' }}>
      <input
        value={query}
        onChange={handleChange}
        placeholder="Search POIs…"
        style={styles.searchInput}
        onFocus={() => results.length > 0 && setOpen(true)}
        onBlur={() => setTimeout(() => setOpen(false), 150)}
      />
      {open && (
        <ul style={styles.dropdown}>
          {results.map((r) => (
            <li key={r.id} onMouseDown={() => handleSelect(r)} style={styles.dropdownItem}>
              <span style={{ color: '#00bfff', fontWeight: 600 }}>{r.name}</span>
              {r.description && (
                <span style={{ color: '#888', fontSize: 11, marginLeft: 6 }}>
                  {r.description.slice(0, 40)}
                </span>
              )}
            </li>
          ))}
        </ul>
      )}
    </div>
  )
}

// ── Sidebar ───────────────────────────────────────────────────────────────────
export default function Sidebar() {
  const { currentScene, scenes, setScene, pois, selectedPOI, mode, setMode, navigationPath, clearSelection } = useStore((s) => ({
    currentScene: s.currentScene,
    scenes: s.scenes || [],
    setScene: s.setScene,
    pois: s.pois,
    selectedPOI: s.selectedPOI,
    mode: s.mode,
    setMode: s.setMode,
    navigationPath: s.navigationPath,
    clearSelection: s.clearSelection,
  }))
  const { navigate, clearPath } = useNavigation()

  return (
    <aside style={styles.sidebar}>
      {/* Header */}
      <div style={styles.header}>
        <div style={styles.logo}>🏠 Namma Space</div>
        {currentScene && (
          <div style={styles.sceneName}>
            <span>{currentScene.name}</span>
            <span style={styles.badge}>3D ROOM</span>
          </div>
        )}
      </div>

      {/* 3D Room Switcher */}
      {scenes && scenes.length > 0 && (
        <div style={styles.section}>
          <div style={styles.sectionLabel}>Select 3D Model / Room</div>
          <select
            value={currentScene?.id || ''}
            onChange={(e) => {
              const selected = scenes.find((s) => String(s.id) === e.target.value)
              if (selected) setScene(selected)
            }}
            style={{
              width: '100%',
              background: '#161f30',
              border: '1px solid #1e3a5f',
              borderRadius: 7,
              color: '#00e5ff',
              padding: '8px 10px',
              fontSize: 12,
              fontWeight: 600,
              cursor: 'pointer',
              outline: 'none',
            }}
          >
            {scenes.map((s) => (
              <option key={s.id} value={s.id}>
                🏛️ {s.name}
              </option>
            ))}
          </select>
        </div>
      )}

      {/* Mode toggle */}
      <div style={styles.modeBar}>
        {['roam', 'poi-select', 'navigate'].map((m) => (
          <button
            key={m}
            onClick={() => setMode(m)}
            style={{
              ...styles.modeBtn,
              ...(mode === m ? styles.modeBtnActive : {}),
            }}
          >
            {m === 'roam' && '🎮 Explore'}
            {m === 'poi-select' && '📍 Add POI'}
            {m === 'navigate' && '🧭 Navigate'}
          </button>
        ))}
      </div>

      {/* Search */}
      {currentScene && (
        <div style={styles.section}>
          <div style={styles.sectionLabel}>Search Points of Interest</div>
          <SearchBar sceneId={currentScene.id} />
        </div>
      )}

      {/* POI info panel */}
      {selectedPOI && (
        <div style={styles.poiCard}>
          <div style={styles.poiCardTitle}>{selectedPOI.name}</div>
          {selectedPOI.description && (
            <div style={styles.poiDesc}>{selectedPOI.description}</div>
          )}
          <div style={styles.poiCoords}>
            x: {selectedPOI.x.toFixed(2)} &nbsp; y: {selectedPOI.y.toFixed(2)} &nbsp; z: {selectedPOI.z.toFixed(2)}
          </div>
          <button onClick={clearSelection} style={styles.clearBtn}>✕ Clear</button>
        </div>
      )}

      {/* POI list */}
      <div style={styles.section}>
        <div style={styles.sectionLabel}>All POIs ({pois.length})</div>
        <ul style={styles.poiList}>
          {pois.map((poi) => (
            <li
              key={poi.id}
              style={{
                ...styles.poiListItem,
                ...(selectedPOI?.id === poi.id ? styles.poiListItemActive : {}),
              }}
              onClick={() => useStore.getState().selectPOI(poi)}
            >
              <span style={{ color: '#00bfff' }}>📍</span> {poi.name}
            </li>
          ))}
          {pois.length === 0 && (
            <li style={{ color: '#555', fontSize: 12, padding: '8px 0' }}>
              No POIs yet. Switch to "Add POI" mode and double-click in the scene.
            </li>
          )}
        </ul>
      </div>

      {/* Path info */}
      {navigationPath && (
        <div style={styles.pathInfo}>
          <span>Path: {navigationPath.length} waypoints</span>
          <button onClick={clearPath} style={styles.clearBtn}>Clear Path</button>
        </div>
      )}

      {/* Controls help */}
      <div style={styles.helpBox}>
        <div style={styles.sectionLabel}>Controls</div>
        <div style={styles.helpLine}><kbd style={styles.kbd}>W A S D</kbd> Move</div>
        <div style={styles.helpLine}><kbd style={styles.kbd}>Shift</kbd> Sprint</div>
        <div style={styles.helpLine}><kbd style={styles.kbd}>Mouse</kbd> Look around</div>
        <div style={styles.helpLine}><kbd style={styles.kbd}>Click</kbd> Lock pointer</div>
        <div style={styles.helpLine}><kbd style={styles.kbd}>Dbl-click</kbd> Place POI</div>
      </div>
    </aside>
  )
}

// ── Styles ────────────────────────────────────────────────────────────────────
const styles = {
  sidebar: {
    width: 280,
    minWidth: 280,
    height: '100vh',
    background: 'linear-gradient(180deg, #0d1117 0%, #111827 100%)',
    borderRight: '1px solid #1e3a5f',
    display: 'flex',
    flexDirection: 'column',
    overflowY: 'auto',
    padding: '0 0 16px',
    gap: 0,
    zIndex: 10,
  },
  header: {
    padding: '16px 16px 12px',
    borderBottom: '1px solid #1e3a5f',
  },
  logo: {
    fontSize: 18,
    fontWeight: 700,
    color: '#00bfff',
    letterSpacing: 0.5,
    marginBottom: 6,
  },
  sceneName: {
    display: 'flex',
    alignItems: 'center',
    gap: 8,
    fontSize: 13,
    color: '#ccc',
  },
  badge: {
    background: '#1e3a5f',
    color: '#00bfff',
    fontSize: 10,
    padding: '2px 6px',
    borderRadius: 4,
    fontWeight: 700,
    letterSpacing: 1,
  },
  modeBar: {
    display: 'flex',
    gap: 4,
    padding: '10px 12px',
    borderBottom: '1px solid #1e3a5f',
  },
  modeBtn: {
    flex: 1,
    padding: '6px 4px',
    background: '#1a2233',
    border: '1px solid #2a3a5a',
    borderRadius: 6,
    color: '#888',
    fontSize: 11,
    cursor: 'pointer',
    transition: 'all 0.15s',
    fontWeight: 500,
  },
  modeBtnActive: {
    background: '#0d3060',
    border: '1px solid #00bfff',
    color: '#00bfff',
  },
  section: {
    padding: '12px 16px',
    borderBottom: '1px solid #1a2a3a',
  },
  sectionLabel: {
    fontSize: 10,
    fontWeight: 700,
    letterSpacing: 1.5,
    color: '#4a6a8a',
    textTransform: 'uppercase',
    marginBottom: 8,
  },
  searchInput: {
    width: '100%',
    background: '#1a2233',
    border: '1px solid #2a3a5a',
    borderRadius: 6,
    color: '#e0e0e0',
    padding: '8px 10px',
    fontSize: 13,
    outline: 'none',
    boxSizing: 'border-box',
  },
  dropdown: {
    position: 'absolute',
    top: '100%',
    left: 0,
    right: 0,
    background: '#111827',
    border: '1px solid #2a3a5a',
    borderRadius: 6,
    listStyle: 'none',
    zIndex: 100,
    maxHeight: 180,
    overflowY: 'auto',
    boxShadow: '0 8px 24px rgba(0,0,0,0.5)',
  },
  dropdownItem: {
    padding: '8px 12px',
    cursor: 'pointer',
    fontSize: 13,
    borderBottom: '1px solid #1a2233',
    display: 'flex',
    alignItems: 'baseline',
    gap: 6,
  },
  poiCard: {
    margin: '0 12px 4px',
    padding: '12px',
    background: '#0d1e36',
    border: '1px solid #1e4080',
    borderRadius: 8,
  },
  poiCardTitle: {
    fontSize: 15,
    fontWeight: 700,
    color: '#00bfff',
    marginBottom: 6,
  },
  poiDesc: {
    fontSize: 12,
    color: '#aaa',
    marginBottom: 6,
    lineHeight: 1.5,
  },
  poiCoords: {
    fontSize: 11,
    color: '#556',
    fontFamily: 'monospace',
    marginBottom: 8,
  },
  clearBtn: {
    background: 'transparent',
    border: '1px solid #2a3a5a',
    borderRadius: 4,
    color: '#888',
    fontSize: 11,
    padding: '3px 8px',
    cursor: 'pointer',
  },
  poiList: {
    listStyle: 'none',
    maxHeight: 160,
    overflowY: 'auto',
    display: 'flex',
    flexDirection: 'column',
    gap: 2,
  },
  poiListItem: {
    padding: '6px 8px',
    borderRadius: 5,
    fontSize: 12,
    cursor: 'pointer',
    color: '#bbb',
    display: 'flex',
    alignItems: 'center',
    gap: 6,
    transition: 'background 0.1s',
  },
  poiListItemActive: {
    background: '#0d3060',
    color: '#00bfff',
  },
  pathInfo: {
    display: 'flex',
    alignItems: 'center',
    justifyContent: 'space-between',
    padding: '8px 16px',
    background: '#0a2040',
    borderTop: '1px solid #1e3a5f',
    borderBottom: '1px solid #1e3a5f',
    fontSize: 12,
    color: '#ffdd00',
  },
  helpBox: {
    padding: '12px 16px',
    marginTop: 'auto',
    borderTop: '1px solid #1a2a3a',
  },
  helpLine: {
    fontSize: 12,
    color: '#666',
    marginBottom: 4,
    display: 'flex',
    alignItems: 'center',
    gap: 8,
  },
  kbd: {
    background: '#1a2233',
    border: '1px solid #2a3a5a',
    borderRadius: 4,
    padding: '1px 5px',
    fontSize: 10,
    color: '#aaa',
    fontFamily: 'monospace',
  },
}
