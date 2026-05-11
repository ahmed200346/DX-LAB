export interface SafetyCheck {
  name: string
  score: number
  status: "pending" | "running" | "Pass" | "Warning" | "Fail"
}

export interface SafetyAlert {
  level: "green" | "yellow" | "red"
  label: string
  detail: string
}

export interface DrugSafetyInteraction {
  drug?: string
  severity?: string
  description?: string
}

export interface DrugSafetyFindings {
  side_effects?: string[]
  interactions?: DrugSafetyInteraction[]
  sources?: { name?: string; url?: string }[]
}

export interface DrugSafetyResult {
  drug?: string
  rxcui?: string
  findings?: DrugSafetyFindings
  risk?: {
    clinical?: Record<string, unknown>
  }
  error?: string
}

export interface SafetyAnalysisResult {
  smiles: string
  patientAge: string
  patientSex: string
  comorbidities: string
  safetyChecks: SafetyCheck[]
  alerts: SafetyAlert[]
  hazardIndex: number
  overallRisk: string
}
