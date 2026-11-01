import React, { useState, useEffect, useRef, Suspense, useMemo } from 'react'
import * as THREE from 'three'
import { useFrame, useThree, useLoader } from '@react-three/fiber'
import { Text, useGLTF } from '@react-three/drei'
import useStore from '../store/useStore'

// ── Progressive Texture Loader Cache ──────────────────────────────────────────
const textureCache = new Map()

function useProgressiveTexture(lodUrl, highResUrl) {
  const [texture, setTexture] = useState(() => textureCache.get(highResUrl) || textureCache.get(lodUrl) || null)

  useEffect(() => {
    let isMounted = true
    const loader = new THREE.TextureLoader()

    // 1. If high-res already in cache, use immediately
    if (highResUrl && textureCache.has(highResUrl)) {
      setTexture(textureCache.get(highResUrl))
      return
    }

    // 2. Load low-res preview LOD first (< 100ms)
    if (lodUrl && !textureCache.has(lodUrl)) {
      loader.load(lodUrl, (lodTex) => {
        if (!isMounted) return
        lodTex.wrapS = THREE.RepeatWrapping
        lodTex.repeat.x = -1
        lodTex.colorSpace = THREE.SRGBColorSpace
        lodTex.needsUpdate = true
        textureCache.set(lodUrl, lodTex)
        if (!textureCache.has(highResUrl)) {
          setTexture(lodTex)
        }
      })
    }

    // 3. Load full 4096x2048 production texture and upgrade
    if (highResUrl) {
      loader.load(highResUrl, (highTex) => {
        if (!isMounted) return
        highTex.wrapS = THREE.RepeatWrapping
        highTex.repeat.x = -1
        highTex.colorSpace = THREE.SRGBColorSpace
        highTex.needsUpdate = true
        textureCache.set(highResUrl, highTex)
        setTexture(highTex)
      })
    }

    return () => {
      isMounted = false
    }
  }, [lodUrl, highResUrl])

  return texture
}

// ── SpherePanorama Component ──────────────────────────────────────────────────
function SpherePanorama({ lodUrl, highResUrl, opacity = 1.0, rotationZ = 0, rotationX = 0 }) {
  const texture = useProgressiveTexture(lodUrl, highResUrl)

  return (
    <mesh rotation={[rotationX, 0, rotationZ]}>
      <sphereGeometry args={[30, 60, 40]} />
      {texture ? (
        <meshBasicMaterial
          map={texture}
          side={THREE.BackSide}
          transparent={opacity < 1.0}
          opacity={opacity}
          depthWrite={false}
        />
      ) : (
        <meshBasicMaterial color="#141a24" side={THREE.BackSide} />
      )}
    </mesh>
  )
}

// ── Projective Transition Proxy Mesh (SPHR-Style Parallax Flight) ─────────────
function ProjectiveProxyMesh({ proxyUrl, textureUrl, nodePos, progress }) {
  const { scene } = useGLTF(proxyUrl)
  const texture = useMemo(() => {
    if (!textureUrl) return null
    return textureCache.get(textureUrl) || new THREE.TextureLoader().load(textureUrl)
  }, [textureUrl])

  // Fade out proxy mesh near arrival as destination panorama sphere crossfades in
  const opacity = useMemo(() => {
    if (progress < 0.7) return 0.95
    return Math.max(0.0, 1.0 - (progress - 0.7) / 0.3)
  }, [progress])

  const clonedScene = useMemo(() => {
    const clone = scene.clone()
    clone.traverse((child) => {
      if (child.isMesh) {
        child.material = new THREE.MeshBasicMaterial({
          map: texture,
          transparent: true,
          opacity: opacity,
          side: THREE.DoubleSide,
        })
      }
    })
    return clone
  }, [scene, texture, opacity])

  return <primitive object={clonedScene} />
}

