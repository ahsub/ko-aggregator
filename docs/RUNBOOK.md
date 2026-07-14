# UIQ RUNBOOK — Betriebs- und Störungshandbuch (Bus-Factor-Dokument)
**Version 1.3 | Stand: 14.07.2026 | Zweck: Ein fähiger Dritter kann das System mit diesem Dokument verstehen, betreiben und im Störfall wiederherstellen.**

> Platzhalter im Format `[VOM INHABER ZU ERGÄNZEN: …]` müssen von Dr. Axel Hildebrand befüllt werden. Dieses Dokument enthält bewusst **keine Secrets** — nur deren Fundorte.

---

## 1. Was ist UnderlyingIQ (in 5 Sätzen)

UIQ (underlyingiq.com) ist eine browserbasierte Marktanalyse-PWA. Ein nächtlicher Python-Job (der „Aggregator") lädt Kursdaten für ~640 Ticker, berechnet Indikatoren, ein Marktregime und Strategie-Scores und schreibt das Ergebnis als JSON in einen Cloudflare-KV-Speicher. Das Frontend (statisches HTML/JS auf Cloudflare Pages) liest ausschließlich aus diesem KV — es gibt keinen klassischen Backend-Server. KI-Funktionen (Morning Briefing, Deep Dive) laufen über einen Cloudflare Worker, der die Anthropic-API kapselt. Kernidee ist der „Strategie-Router": Marktregime erkennen → passende Strategie → beste Underlyings (siehe `docs/STRATEGIE.md`).

## 2. Systemlandkarte

| Komponente | Ort | Zweck |
|---|---|---|
| **Frontend** | Repo `ahsub/axel-scanner` → Cloudflare Pages → underlyingiq.com | UI; monolithische `index.html` + `help.html` (Online-Hilfe; beide gemeinsam versionieren!) |
| **Aggregator** | Repo `ahsub/ko-aggregator` (`market_aggregator.py`, aktuell v5.8.2) | Zweimal täglicher Datenlauf via GitHub Actions (Xetra + NYSE, siehe §3) |
| **Track-Record-Layer** | `ahsub/ko-aggregator/tr_layer.py` | Snapshot-Logging der Empfehlungen (Spez: `docs/TRACK_RECORD_SPEC.md`) |
| **ko-modules (CDN)** | Repo `ahsub/ko-modules` via jsDelivr, **Hash-pinned** | Geteilte ES6-Module (`ko-market-state.js` v2.1, `ko-indicators-loader.js` v1.2.1 = Market Context Module/MCM, u.a.) |
| **ko-ai Worker** | Cloudflare Worker `ko-ai.ahildebrand.workers.dev` (v1.5) | KI-Proxy (Anthropic), Request-Logging, Extra-Ticker-Review |
| **ko-sync Worker** | Cloudflare Worker | Cloud-Sync der Nutzereinstellungen; `/public/*`-Endpoints liefern `master_market_data`, `options_watchlist`, `daily_market_snapshot`, `daily_market_snapshot_us` |
| **ko-watchdog Worker** | Cloudflare Worker `ko-watchdog.ahildebrand.workers.dev` (v1.1) | Zwei Cron-Trigger (04:15 + 13:45 UTC) dispatchen den GHA-Workflow per `workflow_dispatch` — Absicherung falls GitHub-eigener Schedule-Cron ausfällt/verzögert. Manueller Test: `curl https://ko-watchdog.ahildebrand.workers.dev/trigger` |
| **CORS-Proxy** | `my-cors-proxy.ahildebrand.workers.dev` | Umgeht CORS für externe Datenquellen im Frontend |
| **KV-Namespace** | Cloudflare KV `86c05f66e32346b99e720d861fedd1de` | Zentrale Datendrehscheibe |
| **Cloudflare-Account** | Account-ID `2ee58f98cf0979e660841a0764b7f17d` | Pages + Workers + KV |
| Schwesterprojekte | `ahsub/refundex` (+ `refundex-docs`), `ahsub/premium-options`, `ahsub/ko-rechner` u.a. | Eigenständig, teilen Infrastruktur-Muster |

## 3. Der Nachtlauf (das Herz des Systems)

**Zeitplan:** GitHub Actions, **zwei Crons**: `37 03 * * 1-6` UTC (Mo–Sa, vor Xetra-Öffnung) und `30 13 * * 1-5` UTC (Mo–Fr, vor NYSE-Öffnung). Workflow: `.github/workflows/market-aggregator.yml`, Name „KO-Scanner Market Aggregator". **Achtung: GitHub-Cron ist best effort** — Verzögerungen von Minuten bis Stunden sind normal (dokumentiert: 3h23min am 02.07.2026). Deshalb 03:37 statt 04:00. **Absicherung seit 13.07.2026:** `ko-watchdog` (Cloudflare Worker, Crons 04:15 + 13:45 UTC) dispatcht den Workflow zusätzlich per `workflow_dispatch` — falls der GitHub-eigene Schedule ausfällt oder stark verzögert, holt der Watchdog 30–45min später nach. Manueller Trigger jederzeit möglich: `curl https://ko-watchdog.ahildebrand.workers.dev/trigger` oder direkt via GitHub API (`POST /repos/ahsub/ko-aggregator/actions/workflows/market-aggregator.yml/dispatches`, `{"ref":"main"}`).

**Datenreferenz-Prinzip (wichtig):** Der Cron bestimmt nur, *wann* gelaufen wird — niemals, *welche* Daten gelten. Jeder Lauf verarbeitet den **letzten abgeschlossenen Handelstag**, zur Laufzeit ermittelt via `get_last_trading_day()` (SPY-Daten, erkennt Wochenenden UND Börsenfeiertage automatisch). Es gibt keine feste Wochentags-Zuordnung wie „Montag = Freitagsdaten". Läuft der Cron an einem Tag ohne neuen Handelstag (Feiertag, Wochenende), entsteht derselbe Referenztag wie beim Vorlauf: `master_market_data` wird harmlos aktualisiert, der Track-Record-Layer dedupliziert über den Handelstag und schreibt nichts doppelt. Beispiel 03./04.07.2026 (US-Feiertag + Samstag): Läufe am Fr/Sa/Mo referenzieren alle Handelstag 02.07.; erster neuer Snapshot am Di mit Montagsschluss.

**Ablauf (Schritte im Log nachvollziehbar):**
1. Ticker-Universum bauen (fest codierte Listen + admin-freigegebene Extra-Ticker aus KV)
2. OHLCV via yfinance laden (parallel, ~40–60 s)
3. Indikatoren + Regime + 5 Strategie-Scores je Ticker
4. Externe Quellen: VIX-Termstruktur, Fear&Greed (CNN), DIX/GEX (squeezemetrics + FINRA ATS/TRF), PCR (CBOE) — **alle mit Fallback auf leer, brechen den Lauf nie**
5. Leaderboards (**8 Strategien** seit 13.07.2026: ko_long, momentum, swing, csp_wheel/options_csp, covered_call/options_cc, value, dividend, meanrev) + regime-adaptive Master-Shortlist
6. KI-Enrichment der Top 15 (Anthropic API, nur wenn Key vorhanden)
7. Fundamental-Enrichment (3 Felder, Top-Kandidaten)
8. **Track-Record-Snapshot** (tr_layer.py — fehlerisoliert)
9. KV-Upload: `master_market_data` (+ `options_watchlist`, `known_universe_tickers`)
10. **Daily Market Snapshot** (`generate_daily_snapshot()`, seit 13.07.2026): serverseitiges KI-Briefing für Beta-Tester (Cache-First-Architektur, Frontend liest nur, kein eigener API-Call). Baut seit 14.07.2026 auf dem **Market Context Module (MCM)** auf (`build_server_market_context()`/`calc_server_strategy_gates()`, 1:1-Port aus `ko-modules`/JS, Versions-Lock dokumentiert im Quellcode) — liefert Signal-Flags (ok/caution/risk) + FOMC/NFP/CPI-Calendar-Fenster + deterministische Strategie-Gates in den Prompt. Schreibt nach `daily_market_snapshot` (Morgen-Lauf, vor 12:00 UTC) bzw. `daily_market_snapshot_us` (NYSE-Lauf, danach) — der Morgen-Key wird beim NYSE-Lauf zusätzlich mitgeschrieben (Basis-Key). Fehlerisoliert: eine Exception hier bricht `main()` nie ab, aber der KV-Push für diesen Key wird dann übersprungen (siehe §7.5a).

**Manuell starten:** GitHub → ko-aggregator → Actions → „KO-Scanner Market Aggregator" → **Run workflow** (Branch main), oder `curl https://ko-watchdog.ahildebrand.workers.dev/trigger`. **NIEMALS „Re-run"** eines alten Runs verwenden — der nutzt den alten Code-Stand.

**Erfolg verifizieren:** (a) Run grün in Actions; (b) im Frontend nach Refresh: `generated`-Zeitstempel + Ticker-Zahl im Alpha-Desk-Header; (c) im Master-JSON: `meta.version`, `trackRecord.written`, `strategyMeta.regimeUsed`.

## 4. KV-Schlüsselverzeichnis

| Key | Inhalt | Regenerierbar? |
|---|---|---|
| `master_market_data` | Voll-Output des Nachtlaufs (~1–2 MB) | ✅ durch neuen Lauf |
| `options_watchlist` | Kompakt-Kopie für Options-Desk | ✅ |
| `daily_market_snapshot` | Serverseitiges Morning Briefing (Morgen-Lauf), inkl. `marketContext` + `strategyGates` (MCM, seit 14.07.2026) | ✅ durch nächsten Lauf |
| `daily_market_snapshot_us` | Dito, NYSE-Lauf (Nachmittags-Cron) — ermöglicht Intraday-Vergleich Morgen/NYSE im Frontend | ✅ |
| `known_universe_tickers` | Ticker-Liste für Dedupe im Extra-Ticker-Review | ✅ |
| `approved_extra_tickers` | Admin-freigegebene Ticker-Vorschläge | ⚠️ manuell gepflegt |
| `tr:snap:<YYYY-MM-DD>` | Track-Record-Snapshot je Handelstag | ❌ **UNWIEDERBRINGLICH** |
| `tr:index` | Bewertungs-Fahrplan | ⚠️ aus Snapshots rekonstruierbar |
| (Worker-Keys) | ko-ai-Logs, Sync-Daten | teils |

**⚠️ Wichtigste Betriebswahrheit:** Fast alles im KV ist durch einen einzigen Aggregator-Lauf regenerierbar. **Die einzige nicht regenerierbare Datenklasse sind die `tr:*`-Keys** — sie sind das kommerzielle Kapital (Track Record). Backup-Maßnahme siehe §7.3.

## 5. Secrets & Zugänge (Fundorte, keine Werte!)

| Secret | Wo hinterlegt | Wofür |
|---|---|---|
| `CF_ACCOUNT_ID`, `CF_API_TOKEN`, `CF_KV_NS_ID` | GitHub → ko-aggregator → Settings → Secrets → Actions | KV-Schreibzugriff des Nachtlaufs |
| `ANTHROPIC_API_KEY` | ebd. | KI-Enrichment; fehlt er, läuft alles außer KI |
| GitHub-PAT (classic, `repo`) | wird pro Arbeitssession frisch erzeugt, 7 Tage Laufzeit, danach gelöscht | Entwicklungs-Workflow (Claude-Sessions) |
| Cloudflare-Login | [VOM INHABER ZU ERGÄNZEN: Passwort-Manager/Ort, 2FA-Gerät] | Pages, Workers, KV-Konsole |
| GitHub-Account `ahsub` | [VOM INHABER ZU ERGÄNZEN: Ort, 2FA] | Alle Repos |
| Anthropic-Console | [VOM INHABER ZU ERGÄNZEN] | API-Keys, Verbrauch |
| Domain underlyingiq.com | [VOM INHABER ZU ERGÄNZEN: Registrar, Verlängerungsdatum] | DNS zeigt auf Cloudflare Pages |
| EIC-Expert-PIN | im Frontend-Code konfiguriert; Wert: [VOM INHABER ZU ERGÄNZEN: Fundort] | schaltet Expert-Modus frei |

**Notfall-Rotation:** Cloudflare-API-Token und Anthropic-Key können jederzeit in den jeweiligen Konsolen neu erzeugt und in den GitHub-Secrets ersetzt werden — der nächste Lauf nutzt sie automatisch.

## 6. Deploy-Regeln (Kurzfassung der Arbeitsdisziplin)

1. Batch-Deployments: Ideen im Session-Backlog sammeln; deployen erst bei lohnendem Paket. **Ausnahme: kritische Bugs sofort.**
2. Jede Aggregator-Version zählt hoch (`AGGREGATOR_VERSION`), Änderungen ins Docstring-Changelog.
3. Vor jedem Push: `python3 -m py_compile` + Universum-/Logik-Checks.
4. Nach jedem Deploy: „Run workflow" manuell + Output-Review (nicht nur Step-Grün — der KV-Upload färbt Steps bei Fehlschlag nicht rot, siehe Log-Zeile „KV-Upload").
5. Neuer Code ES6-/Modularitäts-konform (STRATEGIE.md §6, Filterfragen 3+4).
6. Strategische Entscheidungen → `docs/STRATEGIE.md` fortschreiben (Entscheidungs-Log §9).

