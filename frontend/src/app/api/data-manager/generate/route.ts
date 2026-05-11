import { NextRequest, NextResponse } from "next/server"

const BACKEND_URL = process.env.DATA_MANAGER_API_URL ?? "http://127.0.0.1:8000"

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
        { success: false, error: "Cannot reach Data Manager backend. Start with: cd backend && python -m services.data_manager.api_server", result: "", targets: [], sources: [], source_count: 0, validation_score: 0, session_id: "" },
        { status: 503 }
      )
    }
    return NextResponse.json(
      { success: false, error: message, result: "", targets: [], sources: [], source_count: 0, validation_score: 0, session_id: "" },
      { status: 500 }
    )
  }
}
