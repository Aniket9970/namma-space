import React, { useEffect, useRef, useState, useCallback, Suspense, useMemo } from 'react'
import { Canvas, useThree, useFrame } from '@react-three/fiber'
import { Splat, Text, Line, Grid, OrbitControls } from '@react-three/drei'
import * as THREE from 'three'

import useStore from '../store/useStore'
import usePOIs from '../hooks/usePOIs'
import Minimap from './Minimap'
import POISearchBar from './POISearchBar'
import ProxyMeshView from './ProxyMeshView.jsx'
import { DEFAULT_SCENES } from '../api/scenesData.js'

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
function SplatWASDControls({ enabled, onSyncPosition }) {
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
    document.addEventListener('pointerlockchange', onPointerLockChange)
    document.addEventListener('mousemove', onMouseMove)
    window.addEventListener('keydown', onKeyDown)
    window.addEventListener('keyup', onKeyUp)

    return () => {
      canvas.removeEventListener('click', onClick)
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

    if (keys.current.w) move.z -= 1
    if (keys.current.s) move.z += 1
    if (keys.current.a) move.x -= 1
    if (keys.current.d) move.x += 1

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
  }
  render() {
    if (this.state.hasError) return null
    return this.props.children
  }
}

// ── 3D Gaussian Splat Renderer ────────────────────────────────────────────────
function PhotorealisticSplat({ splatUrl, rotationZ = 0, rotationX = 0, invertY = false }) {
  if (!splatUrl) return null

  const rx = (invertY ? Math.PI : 0) + rotationX
  const rz = rotationZ

  return (
    <SplatErrorBoundary key={splatUrl}>
      <Suspense fallback={null}>
        <Splat
          key={`${splatUrl}-${invertY}-${rx.toFixed(2)}-${rz.toFixed(2)}`}
          src={splatUrl}
          rotation={[rx, 0, rz]}
          position={[0, 1.65, 0]}
          scale={[1, 1, 1]}
          alphaTest={0.05}
        />
      </Suspense>
    </SplatErrorBoundary>
  )
}

