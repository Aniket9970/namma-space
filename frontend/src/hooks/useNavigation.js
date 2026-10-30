import { useCallback } from 'react'
import { getPath } from '../api/index.js'
import useStore from '../store/useStore.js'

/**
 * useNavigation
 * Fetches the A* path between two POIs and stores it in the global store.
 */
export default function useNavigation() {
  const { currentScene, setPath, setMode, setLoading } = useStore()

  const navigate = useCallback(
    async (fromPoiId, toPoiId) => {
      if (!currentScene) return
      setLoading(true)
      try {
        const data = await getPath(currentScene.id, fromPoiId, toPoiId)
        setPath(data.path)
        setMode('navigate')
      } catch (err) {
        console.error('[useNavigation] navigate error:', err)
        setPath(null)
      } finally {
        setLoading(false)
      }
    },
    [currentScene, setPath, setMode, setLoading],
  )

  const clearPath = useCallback(() => {
    setPath(null)
    setMode('roam')
  }, [setPath, setMode])

  return { navigate, clearPath }
}
