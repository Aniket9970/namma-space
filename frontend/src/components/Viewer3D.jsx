import React, { useEffect, useRef, useState, useCallback, Suspense, useMemo } from 'react'
import { Canvas, useThree, useFrame } from '@react-three/fiber'
import { Text, Line, Grid, OrbitControls } from '@react-three/drei'
import * as THREE from 'three'
import GaussianSplat from './GaussianSplat'

import useStore from '../store/useStore'
import usePOIs from '../hooks/usePOIs'
import Minimap from './Minimap'
import POISearchBar from './POISearchBar'
import { DEFAULT_SCENES } from '../api/scenesData.js'

function SceneDebugger() {
  const { scene, gl, camera } = useThree()
  useEffect(() => {
    window.__DEBUG_SCENE__ = scene
    window.__DEBUG_GL__ = gl
    window.__DEBUG_CAMERA__ = camera
    console.log('[SceneDebugger] Mounted!', {
      children: scene.children.map((c) => ({
        type: c.type,
        name: c.name,
        pos: [c.position.x, c.position.y, c.position.z],
        instanceCount: c.geometry?.instanceCount,
      })),
      camera: [camera.position.x, camera.position.y, camera.position.z],
    })
  }, [scene, gl, camera])
  useFrame(() => {
    window.__FRAME_COUNT__ = (window.__FRAME_COUNT__ || 0) + 1
  })
  return null
}

// ── WebGL Error Boundary ──────────────────────────────────────────────────────
class CanvasErrorBoundary extends React.Component {
  constructor(props) {
    super(props)
    this.state = { hasError: false, error: null }
  }
  static getDerivedStateFromError(error) {
    return { hasError: true, error }
  }
  componentDidCatch(error, errorInfo) {
    console.error('[CanvasErrorBoundary]', error, errorInfo)
  }
  render() {
    if (this.state.hasError) {
      return (
        <div
          style={{
            display: 'flex',
            flexDirection: 'column',
            alignItems: 'center',
            justifyContent: 'center',
            width: '100%',
            height: '100%',
            background: '#0a0e14',
            color: '#fff',
            padding: 24,
            textAlign: 'center',
          }}
        >
          <div style={{ fontSize: 36, marginBottom: 12 }}>⚠️</div>
          <h3 style={{ color: '#00e5ff', marginBottom: 8 }}>3D Acceleration Needed</h3>
          <p style={{ maxWidth: 460, color: '#94a3b8', fontSize: 13, lineHeight: 1.6 }}>
            {this.state.error?.message?.includes('WebGL')
              ? 'Could not create WebGL context. Please enable Hardware Acceleration in your browser settings (Chrome Settings > System > Use graphics acceleration).'
              : `Unable to render 3D space: ${this.state.error?.message || 'Unknown error'}`}
          </p>
          <button
            onClick={() => window.location.reload()}
            style={{
              marginTop: 16,
              background: '#00e5ff',
              color: '#0a101d',
              border: 'none',
              borderRadius: 6,
              padding: '8px 16px',
              fontWeight: 700,
              cursor: 'pointer',
            }}
          >
            ↻ Reload Page
          </button>
        </div>
      )
    }
    return this.props.children
  }
}

// ── Movement & Sensitivity Constants ──────────────────────────────────────────
const WALK_SPEED = 2.5
const SPRINT_SPEED = 5.5
const VERTICAL_SPEED = 2.0
const LOOK_SENSITIVITY = 0.0022
const MAX_PITCH_RAD = (85 * Math.PI) / 180

// ── POIMarkers ────────────────────────────────────────────────────────────────
function POIMarkers({ pois, onSelect }) {
  const selectedPOI = useStore((s) => s.selectedPOI)

  return (
    <group>
      {pois.map((poi) => {
        const isSelected = selectedPOI?.id === poi.id
        const px = poi.x ?? poi.position?.[0] ?? 0
        const py = poi.y ?? poi.position?.[1] ?? 0
        const pz = poi.z ?? poi.position?.[2] ?? 0

        return (
          <group key={poi.id} position={[px, py + 0.8, pz]}>
            {/* Floating marker sphere */}
            <mesh
              onClick={(e) => {
                e.stopPropagation()
                onSelect(poi)
              }}
              onPointerOver={(e) => {
                e.stopPropagation()
                document.body.style.cursor = 'pointer'
              }}
              onPointerOut={() => {
                document.body.style.cursor = 'auto'
              }}
            >
              <sphereGeometry args={[0.15, 16, 16]} />
              <meshStandardMaterial
                color={isSelected ? '#ff9900' : '#00e5ff'}
                emissive={isSelected ? '#ff6600' : '#0088cc'}
                emissiveIntensity={0.9}
              />
            </mesh>

            {/* Glowing ring */}
            <mesh rotation={[-Math.PI / 2, 0, 0]} position={[0, -0.6, 0]}>
              <ringGeometry args={[0.2, 0.28, 32]} />
              <meshBasicMaterial color={isSelected ? '#ff9900' : '#00e5ff'} side={THREE.DoubleSide} />
            </mesh>

            {/* Text label */}
            <Text
              position={[0, 0.35, 0]}
              fontSize={0.22}
              color={isSelected ? '#ffcc00' : '#ffffff'}
              anchorX="center"
              anchorY="bottom"
              outlineWidth={0.015}
              outlineColor="#000000"
            >
              {poi.name}
            </Text>
          </group>
        )
      })}
    </group>
  )
}

