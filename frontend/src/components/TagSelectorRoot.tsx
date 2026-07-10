import * as React from "react"
import { TagSelector, type TagOption } from "./TagSelector"

export interface TagSelectorState {
  availableTags: TagOption[]
  selectedTags: string[]
  disabled: boolean
}

export function TagSelectorRoot() {
  const [state, setState] = React.useState<TagSelectorState>({
    availableTags: [],
    selectedTags: [],
    disabled: false,
  })
  const selectedTagsRef = React.useRef<string[]>([])

  React.useEffect(() => {
    const handleUpdate = (e: Event) => {
      const detail = (e as CustomEvent<TagSelectorState>).detail
      setState((prev) => ({ ...prev, ...detail }))
    }

    const handleReset = () => {
      setState({ availableTags: [], selectedTags: [], disabled: false })
    }

    window.addEventListener("ink:tags:update", handleUpdate)
    window.addEventListener("ink:tags:reset", handleReset)

    // Expose current tags getter for legacy vanilla JS
    ;(window as unknown as Record<string, unknown>).getSelectedTags = () =>
      selectedTagsRef.current

    return () => {
      window.removeEventListener("ink:tags:update", handleUpdate)
      window.removeEventListener("ink:tags:reset", handleReset)
    }
  }, [])

  const handleChange = React.useCallback((tags: string[]) => {
    selectedTagsRef.current = tags
    setState((prev) => ({ ...prev, selectedTags: tags }))
  }, [])

  React.useEffect(() => {
    selectedTagsRef.current = state.selectedTags
  }, [state.selectedTags])

  return (
    <TagSelector
      availableTags={state.availableTags}
      selectedTags={state.selectedTags}
      onChange={handleChange}
      disabled={state.disabled}
    />
  )
}
