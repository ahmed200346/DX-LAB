import type { DrugSafetyResult } from "@/lib/types/safety"

const BASE = "/api/drug-safety"

export async function analyzeDrug(
  drug: string,
  age?: number,
  conditions?: string
): Promise<DrugSafetyResult> {
  const params = new URLSearchParams({ drug })
  if (age !== undefined) params.set("age", String(age))
  if (conditions) params.set("conditions", conditions)

  const res = await fetch(`${BASE}?${params.toString()}`, {
    signal: AbortSignal.timeout(60_000),
  })
  if (!res.ok) {
    const err = await res.json().catch(() => ({ error: res.statusText }))
    throw new Error(err.error || `Drug safety analysis failed: ${res.status}`)
  }
  return res.json()
}