// ── NavigationPath Ribbon ─────────────────────────────────────────────────────
function NavigationPath({ path }) {
  if (!path || path.length < 2) return null

  const points = path.map(([x, y, z]) => new THREE.Vector3(x, (y ?? 0) + 0.05, z ?? y))
  const curve = new THREE.CatmullRomCurve3(points)
  const smoothPoints = curve.getPoints(Math.max(50, points.length * 5))

  return (
    <group>
      {/* Primary gold path line */}
      <Line
        points={smoothPoints}
        color="#ffdd00"
        lineWidth={5}
        dashed={false}
        transparent
        opacity={0.95}
      />
      {/* Wide orange glow ribbon */}
      <Line
        points={smoothPoints}
        color="#ff8800"
        lineWidth={14}
        transparent
        opacity={0.35}
      />
      {/* Start anchor marker */}
      <mesh position={points[0]}>
        <sphereGeometry args={[0.12, 16, 16]} />
        <meshStandardMaterial color="#00ff88" emissive="#00cc44" emissiveIntensity={1} />
      </mesh>
      {/* Goal anchor marker */}
      <mesh position={points[points.length - 1]}>
        <sphereGeometry args={[0.14, 16, 16]} />
        <meshStandardMaterial color="#ff3333" emissive="#cc0000" emissiveIntensity={1} />
      </mesh>
    </group>
  )
}

// ── FloorGrid ─────────────────────────────────────────────────────────────────
function FloorGrid() {
  return (
    <Grid
      position={[0, -0.01, 0]}
      args={[40, 40]}
      cellSize={1}
      cellThickness={0.5}
      cellColor="#1a2a3a"
      sectionSize={5}
      sectionThickness={1}
      sectionColor="#2a3a4a"
      fadeDistance={30}
      fadeStrength={1}
      followCamera={false}
      infiniteGrid={false}
    />
  )
}

// ── Double-Click POI Placement Raycaster ──────────────────────────────────────
function POIPlacementHandler({ onPlace }) {
  const { camera, scene: threeScene, gl } = useThree()
  const raycaster = useRef(new THREE.Raycaster())

  useEffect(() => {
    const canvas = gl.domElement

    const onDblClick = (e) => {
      const rect = canvas.getBoundingClientRect()
      const ndc = new THREE.Vector2(
        ((e.clientX - rect.left) / rect.width) * 2 - 1,
        -((e.clientY - rect.top) / rect.height) * 2 + 1
      )
      raycaster.current.setFromCamera(ndc, camera)
      const intersects = raycaster.current.intersectObjects(threeScene.children, true)
      if (intersects.length > 0) {
        const pt = intersects[0].point
        onPlace({ x: pt.x, y: pt.y, z: pt.z })
      }
    }

    canvas.addEventListener('dblclick', onDblClick)
    return () => canvas.removeEventListener('dblclick', onDblClick)
  }, [camera, threeScene, gl, onPlace])

  return null
}

