import { NextRequest, NextResponse } from "next/server"

const BACKEND_URL = process.env.HYPOTHESIS_API_URL ?? "http://127.0.0.1:8003"

export async function POST(request: NextRequest) {
  try {
    const body = await request.json()
    const targetUrl = `${BACKEND_URL}/generate`

    const backendRes = await fetch(targetUrl, {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify(body),
      signal: AbortSignal.timeout(120_000),
    })

    const data = await backendRes.json()
    return NextResponse.json(data, { status: backendRes.status })
  } catch (err: unknown) {
    const message = err instanceof Error ? err.message : "Unknown error"
    if (message.includes("ECONNREFUSED") || message.includes("fetch failed") || message.includes("TimeoutError")) {
      return NextResponse.json(
        { success: false, error: "Cannot reach Hypothesis Assistant backend. Start with: cd backend/services/hypothesis_assistant_agent && python -c \"import uvicorn; uvicorn.run('api:app', port=8003)\"", hypotheses: [], session_id: "" },
        { status: 503 }
      )
    }
    return NextResponse.json({ success: false, error: message, hypotheses: [], session_id: "" }, { status: 500 })
  }
}