// ── Main 3D Viewer Root ───────────────────────────────────────────────────────
export default function Viewer3D({ onPOIPlace }) {
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
  const [controlMode, setControlMode] = useState('wasd')
  const [invertY, setInvertY] = useState(false)
  const [renderMode, setRenderMode] = useState('mesh') // 'mesh' (instant load) | 'both' | 'splat'

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

  const glbUrl = currentScene?.glb_path || DEFAULT_SCENES[0]?.glb_path || '/static/models/sample_scene.glb'
  const splatUrl = currentScene?.splat_path || DEFAULT_SCENES[0]?.splat_path || '/static/models/sample_scene.splat'
  const navgridUrl = currentScene?.tour_path
    ? `${currentScene.tour_path.substring(0, currentScene.tour_path.lastIndexOf('/'))}/nav/navgrid.json`
    : '/static/navigation/navgrid.json'

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
          top: 14,
          left: 14,
          zIndex: 25,
          display: 'flex',
          flexWrap: 'wrap',
          gap: 10,
          alignItems: 'center',
        }}
      >
        {/* 3DGS Controls Mode Selector Pill */}
        <div
          style={{
            display: 'flex',
            gap: 4,
            background: 'rgba(10, 20, 35, 0.92)',
            padding: 4,
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
              padding: '6px 14px',
              fontSize: 12,
              fontWeight: 700,
              cursor: 'pointer',
              display: 'flex',
              alignItems: 'center',
              gap: 5,
              transition: 'all 0.15s',
            }}
          >
            🕹️ WASD Roam
          </button>
          <button
            onClick={() => setControlMode('orbit')}
            style={{
              background: controlMode === 'orbit' ? '#00e5ff' : 'transparent',
              color: controlMode === 'orbit' ? '#0a101d' : '#88a0b5',
              border: 'none',
              borderRadius: 6,
              padding: '6px 14px',
              fontSize: 12,
              fontWeight: 700,
              cursor: 'pointer',
              display: 'flex',
              alignItems: 'center',
              gap: 5,
              transition: 'all 0.15s',
            }}
          >
            🔄 Orbit View
          </button>
        </div>

        {/* 3D Model vs Gaussian Splat Render Layer Selector */}
        <div
          style={{
            display: 'flex',
            gap: 4,
            background: 'rgba(10, 20, 35, 0.92)',
            padding: 4,
            borderRadius: 8,
            border: '1px solid #1e3a5f',
            boxShadow: '0 4px 16px rgba(0,0,0,0.6)',
            backdropFilter: 'blur(8px)',
          }}
        >
          <button
            onClick={() => setRenderMode('both')}
            title="Render both 3D Room Mesh and Gaussian Splats"
            style={{
              background: renderMode === 'both' ? '#00e5ff' : 'transparent',
              color: renderMode === 'both' ? '#0a101d' : '#88a0b5',
              border: 'none',
              borderRadius: 6,
              padding: '6px 10px',
              fontSize: 12,
              fontWeight: 700,
              cursor: 'pointer',
              transition: 'all 0.15s',
            }}
          >
            🌟 Both
          </button>
          <button
            onClick={() => setRenderMode('mesh')}
            title="Render 3D Reconstructed Mesh"
            style={{
              background: renderMode === 'mesh' ? '#00e5ff' : 'transparent',
              color: renderMode === 'mesh' ? '#0a101d' : '#88a0b5',
              border: 'none',
              borderRadius: 6,
              padding: '6px 10px',
              fontSize: 12,
              fontWeight: 700,
              cursor: 'pointer',
              transition: 'all 0.15s',
            }}
          >
            🏛️ 3D Mesh
          </button>
          <button
            onClick={() => setRenderMode('splat')}
            title="Render 3D Gaussian Splats"
            style={{
              background: renderMode === 'splat' ? '#00e5ff' : 'transparent',
              color: renderMode === 'splat' ? '#0a101d' : '#88a0b5',
              border: 'none',
              borderRadius: 6,
              padding: '6px 10px',
              fontSize: 12,
              fontWeight: 700,
              cursor: 'pointer',
              transition: 'all 0.15s',
            }}
          >
            ✨ Splat
          </button>
        </div>

        {/* POI Search Bar with Fuse.js */}
        <POISearchBar onNavigateToPOI={handleNavigateToPOI} />

        {/* Quick Orientation Buttons */}
        <div
          style={{
            display: 'flex',
            gap: 4,
            background: 'rgba(10, 20, 35, 0.92)',
            padding: 4,
            borderRadius: 8,
            border: '1px solid #1e3a5f',
            boxShadow: '0 4px 16px rgba(0,0,0,0.6)',
            backdropFilter: 'blur(8px)',
          }}
        >
          <button
            onClick={handleRotateLeft}
            title="Rotate 90 degrees to the left (counter-clockwise)"
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
            ↺ Rotate Left 90°
          </button>
          <button
            onClick={handleRotateRight}
            title="Rotate 90 degrees to the right (clockwise)"
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
            ↻ Rotate Right 90°
          </button>
          <button
            onClick={() => setInvertY((v) => !v)}
            title="Flip 180 degrees upright / inverted"
            style={{
              background: 'transparent',
              color: '#ffaa00',
              border: 'none',
              borderRadius: 6,
              padding: '6px 10px',
              fontSize: 12,
              fontWeight: 700,
              cursor: 'pointer',
            }}
          >
            {invertY ? '🔄 Inverted' : '⬆️ Upright'}
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
                padding: '6px 10px',
                fontSize: 11,
                fontWeight: 700,
                cursor: 'pointer',
              }}
            >
              Reset ({(Math.round((rotationZ * 180) / Math.PI) + 360) % 360}°)
            </button>
          )}
        </div>
      </div>

      {/* ── 3D Canvas Viewport ── */}
      <CanvasErrorBoundary>
        <Canvas
          camera={{ position: [0, 1.65, 3.2], fov: 75, near: 0.1, far: 200 }}
          style={{ background: '#0a0e14' }}
        >
          <ambientLight intensity={1.4} />
          <directionalLight position={[10, 20, 10]} intensity={1.6} />
          <directionalLight position={[-10, 20, -10]} intensity={1.2} />
          <directionalLight position={[0, -10, 0]} intensity={0.6} />

          {/* 1. 3D Reconstructed Room Mesh */}
          {(renderMode === 'mesh' || renderMode === 'both') && glbUrl && (
            <ProxyMeshView
              url={glbUrl}
              rotation={[rotationX + (invertY ? Math.PI : 0), 0, rotationZ]}
              position={[0, 0, 0]}
              scale={[1, 1, 1]}
            />
          )}

          {/* 2. High-Fidelity 3D Gaussian Splats */}
          {(renderMode === 'splat' || renderMode === 'both') && splatUrl && (
            <PhotorealisticSplat
              splatUrl={splatUrl}
              rotationZ={rotationZ}
              rotationX={rotationX}
              invertY={invertY}
            />
          )}

          {/* 2. Controls: First-Person WASD vs Orbit */}
          {controlMode === 'wasd' ? (
            <SplatWASDControls enabled={true} onSyncPosition={handleSyncPosition} />
          ) : (
            <OrbitControls
              target={[0, 1.2, 0]}
              maxPolarAngle={Math.PI / 2 + 0.3}
              minDistance={0.5}
              maxDistance={40}
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

      {/* ── Radar Minimap ── */}
      <Minimap navgridUrl={navgridUrl} />

      {/* ── Help Overlay Pill ── */}
      <div
        style={{
          position: 'absolute',
          bottom: 16,
          left: 16,
          background: 'rgba(10, 20, 35, 0.88)',
          padding: '8px 16px',
          borderRadius: 8,
          fontSize: 12,
          fontWeight: 600,
          color: '#00e5ff',
          border: '1px solid rgba(0, 229, 255, 0.25)',
          boxShadow: '0 4px 16px rgba(0,0,0,0.6)',
          pointerEvents: 'none',
          backdropFilter: 'blur(8px)',
        }}
      >
        {controlMode === 'wasd' ? (
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
