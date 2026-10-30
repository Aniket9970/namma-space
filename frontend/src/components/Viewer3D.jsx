import { useEffect, useRef, useState, useCallback, Suspense } from 'react'
import { Canvas, useFrame, useThree } from '@react-three/fiber'
import { Splat, Text, Line, Grid, OrbitControls } from '@react-three/drei'
import * as THREE from 'three'

import useStore from '../store/useStore.js'
import useKeyboard from '../hooks/useKeyboard.js'
import usePOIs from '../hooks/usePOIs.js'

// ── Constants ─────────────────────────────────────────────────────────────────
const WALK_SPEED = 3      // units / second
const SPRINT_SPEED = 6    // units / second with Shift
const LOOK_SENSITIVITY = 0.002
const MAX_PITCH_RAD = (85 * Math.PI) / 180
const CAMERA_HEIGHT = 1.65 // eye height in world units

// ── FirstPersonControls ───────────────────────────────────────────────────────
function FirstPersonControls({ enabled }) {
  const { camera, gl } = useThree()
  const keysRef = useKeyboard()
  const yawRef = useRef(0)
  const pitchRef = useRef(0)
  const isLockedRef = useRef(false)

  // Set initial camera position: standing at entrance looking into the room
  useEffect(() => {
    camera.position.set(0, CAMERA_HEIGHT, -4.0)
    camera.rotation.order = 'YXZ'
    yawRef.current = Math.PI // Face towards +Z
  }, [camera])

  // Pointer lock
  useEffect(() => {
    if (!enabled) return

    const canvas = gl.domElement

    const onClick = () => {
      canvas.requestPointerLock()
    }

    const onPointerLockChange = () => {
      isLockedRef.current = document.pointerLockElement === canvas
    }

    const onMouseMove = (e) => {
      if (!isLockedRef.current) return
      yawRef.current -= e.movementX * LOOK_SENSITIVITY
      pitchRef.current -= e.movementY * LOOK_SENSITIVITY
      pitchRef.current = Math.max(-MAX_PITCH_RAD, Math.min(MAX_PITCH_RAD, pitchRef.current))
    }

    canvas.addEventListener('click', onClick)
    document.addEventListener('pointerlockchange', onPointerLockChange)
    document.addEventListener('mousemove', onMouseMove)

    return () => {
      canvas.removeEventListener('click', onClick)
      document.removeEventListener('pointerlockchange', onPointerLockChange)
      document.removeEventListener('mousemove', onMouseMove)
    }
  }, [enabled, gl])

  useFrame((_, delta) => {
    if (!enabled) return

    // Apply look rotation
    camera.rotation.set(pitchRef.current, yawRef.current, 0, 'YXZ')

    // WASD movement
    const speed = keysRef.current.shift ? SPRINT_SPEED : WALK_SPEED
    const move = new THREE.Vector3()

    if (keysRef.current.w) move.z -= 1
    if (keysRef.current.s) move.z += 1
    if (keysRef.current.a) move.x -= 1
    if (keysRef.current.d) move.x += 1

    if (move.lengthSq() > 0) {
      move.normalize().multiplyScalar(speed * delta)
      const yawQuat = new THREE.Quaternion().setFromEuler(
        new THREE.Euler(0, yawRef.current, 0, 'YXZ')
      )
      move.applyQuaternion(yawQuat)
      camera.position.add(move)
    }

    // Floor clamp
    if (camera.position.y < 0.5) {
      camera.position.y = 0.5
    }
  })

  return null
}

