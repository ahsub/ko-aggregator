// test_worker_ki_eic.mjs — ko-sync-worker v2.5: Sichtbarkeitsregel fuer ki_eic (P1 #5, Befund 03.10.2026)
// Regel: Fuer Static/Tester darf ki_eic (und die vier Options-Parameter) auf KEINEM geprueften
//        oeffentlichen Pfad erscheinen; fuer Owner muss es auf den vorgesehenen Pfaden erhalten bleiben.
// Geprueft: /public/master_market_data (eingebettete optionsWatchlist, masterShortlist) und
//           /public/options_watchlist (Form {tickers:[...]} und reines Array).
// Lauf: node tests/test_worker_ki_eic.mjs   (kopiert den Worker temporaer als .mjs, keine Abhaengigkeiten)
// Optional: WORKER_PATH=<Pfad> um eine andere Worker-Datei zu pruefen (z. B. Negativkontrolle).
import fs from 'fs'; import os from 'os'; import path from 'path'; import { pathToFileURL } from 'url';
import assert from 'assert';
const here = path.dirname(new URL(import.meta.url).pathname);
const src = process.env.WORKER_PATH || path.join(here, '..', 'workers', 'ko-sync-worker.js');
const tmp = path.join(fs.mkdtempSync(path.join(os.tmpdir(), 'w-')), 'worker.mjs');
fs.copyFileSync(src, tmp);
const worker = (await import(pathToFileURL(tmp).href)).default;

const FORBIDDEN = /ki_eic|strikeSuggestion|deltaTarget|premiumEstimate/;
const SHORTLIST_SENSITIVE = ['trigger', 'stopLoss', 'target', 'crv', 'holdingDays', 'positionPct', 'leverageRec'];

const eic = (strike) => ({ strikeSuggestion: strike, dte: 30, deltaTarget: -0.5, premiumEstimate: 3.2 });
const kiOpt = () => ({ strategy: 'csp_atm_na', fitScore: 75, conclusion: 'FAVOURABLE', fitLabel: 'HIGH FIT',
  note: 'Deskriptive Modellauswertung', modelParamRange: { dte: '21-35 Tage', strikeGuideline: 'am oder nahe dem aktuellen Kurs' } });
const OPT = () => [
  { sym: 'AAA', price: 85.2, hvp: 40, ki: kiOpt(), ki_eic: eic(85) },
  { sym: 'BBB', price: 9.23, hvp: 92, ki: { ...kiOpt(), strategy: 'credit_spread' }, ki_eic: eic(8.5) },
  { sym: 'CCC', price: 50.0, hvp: 30 },                                   // ohne ki / ki_eic (Rang > 15)
  { sym: 'DDD', price: 20.0, hvp: 35, ki: kiOpt() },                      // ki ohne ki_eic (Fehlerfall im Aggregator)
];
const SHORT = () => [{ sym: 'AAA', price: 85.2, ki: { fitScore: 70, trigger: 'x', stopLoss: 1, target: 2, crv: 2.1,
  holdingDays: 5, positionPct: 3, leverageRec: 2, conclusion: 'FAVOURABLE' } }];
const MASTER = () => ({ meta: { last_trading_day: '2026-10-02' }, dce_public: { schema: 'dce_public/1' },
  masterShortlist: SHORT(), optionsWatchlist: OPT() });
const WATCH_OBJ = () => ({ generated: '2026-10-03T01:01:35Z', tickers: OPT(), count: 4, criteria: { min_hvp: 20 } });
const WATCH_ARR = () => OPT();

const store = {};
const env = { OWNER_TOKEN: 'own', STATIC_TOKEN: 'sta',
  KO_SYNC_KV: { get: async (k) => store[k] ?? null } };
const call = (p, tok) => worker.fetch(new Request('https://w.test' + p,
  { headers: tok ? { Authorization: 'Bearer ' + tok } : {} }), env);
const setStore = (master, watch) => {
  store.master_market_data = JSON.stringify(master); store.options_watchlist = JSON.stringify(watch); };

let fails = 0; const t = async (n, f) => { try { await f(); console.log('OK  ', n); } catch (e) { fails++; console.log('FAIL', n, '-', e.message); } };
const stripEic = (items) => items.map(({ ki_eic, ...r }) => r);

