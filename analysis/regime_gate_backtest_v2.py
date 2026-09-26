#!/usr/bin/env python3
"""
regime_gate_backtest_v2.py — Korrigierter Regime-Gate-Backtest (Backlog №34 / Go-Kriterium 2)
=============================================================================================
Version: v2.2 (26.09.2026, Claude + Axel) — FORSCHUNGSFASSUNG, kein Produktionscode.

CHANGELOG
  v2.2 (26.09.2026): Reviewer-Runde 2.
       - HAUPTKENNZAHL ist jetzt der Test der taeglichen Differenzrendite
         Gate minus Buy & Hold (Information Ratio, t-Statistik mit
         Newey-West-Standardfehler, einseitiger p-Wert). Die Frage von
         Go-Kriterium 2 lautet "besser als Buy & Hold", nicht "Sharpe > 0".
       - Zwei Ausfuehrungsvarianten: Lag 1 (idealisiert) und Lag 2
         (konservative Verzoegerungs-Sensitivitaet). Lookahead nur noch als
         dokumentierte Fehlervariante.
       - DSR nur noch als Nebeninformation, berechnet mit
         deflated_sharpe_ratio.py v2.0 (Einheitenfehler aus v1 behoben;
         die in v2.0/v2.1 ausgewiesene "DSR 0,00" war ein Rechenartefakt).
       - Kalenderpruefung: Luecken > 2 Werktage muessen bekannte
         Boersenschliessungen sein, sonst Abbruch.
       - Initialisierung der ersten Position dokumentiert und geprueft.
  v2.1 (26.09.2026): Look-ahead-Selbsttest, Turnover, Fehldaten-Politik,
       Testfamilie als Liste.
  v2.0 (26.09.2026): Erstfassung — Lag-Korrektur, Wechselkosten.

ANLASS
  refundex/engine/backtest_2007_2026.py (07.08.2026) wendete das Regime von
  Tag t auf die Rendite desselben Tages t an (Look-ahead). Details:
  UIQ-Suite SUITE.md, Backlog №34 (Versionen 4.32/4.33).

SIGNAL, AUSFUEHRUNG, RENDITEINTERVALL (Modellannahmen)
  - Signal: aus VIX- und VIX3M-SCHLUSSKURS von Tag t (CBOE, ~16:15 ET),
    also erst NACH dem Aktien-Schlusskurs (16:00 ET) bekannt.
  - Lag 1 (idealisiert): Position fuer die Rendite Schluss t -> Schluss t+1.
    Unterstellt Handel zum Schlusskurs t, obwohl das Signal erst danach
    feststeht. Naeherungsweise ueber nachboersliche Ausfuehrung (SPY bis
    20:00 ET) denkbar, aber NICHT exakt ausfuehrbar.
  - Lag 2 (konservativ): Position erst fuer die Rendite Schluss t+1 ->
    Schluss t+2. Verschenkt die Bewegung von t+1 komplett — strenger als
    eine reale Eroeffnungs-Ausfuehrung (Open t+1). Reine Sensitivitaet,
    KEIN Beleg fuer tatsaechlich ausfuehrbare Trades.
  - Nicht modellierbar mit den vorhandenen Daten: echte Open-to-Close /
    Open-to-Open-Simulation (keine Eroeffnungskurse des S&P 500 im Repo).
  - Kosten: COST_BP je Positionswechsel (Default 5 bp; --cost-bp).

DATEN UND FEHLDATEN-POLITIK
  - data/raw_data/VIX_History.csv (vix_close), VIX3M_History.csv (CLOSE) — CBOE.
  - data/raw_data/DIX_GEX_History.csv, Spalte "price" = S&P 500 Index OHNE
    Dividenden -> Zeitraum ab 2011-05-02.
  - Inner Join auf Handelstage, KEIN Forward-Fill. Verworfene Tage werden
    gezaehlt (Stand 26.09.2026: 34, US-Feiertage mit CBOE-Zeilen).
  - Kalenderpruefung (v2.2): jede Luecke > 2 Werktage muss in
    KNOWN_CLOSURES stehen (Stand: nur Hurrikan Sandy, 29./30.10.2012),
    sonst Abbruch — damit pct_change() keine unerkannte Mehrtagesrendite
    als Tagesrendite behandelt.
  - Erste Position: Das Regime des ersten Tages wird auf den ersten
    (Lag-)Tag uebertragen; die erste Rendite ist per Definition 0, die
    Initialisierung beeinflusst Rendite und Turnover daher nicht (geprueft).

TESTFAMILIE (DSR, Nebeninformation)
  Gate A, Gate B (07.08./26.08.2026), regime_v1, regime_v2, regime_5f
  (23.08.2026, regime_compare/dsr_check.py) -> N_TRIALS = 5 (Untergrenze:
  eine groessere Familie kann die DSR nur senken). Streuung der Sharpe
  Ratios aus den tatsaechlich beobachteten Werten der Familie.

EINSCHRAENKUNGEN (bewusst nicht geglaettet)
  - Ohne Dividenden; Cash-Tage 0 % statt Geldmarktzins.
  - Finanzkrise 2008/09 nicht enthalten (Preisreihe ab 05/2011).
  - Nur einfache Long/Flat-Gates dieses einen Klassifikators. Ein negatives
    Ergebnis widerlegt NICHT jede denkbare Regime-Strategie.

AUSFUEHRUNG
  cd analysis && python3 regime_gate_backtest_v2.py [--cost-bp 5]
  -> Konsole + regime_gate_backtest_v2_result.json
"""
import argparse
import json
from pathlib import Path

