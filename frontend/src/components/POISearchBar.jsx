import React, { useState, useMemo, useEffect, useRef } from 'react'
import Fuse from 'fuse.js'
import useStore from '../store/useStore'

export default function POISearchBar({ onNavigateToPOI }) {
  const [query, setQuery] = useState('')
  const [isOpen, setIsOpen] = useState(false)
  const inputRef = useRef(null)

  const {
    pois,
    selectedPOI,
    selectPOI,
    clearSelection,
    navigationPath,
    playerPosition,
    isAutoWalking,
    setIsAutoWalking,
  } = useStore()

  // Configure Fuse.js index
  const fuse = useMemo(() => {
    return new Fuse(pois, {
      keys: ['name', 'category', 'aliases'],
      threshold: 0.35,
      ignoreLocation: true,
    })
  }, [pois])

  const results = useMemo(() => {
    if (!query.trim()) return []
    return fuse.search(query).map((res) => res.item).slice(0, 6)
  }, [query, fuse])

  // Calculate distance and walking ETA
  const pathStats = useMemo(() => {
    if (!navigationPath || navigationPath.length < 2) return null
    let totalDist = 0
    for (let i = 0; i < navigationPath.length - 1; i++) {
      const p1 = navigationPath[i]
      const p2 = navigationPath[i + 1]
      const dx = p2[0] - p1[0]
      const dy = (p2[1] ?? 0) - (p1[1] ?? 0)
      const dz = (p2[2] ?? p2[1]) - (p1[2] ?? p1[1])
      totalDist += Math.sqrt(dx * dx + dy * dy + dz * dz)
    }
    const speed = 1.2 // m/s average walking speed
    const etaSec = Math.round(totalDist / speed)
    return {
      distanceM: totalDist.toFixed(1),
      etaSec,
    }
  }, [navigationPath])

  const handleSelect = (poi) => {
    selectPOI(poi)
    setQuery('')
    setIsOpen(false)
    if (onNavigateToPOI) onNavigateToPOI(poi)
  }

  const handleKeyDown = (e) => {
    if (e.key === 'Enter' && results.length > 0) {
      handleSelect(results[0])
    } else if (e.key === 'Escape') {
      setIsOpen(false)
    }
  }

  return (
    <div style={{ position: 'relative', width: 280 }}>
      {/* Search Input Box */}
      <div
        style={{
          display: 'flex',
          alignItems: 'center',
          background: 'rgba(10, 20, 35, 0.9)',
          border: '1px solid rgba(0, 229, 255, 0.4)',
          borderRadius: 8,
          padding: '6px 12px',
          boxShadow: '0 4px 16px rgba(0,0,0,0.5)',
          backdropFilter: 'blur(8px)',
        }}
      >
        <span style={{ marginRight: 8, color: '#00e5ff', fontSize: 13 }}>🔍</span>
        <input
          ref={inputRef}
          type="text"
          value={query}
          onChange={(e) => {
            setQuery(e.target.value)
            setIsOpen(true)
          }}
          onFocus={() => setIsOpen(true)}
          onKeyDown={handleKeyDown}
          placeholder="Search POIs (e.g. Sofa, Room)..."
          style={{
            background: 'transparent',
            border: 'none',
            color: '#ffffff',
            fontSize: 12,
            width: '100%',
            outline: 'none',
          }}
        />
        {query && (
          <button
            onClick={() => {
              setQuery('')
              setIsOpen(false)
            }}
            style={{
              background: 'transparent',
              border: 'none',
              color: '#888',
              cursor: 'pointer',
              fontSize: 14,
            }}
          >
            ×
          </button>
        )}
      </div>

      {/* Autocomplete Results Dropdown */}
      {isOpen && results.length > 0 && (
        <div
          style={{
            position: 'absolute',
            top: 40,
            left: 0,
            right: 0,
            background: 'rgba(12, 22, 38, 0.96)',
            border: '1px solid #1e3a5f',
            borderRadius: 8,
            overflow: 'hidden',
            boxShadow: '0 8px 24px rgba(0,0,0,0.7)',
            backdropFilter: 'blur(10px)',
            zIndex: 100,
          }}
        >
          {results.map((poi) => (
            <div
              key={poi.id}
              onClick={() => handleSelect(poi)}
              style={{
                padding: '8px 12px',
                borderBottom: '1px solid rgba(255,255,255,0.06)',
                cursor: 'pointer',
                display: 'flex',
                justifyContent: 'space-between',
                alignItems: 'center',
                transition: 'background 0.15s',
              }}
              onMouseEnter={(e) => (e.currentTarget.style.background = 'rgba(0, 229, 255, 0.15)')}
              onMouseLeave={(e) => (e.currentTarget.style.background = 'transparent')}
            >
              <div>
                <div style={{ color: '#ffffff', fontSize: 13, fontWeight: 600 }}>{poi.name}</div>
                <div style={{ color: '#88a0b5', fontSize: 10 }}>{poi.aliases?.join(', ')}</div>
              </div>
              <span
                style={{
                  background: 'rgba(0, 229, 255, 0.15)',
                  color: '#00e5ff',
                  borderRadius: 4,
                  padding: '2px 6px',
                  fontSize: 10,
                  fontWeight: 600,
                }}
              >
                {poi.category || 'POI'}
              </span>
            </div>
          ))}
        </div>
      )}

      {/* Selected POI Details & Pathfinding Card */}
      {selectedPOI && (
        <div
          style={{
            position: 'absolute',
            top: 45,
            left: 0,
            width: 320,
            background: 'rgba(10, 22, 38, 0.95)',
            border: '1px solid #00e5ff',
            borderRadius: 10,
            padding: 14,
            boxShadow: '0 8px 32px rgba(0,0,0,0.8), 0 0 16px rgba(0,229,255,0.2)',
            backdropFilter: 'blur(12px)',
            zIndex: 90,
          }}
        >
          <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'flex-start' }}>
            <div>
              <div style={{ color: '#00e5ff', fontSize: 11, fontWeight: 700, textTransform: 'uppercase' }}>
                {selectedPOI.category || 'Point of Interest'}
              </div>
              <div style={{ color: '#ffffff', fontSize: 16, fontWeight: 700, marginTop: 2 }}>
                {selectedPOI.name}
              </div>
            </div>
            <button
              onClick={clearSelection}
              style={{
                background: 'transparent',
                border: 'none',
                color: '#aaa',
                cursor: 'pointer',
                fontSize: 16,
              }}
            >
              ✕
            </button>
          </div>

          {pathStats && (
            <div
              style={{
                display: 'flex',
                gap: 16,
                margin: '12px 0',
                padding: '8px 12px',
                background: 'rgba(0, 229, 255, 0.08)',
                borderRadius: 6,
                border: '1px solid rgba(0, 229, 255, 0.2)',
              }}
            >
              <div>
                <div style={{ color: '#88a0b5', fontSize: 10 }}>WALKING DISTANCE</div>
                <div style={{ color: '#ffd700', fontSize: 14, fontWeight: 700 }}>
                  {pathStats.distanceM} m
                </div>
              </div>
              <div>
                <div style={{ color: '#88a0b5', fontSize: 10 }}>ESTIMATED TIME</div>
                <div style={{ color: '#00ffcc', fontSize: 14, fontWeight: 700 }}>
                  ~{pathStats.etaSec} s
                </div>
              </div>
            </div>
          )}

          <div style={{ display: 'flex', gap: 8, marginTop: 10 }}>
            <button
              onClick={() => onNavigateToPOI && onNavigateToPOI(selectedPOI)}
              style={{
                flex: 1,
                background: '#00e5ff',
                color: '#0a101d',
                border: 'none',
                borderRadius: 6,
                padding: '8px 12px',
                fontSize: 12,
                fontWeight: 700,
                cursor: 'pointer',
              }}
            >
              🚶 Navigate Path
            </button>
            <button
              onClick={() => setIsAutoWalking(!isAutoWalking)}
              disabled={!navigationPath}
              style={{
                flex: 1,
                background: isAutoWalking ? '#ffaa00' : 'rgba(255,255,255,0.1)',
                color: isAutoWalking ? '#0a101d' : '#ffffff',
                border: '1px solid rgba(255,255,255,0.2)',
                borderRadius: 6,
                padding: '8px 12px',
                fontSize: 12,
                fontWeight: 700,
                cursor: navigationPath ? 'pointer' : 'not-allowed',
                opacity: navigationPath ? 1 : 0.5,
              }}
            >
              {isAutoWalking ? '⏸ Pause Walk' : '▶ Auto-Walk'}
            </button>
          </div>
        </div>
      )}
    </div>
  )
}

