import React, { useEffect, useRef, useState } from 'react'
import * as THREE from 'three'
import { useFrame, useThree } from '@react-three/fiber'
import { useGLTF } from '@react-three/drei'
import { Pathfinding } from 'three-pathfinding'
import useStore from '../store/useStore'
import useKeyboard from '../hooks/useKeyboard'

const WALK_SPEED = 2.5       // metres per second
const SPRINT_SPEED = 5.0     // metres per second with Shift
const LOOK_SENSITIVITY = 0.0022
const MAX_PITCH_RAD = (85 * Math.PI) / 180
const EYE_HEIGHT = 1.65      // canonical eye height in metres

export default function FreeRoamControls({ enabled, navmeshUrl }) {
  const { camera, gl } = useThree()
  const keysRef = useKeyboard()

  const {
    collisionEnabled,
    setPlayerPosition,
    setPlayerYaw,
    isAutoWalking,
    setIsAutoWalking,
    navigationPath,
  } = useStore()

  const yawRef = useRef(0)
  const pitchRef = useRef(0)
  const isLockedRef = useRef(false)

  // Auto-walk waypoint follower state
  const autoWalkIndexRef = useRef(0)
  const autoWalkParamRef = useRef(0.0)

  // 1. Initialize Navmesh Collision Zone
  const pathfindingRef = useRef(null)
  const zoneCreatedRef = useRef(false)
  const currentNavNodeRef = useRef(null)

  // Load navmesh GLTF if provided
  const navmeshGLTF = useGLTF(navmeshUrl || '/static/panoramas/sample_scene/mesh/navmesh.glb')

  useEffect(() => {
    if (!navmeshGLTF || zoneCreatedRef.current) return
    try {
      const pf = new Pathfinding()
      let foundGeom = null

      navmeshGLTF.scene.traverse((child) => {
        if (child.isMesh && child.geometry && !foundGeom) {
          foundGeom = child.geometry.clone()
        }
      })

      if (foundGeom) {
        const zone = Pathfinding.createZone(foundGeom)
        pf.setZoneData('venue', zone)
        pathfindingRef.current = pf
        zoneCreatedRef.current = true
        console.log('[OK] Initialized three-pathfinding navmesh collision zone.')
      }
    } catch (err) {
      console.warn('Failed to initialize navmesh collision zone:', err)
    }
  }, [navmeshGLTF])

  // 2. Pointer Lock & Mouse Look
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

  // Reset auto-walk index on path change
  useEffect(() => {
    autoWalkIndexRef.current = 0
    autoWalkParamRef.current = 0.0
  }, [navigationPath])

  // 3. Movement & Collision Loop (60 FPS)
  useFrame((_, delta) => {
    if (!enabled) return

    // Apply look orientation
    camera.rotation.order = 'YXZ'
    camera.rotation.set(pitchRef.current, yawRef.current, 0)

    // A) Auto-Walking Guidance Along Navigation Ribbon
    if (isAutoWalking && navigationPath && navigationPath.length >= 2) {
      const idx = autoWalkIndexRef.current
      if (idx < navigationPath.length - 1) {
        const p1 = new THREE.Vector3(navigationPath[idx][0], EYE_HEIGHT, navigationPath[idx][2] ?? navigationPath[idx][1])
        const p2 = new THREE.Vector3(navigationPath[idx + 1][0], EYE_HEIGHT, navigationPath[idx + 1][2] ?? navigationPath[idx + 1][1])

        const segDist = p1.distanceTo(p2)
        const walkSpeed = 1.3 // m/s
        autoWalkParamRef.current += (walkSpeed * delta) / Math.max(0.1, segDist)

        if (autoWalkParamRef.current >= 1.0) {
          autoWalkIndexRef.current += 1
          autoWalkParamRef.current = 0.0
          camera.position.copy(p2)
        } else {
          camera.position.lerpVectors(p1, p2, autoWalkParamRef.current)
          // Face in direction of travel
          const dir = new THREE.Vector3().subVectors(p2, p1).normalize()
          if (dir.lengthSq() > 0.01) {
            const targetYaw = Math.atan2(-dir.x, -dir.z)
            yawRef.current = THREE.MathUtils.lerp(yawRef.current, targetYaw, delta * 4.0)
          }
        }
      } else {
        // Reached destination
        setIsAutoWalking(false)
      }
    }
    // B) Standard WASD Free-Roam
    else {
      const speed = keysRef.current.shift ? SPRINT_SPEED : WALK_SPEED
      const move = new THREE.Vector3()

      if (keysRef.current.w) move.z -= 1
      if (keysRef.current.s) move.z += 1
      if (keysRef.current.a) move.x -= 1
      if (keysRef.current.d) move.x += 1

      if (move.lengthSq() > 0) {
        move.normalize().multiplyScalar(speed * delta)
        const yawQuat = new THREE.Quaternion().setFromEuler(new THREE.Euler(0, yawRef.current, 0, 'YXZ'))
        move.applyQuaternion(yawQuat)

        const targetPos = camera.position.clone().add(move)

        // Apply three-pathfinding NavMesh Clamp
        if (collisionEnabled && pathfindingRef.current) {
          try {
            const pf = pathfindingRef.current
            const groupID = pf.getGroup('venue', camera.position) || 0
            if (!currentNavNodeRef.current) {
              currentNavNodeRef.current = pf.getClosestNode(camera.position, 'venue', groupID)
            }
            if (currentNavNodeRef.current) {
              const clamped = new THREE.Vector3()
              currentNavNodeRef.current = pf.clampStep(
                camera.position,
                targetPos,
                currentNavNodeRef.current,
                'venue',
                groupID,
                clamped
              )
              camera.position.copy(clamped)
            } else {
              camera.position.copy(targetPos)
            }
          } catch (e) {
            camera.position.copy(targetPos)
          }
        } else {
          camera.position.copy(targetPos)
        }
      }
    }

    // Keep camera at canonical eye height
    camera.position.y = EYE_HEIGHT

    // Sync state for minimap and UI
    setPlayerPosition([camera.position.x, camera.position.y, camera.position.z])
    setPlayerYaw(yawRef.current)
  })

  return null
}