// ── Interactive Navigation Puck ───────────────────────────────────────────────
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

  const pos = [node.position[0], 0.04, node.position[2]]

  return (
    <group position={pos}>
      {/* Outer pulsing ring */}
      <mesh
        ref={ringRef}
        rotation={[-Math.PI / 2, 0, 0]}
        onClick={(e) => {
          e.stopPropagation()
          onClick(node.id)
        }}
        onPointerOver={(e) => {
          e.stopPropagation()
          setHovered(true)
          document.body.style.cursor = 'pointer'
        }}
        onPointerOut={() => {
          setHovered(false)
          document.body.style.cursor = 'auto'
        }}
      >
        <ringGeometry args={[0.35, 0.48, 32]} />
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
        onClick={(e) => {
          e.stopPropagation()
          onClick(node.id)
        }}
      >
        <circleGeometry args={[0.26, 32]} />
        <meshBasicMaterial
          color={hovered ? '#ff7700' : '#0088cc'}
          side={THREE.DoubleSide}
          transparent
          opacity={0.65}
        />
      </mesh>

      {/* Label */}
      <Text
        position={[0, 0.45, 0]}
        fontSize={0.22}
        color={hovered ? '#ffdd00' : '#ffffff'}
        anchorX="center"
        anchorY="bottom"
        outlineWidth={0.02}
        outlineColor="#000000"
      >
        {node.name || `Node ${node.id.toUpperCase()}`}
      </Text>
    </group>
  )
}

// ── SPHR Projective Flight Controller ─────────────────────────────────────────
function TravelNavigator({ startPos, targetPos, isTravelling, onTravelEnd, onProgress }) {
  const { camera } = useThree()
  const progressRef = useRef(0)
  const durationSec = 0.75 // 750ms fluid transition

  useFrame((state, delta) => {
    if (!isTravelling) return

    progressRef.current += delta / durationSec
    const p = Math.min(1.0, progressRef.current)

    // Smooth cubic ease-in-out curve
    const ease = p < 0.5 ? 4 * p * p * p : 1 - Math.pow(-2 * p + 2, 3) / 2

    const currentPos = new THREE.Vector3().lerpVectors(
      new THREE.Vector3(...startPos),
      new THREE.Vector3(...targetPos),
      ease
    )
    camera.position.copy(currentPos)
    if (onProgress) onProgress(p)

    if (p >= 1.0) {
      camera.position.set(...targetPos)
      progressRef.current = 0
      if (onTravelEnd) onTravelEnd()
    }
  })

  return null
}

