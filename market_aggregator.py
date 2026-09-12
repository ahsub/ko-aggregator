# Workflow-Version: v1.2 (vorheriger, unversionierter Stand = implizit v1.0)
#
# CHANGELOG (neueste zuerst):
# v1.2 (11.09.2026, Axel + Claude): Umstellung von zwei Vor-Handelsschluss-
#      Läufen (Lauf 1: 03:37 UTC vor Xetra, Lauf 2: 13:30 UTC bei NYSE-
#      Öffnung) auf EINEN einzigen Lauf NACH US-Börsenschluss (22:00 UTC
#      Mo-Fr). Root-Cause-Fund: `get_last_trading_day()` liest die letzte
#      SPY-Tageskerze — die erscheint bei yfinance erst nach Börsenschluss
#      (20:00 UTC EDT / 21:00 UTC EST). Beide alten Läufe lagen davor, der
#      Public Digest war dadurch strukturell IMMER auf den Vortag datiert,
#      nie auf den tatsächlichen Handelstag. 22:00 UTC liegt ganzjährig
#      sicher nach Schluss (Puffer für Nachbörsenhandel + Datenverfügbar-
#      keit). Samstag entfällt (war nur wegen Xetra-Bezug in Lauf 1 nötig,
#      s. `* * 1-6`) — dadurch würde das wöchentliche Track-Record-Backup
#      (`tr_backup.py`, prüft intern `isoweekday()==6`) nie mehr laufen;
#      als eigener, schlanker Workflow ausgelagert: `tr-backup-saturday.yml`
#      (kein voller Aggregator-Lauf, keine KI-/yfinance-Kosten, nur Backup +
#      Commit). Env `MORNING_RUN_CRON` → `EOD_RUN_CRON` umbenannt (war beim
#      Public-Digest-Gate ohnehin nur noch ein einziger Cron-Wert, Name
#      spiegelt jetzt den tatsächlichen Zweck). Mit dieser Änderung
#      gekoppelt (separate Deploys, nicht Teil dieser Datei): `ko-watchdog`
#      (wrangler.toml + ko-watchdog.js, RUN_SCHEDULES auf einen Eintrag
#      reduziert) und `ko-cron-trigger` (wrangler.toml, Redundanz-Trigger
#      auf 22:00 UTC verschoben) — beide müssen synchron zu dieser Cron-Zeit
#      bleiben, sonst laufen sie am alten (jetzt falschen) Zeitpunkt weiter
#      und lösen dabei via workflow_dispatch ungewollt wieder einen
#      Vor-Schluss-Digest aus.
# v1.1 (10.09.2026, Axel + Claude): AI_delivery_public — drei neue Steps
#      ("Checkout UIQ-Suite (Public Recommendations Script)", "Node.js
#      Setup", "Generate Public Recommendations") zwischen "Run Market
#      Aggregator" und "Track-Record Backup" eingefuegt, s. Uebergabe-
#      protokoll 09.09./10.09.2026 Punkt 6/10. Ruft
#      UIQ-Suite/scripts/generate_public_recommendations.js auf (Node,
#      liest master_market_data.json aus dem Checkout-Root). Neuer
#      Job-level env MORNING_RUN_CRON bindet alle drei Steps an Lauf 1
#      (03:37 UTC, vor Xetra) + workflow_dispatch — verhindert, dass der
#      Job (2x/Tag) versehentlich 2x/Tag statt der beschlossenen 1x/Tag-
#      Frequenz einen Public Digest erzeugt (Frequenz-Entscheidung s.
#      Uebergabeprotokoll Punkt 10). Bewusst OHNE continue-on-error fuer
#      den Start — Pruefpunkt nach 10 fehlerfreien Handelstags-Laeufen
#      (~2 Wochen), dann auf continue-on-error: true umstellen, damit
#      das Feature den Track-Record-Lauf nie blockieren kann.
# v1.0 (Datum unbekannt — Datei war bisher unversioniert, dieser
#      Changelog-Kopf wurde erst mit v1.1 eingefuehrt): Basis-Workflow
#      (Checkout, Python-Setup, Aggregator-Lauf, Track-Record-Backup,
#      Archiv-Commit, Artifact-Upload).

