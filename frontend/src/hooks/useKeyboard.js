import { useEffect, useRef } from 'react'

/**
 * useKeyboard
 * Tracks WASD + Shift key states via keydown/keyup events.
 * Returns a ref object (keysRef) so consumers can read without causing re-renders.
 */
export default function useKeyboard() {
  const keysRef = useRef({
    w: false,
    a: false,
    s: false,
    d: false,
    shift: false,
  })

  useEffect(() => {
    const onKeyDown = (e) => {
      const k = e.key.toLowerCase()
      if (k === 'w') keysRef.current.w = true
      if (k === 'a') keysRef.current.a = true
      if (k === 's') keysRef.current.s = true
      if (k === 'd') keysRef.current.d = true
      if (k === 'shift') keysRef.current.shift = true
    }

    const onKeyUp = (e) => {
      const k = e.key.toLowerCase()
      if (k === 'w') keysRef.current.w = false
      if (k === 'a') keysRef.current.a = false
      if (k === 's') keysRef.current.s = false
      if (k === 'd') keysRef.current.d = false
      if (k === 'shift') keysRef.current.shift = false
    }

    window.addEventListener('keydown', onKeyDown)
    window.addEventListener('keyup', onKeyUp)
    return () => {
      window.removeEventListener('keydown', onKeyDown)
      window.removeEventListener('keyup', onKeyUp)
    }
  }, [])

  return keysRef
}
