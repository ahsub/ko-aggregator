// test_worker_dce.mjs — ko-sync-worker v2.5: DCE-Trennung (SUITE №72 / Runmap 2, Nacht A)
// Lauf: node tests/test_worker_dce.mjs   (kopiert den Worker temporaer als .mjs, keine Abhaengigkeiten)
import fs from 'fs'; import os from 'os'; import path from 'path'; import { pathToFileURL } from 'url';
import assert from 'assert';
const here = path.dirname(new URL(import.meta.url).pathname);
const tmp = path.join(fs.mkdtempSync(path.join(os.tmpdir(), 'w-')), 'worker.mjs');
fs.copyFileSync(path.join(here, '..', 'workers', 'ko-sync-worker.js'), tmp);
const worker = (await import(pathToFileURL(tmp).href)).default;

const DCE = { confidence: 71, mode: 'GREEN', direction: 'SELL', position_size: 1.0, warnings: ['x'] };
const MASTER = { meta: { last_trading_day: '2026-09-30', dce_cusum_buffer: [17.5] }, dce: DCE,
  dce_public: { schema: 'dce_public/1', signal_breadth: { status: 'ok' } }, masterShortlist: [], optionsWatchlist: [] };
const store = { master_market_data: JSON.stringify(MASTER), dce_internal: JSON.stringify(DCE) };
const env = { OWNER_TOKEN: 'own', STATIC_TOKEN: 'sta',
  KO_SYNC_KV: { get: async (k) => store[k] ?? null } };
const call = (p, tok) => worker.fetch(new Request('https://w.test' + p,
  { headers: tok ? { Authorization: 'Bearer ' + tok } : {} }), env);

let fails = 0; const t = async (n, f) => { try { await f(); console.log('OK  ', n); } catch (e) { fails++; console.log('FAIL', n, e.message); } };

await t('owner/dce: ohne Token 401', async () => assert.equal((await call('/owner/dce')).status, 401));
await t('owner/dce: falsches Token 401', async () => assert.equal((await call('/owner/dce', 'x')).status, 401));
await t('owner/dce: STATIC_TOKEN 403, kein DCE im Body', async () => {
  const r = await call('/owner/dce', 'sta'); assert.equal(r.status, 403);
  assert.ok(!(await r.text()).includes('position_size')); });
await t('owner/dce: OWNER liefert internes Objekt, no-store', async () => {
  const r = await call('/owner/dce', 'own'); assert.equal(r.status, 200);
  assert.equal(r.headers.get('Cache-Control'), 'private, no-store');
  assert.deepEqual(await r.json(), DCE); });
await t('master_market_data: STATIC_TOKEN ohne dce/Puffer, mit dce_public', async () => {
  const j = await (await call('/public/master_market_data', 'sta')).json();
  assert.ok(!('dce' in j)); assert.ok(!('dce_cusum_buffer' in j.meta)); assert.equal(j.dce_public.schema, 'dce_public/1'); });
await t('master_market_data: OWNER unveraendert (Rohdaten)', async () => {
  const j = await (await call('/public/master_market_data', 'own')).json(); assert.ok('dce' in j); });
await t('master_market_data: kein/falsches Token 401', async () => {
  assert.equal((await call('/public/master_market_data')).status, 401);
  assert.equal((await call('/public/master_market_data', 'bad')).status, 401); });
await t('owner/dce: nicht im KV -> 404 fuer Owner', async () => {
  const saved = store.dce_internal; delete store.dce_internal;
  assert.equal((await call('/owner/dce', 'own')).status, 404); store.dce_internal = saved; });
process.exit(fails ? 1 : 0);
