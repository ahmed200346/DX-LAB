/**
 * Headless integration tests for DX-LAB frontend
 * Run: cd frontend && npx tsx tests/integration.test.ts
 */
import assert from "node:assert";
import { readdirSync } from "node:fs";
import { join } from "node:path";

async function main() {
  // ─── 1. Type imports ───────────────────────────────────────────
  console.log("[1/6] Testing type imports...");
  try {
    const types = await import("../src/lib/types/index.ts");
    assert(types, "types barrel should export something");
    console.log("  ✓ All type interfaces importable");
  } catch (e: any) {
    console.error("  ✗ Type import failed:", e.message);
    process.exit(1);
  }

  // ─── 2. API client imports ─────────────────────────────────────
  console.log("[2/6] Testing API client imports...");
  try {
    const api = await import("../src/lib/api/index.ts");
    assert(typeof api.postACPRun === "function", "postACPRun missing");
    assert(typeof api.listAgents === "function", "listAgents missing");
    assert(typeof api.generateQuery === "function", "generateQuery missing");
    assert(typeof api.askQuestion === "function", "askQuestion missing");
    assert(typeof api.analyzeDrug === "function", "analyzeDrug missing");
    assert(typeof api.generateHypotheses === "function", "generateHypotheses missing");
    assert(typeof api.askHypothesis === "function", "askHypothesis missing");
    assert(typeof api.submitPrintJob === "function", "submitPrintJob missing");
    console.log("  ✓ All API client functions present");
  } catch (e: any) {
    console.error("  ✗ API client import failed:", e.message);
    process.exit(1);
  }

  // ─── 3. Hook imports ───────────────────────────────────────────
  console.log("[3/6] Testing hook imports...");
  try {
    const hooks = await import("../src/hooks/index.ts");
    assert(typeof hooks.useDiscovery === "function", "useDiscovery missing");
    assert(typeof hooks.useSafetyAnalysis === "function", "useSafetyAnalysis missing");
    assert(typeof hooks.useHypothesis === "function", "useHypothesis missing");
    assert(typeof hooks.useDataManager === "function", "useDataManager missing");
    assert(typeof hooks.useReporter === "function", "useReporter missing");
    assert(typeof hooks.useOrchestrator === "function", "useOrchestrator missing");
    assert(typeof hooks.usePrinter === "function", "usePrinter missing");
    console.log("  ✓ All hooks present");
  } catch (e: any) {
    console.error("  ✗ Hook import failed:", e.message);
    process.exit(1);
  }

  // ─── 4. ErrorBoundary import ───────────────────────────────────
  console.log("[4/6] Testing ErrorBoundary component...");
  try {
    const eb = await import("../src/components/ErrorBoundary.tsx");
    assert(eb.default, "ErrorBoundary should have default export");
    console.log("  ✓ ErrorBoundary imports correctly");
  } catch (e: any) {
    console.error("  ✗ ErrorBoundary import failed:", e.message);
    process.exit(1);
  }

  // ─── 5. Skeleton components import ─────────────────────────────
  console.log("[5/6] Testing Skeleton components...");
  try {
    const sk = await import("../src/components/ui/skeleton.tsx");
    assert(typeof sk.Skeleton === "function", "Skeleton missing");
    assert(typeof sk.CardSkeleton === "function", "CardSkeleton missing");
    assert(typeof sk.ChartSkeleton === "function", "ChartSkeleton missing");
    assert(typeof sk.TableSkeleton === "function", "TableSkeleton missing");
    console.log("  ✓ Skeleton components present");
  } catch (e: any) {
    console.error("  ✗ Skeleton import failed:", e.message);
    process.exit(1);
  }

  // ─── 6. API route source validation ────────────────────────────
  console.log("[6/6] Testing API route source files exist...");
  const routesDir = join(process.cwd(), "src", "app", "api");
  try {
    const dirs = readdirSync(routesDir, { withFileTypes: true })
      .filter((d) => d.isDirectory())
      .map((d) => d.name);
    assert(dirs.includes("data-manager"), "data-manager route missing");
    assert(dirs.includes("hypothesis"), "hypothesis route missing");
    assert(dirs.includes("printer"), "printer route missing");
    assert(dirs.includes("drug-safety"), "drug-safety route missing");
    assert(dirs.includes("acp"), "acp route missing");
    console.log("  ✓ All API route directories present");
  } catch (e: any) {
    console.error("  ✗ API route check failed:", e.message);
    process.exit(1);
  }

  console.log("\n✅ All 6 headless integration tests passed!");
}

main().catch((e) => {
  console.error("Test runner crashed:", e);
  process.exit(1);
});
