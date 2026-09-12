/**
 * ko-watchdog — Cloudflare Worker
 * =====================================
 * Cron Trigger: 22:45 UTC Mo–Fr (nach GHA-Cron 22:00 UTC, EOD-Lauf)
 *
 * Logik (FIX 09.09.2026 — Dual-Slot Freshness Check; VEREINFACHT 11.09.2026
 * — nur noch EIN Slot, seit market-aggregator.yml v1.2 auf einen einzigen
 * Nachbörsen-Lauf statt zwei Vor-Schluss-Läufe umgestellt hat):
 *   Der urspruenglich einfache Freshness-Check verglich nur das Datum von
 *   master_market_data gegen "heute" — das reichte fuer einen einzelnen
 *   Lauf/Tag nicht aus, um einen ausgefallenen Lauf zuverlaessig zu
 *   erkennen (unterschied nicht zwischen "gar kein Lauf heute" und
 *   "Lauf lief, aber vor der erwarteten Uhrzeit"). Der Slot-genaue Check
 *   (generated >= erwartete Cron-Uhrzeit, nicht nur "irgendwann heute")
 *   bleibt daher auch fuer den Single-Run-Fall bestehen — nur die
 *   RUN_SCHEDULES-Map hat jetzt nur noch einen Eintrag statt zwei.
 *
 *   1. Liest master_market_data aus KV → meta.generated (ISO-Timestamp)
 *   2. Bestimmt anhand von event.cron die erwartete Mindest-Uhrzeit
 *      (EOD-Lauf → heute 22:00 UTC)
 *   3. Prüft ob generated >= dieser Schwelle
 *   4. JA  → GHA hat diesen Lauf geliefert, nichts tun
 *   5. NEIN → GHA-Cron ausgefallen/verzögert, workflow_dispatch via
 *      GitHub API triggern
 *
 * Secrets (CF Worker Environment):
 *   KV_BINDING        — KV Namespace Binding (Name: "KV")
 *   GH_WATCHDOG_PAT   — GitHub PAT (scope: repo, Actions: write)
 *   GH_REPO           — "ahsub/ko-aggregator"
 *   GH_WORKFLOW       — "market-aggregator.yml"
 */

// Ordnet den (seit 11.09.2026 einzigen) Watchdog-Cron-Ausdruck (aus
// wrangler.toml) dem GHA-Aggregator-Lauf und dessen erwarteter Cron-Uhrzeit
// (UTC) zu. Als Map belassen (statt einzelner Konstanten), damit ein
// kuenftiger zweiter Slot ohne Strukturaenderung ergaenzt werden kann.
const RUN_SCHEDULES = {
  "45 22 * * 1-5": { label: "EOD-Lauf (Nachbörse)", thresholdHHMM: "22:00" }
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
      // Ohne Parameter: alter, einfacher "irgendwann heute"-Check (rein
      // informativ, keine Entscheidungsgrundlage mehr für Dispatches).
      // Optional ?slot=1, um den (seit 11.09.2026 einzigen) Tageslauf
      // gezielt zu pruefen, wie der Cron es taete.
      const slot = url.searchParams.get("slot");
      const cronForSlot = slot === "1" ? "45 22 * * 1-5" : null;
      const thresholdISO = cronForSlot ? buildThresholdISO(RUN_SCHEDULES[cronForSlot]) : null;
      const result = await checkFreshness(env, thresholdISO);
      return Response.json(result);
    }

    if (url.pathname === "/trigger") {
      // Nur für manuelle Tests — erzwingt Dispatch unabhängig vom Freshness-Check
      const result = await dispatchGHA(env, "manual-test via /trigger");
      return Response.json(result);
    }

    return new Response("ko-watchdog — GET /status[?slot=1] | /trigger", { status: 200 });
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
