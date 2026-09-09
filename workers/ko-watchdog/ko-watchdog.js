/**
 * ko-watchdog — Cloudflare Worker
 * =====================================
 * Cron Trigger: 04:15 UTC Mo–Sa (nach GHA-Cron 03:37 UTC, Lauf 1/Xetra)
 *               13:45 UTC Mo–Fr (nach GHA-Cron 13:30 UTC, Lauf 2/NYSE)
 *
 * Logik (FIX 09.09.2026 — Dual-Slot Freshness Check):
 *   Der alte Freshness-Check verglich nur das Datum von master_market_data
 *   gegen "heute" — das erkannte einen ausgefallenen Lauf 2 (nachmittags)
 *   NICHT, wenn Lauf 1 (morgens) bereits durchgelaufen war, weil beide
 *   Läufe denselben Tagesstempel setzen.
 *
 *   Neu: anhand von event.cron wird erkannt, welcher der beiden Tagesläufe
 *   gerade geprüft wird, und der Freshness-Check verlangt zusätzlich, dass
 *   der KV-Zeitstempel NACH der jeweils zugehörigen GHA-Cron-Uhrzeit liegt
 *   (nicht nur "irgendwann heute"). Ein durchgekommener Morgenlauf macht
 *   damit den Nachmittags-Check nicht mehr fälschlich "frisch".
 *
 *   1. Liest master_market_data aus KV → meta.generated (ISO-Timestamp)
 *   2. Bestimmt anhand von event.cron die erwartete Mindest-Uhrzeit
 *      (Lauf 1 → heute 03:37 UTC, Lauf 2 → heute 13:30 UTC)
 *   3. Prüft ob generated >= dieser Schwelle
 *   4. JA  → GHA hat diesen Lauf geliefert, nichts tun
 *   5. NEIN → GHA-Cron für diesen Lauf ausgefallen/verzögert,
 *             workflow_dispatch via GitHub API triggern
 *
 * Secrets (CF Worker Environment):
 *   KV_BINDING        — KV Namespace Binding (Name: "KV")
 *   GH_WATCHDOG_PAT   — GitHub PAT (scope: repo, Actions: write)
 *   GH_REPO           — "ahsub/ko-aggregator"
 *   GH_WORKFLOW       — "market-aggregator.yml"
 */

// Ordnet die beiden Watchdog-Cron-Ausdrücke (aus wrangler.toml) ihrem
// jeweiligen GHA-Aggregator-Lauf und dessen erwarteter Cron-Uhrzeit (UTC) zu.
const RUN_SCHEDULES = {
  "15 04 * * 1-6": { label: "Lauf 1 (Xetra-Morgen)", thresholdHHMM: "03:37" },
  "45 13 * * 1-5": { label: "Lauf 2 (NYSE-Nachmittag)", thresholdHHMM: "13:30" }
};

export default {
  // Cron-Handler
  async scheduled(event, env, ctx) {
    ctx.waitUntil(runWatchdog(env, event.cron));
  },

  // HTTP-Handler für manuelle Tests: GET /trigger oder GET /status
  async fetch(request, env, ctx) {
    const url = new URL(request.url);

    if (url.pathname === "/status") {
      // Optional ?slot=1 oder ?slot=2, um gezielt einen der beiden
      // Tagesläufe zu prüfen (wie der jeweilige Cron es täte).
      // Ohne Parameter: alter, einfacher "irgendwann heute"-Check
      // (rein informativ, keine Entscheidungsgrundlage mehr für Dispatches).
      const slot = url.searchParams.get("slot");
      const cronForSlot = slot === "1" ? "15 04 * * 1-6" : slot === "2" ? "45 13 * * 1-5" : null;
      const thresholdISO = cronForSlot ? buildThresholdISO(RUN_SCHEDULES[cronForSlot]) : null;
      const result = await checkFreshness(env, thresholdISO);
      return Response.json(result);
    }

    if (url.pathname === "/trigger") {
      // Nur für manuelle Tests — erzwingt Dispatch unabhängig vom Freshness-Check
      const result = await dispatchGHA(env, "manual-test via /trigger");
      return Response.json(result);
    }

    return new Response("ko-watchdog — GET /status[?slot=1|2] | /trigger", { status: 200 });
  }
};

// ─── Hauptlogik ───────────────────────────────────────────────────────────────

async function runWatchdog(env, cron) {
  const log = [];
  const now = new Date();
  const todayUTC = toDateString(now);
  const schedule = RUN_SCHEDULES[cron];

  if (!schedule) {
    // Unbekannter Cron-Ausdruck (z.B. nach künftiger wrangler.toml-Änderung,
    // die hier nicht nachgezogen wurde) — Fallback auf den alten,
    // einfachen Datums-Check statt stillschweigend nichts zu tun.
    log.push(`[${now.toISOString()}] Watchdog gestartet — unbekannter Cron "${cron}", Fallback auf einfachen Datums-Check`);
    try {
      const freshness = await checkFreshness(env, null);
      log.push(`KV generated: ${freshness.generated ?? "nicht lesbar"}`);
      log.push(`Frisch (Datums-Check): ${freshness.isFresh}`);
      if (!freshness.isFresh) {
        const dispatch = await dispatchGHA(env, `watchdog-trigger unbekannter-cron ${todayUTC}`);
        log.push(`Dispatch-Status: ${dispatch.status} — ${dispatch.message}`);
      }
    } catch (err) {
      log.push(`FEHLER: ${err.message}`);
    }
    console.log(log.join("\n"));
    return;
  }

  const thresholdISO = buildThresholdISO(schedule);
  log.push(`[${now.toISOString()}] Watchdog gestartet — ${schedule.label}, erwartet generated >= ${thresholdISO}`);

  try {
    const freshness = await checkFreshness(env, thresholdISO);
    log.push(`KV generated: ${freshness.generated ?? "nicht lesbar"}`);
    log.push(`Frisch fuer ${schedule.label}: ${freshness.isFresh}`);

    if (freshness.isFresh) {
      log.push("GHA hat diesen Lauf geliefert — kein Eingriff noetig.");
      console.log(log.join("\n"));
      return;
    }

    // Nicht frisch für DIESEN Lauf → Dispatch
    log.push(`GHA-Cron fuer ${schedule.label} ausgefallen oder verzoegert — triggere workflow_dispatch.`);
    const dispatch = await dispatchGHA(env, `watchdog-trigger ${schedule.label} ${todayUTC}`);
    log.push(`Dispatch-Status: ${dispatch.status} — ${dispatch.message}`);

  } catch (err) {
    log.push(`FEHLER: ${err.message}`);
  }

  console.log(log.join("\n"));
}

// ─── Freshness-Check ──────────────────────────────────────────────────────────

// thresholdISO: wenn gesetzt, muss `generated` >= thresholdISO sein (Slot-genauer
// Check). Wenn null, greift der alte, grobe "irgendwann heute"-Check.
async function checkFreshness(env, thresholdISO = null) {
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

  const isFresh = thresholdISO
    ? meta.generated >= thresholdISO   // ISO-8601-Strings sind lexikografisch vergleichbar
    : generatedDate === todayUTC;      // alter, slot-unabhaengiger Fallback

  return { isFresh, generated: meta.generated, generatedDate, todayUTC, thresholdISO };
}

function buildThresholdISO(schedule) {
  const todayUTC = toDateString(new Date());
  return `${todayUTC}T${schedule.thresholdHHMM}:00Z`;
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
      "User-Agent":    "ko-watchdog"
    },
    body: JSON.stringify({ ref: "main" })
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