// ── PhotosphereTour Main Component ────────────────────────────────────────────
export default function PhotosphereTour({
  tourData,
  activeNodeId,
  onNodeChange,
  isDollhouse = false,
  onEnterPOV,
  rotationZ = 0,
  rotationX = 0,
}) {
  const [travelling, setTravelling] = useState(false)
  const [travelStartNode, setTravelStartNode] = useState(null)
  const [travelTargetNode, setTravelTargetNode] = useState(null)
  const [travelProgress, setTravelProgress] = useState(0)

  const { camera } = useThree()
  const nodes = tourData?.nodes || []
  const activeNode = nodes.find((n) => n.id === activeNodeId) || nodes[0]

  // Resolve base asset path
  const tourBasePath = useMemo(() => {
    const raw = tourData?.meta?.base_url || '/static/panoramas/sample_scene'
    return raw.endsWith('/') ? raw.slice(0, -1) : raw
  }, [tourData])

  // Preload neighboring node textures in background
  useEffect(() => {
    if (!activeNode || !nodes) return
    const loader = new THREE.TextureLoader()
    const neighborIds = activeNode.neighbors || []
    nodes
      .filter((n) => neighborIds.includes(n.id))
      .forEach((n) => {
        const lodUrl = `${tourBasePath}/${n.pano?.lod_url || `panos/${n.id}_lod.jpg`}`
        if (!textureCache.has(lodUrl)) {
          loader.load(lodUrl, (tex) => {
            tex.wrapS = THREE.RepeatWrapping
            tex.repeat.x = -1
            textureCache.set(lodUrl, tex)
          })
        }
      })
  }, [activeNode, nodes, tourBasePath])

  // Connected neighbors for floor pucks
  const connectedNodes = useMemo(() => {
    if (!activeNode || !nodes) return []
    const neighborSet = new Set(activeNode.neighbors || [])
    return nodes.filter((n) => neighborSet.has(n.id))
  }, [activeNode, nodes])

  const handlePuckClick = (targetId) => {
    if (travelling || targetId === activeNode?.id) return
    const targetNode = nodes.find((n) => n.id === targetId)
    if (!targetNode) return

    setTravelStartNode(activeNode)
    setTravelTargetNode(targetNode)
    setTravelling(true)
    setTravelProgress(0)

    if (onNodeChange) onNodeChange(targetId)
  }

  const handleTravelEnd = () => {
    setTravelling(false)
    setTravelStartNode(null)
    setTravelTargetNode(null)
    setTravelProgress(1.0)
  }

  const activePos = activeNode ? [activeNode.position[0], 1.65, activeNode.position[2]] : [0, 1.65, 0]
  const startPos = travelStartNode ? [travelStartNode.position[0], 1.65, travelStartNode.position[2]] : activePos
  const targetPos = travelTargetNode ? [travelTargetNode.position[0], 1.65, travelTargetNode.position[2]] : activePos

  const activePanoUrl = activeNode ? `${tourBasePath}/${activeNode.pano?.url || `panos/${activeNode.id}.jpg`}` : null
  const activeLodUrl = activeNode ? `${tourBasePath}/${activeNode.pano?.lod_url || `panos/${activeNode.id}_lod.jpg`}` : null
  const proxyMeshUrl = `${tourBasePath}/mesh/proxy.glb`

  return (
    <group>
      {/* 1. Active Spherical Panorama (POV Mode) */}
      {!isDollhouse && activeNode && (
        <group position={activePos}>
          <Suspense fallback={null}>
            <SpherePanorama
              key={`pano-${activeNode.id}-${rotationZ}-${rotationX}`}
              lodUrl={activeLodUrl}
              highResUrl={activePanoUrl}
              opacity={travelling ? Math.min(1.0, (travelProgress - 0.7) / 0.3) : 1.0}
              rotationZ={rotationZ}
              rotationX={rotationX}
            />
          </Suspense>
        </group>
      )}

      {/* 2. SPHR Projective Proxy Mesh during Travel Flight */}
      {!isDollhouse && travelling && travelStartNode && (
        <Suspense fallback={null}>
          <ProjectiveProxyMesh
            proxyUrl={proxyMeshUrl}
            textureUrl={`${tourBasePath}/${travelStartNode.pano?.url || `panos/${travelStartNode.id}.jpg`}`}
            nodePos={travelStartNode.position}
            progress={travelProgress}
          />
        </Suspense>
      )}

      {/* 3. Navigation Floor Pucks at Connected Neighbors */}
      {!isDollhouse &&
        !travelling &&
        connectedNodes.map((n) => (
          <NavigationPuck key={n.id} node={n} onClick={handlePuckClick} />
        ))}

      {/* 4. Dollhouse Node Markers */}
      {isDollhouse &&
        nodes.map((n) => {
          const isActive = n.id === activeNode?.id
          return (
            <group key={n.id} position={[n.position[0], 0.25, n.position[2]]}>
              <mesh
                onClick={(e) => {
                  e.stopPropagation()
                  if (onNodeChange) onNodeChange(n.id)
                  if (onEnterPOV) onEnterPOV()
                }}
                onPointerOver={(e) => {
                  e.stopPropagation()
                  document.body.style.cursor = 'pointer'
                }}
                onPointerOut={() => {
                  document.body.style.cursor = 'auto'
                }}
              >
                <sphereGeometry args={[0.22, 24, 24]} />
                <meshStandardMaterial
                  color={isActive ? '#ffaa00' : '#00e5ff'}
                  emissive={isActive ? '#ff5500' : '#0088cc'}
                  emissiveIntensity={0.8}
                />
              </mesh>
              <Text
                position={[0, 0.4, 0]}
                fontSize={0.24}
                color={isActive ? '#ffdd00' : '#ffffff'}
                anchorX="center"
                anchorY="bottom"
                outlineWidth={0.02}
                outlineColor="#000000"
              >
                {n.name || `Node ${n.id.toUpperCase()}`}
              </Text>
            </group>
          )
        })}

      {/* 5. Smooth Glide Flight Controller */}
      {!isDollhouse && travelling && (
        <TravelNavigator
          startPos={startPos}
          targetPos={targetPos}
          isTravelling={travelling}
          onProgress={setTravelProgress}
          onTravelEnd={handleTravelEnd}
        />
      )}
    </group>
  )
}