// ── 3DGS Dedicated WASD Roam Controller ───────────────────────────────────────
function SplatWASDControls({ enabled, onSyncPosition, virtualKeys }) {
  const { camera, gl } = useThree()
  const keys = useRef({ w: false, a: false, s: false, d: false, space: false, c: false, shift: false })
  const isLocked = useRef(false)
  const yaw = useRef(0)
  const pitch = useRef(0)

  useEffect(() => {
    if (!enabled) return
    const canvas = gl.domElement

    // Initial look angles
    const dir = new THREE.Vector3()
    camera.getWorldDirection(dir)
    yaw.current = Math.atan2(-dir.x, -dir.z)
    pitch.current = Math.asin(Math.max(-0.99, Math.min(0.99, dir.y)))

    const onClick = () => {
      canvas.requestPointerLock()
    }

    const onPointerLockChange = () => {
      isLocked.current = document.pointerLockElement === canvas
    }

    const onMouseMove = (e) => {
      if (!isLocked.current) return
      yaw.current -= e.movementX * LOOK_SENSITIVITY
      pitch.current -= e.movementY * LOOK_SENSITIVITY
      pitch.current = Math.max(-MAX_PITCH_RAD, Math.min(MAX_PITCH_RAD, pitch.current))
    }

    // Touch look support for mobile
    let touchStartX = 0
    let touchStartY = 0
    let isTouching = false

    const onTouchStart = (e) => {
      if (e.touches.length === 1) {
        isTouching = true
        touchStartX = e.touches[0].clientX
        touchStartY = e.touches[0].clientY
      }
    }

    const onTouchMove = (e) => {
      if (!isTouching || e.touches.length !== 1) return
      const dx = e.touches[0].clientX - touchStartX
      const dy = e.touches[0].clientY - touchStartY
      touchStartX = e.touches[0].clientX
      touchStartY = e.touches[0].clientY

      yaw.current -= dx * 0.004
      pitch.current -= dy * 0.004
      pitch.current = Math.max(-MAX_PITCH_RAD, Math.min(MAX_PITCH_RAD, pitch.current))
    }

    const onTouchEnd = () => {
      isTouching = false
    }

    const onKeyDown = (e) => {
      const k = e.key.toLowerCase()
      if (k === 'w') keys.current.w = true
      if (k === 'a') keys.current.a = true
      if (k === 's') keys.current.s = true
      if (k === 'd') keys.current.d = true
      if (k === ' ' || k === 'space') keys.current.space = true
      if (k === 'c' || k === 'control') keys.current.c = true
      if (k === 'shift') keys.current.shift = true
    }

    const onKeyUp = (e) => {
      const k = e.key.toLowerCase()
      if (k === 'w') keys.current.w = false
      if (k === 'a') keys.current.a = false
      if (k === 's') keys.current.s = false
      if (k === 'd') keys.current.d = false
      if (k === ' ' || k === 'space') keys.current.space = false
      if (k === 'c' || k === 'control') keys.current.c = false
      if (k === 'shift') keys.current.shift = false
    }

    canvas.addEventListener('click', onClick)
    canvas.addEventListener('touchstart', onTouchStart, { passive: true })
    canvas.addEventListener('touchmove', onTouchMove, { passive: true })
    canvas.addEventListener('touchend', onTouchEnd, { passive: true })
    canvas.addEventListener('touchcancel', onTouchEnd, { passive: true })
    document.addEventListener('pointerlockchange', onPointerLockChange)
    document.addEventListener('mousemove', onMouseMove)
    window.addEventListener('keydown', onKeyDown)
    window.addEventListener('keyup', onKeyUp)

    return () => {
      canvas.removeEventListener('click', onClick)
      canvas.removeEventListener('touchstart', onTouchStart)
      canvas.removeEventListener('touchmove', onTouchMove)
      canvas.removeEventListener('touchend', onTouchEnd)
      canvas.removeEventListener('touchcancel', onTouchEnd)
      document.removeEventListener('pointerlockchange', onPointerLockChange)
      document.removeEventListener('mousemove', onMouseMove)
      window.removeEventListener('keydown', onKeyDown)
      window.removeEventListener('keyup', onKeyUp)
      if (document.pointerLockElement === canvas) {
        document.exitPointerLock()
      }
    }
  }, [enabled, camera, gl])

  useFrame((_, delta) => {
    if (!enabled) return

    // Apply look rotation
    camera.rotation.set(pitch.current, yaw.current, 0, 'YXZ')

    // WASD movement in horizontal look direction
    const speed = keys.current.shift ? SPRINT_SPEED : WALK_SPEED
    const move = new THREE.Vector3()

    const isW = keys.current.w || virtualKeys?.w
    const isS = keys.current.s || virtualKeys?.s
    const isA = keys.current.a || virtualKeys?.a
    const isD = keys.current.d || virtualKeys?.d

    if (isW) move.z -= 1
    if (isS) move.z += 1
    if (isA) move.x -= 1
    if (isD) move.x += 1

    if (move.lengthSq() > 0) {
      move.normalize().multiplyScalar(speed * delta)
      const yawQuat = new THREE.Quaternion().setFromEuler(new THREE.Euler(0, yaw.current, 0, 'YXZ'))
      move.applyQuaternion(yawQuat)
      camera.position.add(move)
    }

    // Fly up / down controls
    if (keys.current.space) {
      camera.position.y += VERTICAL_SPEED * delta
    }
    if (keys.current.c) {
      camera.position.y = Math.max(0.2, camera.position.y - VERTICAL_SPEED * delta)
    }

    // Keep above floor level
    if (camera.position.y < 0.3) {
      camera.position.y = 0.3
    }

    if (onSyncPosition) {
      onSyncPosition([camera.position.x, camera.position.y, camera.position.z], yaw.current)
    }
  })

  return null
}

