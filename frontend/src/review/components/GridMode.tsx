import * as React from 'react'
import type { Photo } from '../types'

interface GridModeProps {
  photos: Photo[]
  selected: Set<string>
  onToggle: (path: string) => void
}

/** 平铺勾选模式 */
export function GridMode({ photos, selected, onToggle }: GridModeProps) {
  return (
    <div className="grid grid-cols-2 sm:grid-cols-3 gap-2.5">
      {photos.map((photo) => (
        <GridCard
          key={photo.path}
          photo={photo}
          selected={selected.has(photo.path)}
          onToggle={onToggle}
        />
      ))}
    </div>
  )
}

function GridCard({
  photo,
  selected,
  onToggle,
}: {
  photo: Photo
  selected: boolean
  onToggle: (path: string) => void
}) {
  const imgRef = React.useRef<HTMLImageElement>(null)
  const [loaded, setLoaded] = React.useState(false)

  const thumbUrl = `/photo/${encodeURI(photo.path.replace(/^\//, ''))}`

  return (
    <div
      className={`relative rounded-xl overflow-hidden bg-white shadow-sm cursor-pointer active:scale-[0.97] transition-all ${
        selected ? 'ring-2 ring-blue-500 ring-offset-1' : ''
      }`}
      onClick={() => onToggle(photo.path)}
    >
      <div className="w-full aspect-square relative bg-gray-100">
        {!loaded && (
          <div className="absolute inset-0 flex items-center justify-center text-gray-300 text-3xl">
            📷
          </div>
        )}
        <img
          ref={imgRef}
          src={thumbUrl}
          alt=""
          loading="lazy"
          className={`w-full h-full object-cover transition-opacity duration-300 ${
            loaded ? 'opacity-100' : 'opacity-0'
          }`}
          onLoad={() => setLoaded(true)}
          onError={(e) => {
            setLoaded(true)
            ;(e.target as HTMLImageElement).style.display = 'none'
          }}
        />
        {/* Check overlay */}
        <div
          className={`absolute inset-0 transition-all duration-200 ${
            selected
              ? 'bg-blue-500/10 border-3 border-blue-500 opacity-100'
              : 'opacity-0'
          }`}
          style={{ borderRadius: 'inherit' }}
        >
          <div className="absolute top-1.5 right-1.5 w-7 h-7 rounded-full bg-blue-500 flex items-center justify-center shadow-md">
            <span className="text-white text-sm font-bold">✓</span>
          </div>
        </div>
      </div>
      <div className="px-2 py-1.5 flex justify-between items-center">
        <span className="text-[11px] text-gray-500">
          {photo.date?.slice(5) || ''}
        </span>
        {photo.type && (
          <span className="text-[10px] bg-gray-100 px-1.5 py-0.5 rounded-full text-gray-500">
            {photo.type}
          </span>
        )}
      </div>
    </div>
  )
}
