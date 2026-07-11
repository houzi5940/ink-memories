import * as React from "react"
import { createRoot } from "react-dom/client"
import { TagSelectorRoot } from "@/components/TagSelectorRoot"
import "./index.css"

function mountTagSelector() {
  const container = document.getElementById("tag-selector-root")
  if (!container) return

  const root = createRoot(container)
  root.render(
    <React.StrictMode>
      <TagSelectorRoot />
    </React.StrictMode>
  )
}

if (document.readyState === "loading") {
  document.addEventListener("DOMContentLoaded", mountTagSelector)
} else {
  mountTagSelector()
}
