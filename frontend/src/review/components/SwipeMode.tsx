import * as React from 'react'
import type { Photo } from '../types'

interface SwipeModeProps {
  photos: Photo[]
  selected: Set<string>
  swipeIndex: number
  onSwipe: (action: 'select' | 'skip') => void
  onUndo: () => void
  swipeHistory: { photo: string; action: 'select' | 'skip' }[]
  onDone: () => void
}

/** 滑动选择模式 — Tinder风格左右滑 */
export function SwipeMode({
  photos,
  selected,
  swipeIndex,
  onSwipe,
  onUndo,
  swipeHistory,
  onDone,
}: SwipeModeProps) {
  const swipeDone = swipeIndex >= photos.length

  // 键盘快捷键
  React.useEffect(() => {
    const handler = (e: KeyboardEvent) => {
      if (swipeDone) return
      if (e.key === 'ArrowLeft') onSwipe('skip')
      if (e.key === 'ArrowRight') onSwipe('select')
    }
    window.addEventListener('keydown', handler)
    return () => window.removeEventListener('keydown', handler)
  }, [swipeDone, onSwipe])

  if (swipeDone) {
    return (
      <DoneOverlay
        total={photos.length}
        selectedCount={swipeHistory.filter((h) => h.action === 'select').length}
        onContinue={onDone}
      />
    )
  }

  return (
    <div className="space-y-3">
      {/* Progress dots */}
      <div className="flex justify-center gap-1.5 px-4">
        {photos.slice(0, Math.min(photos.length, 30)).map((p, i) => (
          <div
            key={i}
            className={`h-1.5 rounded-full transition-all duration-200 ${
              i === swipeIndex
                ? 'w-3 bg-blue-500'
                : i < swipeIndex
                ? 'w-1.5 bg-gray-300'
                : 'w-1.5 bg-gray-200'
            }`}
          />
        ))}
      </div>

      {/* Card stack */}
      <div className="relative flex justify-center" style={{ minHeight: '460px' }}>
        <div className="w-full max-w-sm relative" style={{ perspective: '1000px' }}>
          {[2, 1, 0].map((offset) => {
            const idx = swipeIndex + offset
            const photo = photos[idx]
            if (!photo) return null
            const scale = 1 - offset * 0.04
            return (
              <SwipeCard
                key={photo.path}
                photo={photo}
                isTop={offset === 0}
                onSwipe={onSwipe}
                style={{
                  transform: `scale(${scale}) translateY(${offset * 8}px)`,
                  zIndex: 10 - offset,
                }}
              />
            )
          })}

          {/* Hint */}
          {swipeIndex === 0 && (
            <div className="absolute -bottom-1 left-0 right-0 text-center text-xs text-gray-400">
              左滑跳过 · 右滑选中 · 键盘 ← →
            </div>
          )}
        </div>
      </div>

      {/* Undo button */}
      {swipeHistory.length > 0 && (
        <div className="flex justify-center">
          <button
            className="flex items-center gap-1.5 px-4 py-2 rounded-xl bg-gray-100 text-gray-600 text-sm font-medium active:bg-gray-200"
            onClick={onUndo}
          >
            <span>↩</span> 撤销
          </button>
        </div>
      )}
    </div>
  )
}

