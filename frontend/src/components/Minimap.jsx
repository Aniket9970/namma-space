import React, { useEffect, useRef, useState, useMemo } from 'react'
import useStore from '../store/useStore'

export default function Minimap({ navgridUrl }) {
  const canvasRef = useRef(null)
  const [navgridData, setNavgridData] = useState(null)
  const { playerPosition, playerYaw, navigationPath, pois, selectPOI, minimapOpen, toggleMinimap } = useStore()

  // Fetch navgrid data
  useEffect(() => {
    if (!navgridUrl) return
    fetch(navgridUrl)
      .then((res) => (res.ok ? res.json() : null))
      .then((data) => {
        if (data && data.width && data.height) {
          setNavgridData(data)
        }
      })
      .catch((err) => console.warn('Could not load navgrid.json for minimap:', err))
  }, [navgridUrl])

  // Render 2D radar / floorplan onto HTML5 Canvas
  useEffect(() => {
    const canvas = canvasRef.current
    if (!canvas || !navgridData) return
    const ctx = canvas.getContext('2d')
    const { width, height, data, origin, resolution_m } = navgridData

    const cw = canvas.width
    const ch = canvas.height

    ctx.clearRect(0, 0, cw, ch)

    // Scaling factors from world/grid to canvas coordinates
    const scaleX = cw / width
    const scaleY = ch / height

    // Draw background grid cells
    // 0 = free (#1c2430), 1 = obstacle (#ff3b3b), 2 = unknown (#0a0e14)
    const imgData = ctx.createImageData(width, height)
    const buf = imgData.data

    for (let i = 0; i < data.length; i++) {
      const val = data[i]
      const idx = i * 4
      if (val === 1) {
        // Obstacle wall (Red / Coral)
        buf[idx] = 235
        buf[idx + 1] = 55
        buf[idx + 2] = 55
        buf[idx + 3] = 240
      } else if (val === 0) {
        // Walkable floor (Slate Blue)
        buf[idx] = 30
        buf[idx + 1] = 42
        buf[idx + 2] = 58
        buf[idx + 3] = 220
      } else {
        // Unknown / exterior (Dark Void)
        buf[idx] = 10
        buf[idx + 1] = 14
        buf[idx + 2] = 20
        buf[idx + 3] = 255
      }
    }

    // Draw offscreen buffer scaled up to canvas
    const offscreen = document.createElement('canvas')
    offscreen.width = width
    offscreen.height = height
    offscreen.getContext('2d').putImageData(imgData, 0, 0)

    ctx.drawImage(offscreen, 0, 0, cw, ch)

    // Helper: World (x, z) to canvas (px, py)
    const worldToCanvas = (wx, wz) => {
      const gx = (wx - origin[0]) / resolution_m
      const gy = (wz - origin[1]) / resolution_m
      return [gx * scaleX, gy * scaleY]
    }

    // 1. Draw Active Navigation Path
    if (navigationPath && navigationPath.length > 1) {
      ctx.beginPath()
      ctx.strokeStyle = '#ffd700'
      ctx.lineWidth = minimapOpen ? 3.5 : 2.5
      ctx.shadowColor = '#ffaa00'
      ctx.shadowBlur = 6

      for (let i = 0; i < navigationPath.length; i++) {
        const [px, py] = worldToCanvas(navigationPath[i][0], navigationPath[i][2] ?? navigationPath[i][1])
        if (i === 0) ctx.moveTo(px, py)
        else ctx.lineTo(px, py)
      }
      ctx.stroke()
      ctx.shadowBlur = 0
    }

    // 2. Draw POI Pins
    pois.forEach((poi) => {
      const [px, py] = worldToCanvas(poi.x ?? poi.position?.[0] ?? 0, poi.z ?? poi.position?.[2] ?? 0)
      ctx.beginPath()
      ctx.arc(px, py, minimapOpen ? 5 : 3.5, 0, Math.PI * 2)
      ctx.fillStyle = '#00e5ff'
      ctx.shadowColor = '#00e5ff'
      ctx.shadowBlur = 4
      ctx.fill()
      ctx.shadowBlur = 0

      if (minimapOpen) {
        ctx.fillStyle = '#ffffff'
        ctx.font = '10px sans-serif'
        ctx.fillText(poi.name, px + 7, py + 3)
      }
    })

    // 3. Draw Player Position & Yaw Heading (GTA Style Rotating Arrow)
    if (playerPosition) {
      const [px, py] = worldToCanvas(playerPosition[0], playerPosition[2])

      ctx.save()
      ctx.translate(px, py)
      // Rotate by player yaw (inverted for canvas 2D Y-down coords)
      ctx.rotate(-playerYaw)

      // Arrow body
      ctx.beginPath()
      ctx.moveTo(0, -9) // Arrow tip pointing forward
      ctx.lineTo(6, 6)
      ctx.lineTo(0, 3)
      ctx.lineTo(-6, 6)
      ctx.closePath()

      ctx.fillStyle = '#00ffcc'
      ctx.shadowColor = '#00ffcc'
      ctx.shadowBlur = 8
      ctx.fill()

      ctx.strokeStyle = '#051515'
      ctx.lineWidth = 1.2
      ctx.stroke()

      ctx.restore()
    }
  }, [navgridData, playerPosition, playerYaw, navigationPath, pois, minimapOpen])

  if (!navgridData) return null

  const isMobile = typeof window !== 'undefined' && window.innerWidth < 768
  const defaultSize = isMobile ? 110 : 180
  const openSize = isMobile ? Math.min(260, window.innerWidth - 32) : 460
  const size = minimapOpen ? openSize : defaultSize

  return (
    <div
      style={{
        position: 'absolute',
        bottom: isMobile ? 12 : 20,
        right: isMobile ? 12 : 20,
        zIndex: 30,
        display: 'flex',
        flexDirection: 'column',
        alignItems: 'flex-end',
        gap: 6,
      }}
    >
      {/* Minimap Card */}
      <div
        style={{
          width: size,
          height: size,
          borderRadius: minimapOpen ? 12 : '50%',
          overflow: 'hidden',
          border: '2px solid rgba(0, 229, 255, 0.6)',
          boxShadow: '0 8px 32px rgba(0, 0, 0, 0.75), 0 0 12px rgba(0, 229, 255, 0.3)',
          background: 'rgba(10, 15, 24, 0.92)',
          backdropFilter: 'blur(10px)',
          position: 'relative',
          transition: 'all 0.25s cubic-bezier(0.16, 1, 0.3, 1)',
        }}
      >
        <canvas
          ref={canvasRef}
          width={size}
          height={size}
          style={{ width: '100%', height: '100%', display: 'block' }}
        />

        {/* Compass Cardinal Indicator */}
        <div
          style={{
            position: 'absolute',
            top: 6,
            left: '50%',
            transform: 'translateX(-50%)',
            color: '#00e5ff',
            fontSize: 10,
            fontWeight: 800,
            textShadow: '0 0 4px #000',
            pointerEvents: 'none',
          }}
        >
          N
        </div>

        {/* Legend Overlay in Fullscreen Mode */}
        {minimapOpen && (
          <div
            style={{
              position: 'absolute',
              bottom: 8,
              left: 10,
              background: 'rgba(0,0,0,0.7)',
              padding: '4px 8px',
              borderRadius: 4,
              fontSize: 10,
              color: '#aaa',
              display: 'flex',
              gap: 12,
              pointerEvents: 'none',
            }}
          >
            <span><strong style={{ color: '#ff3b3b' }}>■</strong> Walls</span>
            <span><strong style={{ color: '#1c2430' }}>■</strong> Walkable</span>
            <span><strong style={{ color: '#ffd700' }}>─</strong> Path</span>
            <span><strong style={{ color: '#00ffcc' }}>▲</strong> You</span>
          </div>
        )}
      </div>

      {/* Toggle Button */}
      <button
        onClick={toggleMinimap}
        title={minimapOpen ? 'Collapse to corner radar' : 'Expand full floorplan'}
        style={{
          background: 'rgba(10, 20, 35, 0.85)',
          color: '#00e5ff',
          border: '1px solid rgba(0, 229, 255, 0.4)',
          borderRadius: 6,
          padding: '4px 10px',
          fontSize: 11,
          fontWeight: 600,
          cursor: 'pointer',
          backdropFilter: 'blur(6px)',
        }}
      >
        {minimapOpen ? '⤢ Radar Mode' : '⤡ Full Floorplan'}
      </button>
    </div>
  )
}

