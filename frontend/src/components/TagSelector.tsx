import * as React from "react"
import { Check, X, ChevronDown } from "lucide-react"
import { cn } from "@/lib/utils"
import { Button } from "@/components/ui/button"
import {
  Command,
  CommandEmpty,
  CommandGroup,
  CommandInput,
  CommandItem,
  CommandList,
} from "@/components/ui/command"
import {
  Popover,
  PopoverContent,
  PopoverTrigger,
} from "@/components/ui/popover"

export interface TagSelectorProps {
  availableTags: string[]
  selectedTags: string[]
  onChange: (tags: string[]) => void
  placeholder?: string
  disabled?: boolean
}

export function TagSelector({
  availableTags,
  selectedTags,
  onChange,
  placeholder = "请选择或输入标签",
  disabled = false,
}: TagSelectorProps) {
  const [open, setOpen] = React.useState(false)
  const [inputValue, setInputValue] = React.useState("")

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
      (tag) => !query || tag.toLowerCase().includes(query)
    )
  }, [availableTags, inputValue])

  const canCreate =
    inputValue.trim() &&
    !availableTags.some(
      (t) => t.toLowerCase() === inputValue.trim().toLowerCase()
    ) &&
    !selectedSet.has(inputValue.trim())

  return (
    <div className="w-full space-y-2">
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

      <Popover open={open} onOpenChange={setOpen}>
        <PopoverTrigger asChild>
          <Button
            variant="outline"
            role="combobox"
            aria-expanded={open}
            disabled={disabled}
            className={cn(
              "w-full justify-between bg-white font-normal hover:bg-[#faf9f7]",
              "border-[#e8e5e0] text-[#1a1a2e]",
              open && "border-[#e85d3a] ring-1 ring-[#e85d3a]"
            )}
          >
            <span className="text-[#9ca3af]">{placeholder}</span>
            <ChevronDown
              className={cn(
                "h-4 w-4 shrink-0 text-[#9ca3af] transition-transform",
                open && "rotate-180"
              )}
            />
          </Button>
        </PopoverTrigger>
        <PopoverContent
          className="w-full min-w-[var(--radix-popover-trigger-width)] border-[#e8e5e0] p-0 shadow-lg"
          align="start"
          sideOffset={4}
          side="top"
          avoidCollisions
          collisionPadding={8}
        >
          <Command
            className="rounded-md bg-white"
            filter={(value, search) => {
              if (!search) return 1
              return value.toLowerCase().includes(search.toLowerCase()) ? 1 : 0
            }}
          >
            <CommandInput
              placeholder="搜索或输入新标签..."
              value={inputValue}
              onValueChange={setInputValue}
            />
            <CommandList>
              <CommandEmpty className="py-3 text-sm text-[#9ca3af]">
                输入文字创建新标签
              </CommandEmpty>
              {canCreate && (
                <CommandGroup heading="新建标签">
                  <CommandItem
                    value={`__create__${inputValue}`}
                    onSelect={() => handleSelect(inputValue)}
                    className="text-[#1a1a2e] aria-selected:bg-[#fef2ed] aria-selected:text-[#e85d3a]"
                  >
                    <span className="truncate">新建标签：{inputValue.trim()}</span>
                  </CommandItem>
                </CommandGroup>
              )}
              {filteredTags.length > 0 && (
                <CommandGroup heading="已有标签">
                  {filteredTags.map((tag) => (
                    <CommandItem
                      key={tag}
                      value={tag}
                      onSelect={() => handleSelect(tag)}
                      className="text-[#1a1a2e] aria-selected:bg-[#fef2ed] aria-selected:text-[#e85d3a]"
                    >
                      <Check
                        className={cn(
                          "mr-2 h-4 w-4 shrink-0",
                          selectedSet.has(tag)
                            ? "opacity-100 text-[#e85d3a]"
                            : "opacity-0"
                        )}
                      />
                      <span className="truncate">{tag}</span>
                    </CommandItem>
                  ))}
                </CommandGroup>
              )}
            </CommandList>
          </Command>
        </PopoverContent>
      </Popover>
    </div>
  )
}
