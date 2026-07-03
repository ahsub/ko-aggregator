# UIQ RUNBOOK — Betriebs- und Störungshandbuch (Bus-Factor-Dokument)
**Version 1.0 | Stand: 03.07.2026 | Zweck: Ein fähiger Dritter kann das System mit diesem Dokument verstehen, betreiben und im Störfall wiederherstellen.**

> Platzhalter im Format `[VOM INHABER ZU ERGÄNZEN: …]` müssen von Dr. Axel Hildebrand befüllt werden. Dieses Dokument enthält bewusst **keine Secrets** — nur deren Fundorte.

---

## 1. Was ist UnderlyingIQ (in 5 Sätzen)

UIQ (underlyingiq.com) ist eine browserbasierte Marktanalyse-PWA. Ein nächtlicher Python-Job (der „Aggregator") lädt Kursdaten für ~640 Ticker, berechnet Indikatoren, ein Marktregime und Strategie-Scores und schreibt das Ergebnis als JSON in einen Cloudflare-KV-Speicher. Das Frontend (statisches HTML/JS auf Cloudflare Pages) liest ausschließlich aus diesem KV — es gibt keinen klassischen Backend-Server. KI-Funktionen (Morning Briefing, Deep Dive) laufen über einen Cloudflare Worker, der die Anthropic-API kapselt. Kernidee ist der „Strategie-Router": Marktregime erkennen → passende Strategie → beste Underlyings (siehe `docs/STRATEGIE.md`).

## 2. Systemlandkarte

| Komponente | Ort | Zweck |
|---|---|---|
| **Frontend** | Repo `ahsub/axel-scanner` → Cloudflare Pages → underlyingiq.com | UI; monolithische `index.html` (aktuell v241) |
| **Aggregator** | Repo `ahsub/ko-aggregator` (`market_aggregator.py`, aktuell v4.4) | Nächtlicher Datenlauf via GitHub Actions |
| **Track-Record-Layer** | `ahsub/ko-aggregator/tr_layer.py` | Snapshot-Logging der Empfehlungen (Spez: `docs/TRACK_RECORD_SPEC.md`) |
| **ko-modules (CDN)** | Repo `ahsub/ko-modules` via jsDelivr, **Hash-pinned** | Geteilte ES6-Module (ko-strategies.js v2.1.0 = Commit `785e61e` u.a.) |
| **ko-ai Worker** | Cloudflare Worker `ko-ai.ahildebrand.workers.dev` (v1.5) | KI-Proxy (Anthropic), Request-Logging, Extra-Ticker-Review |
| **ko-sync Worker** | Cloudflare Worker | Cloud-Sync der Nutzereinstellungen |
| **CORS-Proxy** | `my-cors-proxy.ahildebrand.workers.dev` | Umgeht CORS für externe Datenquellen im Frontend |
| **KV-Namespace** | Cloudflare KV `86c05f66e32346b99e720d861fedd1de` | Zentrale Datendrehscheibe |
| **Cloudflare-Account** | Account-ID `2ee58f98cf0979e660841a0764b7f17d` | Pages + Workers + KV |
| Schwesterprojekte | `ahsub/refundex` (+ `refundex-docs`), `ahsub/premium-options`, `ahsub/ko-rechner` u.a. | Eigenständig, teilen Infrastruktur-Muster |

## 3. Der Nachtlauf (das Herz des Systems)

**Zeitplan:** GitHub Actions, Cron `37 03 * * 1-6` UTC (Mo–Sa; Mo verarbeitet Freitagsdaten). Workflow: `.github/workflows/market-aggregator.yml`, Name „KO-Scanner Market Aggregator". **Achtung: GitHub-Cron ist best effort** — Verzögerungen von Minuten bis Stunden sind normal (dokumentiert: 3h23min am 02.07.2026). Deshalb 03:37 statt 04:00. Langfristig geplant: minutengenauer Dispatch via Cloudflare-Worker-Cron.

**Ablauf (Schritte im Log nachvollziehbar):**
1. Ticker-Universum bauen (fest codierte Listen + admin-freigegebene Extra-Ticker aus KV)
2. OHLCV via yfinance laden (parallel, ~40–60 s)
3. Indikatoren + Regime + 5 Strategie-Scores je Ticker
4. Externe Quellen: VIX-Termstruktur, Fear&Greed (CNN), DIX/GEX (squeezemetrics), PCR (CBOE) — **alle mit Fallback auf leer, brechen den Lauf nie**
5. Leaderboards + regime-adaptive Master-Shortlist
6. KI-Enrichment der Top 15 (Anthropic API, nur wenn Key vorhanden)
7. Fundamental-Enrichment (3 Felder, Top-Kandidaten)
8. **Track-Record-Snapshot** (tr_layer.py — fehlerisoliert)
9. KV-Upload: `master_market_data` (+ `options_watchlist`, `known_universe_tickers`)

**Manuell starten:** GitHub → ko-aggregator → Actions → „KO-Scanner Market Aggregator" → **Run workflow** (Branch main). **NIEMALS „Re-run"** eines alten Runs verwenden — der nutzt den alten Code-Stand.

**Erfolg verifizieren:** (a) Run grün in Actions; (b) im Frontend nach Refresh: `generated`-Zeitstempel + Ticker-Zahl im Alpha-Desk-Header; (c) im Master-JSON: `meta.version`, `trackRecord.written`, `strategyMeta.regimeUsed`.

## 4. KV-Schlüsselverzeichnis

| Key | Inhalt | Regenerierbar? |
|---|---|---|
| `master_market_data` | Voll-Output des Nachtlaufs (~1–2 MB) | ✅ durch neuen Lauf |
| `options_watchlist` | Kompakt-Kopie für Options-Desk | ✅ |
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
- **Backup (offene Maßnahme, hohe Priorität):** `tr:*`-Keys sind die einzigen unwiederbringlichen Daten. Vorgesehen: wöchentlicher Export aller `tr:`-Keys als Workflow-Artifact oder Repo-Commit (`backups/`). Bis dahin: gelegentlicher manueller Export über die Cloudflare-KV-Konsole.

### 7.4 Externe Quellen leer (dixGex/pcr/fearGreed im Output = `{}`/null)
Bekannt und nicht lauf-kritisch — Overlays laufen dann neutral. Stand 03.07.2026: squeezemetrics + CBOE liefern von Actions-IPs aus wiederholt nicht (Beobachtung läuft; ggf. Quellen ersetzen). Fear&Greed (CNN) funktioniert.

### 7.5 KI-Features tot (Briefing/Deep Dive ohne Antwort)
1. ko-ai Worker erreichbar? `https://ko-ai.ahildebrand.workers.dev` (Cloudflare-Dashboard → Workers → Logs).
2. Anthropic-Key gültig / Kontingent? (Anthropic-Console)
3. Nur Briefing betroffen, Rest ok → bekannter Frontend-Datenfluss-Punkt (Briefing erbt `_alphaData` vom Alpha Desk; Backlog).

### 7.6 Frontend-Deployment
Cloudflare Pages baut automatisch aus `ahsub/axel-scanner` (main). Rollback: Pages-Dashboard → Deployments → früheres Deployment „Rollback". 

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

**Changelog:** v1.0 (03.07.2026) — Erstfassung.
