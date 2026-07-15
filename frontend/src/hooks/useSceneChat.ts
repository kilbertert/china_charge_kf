import { useState } from 'react'

export type RiskLevel = 'low' | 'medium' | 'high' | 'urgent'

export type ChitchatPayload = {
  text: string
  intentHint?: string
}

export type SceneResponse =
  | {
      scene: 'report'
      risk_level: RiskLevel
      confidence: number
      payloadKind?: 'complete' | 'insufficient_data' | 'report_done'
      payload: ReportPayload | ReportInsufficientPayload | ReportDonePayload
    }
  | {
      scene: 'symptom'
      risk_level: RiskLevel
      confidence: number
      payload: SymptomPayload | SymptomDonePayload
    }
  | {
      scene: 'product'
      risk_level: 'low'
      confidence: number
      payload: { productRef?: string; knowledgeBaseAnswer?: string }
    }
  | {
      scene: 'chitchat'
      risk_level: 'low'
      confidence: number
      payload: ChitchatPayload
    }

export type ReportMetric = {
  name: string
  value: number
  level: string
  unit: string
}

export type TValueChart = {
  normal: number
  yours: number | null
  thresholds: { normal: number; loss: number }
}

export type RiskDistributionItem = { name: string; value: number }

export type ProblemPriorityItem = { rank: number; name: string; level: string }

export type ReportPayload = {
  reportType: 'bone_density'
  dataComplete: boolean
  metrics: ReportMetric[]
  tValueChart?: TValueChart
  riskDistribution: RiskDistributionItem[]
  oneLineConclusion: string
  problemPriority: ProblemPriorityItem[]
  questionnaireRef?: string  // 可选:LLM 动态生成问题时,后端不再返回此字段
  questions?: SymptomQuestion[]  // LLM 动态生成的 3-5 个跟进问题(替代 hardcoded 12 题)
}

export type ReportInsufficientPayload = {
  reportType: 'bone_density'
  dataComplete: false
  reason: 'no_metrics_extracted' | string
  userMessage: string
  metrics: []
  problemPriority: []
  questionnaireRef?: string
}

export type ReportDonePayload = {
  tag: string
  riskLevel: RiskLevel
  department: string
  oneLineConclusion: string
  lifestyle: { icon: string; title: string; content: string }[]
  nutrition: { icon: string; title: string; content: string }[]
  alert: { icon: string; title: string; content: string }[]
  solutionRef: string
}

export type SymptomQuestion = {
  id: string
  text: string
  options: { key: string; label: string }[]
}

export type SymptomPayload = {
  symptom: string
  dangerSignals: string[]
  questionnaireRef: string
  currentStep: string
  questions: SymptomQuestion[]
}

export type SymptomDonePayload = {
  riskLevel: RiskLevel
  possibleDirection: string
  department: string
  redFlag: string[]
  lifestyle: string[]
  nutrition: string[]
  solutionRef: string
}

export function useSceneChat(sessionId: string) {
  const [loading, setLoading] = useState(false)
  const [error, setError] = useState<string | null>(null)

  const chat = async (params: {
    text?: string
    files?: File[]
    answers?: Record<string, string>
    language?: string
  }): Promise<SceneResponse | null> => {
    setLoading(true)
    setError(null)
    try {
      const formData = new FormData()
      if (params.text !== undefined) formData.append('text', params.text)
      if (params.files) {
        params.files.forEach((f) => formData.append('files', f))
      }
      if (params.answers) {
        formData.append('answers', JSON.stringify(params.answers))
      }
      formData.append('session_id', sessionId)
      formData.append('language', params.language || '中文')

      const apiBase = import.meta.env.VITE_API_BASE || ''
      const res = await fetch(`${apiBase}/api/health-consult/chat`, {
        method: 'POST',
        body: formData,
      })
      if (!res.ok) {
        throw new Error(`HTTP ${res.status}`)
      }
      return (await res.json()) as SceneResponse
    } catch (e: unknown) {
      setError(e instanceof Error ? e.message : '未知错误')
      return null
    } finally {
      setLoading(false)
    }
  }

  return { chat, loading, error }
}
