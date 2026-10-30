import React, { useMemo } from 'react'
import * as THREE from 'three'
import { useGLTF } from '@react-three/drei'

export default function ProxyMeshView({ url, mode = 'dollhouse' }) {
  const { scene } = useGLTF(url)

  const preparedScene = useMemo(() => {
    const clone = scene.clone()
    clone.traverse((child) => {
      if (child.isMesh) {
        if (mode === 'dollhouse') {
          // In dollhouse mode: transparent or neutral architectural look
          child.material = new THREE.MeshStandardMaterial({
            color: '#b0c4de',
            roughness: 0.6,
            metalness: 0.1,
            side: THREE.DoubleSide,
            transparent: true,
            opacity: 0.85,
          })
        } else {
          // In free-roam mode: textured or shadow-receiving physical walls
          child.material = new THREE.MeshStandardMaterial({
            color: '#9aa8b8',
            roughness: 0.8,
            side: THREE.DoubleSide,
          })
        }
        child.castShadow = true
        child.receiveShadow = true
      }
    })
    return clone
  }, [scene, mode])

  return <primitive object={preparedScene} />
}