import numpy as np
import pandas as pd
from scipy import stats

from deflated_sharpe_ratio import compute_dsr, sharpe_ratio, sr_std_from_trials

RAW = Path(__file__).resolve().parent.parent / "data" / "raw_data"

STRESS_THR = 0.98
BULL_THR = 1.05
VIX_FRAGILE = 25.0

TRIAL_FAMILY = ["gate_A", "gate_B", "regime_v1", "regime_v2", "regime_5f"]
N_TRIALS = len(TRIAL_FAMILY)
# Annualisierte Sharpe Ratios der drei Modelle aus regime_compare/dsr_check.py
# (Lauf 26.09.2026, identisch zum 23.08.2026; die Sharpe-Werte selbst waren in
# v1 des DSR-Moduls korrekt, nur Standardfehler/DSR nicht).
EXTERNAL_TRIAL_SHARPES_ANN = {"regime_v1": 0.763, "regime_v2": 0.7975, "regime_5f": 0.6247}

KNOWN_CLOSURES = {pd.Timestamp("2012-10-31")}   # Luecke endet am 31.10.2012 (Sandy 29./30.10.)
NW_LAGS = 5                                      # Newey-West-Bandbreite (Handelstage)


def load_panel():
    vix = pd.read_csv(RAW / "VIX_History.csv", parse_dates=["date"]).set_index("date")["vix_close"].rename("vix")
    v3 = pd.read_csv(RAW / "VIX3M_History.csv")
    v3["DATE"] = pd.to_datetime(v3["DATE"], format="%m/%d/%Y")
    vix3m = v3.set_index("DATE")["CLOSE"].rename("vix3m")
    px = pd.read_csv(RAW / "DIX_GEX_History.csv", parse_dates=["date"]).set_index("date")["price"].rename("price")
    outer = pd.concat([vix, vix3m, px], axis=1).sort_index()
    outer = outer[(outer.index >= px.index.min()) & (outer.index <= px.index.max())]
    panel = outer.dropna()
    panel = panel[(panel[["vix", "vix3m", "price"]] > 0).all(axis=1)]
    return panel, int(len(outer) - len(panel))


def calendar_check(panel: pd.DataFrame) -> dict:
    d = panel.index.values.astype("datetime64[D]")
    bd = np.busday_count(d[:-1], d[1:])
    ends = panel.index[1:]
    long_gaps = [str(e.date()) for e, b in zip(ends, bd) if b > 2]
    unknown = [g for g in long_gaps if pd.Timestamp(g) not in KNOWN_CLOSURES]
    assert not unknown, f"Unerklaerte Luecken > 2 Werktage (moegl. fehlende Handelstage): {unknown}"
    return {"luecken_gt_2_werktage": long_gaps, "davon_unerklaert": unknown,
            "einzelne_feiertage_2_werktage": int((bd == 2).sum()), "bestanden": True}


def classify(ratio: float, vix: float) -> str:
    """Identisch zu classify_regime() in refundex/engine/backtest_2007_2026.py."""
    if ratio < STRESS_THR:
        return "STRESS_UNSTABLE"
    if ratio < BULL_THR:
        return "POST_PANIC_REVERSION"
    return "BULL_FRAGILE" if vix > VIX_FRAGILE else "BULL_QUIET"


def regimes(panel: pd.DataFrame) -> pd.Series:
    return pd.Series([classify(r, v) for r, v in zip(panel["vix3m"] / panel["vix"], panel["vix"])],
                     index=panel.index)


def signal(reg: pd.Series, gate: str) -> pd.Series:
    return (reg != "STRESS_UNSTABLE") if gate == "A" else (reg == "BULL_QUIET")


