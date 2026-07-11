import type {
  UnanalyzedResponse,
  ReviewSubmitPayload,
  ReviewSubmitResponse,
} from './types'

const BASE = ''

/**
 * 获取未评分的照片列表（分页）
 */
export async function fetchUnanalyzedPhotos(
  limit: number,
  offset: number
): Promise<UnanalyzedResponse> {
  const res = await fetch(
    `${BASE}/api/review/photos?limit=${limit}&offset=${offset}`
  )
  if (!res.ok) throw new Error('获取照片失败')
  return res.json()
}

/**
 * 提交选中照片进行分析
 */
export async function submitForAnalysis(
  payload: ReviewSubmitPayload
): Promise<ReviewSubmitResponse> {
  const res = await fetch(`${BASE}/api/review/submit`, {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify(payload),
  })
  if (!res.ok) throw new Error('提交失败')
  return res.json()
}

/**
 * 跳过（标记无需分析）
 */
export async function skipPhotos(
  payload: ReviewSubmitPayload
): Promise<ReviewSubmitResponse> {
  const res = await fetch(`${BASE}/api/review/skip`, {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify(payload),
  })
  if (!res.ok) throw new Error('跳过失败')
  return res.json()
}
