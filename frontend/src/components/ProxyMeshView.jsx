import React, { useMemo, Suspense } from 'react'
import * as THREE from 'three'
import { useGLTF } from '@react-three/drei'

function MeshModel({ url, rotation = [0, 0, 0], position = [0, 0, 0], scale = [1, 1, 1] }) {
  const { scene } = useGLTF(url)

  const preparedScene = useMemo(() => {
    if (!scene) return null
    const clone = scene.clone(true)
    clone.traverse((child) => {
      if (child.isMesh) {
        child.castShadow = true
        child.receiveShadow = true
        // If geometry contains vertex colors, preserve and display them with realistic lighting
        if (child.geometry?.attributes?.color) {
          child.material = new THREE.MeshStandardMaterial({
            vertexColors: true,
            roughness: 0.7,
            metalness: 0.1,
            side: THREE.DoubleSide,
          })
        } else {
          child.material = new THREE.MeshStandardMaterial({
            color: '#88a0b5',
            roughness: 0.7,
            metalness: 0.1,
            side: THREE.DoubleSide,
          })
        }
      }
    })
    return clone
  }, [scene])

  if (!preparedScene) return null
  return <primitive object={preparedScene} rotation={rotation} position={position} scale={scale} />
}

export default function ProxyMeshView({ url, rotation = [0, 0, 0], position = [0, 0, 0], scale = [1, 1, 1] }) {
  if (!url) return null
  return (
    <Suspense fallback={null}>
      <MeshModel url={url} rotation={rotation} position={position} scale={scale} />
    </Suspense>
  )
}
