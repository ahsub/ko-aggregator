/**
 * ko-watchdog — Cloudflare Worker v1.0
 * =====================================
 * Cron Trigger: 04:15 UTC Mo–Sa (nach GHA-Cron 03:37 UTC)
 *
 * Logik:
 *   1. Liest master_market_data aus KV → meta.generated (ISO-Timestamp)
 *   2. Prüft ob generated-Datum == heute (UTC)
 *   3. JA  → GHA hat geliefert, nichts tun
 *   4. NEIN → GHA-Cron ausgefallen, workflow_dispatch via GitHub API triggern
 *
 * Secrets (CF Worker Environment):
 *   KV_BINDING        — KV Namespace Binding (Name: "KV")
 *   GH_WATCHDOG_PAT   — GitHub PAT (scope: repo, Actions: write)
 *   GH_REPO           — "ahsub/ko-aggregator"
 *   GH_WORKFLOW       — "market-aggregator.yml"
 */

export default {
  // Cron-Handler
  async scheduled(event, env, ctx) {
    ctx.waitUntil(runWatchdog(env));
  },

  // HTTP-Handler für manuelle Tests: GET /trigger oder GET /status
  async fetch(request, env, ctx) {
    const url = new URL(request.url);

    if (url.pathname === "/status") {
      const result = await checkFreshness(env);
      return Response.json(result);
    }

    if (url.pathname === "/trigger") {
      // Nur für manuelle Tests — erzwingt Dispatch unabhängig vom Freshness-Check
      const result = await dispatchGHA(env, "manual-test via /trigger");
      return Response.json(result);
    }

    return new Response("ko-watchdog v1.0 — GET /status | /trigger", { status: 200 });
  }
};

// ─── Hauptlogik ───────────────────────────────────────────────────────────────

async function runWatchdog(env) {
  const log = [];
  const now = new Date();
  const todayUTC = toDateString(now);

  log.push(`[${now.toISOString()}] Watchdog gestartet — prüfe Datum ${todayUTC}`);

  try {
    const freshness = await checkFreshness(env);
    log.push(`KV generated: ${freshness.generated ?? "nicht lesbar"}`);
    log.push(`Frisch: ${freshness.isFresh}`);

    if (freshness.isFresh) {
      log.push("GHA hat geliefert — kein Eingriff nötig.");
      console.log(log.join("\n"));
      return;
    }

    // Nicht frisch → Dispatch
    log.push("GHA-Cron ausgefallen oder verzögert — triggere workflow_dispatch.");
    const dispatch = await dispatchGHA(env, `watchdog-trigger ${todayUTC}`);
    log.push(`Dispatch-Status: ${dispatch.status} — ${dispatch.message}`);

  } catch (err) {
    log.push(`FEHLER: ${err.message}`);
  }

  console.log(log.join("\n"));
}

// ─── Freshness-Check ──────────────────────────────────────────────────────────

async function checkFreshness(env) {
  const todayUTC = toDateString(new Date());

  let raw;
  try {
    raw = await env.KV.get("master_market_data", { type: "text" });
  } catch (err) {
    return { isFresh: false, generated: null, error: `KV-Lesefehler: ${err.message}` };
  }

  if (!raw) {
    return { isFresh: false, generated: null, error: "master_market_data nicht im KV" };
  }

  let meta;
  try {
    // master_market_data ist ~1-2 MB — nur meta-Block parsen
    // Suche "generated":"..." im JSON-String (schneller als vollständiges Parsen)
    const match = raw.match(/"generated"\s*:\s*"([^"]+)"/);
    if (!match) throw new Error("generated-Feld nicht gefunden");
    meta = { generated: match[1] };
  } catch (err) {
    return { isFresh: false, generated: null, error: `Parse-Fehler: ${err.message}` };
  }

  // Datum aus ISO-Timestamp extrahieren (z.B. "2026-07-13T03:58:22Z" → "2026-07-13")
  const generatedDate = meta.generated.slice(0, 10);
  const isFresh = generatedDate === todayUTC;

  return { isFresh, generated: meta.generated, generatedDate, todayUTC };
}

// ─── GitHub workflow_dispatch ─────────────────────────────────────────────────

async function dispatchGHA(env, reason) {
  const repo     = env.GH_REPO     ?? "ahsub/ko-aggregator";
  const workflow = env.GH_WORKFLOW  ?? "market-aggregator.yml";
  const pat      = env.GH_WATCHDOG_PAT;

  if (!pat) {
    return { status: "error", message: "GH_WATCHDOG_PAT Secret fehlt" };
  }

  const url = `https://api.github.com/repos/${repo}/actions/workflows/${workflow}/dispatches`;

  const resp = await fetch(url, {
    method: "POST",
    headers: {
      "Authorization": `token ${pat}`,
      "Accept":        "application/vnd.github.v3+json",
      "Content-Type":  "application/json",
      "User-Agent":    "ko-watchdog/1.0"
    },
    body: JSON.stringify({ ref: "main", inputs: { reason } })
  });

  if (resp.status === 204) {
    return { status: "ok", message: `workflow_dispatch erfolgreich (${reason})` };
  }

  const body = await resp.text().catch(() => "");
  return { status: "error", message: `GH API ${resp.status}: ${body}` };
}

// ─── Hilfsfunktionen ─────────────────────────────────────────────────────────

function toDateString(date) {
  // "2026-07-13" in UTC
  return date.toISOString().slice(0, 10);
}
