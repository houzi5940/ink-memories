import * as React from "react"
import { Check, X, ChevronDown } from "lucide-react"
import { cn } from "@/lib/utils"

export interface TagOption {
  tag: string
  count: number
}

export interface TagSelectorProps {
  availableTags: TagOption[]
  selectedTags: string[]
  onChange: (tags: string[]) => void
  placeholder?: string
  disabled?: boolean
}

const DROPDOWN_MAX_HEIGHT = 220

export function TagSelector({
  availableTags,
  selectedTags,
  onChange,
  placeholder = "请选择或输入标签",
  disabled = false,
}: TagSelectorProps) {
  const [open, setOpen] = React.useState(false)
  const [inputValue, setInputValue] = React.useState("")
  const [dropUp, setDropUp] = React.useState(false)

  const containerRef = React.useRef<HTMLDivElement>(null)
  const inputRef = React.useRef<HTMLInputElement>(null)

  const selectedSet = React.useMemo(() => new Set(selectedTags), [selectedTags])

  const handleSelect = React.useCallback(
    (tag: string) => {
      const trimmed = tag.trim()
      if (!trimmed) return
      if (selectedSet.has(trimmed)) {
        onChange(selectedTags.filter((t) => t !== trimmed))
      } else {
        onChange([...selectedTags, trimmed])
      }
      setInputValue("")
      // 选择标签后保持下拉框展开，支持连续多选
      setOpen(true)
      inputRef.current?.focus()
    },
    [onChange, selectedSet, selectedTags]
  )

  const handleRemove = React.useCallback(
    (tag: string) => {
      onChange(selectedTags.filter((t) => t !== tag))
    },
    [onChange, selectedTags]
  )

  const filteredTags = React.useMemo(() => {
    const query = inputValue.trim().toLowerCase()
    return availableTags.filter(
      (opt) => !query || opt.tag.toLowerCase().includes(query)
    )
  }, [availableTags, inputValue])

  const canCreate = Boolean(
    inputValue.trim() &&
      !availableTags.some(
        (opt) => opt.tag.toLowerCase() === inputValue.trim().toLowerCase()
      ) &&
      !selectedSet.has(inputValue.trim())
  )

  // 仅当点击标签选择器外部区域时关闭下拉框
  React.useEffect(() => {
    if (!open) return
    const handleClickOutside = (e: MouseEvent) => {
      if (
        containerRef.current &&
        !containerRef.current.contains(e.target as Node)
      ) {
        setOpen(false)
      }
    }
    document.addEventListener("mousedown", handleClickOutside)
    return () => document.removeEventListener("mousedown", handleClickOutside)
  }, [open])

  // 智能定位：下方空间不足时向上翻转，随滚动/缩放实时重定位
  const updatePosition = React.useCallback(() => {
    const el = containerRef.current
    if (!el) return
    const rect = el.getBoundingClientRect()
    const spaceBelow = window.innerHeight - rect.bottom
    const spaceAbove = rect.top
    setDropUp(spaceBelow < DROPDOWN_MAX_HEIGHT && spaceAbove > spaceBelow)
  }, [])

  React.useEffect(() => {
    if (!open) return
    updatePosition()
    window.addEventListener("scroll", updatePosition, true)
    window.addEventListener("resize", updatePosition)
    return () => {
      window.removeEventListener("scroll", updatePosition, true)
      window.removeEventListener("resize", updatePosition)
    }
  }, [open, updatePosition])

  const handleKeyDown = (e: React.KeyboardEvent<HTMLInputElement>) => {
    if (e.key === "Enter") {
      e.preventDefault()
      if (canCreate) {
        handleSelect(inputValue)
      } else if (filteredTags.length === 1) {
        handleSelect(filteredTags[0].tag)
      }
    } else if (
      e.key === "Backspace" &&
      inputValue === "" &&
      selectedTags.length > 0
    ) {
      handleRemove(selectedTags[selectedTags.length - 1])
    } else if (e.key === "Escape") {
      setOpen(false)
    }
  }

  return (
    <div ref={containerRef} className="relative w-full space-y-2">
      {selectedTags.length > 0 && (
        <div className="flex flex-wrap gap-1.5">
          {selectedTags.map((tag) => (
            <span
              key={tag}
              className="inline-flex items-center gap-1 rounded-full bg-[#e85d3a] px-2.5 py-1 text-xs font-medium text-white"
            >
              {tag}
              <button
                type="button"
                onClick={() => handleRemove(tag)}
                className="inline-flex rounded-full p-0.5 hover:bg-white/20 focus:outline-none"
                aria-label={`移除标签 ${tag}`}
              >
                <X className="h-3 w-3" />
              </button>
            </span>
          ))}
        </div>
      )}

      <div
        role="combobox"
        aria-expanded={open}
        aria-controls="tag-selector-listbox"
        onClick={() => {
          if (disabled) return
          setOpen(true)
          inputRef.current?.focus()
        }}
        className={cn(
          "flex w-full cursor-text items-center gap-2 rounded-md border bg-white px-3 py-2 text-sm transition-colors",
          "border-[#e8e5e0] text-[#1a1a2e]",
          open && "border-[#e85d3a] ring-1 ring-[#e85d3a]",
          disabled && "cursor-not-allowed opacity-50"
        )}
      >
        <input
          ref={inputRef}
          type="text"
          value={inputValue}
          disabled={disabled}
          placeholder={placeholder}
          onChange={(e) => {
            setInputValue(e.target.value)
            setOpen(true)
          }}
          onFocus={() => setOpen(true)}
          onKeyDown={handleKeyDown}
          className="w-full flex-1 bg-transparent outline-none placeholder:text-[#9ca3af]"
        />
        <ChevronDown
          className={cn(
            "h-4 w-4 shrink-0 text-[#9ca3af] transition-transform",
            open && "rotate-180"
          )}
        />
      </div>

      {open && (
        <div
          id="tag-selector-listbox"
          role="listbox"
          className={cn(
            "absolute left-0 z-[9999] w-full overflow-auto rounded-md border border-[#e8e5e0] bg-white p-1 shadow-lg",
            dropUp ? "bottom-full mb-1" : "top-full mt-1"
          )}
          style={{ maxHeight: DROPDOWN_MAX_HEIGHT }}
        >
          {canCreate && (
            <>
              <div className="px-2 py-1.5 text-xs font-medium text-[#9ca3af]">
                新建标签
              </div>
              <button
                type="button"
                onClick={() => handleSelect(inputValue)}
                className="flex w-full items-center rounded-sm px-2 py-1.5 text-left text-sm text-[#1a1a2e] hover:bg-[#fef2ed] hover:text-[#e85d3a]"
              >
                <span className="truncate">新建标签：{inputValue.trim()}</span>
              </button>
            </>
          )}

          {filteredTags.length > 0 ? (
            <>
              <div className="px-2 py-1.5 text-xs font-medium text-[#9ca3af]">
                已有标签
              </div>
              {filteredTags.map((opt) => {
                const active = selectedSet.has(opt.tag)
                return (
                  <button
                    key={opt.tag}
                    type="button"
                    role="option"
                    aria-selected={active}
                    onClick={() => handleSelect(opt.tag)}
                    className="flex w-full items-center rounded-sm px-2 py-1.5 text-left text-sm text-[#1a1a2e] hover:bg-[#fef2ed] hover:text-[#e85d3a]"
                  >
                    <Check
                      className={cn(
                        "mr-2 h-4 w-4 shrink-0",
                        active ? "opacity-100 text-[#e85d3a]" : "opacity-0"
                      )}
                    />
                    <span className="flex-1 truncate">{opt.tag}</span>
                    <span className="ml-2 shrink-0 rounded-full bg-[#f3f2ef] px-1.5 py-0.5 text-[11px] font-medium text-[#9ca3af]">
                      {opt.count}
                    </span>
                  </button>
                )
              })}
            </>
          ) : (
            !canCreate && (
              <div className="px-2 py-3 text-center text-sm text-[#9ca3af]">
                输入文字创建新标签
              </div>
            )
          )}
        </div>
      )}
    </div>
  )
}
