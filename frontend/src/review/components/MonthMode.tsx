import * as React from 'react'
import type { Photo } from '../types'

interface MonthModeProps {
  monthGroups: [string, Photo[]][]
  selected: Set<string>
  onToggle: (path: string) => void
  onToggleMonth: (photos: Photo[]) => void
}

/** 按月浏览模式 */
export function MonthMode({
  monthGroups,
  selected,
  onToggle,
  onToggleMonth,
}: MonthModeProps) {
  if (monthGroups.length === 0) {
    return (
      <div className="flex flex-col items-center justify-center py-20 text-center">
        <div className="text-5xl mb-4">📭</div>
        <h2 className="text-lg font-bold text-gray-500">暂无未评分照片</h2>
      </div>
    )
  }

  return (
    <div className="space-y-3">
      {monthGroups.map(([monthKey, photos]) => (
        <MonthGroup
          key={monthKey}
          monthKey={monthKey}
          photos={photos}
          selected={selected}
          onToggle={onToggle}
          onToggleAll={() => onToggleMonth(photos)}
        />
      ))}
    </div>
  )
}

function MonthGroup({
  monthKey,
  photos,
  selected,
  onToggle,
  onToggleAll,
}: {
  monthKey: string
  photos: Photo[]
  selected: Set<string>
  onToggle: (path: string) => void
  onToggleAll: () => void
}) {
  const [open, setOpen] = React.useState(true)
  const contentRef = React.useRef<HTMLDivElement>(null)

  const allSelected = photos.every((p) => selected.has(p.path))
  const someSelected = photos.some((p) => selected.has(p.path))

  const monthLabel = monthKey.replace(/^\d{4}-/, '')

  return (
    <div className="bg-white rounded-2xl overflow-hidden shadow-sm border border-gray-100">
      <button
        className="w-full flex items-center justify-between px-4 py-3.5 active:bg-gray-50"
        onClick={() => setOpen((v) => !v)}
      >
        <div className="flex items-center gap-2">
          <svg
            className={`w-4 h-4 text-gray-400 transition-transform ${
              open ? 'rotate-90' : ''
            }`}
            viewBox="0 0 20 20"
            fill="currentColor"
          >
            <path
              fillRule="evenodd"
              d="M7.21 14.77a.75.75 0 01.02-1.06L11.168 10 7.23 6.29a.75.75 0 111.04-1.08l4.5 4.25a.75.75 0 010 1.08l-4.5 4.25a.75.75 0 01-1.06-.02z"
              clipRule="evenodd"
            />
          </svg>
          <span className="font-semibold text-gray-800">
            {monthLabel}月
          </span>
          <span className="text-xs text-gray-400">{photos.length} 张</span>
        </div>
        <button
          className={`px-2.5 py-1 rounded-lg text-xs font-medium transition-colors ${
            allSelected
              ? 'bg-blue-100 text-blue-700'
              : someSelected
              ? 'bg-blue-50 text-blue-500'
              : 'bg-gray-100 text-gray-400'
          }`}
          onClick={(e) => {
            e.stopPropagation()
            onToggleAll()
          }}
        >
          {allSelected
            ? '✓ 全选'
            : someSelected
            ? `已选 ${photos.filter((p) => selected.has(p.path)).length}`
            : '全选'}
        </button>
      </button>

      <div
        ref={contentRef}
        className="overflow-hidden transition-all duration-300"
        style={{
          maxHeight: open ? `${Math.ceil(photos.length / 4) * 130 + 16}px` : '0',
        }}
      >
        <div className="px-3 pb-3 grid grid-cols-4 gap-2">
          {photos.map((photo) => (
            <MonthCard
              key={photo.path}
              photo={photo}
              selected={selected.has(photo.path)}
              onToggle={onToggle}
            />
          ))}
        </div>
      </div>
    </div>
  )
}

function MonthCard({
  photo,
  selected,
  onToggle,
}: {
  photo: Photo
  selected: boolean
  onToggle: (path: string) => void
}) {
  const [loaded, setLoaded] = React.useState(false)
  const thumbUrl = `/photo/${encodeURI(photo.path.replace(/^\//, ''))}`

  return (
    <div
      className={`relative rounded-xl overflow-hidden bg-gray-100 cursor-pointer active:scale-95 transition-all ${
        selected ? 'ring-2 ring-blue-500 ring-offset-1' : ''
      }`}
      onClick={() => onToggle(photo.path)}
    >
      <div className="w-full relative">
        {!loaded && (
          <div className="aspect-square flex items-center justify-center text-gray-300 text-lg">
            📷
          </div>
        )}
        <img
          src={thumbUrl}
          alt=""
          loading="lazy"
          className={`w-full h-auto block transition-opacity ${
            loaded ? 'opacity-100' : 'opacity-0 absolute inset-0'
          }`}
          onLoad={() => setLoaded(true)}
          onError={() => setLoaded(true)}
        />
      </div>

      {selected && (
        <div className="absolute top-1 right-1 w-5 h-5 bg-blue-500 rounded-full flex items-center justify-center shadow">
          <span className="text-white text-[10px] font-bold">✓</span>
        </div>
      )}

      <div className="absolute bottom-0 left-0 right-0 bg-gradient-to-t from-black/40 to-transparent p-1">
        <span className="text-[9px] text-white/90">
          {photo.date?.slice(8)}日
        </span>
      </div>
    </div>
  )
}
