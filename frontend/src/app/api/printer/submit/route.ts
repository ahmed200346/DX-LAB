import { NextRequest, NextResponse } from "next/server"

const BACKEND_URL = process.env.PRINTER_3D_API_URL ?? "http://127.0.0.1:5000"

export async function POST(request: NextRequest) {
  try {
    const body = await request.json()
    const targetUrl = `${BACKEND_URL}/api/submit`

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
        { success: false, error: "Cannot reach 3D Printer backend. Start with: cd backend/services/printer_3d && python web_server.py" },
        { status: 503 }
      )
    }
    return NextResponse.json({ success: false, error: message }, { status: 500 })
  }
}
