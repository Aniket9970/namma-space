import React, { useState, useEffect, useRef, Suspense, useMemo } from 'react'
import * as THREE from 'three'
import { useFrame, useThree, useLoader } from '@react-three/fiber'
import { Text } from '@react-three/drei'

// ── Photosphere Sphere Component ──────────────────────────────────────────────
function SpherePanorama({ imageUrl, opacity = 1.0, rotationZ = 0, rotationX = 0 }) {
  const texture = useLoader(THREE.TextureLoader, imageUrl)
  
  useEffect(() => {
    if (texture) {
      texture.wrapS = THREE.RepeatWrapping
      texture.repeat.x = -1 // Flip horizontally for interior view
      texture.needsUpdate = true
    }
  }, [texture])

  return (
    <mesh rotation={[rotationX, 0, rotationZ]}>
      <sphereGeometry args={[25, 60, 40]} />
      <meshBasicMaterial
        map={texture}
        side={THREE.BackSide}
        transparent={opacity < 1.0}
        opacity={opacity}
        depthWrite={false}
      />
    </mesh>
  )
}

// ── Animated Floor Navigation Puck (Google Street View / Matterport style) ─────
function NavigationPuck({ node, onClick }) {
  const [hovered, setHovered] = useState(false)
  const ringRef = useRef()

  useFrame(({ clock }) => {
    if (ringRef.current) {
      const t = clock.getElapsedTime()
      const s = 1.0 + 0.08 * Math.sin(t * 3.5)
      ringRef.current.scale.set(s, s, s)
    }
  })

  // Ground level at node XZ coordinates
  const pos = [node.position[0], 0.04, node.position[2]]

  return (
    <group position={pos}>
      {/* Outer pulsing ring */}
      <mesh
        ref={ringRef}
        rotation={[-Math.PI / 2, 0, 0]}
        onClick={(e) => { e.stopPropagation(); onClick(node.id) }}
        onPointerOver={(e) => { e.stopPropagation(); setHovered(true); document.body.style.cursor = 'pointer' }}
        onPointerOut={() => { setHovered(false); document.body.style.cursor = 'auto' }}
      >
        <ringGeometry args={[0.35, 0.45, 32]} />
        <meshBasicMaterial
          color={hovered ? '#ffaa00' : '#00e5ff'}
          side={THREE.DoubleSide}
          transparent
          opacity={hovered ? 0.95 : 0.75}
        />
      </mesh>

      {/* Inner solid disc */}
      <mesh
        rotation={[-Math.PI / 2, 0, 0]}
        onClick={(e) => { e.stopPropagation(); onClick(node.id) }}
      >
        <circleGeometry args={[0.25, 32]} />
        <meshBasicMaterial
          color={hovered ? '#ff7700' : '#0088cc'}
          side={THREE.DoubleSide}
          transparent
          opacity={0.6}
        />
      </mesh>

      {/* Hover Room Label */}
      <Text
        position={[0, 0.45, 0]}
        fontSize={0.22}
        color={hovered ? '#ffdd00' : '#ffffff'}
        anchorX="center"
        anchorY="bottom"
        outlineWidth={0.02}
        outlineColor="#000000"
      >
        {node.name}
      </Text>
    </group>
  )
}

// ── Smooth Camera Transition Controller ───────────────────────────────────────
function CameraNavigator({ targetPos, isTransitioning, onTransitionComplete }) {
  const { camera } = useThree()
  const targetVec = useMemo(() => new THREE.Vector3(...targetPos), [targetPos])

  useFrame((state, delta) => {
    if (!isTransitioning) return

    // Smooth exponential approach
    camera.position.lerp(targetVec, Math.min(1.0, delta * 5.0))

    if (camera.position.distanceTo(targetVec) < 0.05) {
      camera.position.copy(targetVec)
      if (onTransitionComplete) onTransitionComplete()
    }
  })

  return null
}

// ── Main Photosphere Tour Root ────────────────────────────────────────────────
export default function PhotosphereTour({
  tourData,
  activeNodeId,
  onNodeChange,
  isDollhouse = false,
  onEnterPOV,
  rotationZ = 0,
  rotationX = 0,
}) {
  const [transitioning, setTransitioning] = useState(false)
  const { camera } = useThree()

  const nodes = tourData?.nodes || []
  const activeNode = nodes.find((n) => n.id === activeNodeId) || nodes[0]

  // Connected neighbors for floor pucks
  const connectedNodes = useMemo(() => {
    if (!activeNode || !nodes) return []
    const connIds = new Set(activeNode.connections || [])
    return nodes.filter((n) => connIds.has(n.id))
  }, [activeNode, nodes])

  const handlePuckClick = (targetId) => {
    if (transitioning) return
    setTransitioning(true)
    if (onNodeChange) onNodeChange(targetId)
  }

  const handleTransitionEnd = () => {
    setTransitioning(false)
  }

  // When active node changes, ensure camera smoothly aligns to that node's eye height
  const eyePosition = activeNode ? [activeNode.position[0], 1.65, activeNode.position[2]] : [0, 1.65, 0]

  return (
    <group>
      {/* Active Room Photosphere (Rendered in POV mode) */}
      {!isDollhouse && activeNode && (
        <group position={[activeNode.position[0], 1.65, activeNode.position[2]]}>
          <Suspense fallback={null}>
            <SpherePanorama
              key={`${activeNode.image_url}-${rotationZ}-${rotationX}`}
              imageUrl={activeNode.image_url}
              rotationZ={rotationZ}
              rotationX={rotationX}
            />
          </Suspense>
        </group>
      )}

      {/* Navigation Floor Pucks (Only shown in Human POV mode for adjacent rooms) */}
      {!isDollhouse &&
        connectedNodes.map((n) => (
          <NavigationPuck
            key={n.id}
            node={n}
            onClick={handlePuckClick}
          />
        ))}

      {/* Dollhouse Mode: All Waypoint Markers in 3D Overview */}
      {isDollhouse &&
        nodes.map((n) => {
          const isActive = n.id === activeNode?.id
          return (
            <group key={n.id} position={[n.position[0], 0.2, n.position[2]]}>
              <mesh
                onClick={(e) => {
                  e.stopPropagation()
                  if (onNodeChange) onNodeChange(n.id)
                  if (onEnterPOV) onEnterPOV()
                }}
                onPointerOver={(e) => { e.stopPropagation(); document.body.style.cursor = 'pointer' }}
                onPointerOut={() => { document.body.style.cursor = 'auto' }}
              >
                <sphereGeometry args={[0.22, 24, 24]} />
                <meshStandardMaterial
                  color={isActive ? '#ff9900' : '#00e5ff'}
                  emissive={isActive ? '#ff5500' : '#0088cc'}
                  emissiveIntensity={0.8}
                />
              </mesh>
              <Text
                position={[0, 0.4, 0]}
                fontSize={0.25}
                color={isActive ? '#ffdd00' : '#ffffff'}
                anchorX="center"
                anchorY="bottom"
                outlineWidth={0.02}
                outlineColor="#000000"
              >
                {n.name}
              </Text>
            </group>
          )
        })}

      {/* Smooth glide camera navigator */}
      {!isDollhouse && (
        <CameraNavigator
          targetPos={eyePosition}
          isTransitioning={transitioning}
          onTransitionComplete={handleTransitionEnd}
        />
      )}
    </group>
  )
}