name: KO-Scanner Market Aggregator

permissions:
  contents: write   # v4.5: Track-Record-Backup committet nach backups/ (RUNBOOK §7.3)

on:
  schedule:
    - cron: '00 22 * * 1-5'   # Nachbörsen-Lauf: 22:00 UTC = 00:00 MESZ/01:00 MEZ (nach NYSE-Schluss 20:00/21:00 UTC)
  workflow_dispatch:
    inputs:
      force_backup:
        description: 'TR-Backup erzwingen (überschreibt Samstag-Guard)'
        required: false
        default: 'false'
        type: choice
        options:
          - 'false'
          - 'true'

jobs:
  aggregate:
    runs-on: ubuntu-latest
    timeout-minutes: 30
    env:
      # AI_delivery_public (10.09.2026, umbenannt 11.09.2026 v1.2): muss exakt
      # der Cron-Zeile oben entsprechen — einzige Stelle, die bei einer
      # künftigen Cron-Änderung noch von Hand mitgepflegt werden muss. Alle
      # "if"-Bedingungen unten referenzieren diese eine Variable statt den
      # String mehrfach zu wiederholen. Umbenannt von MORNING_RUN_CRON, da
      # es seit v1.2 kein "Morgen-Lauf" mehr ist, sondern der einzige,
      # nachbörsliche Lauf.
      EOD_RUN_CRON: '00 22 * * 1-5'

    steps:
      - name: Checkout
        uses: actions/checkout@v4

      - name: Python 3.11 Setup
        uses: actions/setup-python@v5
        with:
          python-version: '3.11'

      - name: Install dependencies
        run: |
          pip install --upgrade pip
          # yfinance GEPINNT (SWOT №35, 07.08.2026): Breaking-Changes schlagen sonst
          # ungefiltert auf den Produktionslauf durch. Update nur nach explizitem Test.
          # Aktuelle stabile Version: 1.5.2 (07.08.2026)
          pip install "yfinance==1.5.2" requests numpy pandas openpyxl

      - name: Clear yfinance cache
        run: rm -rf ~/.cache/py-yfinance/ || true

      - name: Unit Tests (DCE + Regime)
        run: |
          pip install pytest scipy numpy --break-system-packages -q
          # DCE-Tests (Brier Score, Konfidenz-Engine)
          pytest tests/test_dce_layer.py -v --tb=short
          # Regime-Tests (SWOT №32, 07.08.2026): schützt Track-Record vor Scoring-Bugs
          # Testet: Ratio-Konventionen, MSE-Klassifikation, History-Flag, v4.3-Regression
          pytest tests/test_regime.py -v --tb=short

      - name: Run Market Aggregator
        env:
          CF_ACCOUNT_ID:        ${{ secrets.CF_ACCOUNT_ID }}
          CF_API_TOKEN:         ${{ secrets.CF_API_TOKEN }}
          CF_KV_NS_ID:          ${{ secrets.CF_KV_NS_ID }}
          ANTHROPIC_API_KEY:    ${{ secrets.ANTHROPIC_API_KEY }}
          FLASHALPHA_API_KEY:   ${{ secrets.FLASHALPHA_API_KEY }}
          FRED_API_KEY:         ${{ secrets.FRED_API_KEY }}
          FINRA_CLIENT_ID:      ${{ secrets.FINRA_CLIENT_ID }}
          FINRA_CLIENT_SECRET:  ${{ secrets.FINRA_CLIENT_SECRET }}
          PYTHONUNBUFFERED:     "1"
        run: |
          python market_aggregator.py
          echo "Exit Code: $?"

      - name: Checkout UIQ-Suite (Public Recommendations Script)
        # UIQ-Suite ist ein oeffentliches Repo -> kein zusaetzliches PAT-Secret
        # noetig, der Default-GITHUB_TOKEN reicht fuer den Checkout.
        if: github.event.schedule == env.EOD_RUN_CRON || github.event_name == 'workflow_dispatch'
        uses: actions/checkout@v4
        with:
          repository: ahsub/UIQ-Suite
          path: uiq-suite

      - name: Node.js Setup
        if: github.event.schedule == env.EOD_RUN_CRON || github.event_name == 'workflow_dispatch'
        uses: actions/setup-node@v4
        with:
          node-version: '22'

      - name: Generate Public Recommendations
        # PRUEFPUNKT (Axel-Entscheidung, 10.09.2026): nach 10 fehlerfreien
        # Handelstags-Laeufen (~2 Wochen) auf `continue-on-error: true`
        # umstellen — das Public-Digest-Feature ist dauerhaft nachrangig
        # zum Track-Record-Lauf und soll ihn langfristig nie blockieren
        # koennen. Bis dahin bewusst OHNE continue-on-error, damit Fehler
        # in diesem neuen Codepfad sofort auffallen statt still zu
        # verschwinden.
        if: github.event.schedule == env.EOD_RUN_CRON || github.event_name == 'workflow_dispatch'
        env:
          ANTHROPIC_API_KEY:    ${{ secrets.ANTHROPIC_API_KEY }}
          CF_ACCOUNT_ID:        ${{ secrets.CF_ACCOUNT_ID }}
          CF_API_TOKEN:         ${{ secrets.CF_API_TOKEN }}
          CF_KV_NS_ID:          ${{ secrets.CF_KV_NS_ID }}
        run: |
          node uiq-suite/scripts/generate_public_recommendations.js
          echo "Exit Code: $?"

      - name: Track-Record Backup (nur samstags aktiv, ODER force_backup)
        # Seit v1.2 (11.09.2026): dieser Workflow laeuft nur noch Mo-Fr, der
        # interne Samstag-Guard in tr_backup.py (isoweekday()==6) greift hier
        # also im Regelfall NIE mehr — das woechentliche Backup kommt seither
        # aus dem separaten `tr-backup-saturday.yml`. Dieser Step bleibt
        # trotzdem bestehen, rein als manueller Force-Pfad (workflow_dispatch
        # mit force_backup=true) fuer Ad-hoc-Backups ausserhalb des
        # Samstags-Rhythmus.
        if: always()
        env:
          CF_ACCOUNT_ID:    ${{ secrets.CF_ACCOUNT_ID }}
          CF_API_TOKEN:     ${{ secrets.CF_API_TOKEN }}
          CF_KV_NS_ID:      ${{ secrets.CF_KV_NS_ID }}
          TR_BACKUP_FORCE:  ${{ github.event.inputs.force_backup == 'true' && '1' || '0' }}
        run: python tr_backup.py

      - name: Archive committen (tr-Backup + FIN-Archiv + Snapshots, Git-History = Archiv)
        if: always()
        run: |
          git config user.name "uiq-nightly"
          git config user.email "actions@users.noreply.github.com"
          [ -f backups/tr_backup_latest.json ] && git add backups/tr_backup_latest.json || true
          [ -d data/fundamentals ] && git add data/fundamentals || true
          [ -d data/iv_history ] && git add data/iv_history || true
          [ -d data/breadth_history ] && git add data/breadth_history || true
          # Rolling-Window-Snapshots (v5.16.0): gzip'd master_market_data, 90-Tage-Fenster
          # Gelöschte Snapshots (>90 Tage) via git rm entfernen
          [ -d data/snapshots ] && git add data/snapshots/ || true
          git ls-files --deleted data/snapshots/ | xargs -r git rm --cached
          git diff --cached --quiet || (git pull --rebase --autostash && git commit -m "archive: tr-Backup/FIN-Archiv/Snapshots $(date -u +%F)" && git push)

      - name: Upload artifact
        uses: actions/upload-artifact@v4
        if: always()
        with:
          name: master-market-data-${{ github.run_number }}
          path: master_market_data.json
          retention-days: 7