def positions(reg: pd.Series, gate: str, lag: int) -> pd.Series:
    """Position fuer die Rendite von Tag t. lag=0: FEHLERHAFT (Regime t auf Rendite t);
    lag=1: Regime t-1; lag=2: Regime t-2. Erste lag Tage: Regime des ersten Tages."""
    sig = signal(reg, gate)
    if lag > 0:
        sig = sig.shift(lag, fill_value=bool(sig.iloc[0]))
    return sig.astype(float)


def strategy_returns(ret: pd.Series, pos: pd.Series, cost_bp: float) -> pd.Series:
    switches = pos.diff().abs().fillna(0.0)
    return ret * pos - switches * cost_bp / 10_000.0


def descriptive(r: pd.Series, pos: pd.Series) -> dict:
    cum = (1 + r).cumprod()
    years = len(r) / 252
    sw = float(pos.diff().abs().fillna(0.0).sum())
    return {
        "sharpe_ann": round(sharpe_ratio(r.values), 3),
        "cagr_pct": round(float((cum.iloc[-1] ** (1 / years) - 1) * 100), 2),
        "max_dd_pct": round(float((cum / cum.cummax() - 1).min() * 100), 2),
        "pct_invested": round(float(pos.mean() * 100), 1),
        "wechsel_gesamt": int(sw),
        "wechsel_pro_jahr": round(sw / years, 1),
        "n_days": int(len(r)),
    }


def newey_west_se_mean(x: np.ndarray, lags: int) -> float:
    """HAC-Standardfehler des Mittelwerts (Bartlett-Gewichte)."""
    x = np.asarray(x, dtype=float)
    n = len(x)
    e = x - x.mean()
    s = float(e @ e) / n
    for k in range(1, lags + 1):
        w = 1.0 - k / (lags + 1.0)
        s += 2.0 * w * float(e[k:] @ e[:-k]) / n
    return float(np.sqrt(max(s, 0.0) / n))


def excess_test(r_strat: pd.Series, r_bh: pd.Series) -> dict:
    """HAUPTKENNZAHL: taegliche Differenzrendite Gate minus Buy & Hold.
    H0: mittlere Differenz <= 0; einseitig gegen "Gate besser"."""
    ex = (r_strat - r_bh).values
    mean = float(ex.mean())
    sd = float(ex.std(ddof=1))
    t_iid = mean / (sd / np.sqrt(len(ex))) if sd > 0 else 0.0
    se_nw = newey_west_se_mean(ex, NW_LAGS)
    t_nw = mean / se_nw if se_nw > 0 else 0.0
    return {
        "mittlere_differenz_pct_p_a": round(mean * 252 * 100, 2),
        "tracking_error_pct_p_a": round(sd * np.sqrt(252) * 100, 2),
        "information_ratio_ann": round(float(mean / sd * np.sqrt(252)) if sd > 0 else 0.0, 3),
        "t_iid": round(float(t_iid), 2),
        "t_newey_west": round(float(t_nw), 2),
        "p_einseitig_newey_west": round(float(1 - stats.norm.cdf(t_nw)), 3),
        "gate_signifikant_besser_5pct": bool(t_nw > stats.norm.ppf(0.95)),
    }


def lookahead_selftest(panel: pd.DataFrame) -> dict:
    """Perturbationstest: Daten ab Tag k veraendern -> Positionen bis Tag k duerfen sich
    fuer lag >= 1 NICHT aendern; die fehlerhafte lag-0-Variante muss den Test verletzen."""
    reg = regimes(panel)
    rng = np.random.default_rng(42)
    ks = rng.choice(np.arange(50, len(panel) - 50), size=25, replace=False)
    viol = {0: 0, 1: 0, 2: 0}
    for k in ks:
        pert = panel.copy()
        pert.iloc[k:, pert.columns.get_loc("vix")] *= 3.0
        reg_p = regimes(pert)
        for lag in viol:
            if not positions(reg, "A", lag).iloc[: k + 1].equals(positions(reg_p, "A", lag).iloc[: k + 1]):
                viol[lag] += 1
    assert viol[1] == 0 and viol[2] == 0, f"Look-ahead in Lag-Variante: {viol}"
    return {"stichproben": int(len(ks)), "verletzungen_lag1": viol[1], "verletzungen_lag2": viol[2],
            "verletzungen_lag0_erwartet_gt_0": viol[0], "bestanden": viol[1] == 0 and viol[2] == 0 and viol[0] > 0}


