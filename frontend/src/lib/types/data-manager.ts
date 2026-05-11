export interface Target {
  gene: string
  protein: string
  uniprot_id: string
  organism?: string
  druggability_score: number
  mutations: string[]
  disease_context: string
  druggability_notes: string
  pubmed_total_count: number
  pubmed_recent_count: number
  pubmed_trend: "rising" | "declining" | "stable"
  evidence_tier: string
  pubmed_url?: string
  associated_diseases?: string[]
  pdb_ids: string[]
  alphafold?: { alphafold_url: string }
  top_pathway?: string
  pathway_score?: number
  pathway_profile?: {
    reactome_pathways: unknown[]
    kegg_pathways: unknown[]
    text_pathways: string[]
  }
  go_terms?: string[]
  uniprot_keywords?: string[]
  chembl_ids?: string[]
  subcellular_locs?: string[]
  function?: string
  protein_full_name?: string
}

export interface SourceEntry {
  title: string
  url: string
  pmid: string
  doi: string
  type: string
}

export interface GenerateResponse {
  success: boolean
  result: string
  targets: Target[]
  sources: SourceEntry[]
  source_count: number
  validation_score: number
  session_id: string
  error?: string
}

export interface AskResponse {
  answer: string
}

export interface FileEntry {
  name: string
  size: string
  type: string
  date: string
  status: string
}

export interface SvgMetric {
  metric: string
  score: number
}

export interface ModalityData {
  name: string
  count: number
  fill: string
}
