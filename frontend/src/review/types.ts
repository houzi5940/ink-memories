/** 照片数据类型 */
export interface Photo {
  path: string
  date: string       // "2024-06-15"
  type: string       // "风景" | "人物" | ...
  color?: string     // 占位色（仅 mock 用）
  size?: string      // 文件大小
}

export type ReviewMode = 'grid' | 'swipe' | 'month'

export const BATCH_OPTIONS = [8, 12, 20, 30, 50] as const

/** 从后端返回的未评分照片列表 */
export interface UnanalyzedResponse {
  photos: Photo[]
  total: number
}

/** 提交/跳过请求 */
export interface ReviewSubmitPayload {
  paths: string[]
}

export interface ReviewSubmitResponse {
  status: string
  message?: string
  skipped?: number
}

/** 月份分组 */
export interface MonthGroup {
  monthKey: string    // "2024-06"
  photos: Photo[]
}