// ── Static/Tester: kein ki_eic und keine Options-Parameter, auf keinem Pfad ─────────────────────
for (const [label, mk] of [['{tickers:[…]}', WATCH_OBJ], ['reines Array', WATCH_ARR]]) {
  await t(`options_watchlist (${label}): STATIC ohne ki_eic/Options-Parameter im gesamten Body`, async () => {
    setStore(MASTER(), mk());
    const r = await call('/public/options_watchlist', 'sta'); assert.equal(r.status, 200);
    const txt = await r.text(); assert.ok(!FORBIDDEN.test(txt), 'verbotenes Feld im Static-Body: ' + (txt.match(FORBIDDEN) || [])[0]);
  });
  await t(`options_watchlist (${label}): STATIC behaelt uebrige Felder (nur ki_eic entfernt)`, async () => {
    setStore(MASTER(), mk());
    const j = await (await call('/public/options_watchlist', 'sta')).json();
    const items = Array.isArray(j) ? j : j.tickers;
    assert.deepEqual(items, stripEic(OPT()));
    assert.equal(items[0].ki.fitScore, 75); assert.ok(items[0].ki.modelParamRange);
  });
  await t(`options_watchlist (${label}): OWNER erhaelt ki_eic (Rohdaten, byte-identisch)`, async () => {
    setStore(MASTER(), mk());
    const raw = store.options_watchlist;
    const r = await call('/public/options_watchlist', 'own'); assert.equal(r.status, 200);
    assert.equal(await r.text(), raw);
    assert.ok(/"ki_eic"/.test(raw));
  });
}
await t('master_market_data: STATIC ohne ki_eic/Options-Parameter im gesamten Body', async () => {
  setStore(MASTER(), WATCH_OBJ());
  const r = await call('/public/master_market_data', 'sta'); assert.equal(r.status, 200);
  const txt = await r.text(); assert.ok(!FORBIDDEN.test(txt), 'verbotenes Feld im Static-Body: ' + (txt.match(FORBIDDEN) || [])[0]);
});
await t('master_market_data: STATIC ohne sensible Shortlist-Felder, uebrige ki-Felder erhalten', async () => {
  setStore(MASTER(), WATCH_OBJ());
  const j = await (await call('/public/master_market_data', 'sta')).json();
  const ki = j.masterShortlist[0].ki;
  for (const k of SHORTLIST_SENSITIVE) assert.ok(!(k in ki), 'sensibles Feld vorhanden: ' + k);
  assert.equal(ki.fitScore, 70); assert.equal(ki.conclusion, 'FAVOURABLE');
  assert.deepEqual(j.optionsWatchlist, stripEic(OPT()));
});
await t('master_market_data: OWNER erhaelt ki_eic und Shortlist-Felder (byte-identisch)', async () => {
  setStore(MASTER(), WATCH_OBJ());
  const raw = store.master_market_data;
  const r = await call('/public/master_market_data', 'own'); assert.equal(r.status, 200);
  assert.equal(await r.text(), raw);
  const j = JSON.parse(raw);
  assert.equal(j.optionsWatchlist.filter((x) => x.ki_eic).length, 2);
  for (const k of SHORTLIST_SENSITIVE) assert.ok(k in j.masterShortlist[0].ki);
});
// ── Gleiche Symbolmenge: Static zeigt dieselben Ticker wie Owner (nur Felder fehlen) ───────────────
await t('beide Routen: Static und Owner liefern dieselben Ticker in derselben Reihenfolge', async () => {
  setStore(MASTER(), WATCH_OBJ());
  const syms = async (p, tok) => { const j = await (await call(p, tok)).json(); return (Array.isArray(j) ? j : (j.tickers || j.optionsWatchlist)).map((x) => x.sym); };
  assert.deepEqual(await syms('/public/options_watchlist', 'sta'), await syms('/public/options_watchlist', 'own'));
  assert.deepEqual(await syms('/public/master_market_data', 'sta'), await syms('/public/master_market_data', 'own'));
});
// ── Auth-Grenzen ──────────────────────────────────────────────────────────────────────────────────
await t('beide Routen: kein/falsches Token -> 401, kein Body mit ki_eic', async () => {
  setStore(MASTER(), WATCH_OBJ());
  for (const p of ['/public/options_watchlist', '/public/master_market_data']) {
    for (const tok of [undefined, 'bad']) {
      const r = await call(p, tok); assert.equal(r.status, 401); assert.ok(!FORBIDDEN.test(await r.text()));
    }
  }
});
await t('/sync/*: liefert ki_eic nicht aus Aggregator-Keys (options_watchlist/master_market_data nicht in Allowlist)', async () => {
  setStore(MASTER(), WATCH_OBJ());
  for (const k of ['options_watchlist', 'master_market_data']) {
    const r = await worker.fetch(new Request('https://w.test/sync/' + k, { headers: { 'X-UIQ-Token': 'tester123' } }), env);
    assert.equal(r.status, 400); assert.ok(!FORBIDDEN.test(await r.text()));
  }
});
// ── Negativkontrolle: Der Scan erkennt das Feld im Owner-Body (Test kann also fehlschlagen) ────────
await t('Negativkontrolle: FORBIDDEN-Scan trifft den Owner-Body', async () => {
  setStore(MASTER(), WATCH_OBJ());
  assert.ok(FORBIDDEN.test(await (await call('/public/options_watchlist', 'own')).text()));
});
process.exit(fails ? 1 : 0);
