export interface Hypothesis {
  id: number
  title: string
  confidence: number
  category: string
  impact: string
  novelty: string
  abstract?: string
  rationale: string
  experiment: string
  citations: string[]
}

export interface HypothesisResult {
  success: boolean
  session_id: string
  hypotheses: Hypothesis[]
  literature_gaps?: string[]
  conflicts?: string[]
  summary?: string
  analysis_metadata?: Record<string, unknown>
}

export interface ChatMessage {
  role: "dexter" | "user"
  content: string
}

export interface HypothesisActivity {
  icon: string
  text: string
  time: string
}