// ── POIMarkers ────────────────────────────────────────────────────────────────
function POIMarkers({ pois, onSelect }) {
  const selectedPOI = useStore((s) => s.selectedPOI)

  return (
    <group>
      {pois.map((poi) => {
        const isSelected = selectedPOI?.id === poi.id
        return (
          <group key={poi.id} position={[poi.x, poi.y + 0.8, poi.z]}>
            {/* Floating marker sphere */}
            <mesh
              onClick={(e) => { e.stopPropagation(); onSelect(poi) }}
              onPointerOver={(e) => { e.stopPropagation(); document.body.style.cursor = 'pointer' }}
              onPointerOut={() => { document.body.style.cursor = 'auto' }}
            >
              <sphereGeometry args={[0.15, 16, 16]} />
              <meshStandardMaterial
                color={isSelected ? '#ff9900' : '#00bfff'}
                emissive={isSelected ? '#ff6600' : '#0077aa'}
                emissiveIntensity={0.8}
              />
            </mesh>

            {/* Glowing ring */}
            <mesh rotation={[-Math.PI / 2, 0, 0]} position={[0, -0.6, 0]}>
              <ringGeometry args={[0.2, 0.28, 32]} />
              <meshBasicMaterial color={isSelected ? '#ff9900' : '#00bfff'} side={THREE.DoubleSide} />
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

// ── NavigationPath ────────────────────────────────────────────────────────────
function NavigationPath({ path }) {
  if (!path || path.length < 2) return null

  const points = path.map(([x, y, z]) => new THREE.Vector3(x, y + 0.05, z))
  const curve = new THREE.CatmullRomCurve3(points)
  const smoothPoints = curve.getPoints(Math.max(50, points.length * 5))

  return (
    <group>
      <Line
        points={smoothPoints}
        color="#ffdd00"
        lineWidth={5}
        dashed={false}
        transparent
        opacity={0.95}
      />
      <Line
        points={smoothPoints}
        color="#ff8800"
        lineWidth={12}
        transparent
        opacity={0.3}
      />
      <mesh position={points[0]}>
        <sphereGeometry args={[0.1, 16, 16]} />
        <meshStandardMaterial color="#00ff88" emissive="#00cc44" emissiveIntensity={1} />
      </mesh>
      <mesh position={points[points.length - 1]}>
        <sphereGeometry args={[0.1, 16, 16]} />
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
      fadeDistance={25}
      fadeStrength={1}
      followCamera={false}
      infiniteGrid={false}
    />
  )
}

// ── POI Placement Raycaster ───────────────────────────────────────────────────
function POIPlacementHandler({ onPlace }) {
  const { camera, scene: threeScene, gl } = useThree()
  const raycaster = useRef(new THREE.Raycaster())

  useEffect(() => {
    const canvas = gl.domElement

    const onDblClick = (e) => {
      const rect = canvas.getBoundingClientRect()
      const ndc = new THREE.Vector2(
        ((e.clientX - rect.left) / rect.width) * 2 - 1,
        -((e.clientY - rect.top) / rect.height) * 2 + 1,
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

import PhotosphereTour from './PhotosphereTour.jsx'

// ── Gaussian Splat Component ──────────────────────────────────────────────────
function PhotorealisticSplat({ splatUrl, invertY, sceneId, rotationZ = 0, rotationX = 0 }) {
  if (!splatUrl) return null

  // By default (invertY = false), rotation is [0, 0, 0] so ceiling is upright overhead.
  // If inverted, [Math.PI, 0, 0] flips it. rotationZ rolls, rotationX pitches.
  const rx = (invertY ? Math.PI : 0) + rotationX
  const rz = rotationZ
  const yPos = invertY ? 1.2 : 1.65

  return (
    <Suspense fallback={null}>
      <Splat
        key={`${sceneId}-${splatUrl}-${invertY}-${rx.toFixed(2)}-${rz.toFixed(2)}`}
        src={splatUrl}
        rotation={[rx, 0, rz]}
        position={[0, yPos, 0]}
        scale={[1, 1, 1]}
        alphaTest={0.05}
      />
    </Suspense>
  )
}

// ── Main 3D Viewer ────────────────────────────────────────────────────────────
export default function Viewer3D({ onPOIPlace }) {
  const { currentScene, pois, navigationPath, mode, selectPOI } = useStore()
  const [controlType, setControlType] = useState('orbit') // 'fps' | 'orbit'
  const [invertY, setInvertY] = useState(false) // Default upright: ceiling overhead
  const [tourData, setTourData] = useState(null)
  const [activeNodeId, setActiveNodeId] = useState(null)
  const [tourMode, setTourMode] = useState('photosphere') // 'photosphere' | 'dollhouse' | 'splat'

  // Rotation roll (Z) and pitch (X) in radians
  // Roomvid portrait video defaults to rotated left (+90 deg / Math.PI / 2)
  const isRoomvid = currentScene?.name?.toLowerCase().includes('roomvid')
  const [rotationZ, setRotationZ] = useState(isRoomvid ? Math.PI / 2 : 0)
  const [rotationX, setRotationX] = useState(0)

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
  const handlePitch = () => setRotationX((prev) => (prev + Math.PI / 2) % (2 * Math.PI))
  const handleReset = () => { setRotationZ(0); setRotationX(0); setInvertY(false) }

  const splatUrl = currentScene?.splat_path || '/static/models/scene.splat'

  // Fetch photosphere tour if available for this scene
  useEffect(() => {
    if (currentScene?.tour_path) {
      fetch(currentScene.tour_path)
        .then((res) => (res.ok ? res.json() : null))
        .then((data) => {
          if (data && data.nodes && data.nodes.length > 0) {
            setTourData(data)
            setActiveNodeId(data.default_node || data.nodes[0].id)
            setTourMode('photosphere')
          } else {
            setTourData(null)
            setTourMode('splat')
          }
        })
        .catch(() => {
          setTourData(null)
          setTourMode('splat')
        })
    } else {
      setTourData(null)
      setTourMode('splat')
    }
  }, [currentScene])

  const handleSelect = useCallback((poi) => {
    selectPOI(poi)
    // If in tour mode, find closest photosphere node to the POI
    if (tourData?.nodes) {
      let closestNode = null
      let minDist = Infinity
      for (const n of tourData.nodes) {
        const dx = n.position[0] - poi.x
        const dz = n.position[2] - poi.z
        const d = dx * dx + dz * dz
        if (d < minDist) {
          minDist = d
          closestNode = n
        }
      }
      if (closestNode) {
        setActiveNodeId(closestNode.id)
        setTourMode('photosphere')
      }
    }
  }, [selectPOI, tourData])

  const handlePlace = useCallback((position) => {
    if (onPOIPlace) onPOIPlace(position)
  }, [onPOIPlace])

  const activeNode = tourData?.nodes?.find(n => n.id === activeNodeId) || tourData?.nodes?.[0]
  const orbitTarget = (tourMode === 'photosphere' && activeNode)
    ? [activeNode.position[0], 1.65, activeNode.position[2] + 0.01]
    : [0, 0.8, 1.5]

  return (
    <div style={{ width: '100%', height: '100%', position: 'relative' }}>
      {/* View Switcher Toolbar */}
      <div style={{
        position: 'absolute',
        top: 14,
        left: 14,
        zIndex: 20,
        display: 'flex',
        flexWrap: 'wrap',
        gap: 8,
      }}>
        {/* Photosphere / Dollhouse / Splat Mode Switcher */}
        {tourData && (
          <div style={{
            display: 'flex',
            gap: 4,
            background: 'rgba(10, 20, 35, 0.9)',
            padding: 3,
            borderRadius: 8,
            border: '1px solid #1e3a5f',
            backdropFilter: 'blur(8px)',
          }}>
            <button
              onClick={() => setTourMode('photosphere')}
              style={{
                background: tourMode === 'photosphere' ? '#00e5ff' : 'transparent',
                color: tourMode === 'photosphere' ? '#0a101d' : '#00e5ff',
                border: 'none',
                borderRadius: 6,
                padding: '6px 12px',
                fontSize: 12,
                fontWeight: 700,
                cursor: 'pointer',
              }}
            >
              👁️ Photosphere POV
            </button>
            <button
              onClick={() => setTourMode('dollhouse')}
              style={{
                background: tourMode === 'dollhouse' ? '#00e5ff' : 'transparent',
                color: tourMode === 'dollhouse' ? '#0a101d' : '#00e5ff',
                border: 'none',
                borderRadius: 6,
                padding: '6px 12px',
                fontSize: 12,
                fontWeight: 700,
                cursor: 'pointer',
              }}
            >
              🏠 3D Dollhouse
            </button>
            <button
              onClick={() => setTourMode('splat')}
              style={{
                background: tourMode === 'splat' ? '#00e5ff' : 'transparent',
                color: tourMode === 'splat' ? '#0a101d' : '#00e5ff',
                border: 'none',
                borderRadius: 6,
                padding: '6px 12px',
                fontSize: 12,
                fontWeight: 700,
                cursor: 'pointer',
              }}
            >
              ✨ 3DGS Splats
            </button>
          </div>
        )}

        {/* Orbit / FPS Control Toggle (for Dollhouse & Splat views) */}
        {tourMode !== 'photosphere' && (
          <button
            onClick={() => setControlType(c => c === 'fps' ? 'orbit' : 'fps')}
            style={{
              background: 'rgba(10, 20, 35, 0.85)',
              border: '1px solid #00bfff',
              borderRadius: 8,
              color: '#00bfff',
              padding: '7px 14px',
              fontSize: 12,
              fontWeight: 700,
              cursor: 'pointer',
              backdropFilter: 'blur(8px)',
            }}
          >
            {controlType === 'fps' ? '🕹️ WASD Roam' : '🔄 Orbit View'}
          </button>
        )}

        {/* Orientation & Rotation Controls Toolbar */}
        <div style={{ display: 'flex', gap: 6, alignItems: 'center' }}>
          <button
            onClick={handleRotateLeft}
            title="Rotate 90 degrees to the left (counter-clockwise)"
            style={{
              background: 'rgba(10, 20, 35, 0.85)',
              border: '1px solid #00e5ff',
              borderRadius: 8,
              color: '#00e5ff',
              padding: '7px 12px',
              fontSize: 12,
              fontWeight: 700,
              cursor: 'pointer',
              backdropFilter: 'blur(8px)',
              display: 'flex',
              alignItems: 'center',
              gap: 4,
            }}
          >
            ↺ Rotate Left 90°
          </button>
          <button
            onClick={handleRotateRight}
            title="Rotate 90 degrees to the right (clockwise)"
            style={{
              background: 'rgba(10, 20, 35, 0.85)',
              border: '1px solid #00e5ff',
              borderRadius: 8,
              color: '#00e5ff',
              padding: '7px 12px',
              fontSize: 12,
              fontWeight: 700,
              cursor: 'pointer',
              backdropFilter: 'blur(8px)',
              display: 'flex',
              alignItems: 'center',
              gap: 4,
            }}
          >
            ↻ Rotate Right 90°
          </button>
          <button
            onClick={() => setInvertY(v => !v)}
            title="Flip 180 degrees upside down"
            style={{
              background: 'rgba(10, 20, 35, 0.85)',
              border: '1px solid #ff9900',
              borderRadius: 8,
              color: '#ffaa00',
              padding: '7px 12px',
              fontSize: 12,
              fontWeight: 700,
              cursor: 'pointer',
              backdropFilter: 'blur(8px)',
            }}
          >
            {invertY ? '🔄 Inverted' : '⬆️ Upright'}
          </button>
          {(rotationZ !== 0 || rotationX !== 0 || invertY) && (
            <button
              onClick={handleReset}
              title="Reset rotation to 0°"
              style={{
                background: 'rgba(30, 20, 20, 0.85)',
                border: '1px solid #ff4444',
                borderRadius: 8,
                color: '#ff6666',
                padding: '7px 10px',
                fontSize: 11,
                fontWeight: 700,
                cursor: 'pointer',
                backdropFilter: 'blur(8px)',
              }}
            >
              Reset ({(Math.round((rotationZ * 180) / Math.PI) + 360) % 360}°)
            </button>
          )}
        </div>

        {/* Active room indicator badge in Photosphere mode */}
        {tourMode === 'photosphere' && activeNode && (
          <div style={{
            background: 'rgba(10, 25, 45, 0.9)',
            border: '1px solid #00e5ff',
            borderRadius: 8,
            color: '#ffffff',
            padding: '7px 14px',
            fontSize: 12,
            fontWeight: 700,
            backdropFilter: 'blur(8px)',
            display: 'flex',
            alignItems: 'center',
            gap: 6,
          }}>
            <span style={{ color: '#00e5ff' }}>📍 Current Room:</span> {activeNode.name}
          </div>
        )}
      </div>

      <Canvas
        camera={{
          fov: tourMode === 'photosphere' ? 75 : 70,
          near: 0.1,
          far: 200,
          position: tourMode === 'photosphere' && activeNode
            ? [activeNode.position[0], 1.65, activeNode.position[2]]
            : [0, CAMERA_HEIGHT, -4]
        }}
        style={{ background: '#080c14' }}
        gl={{ antialias: true, alpha: false, powerPreference: 'high-performance' }}
      >
        {/* Environment Lights */}
        <ambientLight intensity={0.7} />
        <directionalLight position={[5, 12, 5]} intensity={1.0} />
        <hemisphereLight skyColor="#1a2a4a" groundColor="#0a0a0a" intensity={0.4} />

        {/* Floor Grid (hidden in human photosphere POV for pure realism) */}
        {tourMode !== 'photosphere' && <FloorGrid />}

        {/* Matterport / Google Street View Style Photosphere Tour */}
        {tourData && (tourMode === 'photosphere' || tourMode === 'dollhouse') && (
          <PhotosphereTour
            tourData={tourData}
            activeNodeId={activeNodeId}
            onNodeChange={setActiveNodeId}
            isDollhouse={tourMode === 'dollhouse'}
            onEnterPOV={() => setTourMode('photosphere')}
            rotationZ={rotationZ}
            rotationX={rotationX}
          />
        )}

        {/* 3D Gaussian Splats View */}
        {tourMode === 'splat' && (
          <PhotorealisticSplat
            key={`${currentScene?.id || 'default'}-${splatUrl}-${invertY}-${rotationZ}-${rotationX}`}
            sceneId={currentScene?.id}
            splatUrl={splatUrl}
            invertY={invertY}
            rotationZ={rotationZ}
            rotationX={rotationX}
          />
        )}

        {/* POI Markers (shown in Dollhouse & Splat modes) */}
        {tourMode !== 'photosphere' && <POIMarkers pois={pois} onSelect={handleSelect} />}

        {/* A* Navigation Path */}
        {navigationPath && <NavigationPath path={navigationPath} />}

        {/* Camera Controls */}
        {controlType === 'fps' && tourMode !== 'photosphere' ? (
          <FirstPersonControls enabled={mode === 'roam'} />
        ) : (
          <OrbitControls
            makeDefault
            enableDamping
            dampingFactor={0.05}
            target={orbitTarget}
            maxPolarAngle={tourMode === 'photosphere' ? Math.PI : Math.PI / 2 + 0.1}
            minDistance={tourMode === 'photosphere' ? 0.01 : 0.5}
            maxDistance={tourMode === 'photosphere' ? 0.2 : 50}
          />
        )}

        {/* POI placement handler (active in poi-select mode) */}
        {mode === 'poi-select' && <POIPlacementHandler onPlace={handlePlace} />}
      </Canvas>
    </div>
  )
}