def init_check(ret: pd.Series, reg: pd.Series) -> dict:
    """Die ersten `lag` Positionen werden mit dem Regime des ersten Tages belegt
    (kein Look-ahead: dieses Regime ist am Schluss von Tag 0 bekannt). Geprueft
    wird der Einfluss dieser Initialisierung: Umkehren der Initialpositionen
    darf die Gesamtrendite hoechstens um die Renditen der ersten `lag` Tage
    veraendern (Tag 0 hat per Definition Rendite 0)."""
    assert ret.iloc[0] == 0.0, "Erste Rendite muss 0 sein"
    out = {"erste_rendite": 0.0}
    for gate in "AB":
        for lag in (1, 2):
            p = positions(reg, gate, lag)
            alt = p.copy()
            alt.iloc[:lag] = 1.0 - alt.iloc[:lag]
            delta_bp = float(((ret * p).sum() - (ret * alt).sum()) * 10_000)
            bound_bp = float(ret.iloc[:lag].abs().sum() * 10_000)
            assert abs(delta_bp) <= bound_bp + 1e-9
            out[f"gate_{gate}_lag{lag}"] = {
                "einfluss_initialisierung_bp": round(delta_bp, 2),
                "erster_positionswechsel": str(p.diff().abs().fillna(0).ne(0).idxmax().date()),
            }
    return out


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--cost-bp", type=float, default=5.0, help="Kosten je Positionswechsel in Basispunkten")
    args = ap.parse_args()

    panel, dropped = load_panel()
    reg = regimes(panel)
    ret = panel["price"].pct_change().fillna(0.0)
    ones = pd.Series(1.0, index=panel.index)

    res = {
        "meta": {
            "version": "v2.2",
            "zeitraum": f"{panel.index[0].date()} bis {panel.index[-1].date()}",
            "preisreihe": "S&P 500 Index ohne Dividenden (DIX_GEX_History.csv, Spalte price)",
            "fehldaten_verworfene_tage": dropped,
            "wechselkosten_bp": args.cost_bp,
            "hauptkennzahl": "Differenzrendite Gate minus Buy & Hold (Newey-West, einseitig)",
            "dsr_testfamilie": TRIAL_FAMILY,
            "n_trials_dsr": N_TRIALS,
        },
        "pruefungen": {
            "lookahead_selbsttest": lookahead_selftest(panel),
            "kalender": calendar_check(panel),
            "initialisierung": init_check(ret, reg),
        },
        "buy_and_hold": descriptive(ret, ones),
    }

    variants = {}
    for gate, name in (("A", "gate_A_kein_STRESS"), ("B", "gate_B_nur_BULL_QUIET")):
        block = {}
        for lag, label in ((1, "lag1_idealisiert"), (2, "lag2_konservativ")):
            pos = positions(reg, gate, lag)
            r = strategy_returns(ret, pos, args.cost_bp)
            variants[f"{gate}_{lag}"] = r
            block[label] = {"vergleich_buy_and_hold": excess_test(r, ret), "deskriptiv": descriptive(r, pos)}
        pos0 = positions(reg, gate, 0)
        block["lag0_FEHLERHAFT_nur_doku"] = {"deskriptiv": descriptive(strategy_returns(ret, pos0, args.cost_bp), pos0)}
        res[name] = block

    fam = {"gate_A": sharpe_ratio(variants["A_1"].values), "gate_B": sharpe_ratio(variants["B_1"].values),
           **EXTERNAL_TRIAL_SHARPES_ANN}
    sd_fam = sr_std_from_trials(list(fam.values()))
    res["dsr_nebeninformation"] = {
        "hinweis": "DSR prueft 'Sharpe > 0 nach Mehrfachtest-Korrektur', NICHT 'besser als Buy & Hold'.",
        "familie_sharpe_ann": {k: round(v, 4) for k, v in fam.items()},
        "gate_A_lag1": compute_dsr(variants["A_1"].values, n_trials=N_TRIALS, sr_std_across_trials_ann=sd_fam),
        "gate_B_lag1": compute_dsr(variants["B_1"].values, n_trials=N_TRIALS, sr_std_across_trials_ann=sd_fam),
    }

    stress = reg == "STRESS_UNSTABLE"
    res["diagnose"] = {
        "mittlere_tagesrendite_pct_an_STRESS_tagen_gleicher_tag": round(float(ret[stress].mean() * 100), 3),
        "mittlere_tagesrendite_pct_an_STRESS_tagen_folgetag": round(float(ret.shift(-1)[stress].mean() * 100), 3),
        "anteil_STRESS_tage_pct": round(float(stress.mean() * 100), 1),
    }

    out = Path(__file__).resolve().parent / "regime_gate_backtest_v2_result.json"
    out.write_text(json.dumps(res, indent=2, ensure_ascii=False, default=float), encoding="utf-8")
    print(json.dumps(res, indent=2, ensure_ascii=False, default=float))


if __name__ == "__main__":
    main()