## 7. Störungs-Runbook (Symptom → Diagnose → Maßnahme)

### 7.1 Frontend zeigt alte Daten / kein neuer Nachtlauf
1. GitHub → Actions: Gibt es heute einen Schedule-Run? **Kein Run bis ~07:00 UTC = wahrscheinlich nur GitHub-Queue-Verzögerung** (Geduld oder manuell „Run workflow").
2. Run rot → §7.2. Run grün, aber Frontend alt → Browser-Refresh erzwingen; dann `generated` im Master-JSON prüfen (KV-Konsole oder Frontend-Netzwerk-Tab).
3. Läuft der Cron seit >60 Tagen gar nicht: GitHub deaktiviert Schedules in inaktiven Repos — Actions-Seite zeigt dann einen Reaktivieren-Banner.

### 7.2 Nachtlauf schlägt fehl (Run rot)
Log des Steps „Run Market Aggregator" lesen. Häufigste Ursachen:
- **yfinance-Massenfehler / Rate-Limit:** viele „(2y_explicit)"-Warnungen, tickers_ok bricht ein → einige Stunden später manuell neu starten. Hält es an: yfinance-Version im Workflow pinnen/aktualisieren.
- **KV-Upload fehlgeschlagen** (`❌ KV-Upload`): CF-Token abgelaufen/rotiert → Secrets erneuern (§5).
- **MemoryError/OOM:** `max_workers` in `fetch_batch()` senken (12 → 8).
- **Einzelner Ticker-Crash:** ist abgefangen (landet in errors) — nie Lauf-fatal.

### 7.3 Track-Record-Probleme
- `master["trackRecord"].written == false`: `reason` lesen. `exists` = Dedupe (normal an Feiertagen/Doppel-Runs); `no_kv_creds`/`kv_put_failed` = Secrets prüfen; `exception:` = Bug melden, **Hauptlauf ist davon nie betroffen**.
- **Backup (implementiert 03.07.2026):** `tr_backup.py` exportiert **jeden Samstag** im Nachtlauf alle `tr:*`-Keys nach `backups/tr_backup_latest.json`; der Workflow committet die Datei — **die Git-History ist das Archiv** (jede Woche ein Stand). Wiederherstellung: gewünschten Stand aus der History holen, Keys per Cloudflare-API/Konsole zurückschreiben. Manuell auslösbar: Workflow-Run mit Env `TR_BACKUP_FORCE=1` (oder Script lokal mit CF-Credentials).

### 7.4 Externe Quellen leer (dixGex/pcr/fearGreed im Output = `{}`/null)
Bekannt und nicht lauf-kritisch — Overlays laufen dann neutral. Stand 03.07.2026: squeezemetrics + CBOE liefern von Actions-IPs aus wiederholt nicht (Beobachtung läuft; ggf. Quellen ersetzen). Fear&Greed (CNN) funktioniert.

### 7.5 KI-Features tot (Briefing/Deep Dive ohne Antwort)
1. ko-ai Worker erreichbar? `https://ko-ai.ahildebrand.workers.dev` (Cloudflare-Dashboard → Workers → Logs).
2. Anthropic-Key gültig / Kontingent? (Anthropic-Console)
3. Nur Briefing betroffen, Rest ok → bekannter Frontend-Datenfluss-Punkt (Briefing erbt `_alphaData` vom Alpha Desk; Backlog).

### 7.5a Daily-Snapshot-Briefing zeigt „n/v" bei VIX/Regime/PCR trotz vorhandener Daten
**Historie (14.07.2026):** Genau dieses Symptom war monatelang aktiv, unbemerkt — drei permanente Feldpfad-Bugs in `generate_daily_snapshot()` (Aggregator v5.8.1 und früher): `regime` suchte in `meta["regimeUsed"]` (existierte dort nie, lag nur in `strategyMeta`); `VIX` suchte in `snapshot["vix"]` (kein VIX-Symbol in `fetch_market_snapshot()`, echter Wert lag in `vixTerm["vix"]`); `PCR` suchte `pcr["pcr_equity"]`/`["pcr_index"]` (Schema hat nur einen Blended-Wert `pcr["pcr"]`). Seit v5.8.2 behoben — **falls dieses Symptom wieder auftaucht, zuerst hier nachsehen, ob jemand die Feldpfade in `generate_daily_snapshot()` versehentlich zurückgesetzt hat**, bevor eine neue Fehlersuche gestartet wird.
**Diagnose:** `curl https://ko-sync.ahildebrand.workers.dev/public/daily_market_snapshot | python3 -m json.tool` — `regime`, `marketContext.factors.vix.value` prüfen. Lokaler Reproduktionstest möglich: `generate_daily_snapshot()` isoliert mit synthetischem `master`-Dict aufrufen (siehe Commit-Historie `b269db1`/`afb85ac` für Testmuster).
**Verwandte Regression (14.07.2026):** Der MCM-Python-Port (`build_server_market_context()`) nutzt `timedelta` — fehlte kurzzeitig im Modul-Import (`from datetime import datetime, timezone` ohne `timedelta`), wodurch `generate_daily_snapshot()` bei JEDEM Aufruf mit `NameError` abstürzte und der KV-Push komplett übersprungen wurde (`ok: False`, alter Snapshot blieb stehen). Symptom: `curl .../daily_market_snapshot` liefert `ok: false` nach einem Deploy. **Erste Prüfung bei `ok: false`:** GitHub Actions Job-Log des letzten Laufs lesen (Job „aggregate" → Step-Output), Exception-Nachricht direkt sichtbar.

### 7.5b Frontend-Widgets zeigen stundenlang identische Live-Werte (VIX, Sektor-Mover, Screener)
**Historie (14.07.2026):** Zwei unabhängige Root Causes, beide behoben in axel-scanner v324–v326:
1. **Fehlender Cache-Buster:** `fetch(corsProxy + '/?url=' + encodeURIComponent(url))` ohne Zeitstempel-Query-Param + ohne `{cache:'no-store'}` — identische URL bei jedem Aufruf, Cache-Treffer (Browser und/oder CF-Worker-Proxy) statt echtem Request. Betraf 9 Stellen (VIX/VVIX/SKEW-Widget, Home-Mover, Gainers/Losers-Screener, Deep-Dive-Fetch, Treasury-Stress). **Standard-Fix-Muster:** `_cb=Date.now()` an die Ziel-URL anhängen, `{cache:'no-store'}` im `fetch()`-Call.
2. **Session-weiter „Fetch nie wieder"-Guard:** `fetchVix()` hatte an manchen Aufrufstellen einen äußeren Guard `if (_vixLevel === null)` — nach dem ersten erfolgreichen Fetch der Browser-Session wurde die Funktion nie wieder aufgerufen, wodurch die intern bereits korrekte 30-Minuten-TTL-Logik komplett wirkungslos blieb. **Prüfroutine bei ähnlichem Symptom:** nach Mustern wie `if (irgendeineVariable === null) fetchXYZ()` suchen — das ist fast immer ein Zeichen für einen unbeabsichtigten „einmal pro Session"-Cache, wo eigentlich die TTL-Logik in der Zielfunktion selbst die Freshness steuern sollte.

### 7.6 Frontend-Deployment
**Korrektur (14.07.2026): Cloudflare Pages baut NICHT automatisch aus dem Git-Repo.** Tatsächlicher Prozess (Axel): `index.html` wird lokal heruntergeladen, zusammen mit `help.html` in ein ZIP gepackt und manuell über das CF-Pages-Dashboard hochgeladen. **Praktische Konsequenz:** jede neue statische Datei (z.B. `macro-calendar.json`, hinzugefügt 13.07.2026) landet NICHT automatisch live, nur weil sie ins GitHub-Repo committed wurde — sie muss aktiv ins Deploy-ZIP aufgenommen werden, sonst liefert CF Pages für sie eine 404-HTML-Seite zurück (führte am 14.07.2026 zu einem `Unexpected token '<'`-Crash beim JSON-Parse im Frontend). **Deshalb Grundsatz seit 14.07.2026:** Neue Dateien, die das Frontend zur Laufzeit lädt, nach Möglichkeit direkt von `raw.githubusercontent.com/ahsub/axel-scanner/main/<datei>` fetchen statt als eigenständige Datei auf CF Pages zu erwarten — entkoppelt das Feature vollständig vom manuellen Deploy-Zip (siehe `ko-indicators-loader.js` `loadMacroCalendar()` als Referenzimplementierung).
Rollback: Pages-Dashboard → Deployments → früheres Deployment „Rollback".

### 7.7 Totalausfall / Disaster Recovery
Alles Wiederherstellbare liegt in den GitHub-Repos (Quelle der Wahrheit):
1. Cloudflare-Konto/Zone neu: Pages-Projekt auf `axel-scanner` zeigen, Worker aus `ahsub/workers` deployen, neuen KV-Namespace anlegen → dessen ID in GitHub-Secrets (`CF_KV_NS_ID`) und ggf. Worker-Bindings eintragen.
2. Einen Aggregator-Lauf starten → alle regenerierbaren KV-Daten sind wieder da.
3. `tr:*`-Historie aus letztem Backup einspielen (§7.3).
4. DNS: underlyingiq.com auf Cloudflare Pages [VOM INHABER ZU ERGÄNZEN: Registrar-Zugang].

## 8. Wer weiß was (Stand 03.07.2026)

- **Dr. Axel Hildebrand:** Inhaber, einziger Kenner des Gesamtsystems, aller Konten und der fachlichen Logik. **Single Point of Failure — dieses Dokument ist die Gegenmaßnahme.**
- **Claude-Arbeitssessions:** Entwicklungsarbeit erfolgt sessionweise ohne persistenten Zugriff; Kontext wird über Übergabeprotokolle + `docs/STRATEGIE.md` + dieses RUNBOOK transportiert.
- Nachfolge-/Mitwirkungsfrage: offen (STRATEGIE.md §7, Entscheidung 1).

## 9. Fortschreibung

Dieses Dokument wird bei jeder Infrastruktur-Änderung mitversioniert (Pflichtteil der Deploy-Disziplin). Prüfroutine: einmal pro Quartal alle Platzhalter und §5-Fundorte gegenchecken.

**Changelog:**
- v1.3 (14.07.2026): §2/§3 — ko-watchdog (Dispatch-Absicherung, 2 Crons), zweiter Aggregator-Cron (NYSE-Lauf 13:30 UTC), 8 Leaderboards, Daily-Market-Snapshot-Schritt (MCM-Port) ergänzt. §4 — daily_market_snapshot/daily_market_snapshot_us Keys ergänzt. §7.5a/§7.5b neu — dokumentiert 3 permanente Feldpfad-Bugs im Snapshot-Briefing (VIX/Regime/PCR "n/v", seit v5.8.2 behoben) und die Cache-Staleness-Bugklasse im Frontend (fehlender Cache-Buster + Session-weiter "Fetch nie wieder"-Guard). §7.6 korrigiert — CF Pages deployt NICHT automatisch aus Git, sondern ueber manuellen ZIP-Upload (index.html+help.html); neuer Grundsatz: laufzeit-geladene Dateien wo moeglich direkt von raw.githubusercontent fetchen statt vom Deploy-Zip abhaengig zu machen.
- v1.2 (03.07.2026): §7.3 — tr-Backup implementiert (samstags, Git-History als Archiv); Phase B (Evaluator) live.
- v1.1 (03.07.2026): §3 präzisiert — Datenreferenz ist immer „letzter Handelstag" (Feiertags-robust), keine feste Wochentags-Zuordnung.
- v1.0 (03.07.2026): Erstfassung.