// ── Swipeable card ──
function SwipeCard({
  photo,
  isTop,
  onSwipe,
  style,
}: {
  photo: Photo
  isTop: boolean
  onSwipe: (action: 'select' | 'skip') => void
  style: React.CSSProperties
}) {
  const ref = React.useRef<HTMLDivElement>(null)
  const labelRef = React.useRef<HTMLDivElement>(null)
  const drag = React.useRef({ startX: 0, startY: 0, dx: 0, dy: 0, dragging: false })

  const thumbUrl = `/photo/${encodeURI(photo.path.replace(/^\//, ''))}`
  const [imgLoaded, setImgLoaded] = React.useState(false)

  const onTouchStart = (e: React.TouchEvent) => {
    if (!isTop) return
    const t = e.touches[0]
    drag.current = { startX: t.clientX, startY: t.clientY, dx: 0, dy: 0, dragging: true }
    ref.current?.classList.add('!transition-none')
  }

  const onTouchMove = (e: React.TouchEvent) => {
    if (!drag.current.dragging) return
    const t = e.touches[0]
    const dx = t.clientX - drag.current.startX
    const dy = t.clientY - drag.current.startY
    drag.current.dx = dx
    drag.current.dy = dy
    const el = ref.current
    if (!el) return
    const rot = Math.min(20, Math.abs(dx) / 8) * Math.sign(dx)
    el.style.transform = `translateX(${dx}px) rotate(${rot}deg)`
    el.style.opacity = String(Math.max(0.3, 1 - Math.abs(dx) / 600))

    if (labelRef.current) {
      const sel = labelRef.current.querySelector('.swipe-label-sel') as HTMLElement | null
      const skp = labelRef.current.querySelector('.swipe-label-skp') as HTMLElement | null
      const intensity = Math.min(1, Math.abs(dx) / 150)
      if (dx > 0) {
        if (sel) sel.style.opacity = String(intensity)
        if (skp) skp.style.opacity = '0'
      } else {
        if (skp) skp.style.opacity = String(intensity)
        if (sel) sel.style.opacity = '0'
      }
    }
  }

  const onTouchEnd = () => {
    if (!drag.current.dragging) return
    drag.current.dragging = false
    const el = ref.current
    if (!el) return
    el.classList.remove('!transition-none')
    const dx = drag.current.dx
    if (Math.abs(dx) > 80) {
      const dir = dx > 0 ? 'right' : 'left'
      el.style.transition = 'transform 0.25s ease, opacity 0.25s ease'
      el.style.transform = `translateX(${dir === 'right' ? '120%' : '-120%'}) rotate(${dir === 'right' ? 12 : -12}deg)`
      el.style.opacity = '0'
      setTimeout(() => onSwipe(dir === 'right' ? 'select' : 'skip'), 220)
    } else {
      el.style.transform = ''
      el.style.opacity = ''
      if (labelRef.current) {
        labelRef.current.querySelectorAll('[class*="swipe-label"]').forEach((l) => {
          ;(l as HTMLElement).style.opacity = '0'
        })
      }
    }
  }

  return (
    <div
      ref={ref}
      className="swipe-card absolute inset-x-0 rounded-2xl overflow-hidden bg-white shadow-xl select-none touch-none"
      style={style}
      onTouchStart={onTouchStart}
      onTouchMove={onTouchMove}
      onTouchEnd={onTouchEnd}
    >
      <div ref={labelRef} className="relative">
        <div className="w-full aspect-[4/3] relative bg-gray-100">
          {!imgLoaded && (
            <div className="absolute inset-0 flex items-center justify-center text-gray-300 text-5xl">
              📷
            </div>
          )}
          <img
            src={thumbUrl}
            alt=""
            className={`w-full h-full object-cover transition-opacity duration-300 ${
              imgLoaded ? 'opacity-100' : 'opacity-0'
            }`}
            onLoad={() => setImgLoaded(true)}
            onError={() => setImgLoaded(true)}
          />
          {/* Swipe labels */}
          <div
            className="swipe-label-sel absolute top-8 right-4 px-5 py-2 rounded-lg font-bold text-2xl tracking-wider border-4"
            style={{ color: '#22c55e', borderColor: '#22c55e', transform: 'rotate(8deg)', opacity: 0, pointerEvents: 'none' }}
          >
            选中
          </div>
          <div
            className="swipe-label-skp absolute top-8 left-4 px-5 py-2 rounded-lg font-bold text-2xl tracking-wider border-4"
            style={{ color: '#ef4444', borderColor: '#ef4444', transform: 'rotate(-8deg)', opacity: 0, pointerEvents: 'none' }}
          >
            跳过
          </div>
        </div>
      </div>
      <div className="p-3.5">
        <div className="flex justify-between items-center">
          <span className="text-sm font-medium text-gray-800">
            {photo.date || ''}
          </span>
          {photo.type && (
            <span className="text-xs bg-gray-100 px-2 py-0.5 rounded-full text-gray-600">
              {photo.type}
            </span>
          )}
        </div>
        <p className="text-xs text-gray-400 mt-1 truncate">{photo.path}</p>
      </div>
    </div>
  )
}

// ── Done overlay ──
function DoneOverlay({
  total,
  selectedCount,
  onContinue,
}: {
  total: number
  selectedCount: number
  onContinue: () => void
}) {
  return (
    <div className="flex flex-col items-center justify-center py-20 text-center">
      <div className="text-5xl mb-4">🎉</div>
      <h2 className="text-lg font-bold text-gray-700">本批已看完</h2>
      <p className="text-sm text-gray-400 mt-1">
        选中 <strong className="text-blue-600">{selectedCount}</strong> 张 /
        共 {total} 张
      </p>
      <button
        className="mt-6 px-6 py-2.5 rounded-xl bg-blue-500 text-white font-medium active:bg-blue-600 shadow-lg shadow-blue-200"
        onClick={onContinue}
      >
        继续下一批 →
      </button>
    </div>
  )
}
