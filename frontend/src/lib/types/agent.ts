export interface PipelineStep {
  id: string
  name: string
  description: string
  status: "pending" | "running" | "completed" | "error"
  progress?: number
  details?: string
}

export interface Candidate {
  id: string
  name: string
  smiles: string
  pkd: number
  qed: number
  sa: number
  status: string
}

export interface DiscoveryResult {
  protein: string
  disease: string
  steps: PipelineStep[]
  candidates: Candidate[]
  runId: string
}

export interface PlanStep {
  id: number
  task: string
  agent: string
  status: "pending" | "running" | "completed" | "error"
}

export interface LogEntry {
  time: string
  msg: string
  type: "info" | "success" | "warning" | "error"
  agent: string
}

export interface OrchestratorResult {
  plan: PlanStep[]
  logs: LogEntry[]
  progress: number
}

export interface PrinterRankerValidation {
  has_smiles: boolean
  has_protein_sequence: boolean
  molecule_name: string
  smiles?: string
  sequence_length: number
  mw?: number
  logp?: number
  drug_likeness?: number
}

export interface PrinterRankerOutput {
  case: number
  model: string
  confidence: number
  llm_reasoning: string
  alternative_cases: number[]
  validation: PrinterRankerValidation
}

export interface PrinterOutput {
  success: boolean
  format: string
  model_used: string
  generation_time_s: number
  structure_size: number
  error_message?: string
  structure?: string
}

export interface PrinterMetrics {
  ranker: {
    extraction: number
    classification: number
    confidence: number
    reliability: number
    global: number
    status: string
  }
  printer: {
    generation: number
    format: number
    quality: number
    reliability: number
    global: number
    status: string
  }
  pipeline: {
    global: number
    status: string
  }
}

export interface PrinterInputAnalysis {
  type: string
  description: string
}

export interface PrinterResult {
  input_analysis: PrinterInputAnalysis
  ranker: PrinterRankerOutput
  printer: PrinterOutput
  metrics: PrinterMetrics
}

export interface PrinterApiResponse {
  success: boolean
  data?: PrinterResult
  error?: string
}

export interface ACPRunRequest {
  agent: string
  input: string
}

export interface ACPRunResponse {
  result: string
  error?: string
}