// ── 3D Gaussian Splat Error Boundary ───────────────────────────────────────────
class SplatErrorBoundary extends React.Component {
  constructor(props) {
    super(props)
    this.state = { hasError: false }
  }
  static getDerivedStateFromError() {
    return { hasError: true }
  }
  componentDidCatch(error) {
    console.warn('[PhotorealisticSplat] Splat loading caught by boundary:', error)
    if (this.props.onError) this.props.onError()
  }
  render() {
    if (this.state.hasError) return null
    return this.props.children
  }
}

// ── 3D Gaussian Splat Renderer ────────────────────────────────────────────────
function PhotorealisticSplat({
  splatUrl,
  rotationZ = 0,
  rotationX = 0,
  invertY = false,
  onProgress,
  onLoaded,
}) {
  if (!splatUrl) return null

  const rx = (invertY ? Math.PI : 0) + rotationX
  const rz = rotationZ

  return (
    <SplatErrorBoundary key={splatUrl} onError={onLoaded}>
      <Suspense fallback={null}>
        <GaussianSplat
          key={`${splatUrl}-${invertY}-${rx.toFixed(2)}-${rz.toFixed(2)}`}
          src={splatUrl}
          rotation={[rx, 0, rz]}
          position={[0, 1.65, 0]}
          scale={[1, 1, 1]}
          alphaTest={0.05}
          onProgress={onProgress}
          onLoaded={onLoaded}
        />
      </Suspense>
    </SplatErrorBoundary>
  )
}

