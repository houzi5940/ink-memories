import * as React from 'react'
import { GridMode } from './components/GridMode'
import { SwipeMode } from './components/SwipeMode'
import { MonthMode } from './components/MonthMode'
import { fetchUnanalyzedPhotos, submitForAnalysis, skipPhotos } from './api'
import type { Photo, ReviewMode } from './types'
import { BATCH_OPTIONS } from './types'

const MODE_CONFIG: Record<ReviewMode, { icon: string; label: string }> = {
  grid: { icon: '▦', label: '平铺' },
  swipe: { icon: '↔', label: '滑动' },
  month: { icon: '📅', label: '按月' },
}

export function App() {
  const [mode, setMode] = React.useState<ReviewMode>('grid')
  const [batchSize, setBatchSize] = React.useState(20)
  const [page, setPage] = React.useState(0)
  const [selected, setSelected] = React.useState<Set<string>>(new Set())
  const [submitting, setSubmitting] = React.useState(false)

  // Photo data
  const [photos, setPhotos] = React.useState<Photo[]>([])
  const [total, setTotal] = React.useState(0)
  const [loading, setLoading] = React.useState(true)
  const [error, setError] = React.useState('')

  // Swipe state
  const [swipeIndex, setSwipeIndex] = React.useState(0)
  const [swipeHistory, setSwipeHistory] = React.useState<
    { photo: string; action: 'select' | 'skip' }[]
  >([])

  // Dropdowns
  const [showModeMenu, setShowModeMenu] = React.useState(false)
  const [showBatchMenu, setShowBatchMenu] = React.useState(false)

  // Month grouping
  const monthGroups = React.useMemo(() => {
    const groups: Record<string, Photo[]> = {}
    photos.forEach((p) => {
      const m = (p.date || '').slice(0, 7)
      if (!m) return
      if (!groups[m]) groups[m] = []
      groups[m].push(p)
    })
    return Object.entries(groups).sort((a, b) => b[0].localeCompare(a[0]))
  }, [photos])

  // Load photos
  const loadPhotos = React.useCallback(async (lim: number, off: number) => {
    setLoading(true)
    setError('')
    try {
      const res = await fetchUnanalyzedPhotos(lim, off)
      setPhotos(res.photos)
      setTotal(res.total)
    } catch (e: any) {
      setError(e.message || '加载失败')
      setPhotos([])
    } finally {
      setLoading(false)
    }
  }, [])

  React.useEffect(() => {
    loadPhotos(batchSize, page * batchSize)
  }, [batchSize, page, loadPhotos])

  // Reset swipe state on page/batch change
  React.useEffect(() => {
    setSwipeIndex(0)
    setSwipeHistory([])
  }, [page, batchSize])

  const totalBatches = Math.max(1, Math.ceil(total / batchSize))

  // Selection
  const toggleSelect = React.useCallback((path: string) => {
    setSelected((prev) => {
      const next = new Set(prev)
      if (next.has(path)) next.delete(path)
      else next.add(path)
      return next
    })
  }, [])

  const toggleMonth = React.useCallback(
    (monthPhotos: Photo[]) => {
      const paths = monthPhotos.map((p) => p.path)
      const allSelected = paths.every((p) => selected.has(p))
      setSelected((prev) => {
        const next = new Set(prev)
        paths.forEach((p) => {
          if (allSelected) next.delete(p)
          else next.add(p)
        })
        return next
      })
    },
    [selected]
  )

  // Swipe
  const handleSwipe = React.useCallback(
    (action: 'select' | 'skip') => {
      const photo = photos[swipeIndex]
      if (!photo) return
      setSwipeHistory((prev) => [...prev, { photo: photo.path, action }])
      if (action === 'select') toggleSelect(photo.path)
      setSwipeIndex((prev) => prev + 1)
    },
    [photos, swipeIndex, toggleSelect]
  )

  const handleUndo = React.useCallback(() => {
    const last = swipeHistory[swipeHistory.length - 1]
    if (!last) return
    setSwipeHistory((prev) => prev.slice(0, -1))
    setSwipeIndex((prev) => prev - 1)
    if (last.action === 'select') {
      setSelected((prev) => {
        const next = new Set(prev)
        next.delete(last.photo)
        return next
      })
    }
  }, [swipeHistory])

  // Submit
  const handleSubmit = React.useCallback(async () => {
    if (selected.size === 0 || submitting) return
    setSubmitting(true)
    try {
      const selectedPaths = Array.from(selected)
      const skippedPaths = photos
        .map((p) => p.path)
        .filter((p) => !selected.has(p))

      // Submit selected for analysis
      const res = await submitForAnalysis({ paths: selectedPaths })
      console.log('Submit result:', res)

      // Skip unselected
      if (skippedPaths.length > 0) {
        await skipPhotos({ paths: skippedPaths })
      }

      // Clear selection for submitted photos
      setSelected((prev) => {
        const next = new Set(prev)
        selectedPaths.forEach((p) => next.delete(p))
        return next
      })

      // Reload current batch
      loadPhotos(batchSize, page * batchSize)
    } catch (e: any) {
      setError(e.message || '提交失败')
    } finally {
      setSubmitting(false)
    }
  }, [selected, photos, submitting, batchSize, page, loadPhotos])

  // Mode change
  const changeMode = React.useCallback((m: ReviewMode) => {
    setMode(m)
    setShowModeMenu(false)
  }, [])

  // Page navigation
  const prevPage = React.useCallback(() => {
    setPage((p) => Math.max(0, p - 1))
  }, [])

  const nextPage = React.useCallback(() => {
    setPage((p) => Math.min(totalBatches - 1, p + 1))
  }, [totalBatches])

  // Jump to a specific page (1-based input)
  const [pageInput, setPageInput] = React.useState('')
  const jumpToPage = React.useCallback(() => {
    const n = parseInt(pageInput, 10)
    if (isNaN(n)) return
    const target = Math.max(1, Math.min(totalBatches, n)) - 1
    setPage(target)
    setPageInput('')
  }, [pageInput, totalBatches])

  const swipeDone = swipeIndex >= photos.length

  return (
    <div className="max-w-2xl mx-auto min-h-screen flex flex-col bg-gray-50/80 pb-24">
      {/* ──────── Header ──────── */}
      <header className="sticky top-0 z-30 bg-white/90 backdrop-blur-lg border-b border-gray-100 px-4 pt-3 pb-2.5">
        <div className="flex items-center justify-between mb-2">
          <div className="flex items-center gap-2">
            <a
              href="/"
              className="inline-flex items-center justify-center w-8 h-8 rounded-lg text-gray-500 hover:bg-gray-100 active:bg-gray-200 transition-colors"
              aria-label="返回首页"
            >
              <svg className="w-5 h-5" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round">
                <path d="M19 12H5M12 19l-7-7 7-7"/>
              </svg>
            </a>
            <h1 className="text-lg font-bold text-gray-800">人工审核</h1>
          </div>
          {!loading && (
            <span className="text-xs text-gray-400 bg-gray-50 px-2.5 py-1 rounded-full">
              已选 <strong className="text-blue-600">{selected.size}</strong> 张
            </span>
          )}
        </div>
        <div className="flex items-center gap-2 text-sm">
          {/* Mode selector */}
          <div className="relative">
            <button
              className="flex items-center gap-1.5 bg-gray-100 rounded-lg px-3 py-1.5 text-gray-700 active:bg-gray-200"
              onClick={() => {
                setShowModeMenu((v) => !v)
                setShowBatchMenu(false)
              }}
            >
              <span>{MODE_CONFIG[mode].icon}</span>
              <span>{MODE_CONFIG[mode].label}</span>
              <svg
                className="w-3.5 h-3.5 text-gray-400"
                viewBox="0 0 20 20"
                fill="currentColor"
              >
                <path
                  fillRule="evenodd"
                  d="M5.23 7.21a.75.75 0 011.06.02L10 11.168l3.71-3.938a.75.75 0 111.08 1.04l-4.25 4.5a.75.75 0 01-1.08 0l-4.25-4.5a.75.75 0 01.02-1.06z"
                  clipRule="evenodd"
                />
              </svg>
            </button>
            {showModeMenu && (
              <div className="absolute top-full mt-1 left-0 bg-white rounded-xl shadow-xl border p-1.5 z-40 min-w-[160px]">
                {Object.entries(MODE_CONFIG).map(([key, cfg]) => (
                  <button
                    key={key}
                    className={`w-full flex items-center gap-2 px-3 py-2.5 rounded-lg text-sm ${
                      mode === key
                        ? 'bg-blue-50 text-blue-700 font-medium'
                        : 'text-gray-600 hover:bg-gray-50'
                    }`}
                    onClick={() => changeMode(key as ReviewMode)}
                  >
                    <span className="text-lg">{cfg.icon}</span>
                    <span>{cfg.label}</span>
                    {mode === key && (
                      <span className="ml-auto text-blue-500">✓</span>
                    )}
                  </button>
                ))}
              </div>
            )}
          </div>

          {/* Batch size */}
          <div className="relative">
            <button
              className="flex items-center gap-1 bg-gray-100 rounded-lg px-3 py-1.5 text-gray-700 active:bg-gray-200"
              onClick={() => {
                setShowBatchMenu((v) => !v)
                setShowModeMenu(false)
              }}
            >
              <span className="text-xs text-gray-400 mr-0.5">每批</span>
              <span className="font-medium">{batchSize}</span>
              <svg
                className="w-3.5 h-3.5 text-gray-400"
                viewBox="0 0 20 20"
                fill="currentColor"
              >
                <path
                  fillRule="evenodd"
                  d="M5.23 7.21a.75.75 0 011.06.02L10 11.168l3.71-3.938a.75.75 0 111.08 1.04l-4.25 4.5a.75.75 0 01-1.08 0l-4.25-4.5a.75.75 0 01.02-1.06z"
                  clipRule="evenodd"
                />
              </svg>
            </button>
            {showBatchMenu && (
              <div className="absolute top-full mt-1 left-0 bg-white rounded-xl shadow-xl border p-1.5 z-40 min-w-[120px]">
                {BATCH_OPTIONS.map((n) => (
                  <button
                    key={n}
                    className={`w-full px-3 py-2.5 rounded-lg text-sm ${
                      batchSize === n
                        ? 'bg-blue-50 text-blue-700 font-medium'
                        : 'text-gray-600 hover:bg-gray-50'
                    }`}
                    onClick={() => {
                      setBatchSize(n)
                      setShowBatchMenu(false)
                      setPage(0)
                    }}
                  >
                    {n} 张
                  </button>
                ))}
              </div>
            )}
          </div>

          {/* Page info */}
          {mode !== 'month' && !loading && total > 0 && (
            <span className="text-xs text-gray-400 ml-auto">
              {page * batchSize + 1}-{Math.min((page + 1) * batchSize, total)} /{' '}
              {total}
            </span>
          )}

          {loading && (
            <span className="text-xs text-blue-400 ml-auto animate-pulse">
              加载中...
            </span>
          )}
        </div>
      </header>

      {/* ──────── Error ──────── */}
      {error && (
        <div className="mx-3 mt-3 px-4 py-3 bg-red-50 text-red-600 text-sm rounded-xl">
          {error}
          <button
            className="ml-3 underline"
            onClick={() => loadPhotos(batchSize, page * batchSize)}
          >
            重试
          </button>
        </div>
      )}

      {/* ──────── Main content ──────── */}
      <div className="flex-1 px-3 mt-3">
        {loading ? (
          /* Loading shimmer */
          <div className="grid grid-cols-2 gap-2.5">
            {Array.from({ length: 6 }).map((_, i) => (
              <div
                key={i}
                className="bg-gray-200 rounded-xl animate-pulse"
                style={{ aspectRatio: '1' }}
              />
            ))}
          </div>
        ) : photos.length === 0 ? (
          /* Empty state */
          <div className="flex flex-col items-center justify-center py-20 text-center">
            <div className="text-5xl mb-4">🎉</div>
            <h2 className="text-lg font-bold text-gray-700">没有未评分的照片</h2>
            <p className="text-sm text-gray-400 mt-1">所有照片已完成评分</p>
          </div>
        ) : (
          <>
            {/* Grid mode */}
            {mode === 'grid' && (
              <div className="animate-fadeSlideIn">
                <GridMode
                  photos={photos}
                  selected={selected}
                  onToggle={toggleSelect}
                />
              </div>
            )}

            {/* Swipe mode */}
            {mode === 'swipe' && (
              <div className="animate-fadeSlideIn">
                <SwipeMode
                  photos={photos}
                  selected={selected}
                  swipeIndex={swipeIndex}
                  onSwipe={handleSwipe}
                  onUndo={handleUndo}
                  swipeHistory={swipeHistory}
                  onDone={nextPage}
                />
              </div>
            )}

            {/* Month mode */}
            {mode === 'month' && (
              <div className="animate-fadeSlideIn">
                <MonthMode
                  monthGroups={monthGroups}
                  selected={selected}
                  onToggle={toggleSelect}
                  onToggleMonth={toggleMonth}
                />
              </div>
            )}

            {/* Pagination (grid only) */}
            {mode === 'grid' && totalBatches > 1 && (
              <div className="flex justify-center items-center gap-4 mt-5 mb-4">
                <button
                  className={`px-4 py-2 rounded-xl text-sm font-medium ${
                    page === 0
                      ? 'text-gray-300'
                      : 'text-blue-600 bg-blue-50 active:bg-blue-100'
                  }`}
                  disabled={page === 0}
                  onClick={prevPage}
                >
                  ← 上一批
                </button>
                <span className="text-xs text-gray-400">
                  {page + 1} / {totalBatches}
                </span>
                <button
                  className={`px-4 py-2 rounded-xl text-sm font-medium ${
                    page >= totalBatches - 1
                      ? 'text-gray-300'
                      : 'text-blue-600 bg-blue-50 active:bg-blue-100'
                  }`}
                  disabled={page >= totalBatches - 1}
                  onClick={nextPage}
                >
                  下一批 →
                </button>
                <form
                  className="flex items-center gap-1.5 ml-1"
                  onSubmit={(e) => {
                    e.preventDefault()
                    jumpToPage()
                  }}
                >
                  <input
                    type="number"
                    min={1}
                    max={totalBatches}
                    value={pageInput}
                    onChange={(e) => setPageInput(e.target.value)}
                    placeholder="页码"
                    aria-label="跳转到指定批次"
                    className="w-14 px-2 py-1.5 text-sm text-center text-gray-700 bg-gray-100 rounded-lg border border-transparent focus:border-blue-400 focus:bg-white focus:outline-none"
                  />
                  <button
                    type="submit"
                    className="px-3 py-1.5 rounded-lg text-sm font-medium text-blue-600 bg-blue-50 active:bg-blue-100"
                  >
                    跳转
                  </button>
                </form>
              </div>
            )}
          </>
        )}
      </div>

      {/* ──────── Bottom bar ──────── */}
      <div className="fixed bottom-0 left-0 right-0 z-30 bg-white/80 backdrop-blur-lg border-t border-gray-100 px-4 py-3 safe-area-bottom">
        <div className="max-w-2xl mx-auto flex items-center justify-between">
          <div className="text-sm">
            <span className="text-gray-500">已选 </span>
            <span className="text-blue-600 font-bold text-lg">
              {selected.size}
            </span>
            <span className="text-gray-400 text-xs ml-1">张</span>
          </div>
          <button
            className={`px-6 py-2.5 rounded-xl text-sm font-bold transition-all active:scale-95 ${
              selected.size > 0 && !submitting
                ? 'bg-blue-500 text-white shadow-lg shadow-blue-200'
                : 'bg-gray-200 text-gray-400'
            }`}
            disabled={selected.size === 0 || submitting}
            onClick={handleSubmit}
          >
            {submitting ? '⏳ 提交中...' : '🚀 开始评分'}
          </button>
        </div>
      </div>
    </div>
  )
}
