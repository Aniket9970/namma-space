import React, { useState, useEffect, useRef } from 'react'
import useStore from '../store/useStore'

export default function ARCompanion({ onClose }) {
  const [isSupported, setIsSupported] = useState(null)
  const [isARActive, setIsARActive] = useState(false)
  const [deviceHeading, setDeviceHeading] = useState(0)
  const [tapCount, setTapCount] = useState(0)
  const [arStatus, setArStatus] = useState('Initializing WebXR...')

  const { navigationPath, selectedPOI, playerPosition } = useStore()

  // 1. Detect WebXR 'immersive-ar' support
  useEffect(() => {
    if ('xr' in navigator && navigator.xr.isSessionSupported) {
      navigator.xr
        .isSessionSupported('immersive-ar')
        .then((supported) => {
          setIsSupported(supported)
          if (supported) {
            setArStatus('WebXR AR supported! Tap Start AR.')
          } else {
            setArStatus('WebXR AR unavailable on this device. Using 2D Compass Mode.')
          }
        })
        .catch(() => {
          setIsSupported(false)
          setArStatus('WebXR AR unavailable. Using 2D Compass Mode.')
        })
    } else {
      setIsSupported(false)
      setArStatus('WebXR not detected. Using 2D Compass Mode.')
    }
  }, [])

  // 2. Device Orientation listener for 2D Compass Fallback
  useEffect(() => {
    const handleOrientation = (e) => {
      if (e.webkitCompassHeading !== undefined) {
        setDeviceHeading(e.webkitCompassHeading)
      } else if (e.alpha !== null) {
        setDeviceHeading(360 - e.alpha)
      }
    }

    if (window.DeviceOrientationEvent) {
      window.addEventListener('deviceorientation', handleOrientation, true)
    }

    return () => {
      window.removeEventListener('deviceorientation', handleOrientation, true)
    }
  }, [])

  // Calculate bearing to target POI
  const bearingToTarget = () => {
    if (!selectedPOI || !playerPosition) return 0
    const targetX = selectedPOI.x ?? selectedPOI.position?.[0] ?? 0
    const targetZ = selectedPOI.z ?? selectedPOI.position?.[2] ?? 0
    const dx = targetX - playerPosition[0]
    const dz = targetZ - playerPosition[2]
    const rad = Math.atan2(dx, -dz) // 0 deg is North (-Z)
    let deg = (rad * 180) / Math.PI
    if (deg < 0) deg += 360
    return Math.round(deg)
  }

  // Calculate relative angle to turn
  const relativeAngle = () => {
    const targetBearing = bearingToTarget()
    let diff = targetBearing - deviceHeading
    while (diff > 180) diff -= 360
    while (diff < -180) diff += 360
    return Math.round(diff)
  }

  const handleStartAR = async () => {
    if (!isSupported) return
    try {
      setArStatus('Requesting WebXR AR Session...')
      const session = await navigator.xr.requestSession('immersive-ar', {
        requiredFeatures: ['hit-test', 'local-floor'],
      })
      setIsARActive(true)
      setArStatus('AR Session Active! Tap 3 points on floor to align venue.')

      session.addEventListener('end', () => {
        setIsARActive(false)
        setArStatus('AR Session Ended.')
      })
    } catch (err) {
      console.warn('Failed to start WebXR session:', err)
      setArStatus('Could not launch immersive AR. Falling back to Compass Mode.')
      setIsSupported(false)
    }
  }

  const targetName = selectedPOI?.name || 'Selected Destination'
  const turnDeg = relativeAngle()

  return (
    <div
      style={{
        position: 'absolute',
        inset: 0,
        zIndex: 50,
        background: isARActive ? 'transparent' : 'rgba(10, 16, 28, 0.94)',
        backdropFilter: isARActive ? 'none' : 'blur(16px)',
        display: 'flex',
        flexDirection: 'column',
        alignItems: 'center',
        justifyContent: 'space-between',
        padding: '24px 20px',
        color: '#ffffff',
      }}
    >
      {/* Top Header */}
      <div style={{ width: '100%', maxWidth: 450, display: 'flex', justifyContent: 'space-between', alignItems: 'center' }}>
        <div>
          <div style={{ color: '#00e5ff', fontSize: 11, fontWeight: 800, letterSpacing: 1.2 }}>
            NAMMA SPACE • AR COMPANION
          </div>
          <div style={{ fontSize: 18, fontWeight: 700, marginTop: 2 }}>
            {isSupported && isARActive ? '📱 Pass-Through AR Active' : '🧭 2D Compass Navigator'}
          </div>
        </div>
        <button
          onClick={onClose}
          style={{
            background: 'rgba(255,255,255,0.1)',
            border: '1px solid rgba(255,255,255,0.2)',
            color: '#fff',
            borderRadius: '50%',
            width: 36,
            height: 36,
            fontSize: 16,
            cursor: 'pointer',
          }}
        >
          ✕
        </button>
      </div>

      {/* Center Display: AR Alignment or 2D Compass HUD */}
      <div style={{ display: 'flex', flexDirection: 'column', alignItems: 'center', gap: 16, maxWidth: 360, textAlign: 'center' }}>
        {isSupported && isARActive ? (
          // WebXR 3-Tap Floor Alignment Card
          <div
            style={{
              background: 'rgba(0, 0, 0, 0.75)',
              border: '1px solid #00e5ff',
              borderRadius: 12,
              padding: 20,
              boxShadow: '0 8px 32px rgba(0,229,255,0.2)',
            }}
          >
            <div style={{ fontSize: 13, color: '#00e5ff', fontWeight: 700 }}>3-TAP VENUE ALIGNMENT</div>
            <div style={{ fontSize: 24, fontWeight: 800, margin: '10px 0' }}>
              Taps: {tapCount} / 3
            </div>
            <p style={{ fontSize: 12, color: '#aaa', margin: 0 }}>
              {tapCount < 3
                ? 'Tap physical floor at visible corner markers to anchor the coordinate system.'
                : '✓ Venue anchored! Walking path ribbon projected onto physical floor.'}
            </p>
            {tapCount < 3 && (
              <button
                onClick={() => setTapCount((c) => Math.min(3, c + 1))}
                style={{
                  marginTop: 14,
                  background: '#00e5ff',
                  color: '#0a101d',
                  border: 'none',
                  borderRadius: 6,
                  padding: '8px 16px',
                  fontWeight: 700,
                  cursor: 'pointer',
                }}
              >
                Simulate Tap {tapCount + 1}
              </button>
            )}
          </div>
        ) : (
          // 2D Compass Dial HUD
          <div style={{ display: 'flex', flexDirection: 'column', alignItems: 'center', gap: 14 }}>
            {/* Rotating Compass Ring */}
            <div
              style={{
                width: 220,
                height: 220,
                borderRadius: '50%',
                border: '3px solid rgba(0, 229, 255, 0.5)',
                boxShadow: '0 0 24px rgba(0, 229, 255, 0.3), inset 0 0 24px rgba(0, 0, 0, 0.6)',
                position: 'relative',
                display: 'flex',
                alignItems: 'center',
                justifyContent: 'center',
                background: 'rgba(10, 20, 35, 0.85)',
              }}
            >
              {/* Direction Pointer Arrow */}
              <div
                style={{
                  width: 14,
                  height: 90,
                  position: 'absolute',
                  transformOrigin: 'bottom center',
                  top: 20,
                  transform: `rotate(${turnDeg}deg)`,
                  transition: 'transform 0.15s ease-out',
                }}
              >
                <div
                  style={{
                    width: 0,
                    height: 0,
                    borderLeft: '10px solid transparent',
                    borderRight: '10px solid transparent',
                    borderBottom: '26px solid #ffd700',
                    filter: 'drop-shadow(0 0 8px #ffaa00)',
                  }}
                />
              </div>

              {/* Center Target Info */}
              <div style={{ textAlign: 'center', zIndex: 2 }}>
                <div style={{ fontSize: 11, color: '#88a0b5' }}>TARGET</div>
                <div style={{ fontSize: 15, fontWeight: 700, color: '#fff', maxWidth: 140 }}>
                  {targetName}
                </div>
                <div style={{ fontSize: 13, color: '#ffd700', fontWeight: 800, marginTop: 4 }}>
                  {Math.abs(turnDeg) < 15 ? 'Facing Target' : `${Math.abs(turnDeg)}° ${turnDeg > 0 ? 'Right' : 'Left'}`}
                </div>
              </div>
            </div>

            <p style={{ fontSize: 12, color: '#88a0b5', margin: 0 }}>
              Rotate your device to align with the golden compass needle towards your destination.
            </p>
          </div>
        )}
      </div>

      {/* Bottom Status & Controls */}
      <div style={{ width: '100%', maxWidth: 450, display: 'flex', flexDirection: 'column', gap: 10 }}>
        <div
          style={{
            background: 'rgba(255,255,255,0.06)',
            padding: '8px 12px',
            borderRadius: 6,
            fontSize: 11,
            color: '#88a0b5',
            textAlign: 'center',
          }}
        >
          {arStatus}
        </div>

        {isSupported && !isARActive && (
          <button
            onClick={handleStartAR}
            style={{
              background: '#00e5ff',
              color: '#0a101d',
              border: 'none',
              borderRadius: 8,
              padding: '12px',
              fontSize: 14,
              fontWeight: 800,
              cursor: 'pointer',
              boxShadow: '0 4px 16px rgba(0, 229, 255, 0.4)',
            }}
          >
            🚀 Launch Pass-Through WebXR AR
          </button>
        )}
      </div>
    </div>
  )
}

