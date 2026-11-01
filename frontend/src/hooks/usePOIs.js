import { useCallback } from 'react'
import { createPOI, getPOIs } from '../api/index.js'
import useStore from '../store/useStore.js'

/**
 * usePOIs
 * Provides helpers for fetching and creating POIs for the current scene.
 */
export default function usePOIs() {
  const { currentScene, setPOIs, addPOI } = useStore()

  const fetchPOIs = useCallback(async () => {
    if (!currentScene) return
    try {
      const data = await getPOIs(currentScene.id)
      setPOIs(data)
    } catch (err) {
      console.error('[usePOIs] fetchPOIs error:', err)
    }
  }, [currentScene, setPOIs])

  const submitPOI = useCallback(
    async ({ name, description, x, y, z }) => {
      if (!currentScene) return null
      try {
        const poi = await createPOI(currentScene.id, { name, description, x, y, z })
        addPOI(poi)
        return poi
      } catch (err) {
        console.error('[usePOIs] submitPOI error:', err)
        return null
      }
    },
    [currentScene, addPOI],
  )

  return { fetchPOIs, submitPOI }
}
