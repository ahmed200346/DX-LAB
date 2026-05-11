export interface ReportSection {
  id: string
  title: string
  icon: string
  content: string
  data?: Record<string, unknown>[]
}

export interface ReportData {
  subject: string
  sections: ReportSection[]
  generatedAt: string
  validationScore?: number
  sessionId?: string
}