// ── Main 3D Viewer Root ───────────────────────────────────────────────────────
export default function Viewer3D({ onPOIPlace, isMobile = false }) {
  const {
    currentScene,
    pois,
    setPOIs,
    selectedPOI,
    selectPOI,
    navigationPath,
    setPath,
    setPlayerPosition,
    setPlayerYaw,
  } = useStore()

  // Control mode: 'wasd' (First-person walk) vs 'orbit' (Inspect from outside)
  const [controlMode, setControlMode] = useState(() => (isMobile ? 'orbit' : 'wasd'))
  const [virtualKeys, setVirtualKeys] = useState({ w: false, a: false, s: false, d: false })
  const [invertY, setInvertY] = useState(false)

  // Orientation offsets
  const isRoomvid = currentScene?.name?.toLowerCase().includes('roomvid')
  const [rotationZ, setRotationZ] = useState(isRoomvid ? Math.PI / 2 : 0)
  const [rotationX, setRotationX] = useState(0)

  // Sync orientation on scene switch
  useEffect(() => {
    if (currentScene?.name?.toLowerCase().includes('roomvid')) {
      setRotationZ(Math.PI / 2)
      setRotationX(0)
    } else {
      setRotationZ(0)
      setRotationX(0)
    }
  }, [currentScene?.id])

  const handleRotateLeft = () => setRotationZ((prev) => (prev + Math.PI / 2) % (2 * Math.PI))
  const handleRotateRight = () => setRotationZ((prev) => (prev - Math.PI / 2 + 2 * Math.PI) % (2 * Math.PI))
  const handleResetRotation = () => { setRotationZ(0); setRotationX(0); setInvertY(false) }

  // Load POIs when scene changes
  useEffect(() => {
    if (!currentScene?.id) return
    const poisUrl = currentScene.tour_path
      ? `${currentScene.tour_path.substring(0, currentScene.tour_path.lastIndexOf('/'))}/pois.json`
      : '/static/panoramas/sample_scene/pois.json'

    fetch(poisUrl)
      .then((res) => (res.ok ? res.json() : null))
      .then((data) => {
        if (Array.isArray(data) && data.length > 0) {
          setPOIs(
            data.map((p) => ({
              id: p.id,
              name: p.name,
              category: p.category,
              aliases: p.aliases || [],
              x: p.position[0],
              y: p.position[1],
              z: p.position[2],
            }))
          )
        }
      })
      .catch(() => {})
  }, [currentScene?.id, setPOIs])

  // Navigate to POI: computes route path
  const handleNavigateToPOI = useCallback(
    async (poi) => {
      selectPOI(poi)
      const targetPos = [poi.x, poi.y, poi.z]
      const currentPos = [0, 1.65, 0]

      try {
        const sceneId = currentScene?.id || 1
        const res = await fetch(`/api/scenes/${sceneId}/route`, {
          method: 'POST',
          headers: { 'Content-Type': 'application/json' },
          body: JSON.stringify({
            start: currentPos,
            goal: targetPos,
          }),
        })
        if (res.ok) {
          const data = await res.json()
          if (data.path && data.path.length > 0) {
            setPath(data.path)
            return
          }
        }
        setPath([currentPos, targetPos])
      } catch (err) {
        setPath([currentPos, targetPos])
      }
    },
    [currentScene?.id, selectPOI, setPath]
  )

  const handlePlace = useCallback(
    (pos) => {
      if (onPOIPlace) onPOIPlace(pos)
    },
    [onPOIPlace]
  )

  const splatUrl = useMemo(() => {
    return currentScene?.splat_path || DEFAULT_SCENES[0]?.splat_path || '/static/models/sample_scene.splat'
  }, [currentScene])
  const navgridUrl = currentScene?.tour_path
    ? `${currentScene.tour_path.substring(0, currentScene.tour_path.lastIndexOf('/'))}/nav/navgrid.json`
    : '/static/navigation/navgrid.json'

  const [splatLoadingProgress, setSplatLoadingProgress] = useState({
    loading: true,
    percent: 0,
    loaded: 0,
    total: 0,
  })

  // Reset loading progress whenever scene / splatUrl changes
  useEffect(() => {
    setSplatLoadingProgress({ loading: true, percent: 0, loaded: 0, total: 0 })
    // Safety auto-dismiss: if splats finish rendering or network takes max 18s, dismiss loading HUD
    const timer = setTimeout(() => {
      setSplatLoadingProgress((prev) => ({ ...prev, loading: false }))
    }, 18000)
    return () => clearTimeout(timer)
  }, [splatUrl])

  const handleSplatProgress = useCallback((p) => {
    setSplatLoadingProgress({ loading: true, ...p })
  }, [])

  const handleSplatLoaded = useCallback(() => {
    setSplatLoadingProgress((prev) => ({ ...prev, loading: false, percent: 100 }))
  }, [])

  const handleSyncPosition = useCallback(
    (pos, yaw) => {
      setPlayerPosition(pos)
      setPlayerYaw(yaw)
    },
    [setPlayerPosition, setPlayerYaw]
  )

  return (
    <div style={{ width: '100%', height: '100%', position: 'relative', overflow: 'hidden' }}>
      {/* ── Top Floating Navigation & Mode Bar ── */}
      <div
        style={{
          position: 'absolute',
          top: isMobile ? 8 : 14,
          left: isMobile ? 8 : 14,
          zIndex: 25,
          display: 'flex',
          gap: isMobile ? 4 : 8,
          alignItems: 'center',
          maxWidth: isMobile ? 'calc(100vw - 140px)' : 'auto',
        }}
      >
        {/* 3DGS Controls Mode Selector Pill */}
        <div
          style={{
            display: 'flex',
            gap: 2,
            background: 'rgba(10, 20, 35, 0.92)',
            padding: 3,
            borderRadius: 8,
            border: '1px solid #1e3a5f',
            boxShadow: '0 4px 16px rgba(0,0,0,0.6)',
            backdropFilter: 'blur(8px)',
          }}
        >
          <button
            onClick={() => setControlMode('wasd')}
            style={{
              background: controlMode === 'wasd' ? '#00e5ff' : 'transparent',
              color: controlMode === 'wasd' ? '#0a101d' : '#00e5ff',
              border: 'none',
              borderRadius: 6,
              padding: isMobile ? '4px 7px' : '6px 14px',
              fontSize: isMobile ? 11 : 12,
              fontWeight: 700,
              cursor: 'pointer',
              display: 'flex',
              alignItems: 'center',
              gap: 3,
              transition: 'all 0.15s',
            }}
          >
            {isMobile ? '🕹️ Roam' : '🕹️ WASD Roam'}
          </button>
          <button
            onClick={() => setControlMode('orbit')}
            style={{
              background: controlMode === 'orbit' ? '#00e5ff' : 'transparent',
              color: controlMode === 'orbit' ? '#0a101d' : '#88a0b5',
              border: 'none',
              borderRadius: 6,
              padding: isMobile ? '4px 7px' : '6px 14px',
              fontSize: isMobile ? 11 : 12,
              fontWeight: 700,
              cursor: 'pointer',
              display: 'flex',
              alignItems: 'center',
              gap: 3,
              transition: 'all 0.15s',
            }}
          >
            {isMobile ? '🔄 Orbit' : '🔄 Orbit View'}
          </button>
        </div>

        {/* POI Search Bar with Fuse.js (Desktop only) */}
        {!isMobile && (
          <POISearchBar onNavigateToPOI={handleNavigateToPOI} />
        )}

        {/* Quick Orientation Buttons */}
        <div
          style={{
            display: 'flex',
            gap: 2,
            background: 'rgba(10, 20, 35, 0.92)',
            padding: 3,
            borderRadius: 8,
            border: '1px solid #1e3a5f',
            boxShadow: '0 4px 16px rgba(0,0,0,0.6)',
            backdropFilter: 'blur(8px)',
          }}
        >
          <button
            onClick={handleRotateLeft}
            title="Rotate 90 degrees left"
            style={{
              background: 'transparent',
              color: '#00e5ff',
              border: 'none',
              borderRadius: 6,
              padding: isMobile ? '4px 6px' : '6px 10px',
              fontSize: isMobile ? 11 : 12,
              fontWeight: 700,
              cursor: 'pointer',
            }}
          >
            ↺ 90°
          </button>
          {!isMobile && (
            <button
              onClick={handleRotateRight}
              title="Rotate 90 degrees right"
              style={{
                background: 'transparent',
                color: '#00e5ff',
                border: 'none',
                borderRadius: 6,
                padding: '6px 10px',
                fontSize: 12,
                fontWeight: 700,
                cursor: 'pointer',
              }}
            >
              ↻ 90°
            </button>
          )}
          <button
            onClick={() => setInvertY((v) => !v)}
            title="Flip 180 degrees upright / inverted"
            style={{
              background: 'transparent',
              color: '#ffaa00',
              border: 'none',
              borderRadius: 6,
              padding: isMobile ? '4px 6px' : '6px 10px',
              fontSize: isMobile ? 11 : 12,
              fontWeight: 700,
              cursor: 'pointer',
            }}
          >
            {invertY ? '🔄 Invert' : '⬆️ Upright'}
          </button>
          {(rotationZ !== 0 || rotationX !== 0 || invertY) && (
            <button
              onClick={handleResetRotation}
              title="Reset orientation"
              style={{
                background: 'rgba(255, 60, 60, 0.15)',
                color: '#ff6666',
                border: '1px solid rgba(255, 60, 60, 0.3)',
                borderRadius: 6,
                padding: isMobile ? '4px 6px' : '6px 10px',
                fontSize: 11,
                fontWeight: 700,
                cursor: 'pointer',
              }}
            >
              Reset
            </button>
          )}
        </div>
      </div>

      {/* ── 3D Canvas Viewport ── */}
      <CanvasErrorBoundary>
        <Canvas
          dpr={[1, Math.min(2, typeof window !== 'undefined' ? window.devicePixelRatio : 2)]}
          gl={{ antialias: true, powerPreference: 'high-performance' }}
          camera={{ position: [0, 1.65, 3.2], fov: isMobile ? 80 : 75, near: 0.1, far: 200 }}
          style={{ background: '#0a0e14', touchAction: 'none' }}
        >
          <ambientLight intensity={1.8} />
          <directionalLight position={[10, 20, 10]} intensity={1.6} />
          <directionalLight position={[-10, 20, -10]} intensity={1.4} />
          <directionalLight position={[0, -10, 0]} intensity={1.0} />
          <directionalLight position={[0, 15, 0]} intensity={1.0} />

          {/* Debug Inspector */}
          <SceneDebugger />

          {/* 1. High-Fidelity 3D Gaussian Splats */}
          {splatUrl && (
            <PhotorealisticSplat
              splatUrl={splatUrl}
              rotationZ={rotationZ}
              rotationX={rotationX}
              invertY={invertY}
              onProgress={handleSplatProgress}
              onLoaded={handleSplatLoaded}
            />
          )}

          {/* 2. Controls: First-Person WASD vs Orbit */}
          {controlMode === 'wasd' ? (
            <SplatWASDControls
              enabled={true}
              onSyncPosition={handleSyncPosition}
              virtualKeys={virtualKeys}
            />
          ) : (
            <OrbitControls
              target={[0, 1.65, 0]}
              maxPolarAngle={Math.PI}
              minDistance={0.2}
              maxDistance={60}
              enableDamping
              dampingFactor={0.08}
            />
          )}

          {/* Interactive Floor Markers & Navigation Ribbon */}
          <Suspense fallback={null}>
            <POIMarkers pois={pois} onSelect={handleNavigateToPOI} />
          </Suspense>
          <NavigationPath path={navigationPath} />
          <FloorGrid />
          <POIPlacementHandler onPlace={handlePlace} />
        </Canvas>
      </CanvasErrorBoundary>

      {/* ── Mobile Touch Roam D-Pad (Visible in Roam mode on mobile) ── */}
      {isMobile && controlMode === 'wasd' && (
        <div
          style={{
            position: 'absolute',
            bottom: 70,
            left: 14,
            zIndex: 40,
            display: 'flex',
            flexDirection: 'column',
            alignItems: 'center',
            gap: 6,
            background: 'rgba(10, 20, 35, 0.85)',
            padding: '8px 10px',
            borderRadius: 14,
            border: '1px solid rgba(0, 229, 255, 0.4)',
            boxShadow: '0 8px 32px rgba(0,0,0,0.6)',
            backdropFilter: 'blur(10px)',
            userSelect: 'none',
            touchAction: 'none',
          }}
        >
          <button
            onTouchStart={(e) => { e.preventDefault(); setVirtualKeys((k) => ({ ...k, w: true })) }}
            onTouchEnd={() => setVirtualKeys((k) => ({ ...k, w: false }))}
            onMouseDown={() => setVirtualKeys((k) => ({ ...k, w: true }))}
            onMouseUp={() => setVirtualKeys((k) => ({ ...k, w: false }))}
            style={{
              width: 44,
              height: 44,
              background: 'rgba(0, 229, 255, 0.2)',
              border: '1px solid #00e5ff',
              borderRadius: 8,
              color: '#00e5ff',
              fontSize: 16,
              fontWeight: 700,
              cursor: 'pointer',
              display: 'flex',
              alignItems: 'center',
              justifyContent: 'center',
            }}
          >
            ▲
          </button>
          <div style={{ display: 'flex', gap: 10 }}>
            <button
              onTouchStart={(e) => { e.preventDefault(); setVirtualKeys((k) => ({ ...k, a: true })) }}
              onTouchEnd={() => setVirtualKeys((k) => ({ ...k, a: false }))}
              onMouseDown={() => setVirtualKeys((k) => ({ ...k, a: true }))}
              onMouseUp={() => setVirtualKeys((k) => ({ ...k, a: false }))}
              style={{
                width: 44,
                height: 44,
                background: 'rgba(0, 229, 255, 0.2)',
                border: '1px solid #00e5ff',
                borderRadius: 8,
                color: '#00e5ff',
                fontSize: 16,
                fontWeight: 700,
                cursor: 'pointer',
                display: 'flex',
                alignItems: 'center',
                justifyContent: 'center',
              }}
            >
              ◀
            </button>
            <button
              onTouchStart={(e) => { e.preventDefault(); setVirtualKeys((k) => ({ ...k, s: true })) }}
              onTouchEnd={() => setVirtualKeys((k) => ({ ...k, s: false }))}
              onMouseDown={() => setVirtualKeys((k) => ({ ...k, s: true }))}
              onMouseUp={() => setVirtualKeys((k) => ({ ...k, s: false }))}
              style={{
                width: 44,
                height: 44,
                background: 'rgba(0, 229, 255, 0.2)',
                border: '1px solid #00e5ff',
                borderRadius: 8,
                color: '#00e5ff',
                fontSize: 16,
                fontWeight: 700,
                cursor: 'pointer',
                display: 'flex',
                alignItems: 'center',
                justifyContent: 'center',
              }}
            >
              ▼
            </button>
            <button
              onTouchStart={(e) => { e.preventDefault(); setVirtualKeys((k) => ({ ...k, d: true })) }}
              onTouchEnd={() => setVirtualKeys((k) => ({ ...k, d: false }))}
              onMouseDown={() => setVirtualKeys((k) => ({ ...k, d: true }))}
              onMouseUp={() => setVirtualKeys((k) => ({ ...k, d: false }))}
              style={{
                width: 44,
                height: 44,
                background: 'rgba(0, 229, 255, 0.2)',
                border: '1px solid #00e5ff',
                borderRadius: 8,
                color: '#00e5ff',
                fontSize: 16,
                fontWeight: 700,
                cursor: 'pointer',
                display: 'flex',
                alignItems: 'center',
                justifyContent: 'center',
              }}
            >
              ▶
            </button>
          </div>
        </div>
      )}

      {/* ── High-Tech HUD Loading Indicator ── */}
      {splatLoadingProgress.loading && (
        <div
          style={{
            position: 'absolute',
            top: '50%',
            left: '50%',
            transform: 'translate(-50%, -50%)',
            zIndex: 60,
            background: 'rgba(10, 18, 30, 0.95)',
            padding: isMobile ? '20px 24px' : '24px 36px',
            borderRadius: 12,
            border: '1px solid #00e5ff',
            boxShadow: '0 8px 32px rgba(0, 0, 0, 0.8), 0 0 25px rgba(0, 229, 255, 0.3)',
            backdropFilter: 'blur(12px)',
            textAlign: 'center',
            width: 'min(320px, 86vw)',
            maxWidth: '90vw',
          }}
        >
          <button
            onClick={() => setSplatLoadingProgress((prev) => ({ ...prev, loading: false }))}
            style={{
              position: 'absolute',
              top: 8,
              right: 8,
              background: 'transparent',
              border: 'none',
              color: '#88a0b5',
              fontSize: 16,
              cursor: 'pointer',
              padding: 4,
            }}
            title="Dismiss loading overlay"
          >
            ✕
          </button>
          <div style={{ fontSize: 26, marginBottom: 8 }}>⚡</div>
          <div
            style={{
              color: '#00e5ff',
              fontWeight: 700,
              fontSize: 15,
              marginBottom: 6,
              letterSpacing: '0.5px',
            }}
          >
            Loading Photorealistic 3D Space
          </div>
          <div style={{ color: '#88a0b5', fontSize: 12, marginBottom: 14 }}>
            {splatLoadingProgress.total > 0
              ? `${(splatLoadingProgress.loaded / (1024 * 1024)).toFixed(1)} MB / ${(splatLoadingProgress.total / (1024 * 1024)).toFixed(1)} MB (${splatLoadingProgress.percent}%)`
              : 'Streaming 3D Gaussian Splats...'}
          </div>
          <div
            style={{
              width: '100%',
              height: 6,
              background: 'rgba(255, 255, 255, 0.1)',
              borderRadius: 3,
              overflow: 'hidden',
            }}
          >
            <div
              style={{
                width: `${Math.max(6, splatLoadingProgress.percent || 0)}%`,
                height: '100%',
                background: 'linear-gradient(90deg, #0077ff, #00e5ff)',
                transition: 'width 0.2s ease-out',
                borderRadius: 3,
              }}
            />
          </div>
        </div>
      )}

      {/* ── Radar Minimap ── */}
      <Minimap navgridUrl={navgridUrl} />

      {/* ── Help Overlay Pill ── */}
      <div
        style={{
          position: 'absolute',
          bottom: 16,
          left: 16,
          background: 'rgba(10, 20, 35, 0.88)',
          padding: '8px 14px',
          borderRadius: 8,
          fontSize: 11,
          fontWeight: 600,
          color: '#00e5ff',
          border: '1px solid rgba(0, 229, 255, 0.25)',
          boxShadow: '0 4px 16px rgba(0,0,0,0.6)',
          pointerEvents: 'none',
          backdropFilter: 'blur(8px)',
          maxWidth: 'calc(100vw - 32px)',
        }}
      >
        {isMobile ? (
          controlMode === 'wasd' ? (
            <span>📱 <strong>Swipe screen</strong> to look • <strong>Touch D-Pad</strong> to walk</span>
          ) : (
            <span>📱 <strong>1-Finger drag</strong> to rotate • <strong>Pinch</strong> to zoom</span>
          )
        ) : controlMode === 'wasd' ? (
          <span>
            🕹️ <strong>Click screen to lock mouse</strong> | <strong>W A S D</strong> to walk | <strong>Shift</strong> to sprint | <strong>Space / C</strong> to fly up/down | <strong>Esc</strong> to unlock cursor
          </span>
        ) : (
          <span>
            🖱️ <strong>Left-click drag</strong> to orbit | <strong>Scroll</strong> to zoom | <strong>Right-click drag</strong> to pan
          </span>
        )}
      </div>
    </div>
  )
}
