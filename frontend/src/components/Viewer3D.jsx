import React, { useEffect, useRef, useState, useCallback, Suspense, useMemo } from 'react'
import { Canvas, useThree } from '@react-three/fiber'
import { Splat, Text, Line, Grid, OrbitControls } from '@react-three/drei'
import * as THREE from 'three'

import useStore from '../store/useStore'
import usePOIs from '../hooks/usePOIs'
import PhotosphereTour from './PhotosphereTour'
import FreeRoamControls from './FreeRoamControls'
import ProxyMeshView from './ProxyMeshView'
import Minimap from './Minimap'
import POISearchBar from './POISearchBar'
import ARCompanion from './ARCompanion'

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

// ── Lazy Photoreal Splat Component ────────────────────────────────────────────
function PhotorealisticSplat({ splatUrl, rotationZ = 0, rotationX = 0 }) {
  if (!splatUrl) return null

  return (
    <Suspense fallback={null}>
      <Splat
        src={splatUrl}
        rotation={[rotationX, 0, rotationZ]}
        position={[0, 1.65, 0]}
        scale={[1, 1, 1]}
        alphaTest={0.05}
      />
    </Suspense>
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
    tourMode,
    setTourMode,
    activeNodeId,
    setActiveNodeId,
    collisionEnabled,
    setCollisionEnabled,
    tourData,
    setTourData,
  } = useStore()

  // Scene rotation adjustments if needed
  const [rotationZ, setRotationZ] = useState(0)
  const [rotationX, setRotationX] = useState(0)
  const [showAR, setShowAR] = useState(false)

  // 1. Fetch tour.json manifest on scene load
  useEffect(() => {
    const tourUrl = currentScene?.tour_path || '/static/panoramas/sample_scene/tour.json'
    fetch(tourUrl)
      .then((res) => (res.ok ? res.json() : null))
      .then((data) => {
        if (data && data.nodes && data.nodes.length > 0) {
          // Normalize base URL
          data.meta = data.meta || {}
          data.meta.base_url = tourUrl.substring(0, tourUrl.lastIndexOf('/'))
          setTourData(data)
          setActiveNodeId(data.default_node || data.nodes[0].id)
          setTourMode('photosphere')
        }
      })
      .catch((err) => console.warn('Could not load tour.json:', err))
  }, [currentScene?.id, setTourData, setActiveNodeId, setTourMode])

  // 2. Fetch or initialize POIs catalog
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

  // 3. Navigate to a POI: computes route and draws 3D ribbon
  const handleNavigateToPOI = useCallback(
    async (poi) => {
      selectPOI(poi)
      const targetPos = [poi.x, poi.y, poi.z]

      // Determine current player / camera position
      const activeNode = tourData?.nodes?.find((n) => n.id === activeNodeId) || tourData?.nodes?.[0]
      const currentPos = activeNode ? activeNode.position : [0, 1.65, 0]

      try {
        const sceneId = currentScene?.id || 5
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
          }
        } else {
          // Fallback direct path line
          setPath([currentPos, targetPos])
        }
      } catch (err) {
        setPath([currentPos, targetPos])
      }

      // Jump camera closer to target node if in photosphere mode
      if (tourData?.nodes) {
        let closest = null
        let minDist = Infinity
        for (const n of tourData.nodes) {
          const d = Math.hypot(n.position[0] - poi.x, n.position[2] - poi.z)
          if (d < minDist) {
            minDist = d
            closest = n
          }
        }
        if (closest && closest.id !== activeNodeId) {
          setActiveNodeId(closest.id)
        }
      }
    },
    [currentScene?.id, tourData, activeNodeId, selectPOI, setPath, setActiveNodeId]
  )

  const handlePOISelect = useCallback(
    (poi) => {
      handleNavigateToPOI(poi)
    },
    [handleNavigateToPOI]
  )

  const handlePlace = useCallback(
    (pos) => {
      if (onPOIPlace) onPOIPlace(pos)
    },
    [onPOIPlace]
  )

  // Asset URLs
  const tourBasePath = tourData?.meta?.base_url || '/static/panoramas/sample_scene'
  const proxyMeshUrl = `${tourBasePath}/mesh/proxy.glb`
  const navmeshUrl = `${tourBasePath}/mesh/navmesh.glb`
  const navgridUrl = `${tourBasePath}/nav/navgrid.json`
  const splatUrl = currentScene?.splat_path || '/static/models/scene.splat'

  const activeNode = tourData?.nodes?.find((n) => n.id === activeNodeId) || tourData?.nodes?.[0]
  const dollhouseTarget = activeNode ? [activeNode.position[0], 0.5, activeNode.position[2]] : [0, 0.5, 0]

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
        {/* Mode Selector Pill */}
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
              transition: 'all 0.15s',
            }}
          >
            👁️ Photosphere POV
          </button>
          <button
            onClick={() => setTourMode('freeroam')}
            style={{
              background: tourMode === 'freeroam' ? '#00e5ff' : 'transparent',
              color: tourMode === 'freeroam' ? '#0a101d' : '#00e5ff',
              border: 'none',
              borderRadius: 6,
              padding: '6px 12px',
              fontSize: 12,
              fontWeight: 700,
              cursor: 'pointer',
              transition: 'all 0.15s',
            }}
          >
            🚶 Free-Roam 3D
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
              transition: 'all 0.15s',
            }}
          >
            🏠 3D Dollhouse
          </button>
          <button
            onClick={() => setTourMode('splat')}
            style={{
              background: tourMode === 'splat' ? '#00e5ff' : 'transparent',
              color: tourMode === 'splat' ? '#0a101d' : '#88a0b5',
              border: 'none',
              borderRadius: 6,
              padding: '6px 12px',
              fontSize: 12,
              fontWeight: 700,
              cursor: 'pointer',
              transition: 'all 0.15s',
            }}
          >
            ✨ Photoreal (3DGS)
          </button>
          <button
            onClick={() => setShowAR(true)}
            style={{
              background: 'transparent',
              color: '#00ffcc',
              border: 'none',
              borderRadius: 6,
              padding: '6px 12px',
              fontSize: 12,
              fontWeight: 700,
              cursor: 'pointer',
              transition: 'all 0.15s',
            }}
          >
            📱 AR Companion
          </button>
        </div>

        {/* Collision Toggle (In Free-Roam Mode) */}
        {tourMode === 'freeroam' && (
          <button
            onClick={() => setCollisionEnabled(!collisionEnabled)}
            style={{
              background: collisionEnabled ? 'rgba(0, 229, 255, 0.15)' : 'rgba(255, 60, 60, 0.2)',
              color: collisionEnabled ? '#00e5ff' : '#ff5555',
              border: `1px solid ${collisionEnabled ? '#00e5ff' : '#ff5555'}`,
              borderRadius: 8,
              padding: '6px 12px',
              fontSize: 12,
              fontWeight: 700,
              cursor: 'pointer',
              backdropFilter: 'blur(8px)',
            }}
          >
            {collisionEnabled ? '🛡️ Navmesh Collision: ON' : '⚠️ Collision: OFF (Fly)'}
          </button>
        )}

        {/* POI Search Bar with Fuse.js */}
        <POISearchBar onNavigateToPOI={handleNavigateToPOI} />
      </div>

      {/* ── 3D Canvas Viewport ── */}
      <Canvas
        camera={{ position: [0, 1.65, 0], fov: 75, near: 0.1, far: 200 }}
        style={{ background: '#0a0e14' }}
      >
        <ambientLight intensity={0.9} />
        <directionalLight position={[10, 20, 10]} intensity={1.2} />

        {/* 1. Photosphere Tour Mode */}
        {tourMode === 'photosphere' && tourData && (
          <PhotosphereTour
            tourData={tourData}
            activeNodeId={activeNodeId}
            onNodeChange={setActiveNodeId}
            isDollhouse={false}
            rotationZ={rotationZ}
            rotationX={rotationX}
          />
        )}

        {/* 2. Free-Roam First-Person Mode */}
        {tourMode === 'freeroam' && (
          <>
            <FreeRoamControls enabled={true} navmeshUrl={navmeshUrl} />
            <Suspense fallback={null}>
              <ProxyMeshView url={proxyMeshUrl} mode="freeroam" />
            </Suspense>
          </>
        )}

        {/* 3. Dollhouse Orbit Mode */}
        {tourMode === 'dollhouse' && (
          <>
            <OrbitControls
              target={dollhouseTarget}
              maxPolarAngle={Math.PI / 2 - 0.05}
              minDistance={2}
              maxDistance={35}
              enableDamping
              dampingFactor={0.08}
            />
            <Suspense fallback={null}>
              <ProxyMeshView url={proxyMeshUrl} mode="dollhouse" />
            </Suspense>
            {tourData && (
              <PhotosphereTour
                tourData={tourData}
                activeNodeId={activeNodeId}
                onNodeChange={setActiveNodeId}
                isDollhouse={true}
                onEnterPOV={() => setTourMode('photosphere')}
              />
            )}
          </>
        )}

        {/* 4. Optional Photoreal 3DGS Mode (Lazy Loaded) */}
        {tourMode === 'splat' && (
          <>
            <OrbitControls target={[0, 1.2, 0]} enableDamping dampingFactor={0.08} />
            <PhotorealisticSplat splatUrl={splatUrl} rotationZ={rotationZ} rotationX={rotationX} />
          </>
        )}

        {/* Interactive Floor Markers & Navigation Ribbon */}
        <POIMarkers pois={pois} onSelect={handlePOISelect} />
        <NavigationPath path={navigationPath} />
        <FloorGrid />
        <POIPlacementHandler onPlace={handlePlace} />
      </Canvas>

      {/* ── Milestone M8: GTA-Style Radar Minimap ── */}
      <Minimap navgridUrl={navgridUrl} />

      {/* ── Mode Help Overlay Pill ── */}
      <div
        style={{
          position: 'absolute',
          bottom: 16,
          left: 16,
          background: 'rgba(10, 20, 35, 0.85)',
          padding: '6px 12px',
          borderRadius: 6,
          fontSize: 11,
          color: '#88a0b5',
          border: '1px solid rgba(255,255,255,0.08)',
          pointerEvents: 'none',
        }}
      >
        {tourMode === 'photosphere' && '🖱️ Drag to look | Click glowing floor pucks to travel | Double-click to drop POI'}
        {tourMode === 'freeroam' && '⌨️ WASD to walk | Shift to sprint | Mouse to look | Collision clamped to navmesh'}
        {tourMode === 'dollhouse' && '🖱️ Left-drag orbit | Right-drag pan | Scroll zoom | Click node or double-click to enter POV'}
        {tourMode === 'splat' && '✨ 3D Gaussian Splatting Photoreal Mode | Orbit around capture volume'}
      </div>

      {/* ── WebXR / 2D Compass AR Companion Modal ── */}
      {showAR && <ARCompanion onClose={() => setShowAR(false)} />}
    </div>
  )
}
