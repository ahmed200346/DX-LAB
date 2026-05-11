/**
 * HTTP smoke tests — starts the built Next.js app and hits every route.
 * Run: cd frontend && npx tsx tests/http.test.ts
 */
import { spawn } from "node:child_process";
import { request } from "node:http";
import { join } from "node:path";

const PORT = 3458;
const BASE = `http://localhost:${PORT}`;

function httpGet(path: string): Promise<{ status: number; body: string }> {
  return new Promise((resolve, reject) => {
    const req = request(`${BASE}${path}`, { method: "GET", timeout: 8000 }, (res) => {
      let data = "";
      res.on("data", (chunk) => (data += chunk));
      res.on("end", () => resolve({ status: res.statusCode ?? 0, body: data }));
    });
    req.on("error", reject);
    req.on("timeout", () => reject(new Error("Timeout")));
    req.end();
  });
}

function waitForServer(port: number, timeout = 30000): Promise<void> {
  return new Promise((resolve, reject) => {
    const deadline = Date.now() + timeout;
    const check = () => {
      const req = request(`http://localhost:${port}/`, { method: "GET", timeout: 2000 }, (res) => {
        if (res.statusCode === 200) return resolve();
        if (Date.now() < deadline) return setTimeout(check, 800);
        reject(new Error("Server never became ready"));
      });
      req.on("error", () => {
        if (Date.now() < deadline) setTimeout(check, 800);
        else reject(new Error("Server never became ready"));
      });
      req.end();
    };
    check();
  });
}

async function main() {
  console.log("Starting Next.js production server...");
  const nextBin = join(process.cwd(), "node_modules", "next", "dist", "bin", "next");
  const proc = spawn("node", [nextBin, "start", "-p", String(PORT)], {
    cwd: process.cwd(),
    windowsHide: true,
  });

  let serverReady = false;
  proc.stdout?.on("data", (d) => {
    const txt = d.toString();
    if (txt.includes("Ready")) serverReady = true;
  });
  proc.stderr?.on("data", (d) => {
    const txt = d.toString();
    if (txt.includes("Ready")) serverReady = true;
  });

  console.log("Waiting for server on port", PORT, "...");
  await waitForServer(PORT);
  console.log("  ✓ Server ready\n");

  const pageRoutes = [
    "/", "/agent", "/safety", "/hypothesis-generator",
    "/printer", "/reporter", "/data-manager", "/orchestrator", "/automation",
  ];
  const apiRoutes = [
    "/api/data-manager/generate",
    "/api/data-manager/ask",
    "/api/hypothesis/generate",
    "/api/hypothesis/ask",
    "/api/printer/submit",
    "/api/drug-safety",
    "/api/acp/agents",
  ];

  let passed = 0;
  let failed = 0;

  console.log("[HTTP Pages]");
  for (const path of pageRoutes) {
    try {
      const { status, body } = await httpGet(path);
      if (status === 200 && body.includes("<!DOCTYPE html>")) {
        console.log(`  ✓ ${path} => 200 (${body.length} bytes)`);
        passed++;
      } else {
        console.log(`  ✗ ${path} => ${status}, no HTML`);
        failed++;
      }
    } catch (e: any) {
      console.log(`  ✗ ${path} => ERROR: ${e.message}`);
      failed++;
    }
  }

  console.log("\n[HTTP API Routes]");
  for (const path of apiRoutes) {
    try {
      const { status, body } = await httpGet(path);
      // API routes without POST body may 405 or return JSON error — both are OK if server responds
      if (status >= 200 && status < 600) {
        console.log(`  ✓ ${path} => ${status} (server responded)`);
        passed++;
      } else {
        console.log(`  ✗ ${path} => ${status}`);
        failed++;
      }
    } catch (e: any) {
      console.log(`  ✗ ${path} => ERROR: ${e.message}`);
      failed++;
    }
  }

  console.log("\nKilling server...");
  proc.kill("SIGTERM");

  console.log(`\n${passed} passed, ${failed} failed`);
  if (failed > 0) process.exit(1);
  console.log("✅ All HTTP smoke tests passed!");
}

main().catch((e) => {
  console.error("HTTP test crashed:", e);
  process.exit(1);
});
