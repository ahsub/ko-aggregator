"""
Deflated Sharpe Ratio (DSR) — Backtest-Reporting-Ergänzung für UIQ
===================================================================
Version: v2.0 (26.09.2026, Claude + Axel) — FORSCHUNGSCODE, kein Produktionscode.

Quellen: Bailey & López de Prado (2012), "The Sharpe Ratio Efficient Frontier"
(Probabilistic Sharpe Ratio, PSR); Bailey & López de Prado (2014), "The
Deflated Sharpe Ratio" (DSR); Mertens (2002) bzw. Lo (2002) für den
Standardfehler der Sharpe Ratio bei nicht-normalverteilten Renditen.

CHANGELOG
  v2.0 (26.09.2026): EINHEITENFEHLER BEHOBEN.
    - v1 setzte die ANNUALISIERTE Sharpe Ratio in die Standardfehler-Formel
      ein, zusammen mit der Anzahl TAEGLICHER Beobachtungen. Die Formel
      verlangt Sharpe Ratio und Beobachtungszahl in DERSELBEN Periode.
      Folge: Standardfehler um Faktor ~sqrt(252)/sqrt(1+SR_ann^2/2)
      unterschaetzt (Beispiel Regime-Gate A: 0,023 statt korrekt 0,259).
    - v1 hatte `sr_std_across_trials = 1.0` als Default, faktisch in
      Jahres-Einheiten interpretiert — fuer taegliche Strategievarianten
      unrealistisch hoch (erwartete Max-Sharpe unter H0 bei 5 Versuchen:
      1,19 p. a. statt ~0,11 bei der tatsaechlich beobachteten Streuung).
    - Beide Fehler zusammen erzeugten DSR ~0 fuer JEDE Gate-Variante und
      DSR = 1 fuer Buy & Hold (n_trials = 1) — ein Rechenartefakt, kein
      statistischer Befund (betroffen: regime_compare/dsr_check.py vom
      23.08.2026, regime_gate_backtest_v2.py v2.0/v2.1).
    - Jetzt: alle Rechnungen intern pro Periode; Ein-/Ausgabe der Sharpe
      Ratio explizit getrennt (…_pp = pro Periode, …_ann = annualisiert);
      `sr_std_across_trials_ann` ist Pflichtparameter ohne Default;
      Hilfsfunktion sr_std_from_trials(); Selbsttests (python3
      deflated_sharpe_ratio.py --selftest) mit bekannten Erwartungswerten.
  v1.0 (18.08.2026): Erstfassung (nach Pagliaro 2026, Abschnitt 3.8.2).

WAS DIE DSR AUSSAGT — UND WAS NICHT
  - DSR = Wahrscheinlichkeit, dass die WAHRE Sharpe Ratio der berichteten
    Variante groesser ist als die unter H0 erwartete Maximal-Sharpe von
    n_trials unabhaengigen, wertlosen Varianten. Sie korrigiert fuer
    Mehrfachtests ("bestes von N ausgesucht").
  - Sie prueft NICHT, ob eine Strategie eine Benchmark schlaegt. Eine
    Long/Flat-Variante des Aktienmarkts hat eine positive Sharpe Ratio,
    weil der Aktienmarkt eine hat — das ist kein Verdienst des Signals.
    Fuer "besser als Buy & Hold" ist die Differenzrendite (Strategie minus
    Benchmark) zu testen, z. B. psr() auf die Differenzrendite mit
    Benchmark 0 oder ein t-Test (s. regime_gate_backtest_v2.py v2.2).
  - Die Aussagekraft haengt an einer EHRLICH gezaehlten Testfamilie
    (n_trials) und an einer realistischen Streuung der Sharpe Ratios ueber
    diese Familie. Eine nachtraeglich verkleinerte Familie verbessert die
    DSR kuenstlich. Bei unbekannter Familie: n_trials als Untergrenze
    kennzeichnen (groesseres n kann die DSR nur senken).
  - Die Formel fuer die erwartete Maximal-Sharpe ist eine Naeherung fuer
    UNABHAENGIGE Versuche; stark korrelierte Varianten (z. B. Gate A und
    regime_v1) machen sie konservativ.

SCHWELLENWERT
  DSR > 0,95 gilt in der Literatur als "robust nach Mehrfachtest-
  Korrektur" gegenueber der Frage "Sharpe > 0". Nicht mit einem
  Benchmark-Vergleich verwechseln.
"""
from __future__ import annotations

import sys

import numpy as np
from scipy import stats

EULER_MASCHERONI = 0.5772156649015329


# ── Sharpe Ratio: pro Periode und annualisiert, strikt getrennt ────────────────

def sharpe_ratio_pp(returns: np.ndarray) -> float:
    """Sharpe Ratio pro Periode (z. B. taeglich), rf = 0, Stichproben-Std (ddof=1)."""
    r = np.asarray(returns, dtype=float)
    sd = np.std(r, ddof=1)
    return 0.0 if sd == 0 else float(np.mean(r) / sd)


def annualize(sr_pp: float, periods_per_year: int = 252) -> float:
    return float(sr_pp * np.sqrt(periods_per_year))


def deannualize(sr_ann: float, periods_per_year: int = 252) -> float:
    return float(sr_ann / np.sqrt(periods_per_year))


def sharpe_ratio(returns: np.ndarray, periods_per_year: int = 252) -> float:
    """Annualisierte Sharpe Ratio (Kompatibilitaet zu v1 — Wert war dort korrekt)."""
    return annualize(sharpe_ratio_pp(returns), periods_per_year)


def sharpe_se_pp(returns: np.ndarray, sr_pp: float | None = None) -> float:
    """Standardfehler der Sharpe Ratio PRO PERIODE nach Mertens (2002):
    Var(SR) = (1 - g3*SR + (g4 - 1)/4 * SR^2) / (T - 1),
    g3 = Schiefe, g4 = Kurtosis (NICHT Exzess). SR und T in derselben Periode."""
    r = np.asarray(returns, dtype=float)
    t = len(r)
    if sr_pp is None:
        sr_pp = sharpe_ratio_pp(r)
    g3 = float(stats.skew(r))
    g4 = float(stats.kurtosis(r, fisher=False))
    var = (1.0 - g3 * sr_pp + (g4 - 1.0) / 4.0 * sr_pp ** 2) / (t - 1)
    return float(np.sqrt(max(var, 0.0)))


def lo_sharpe_se(returns: np.ndarray, sr: float) -> float:
    """ENTFERNT in v2.0 (Einheitenfehler). Stattdessen sharpe_se_pp() verwenden."""
    raise NotImplementedError("lo_sharpe_se() ist seit v2.0 entfernt — sharpe_se_pp() verwenden "
                              "(Einheitenfehler in v1, s. CHANGELOG).")


# ── Probabilistic / Deflated Sharpe Ratio ──────────────────────────────────────

def psr(returns: np.ndarray, sr_benchmark_pp: float = 0.0) -> float:
    """Probabilistic Sharpe Ratio: P(wahre SR_pp > sr_benchmark_pp)."""
    sr = sharpe_ratio_pp(returns)
    se = sharpe_se_pp(returns, sr)
    if se == 0:
        return 1.0 if sr > sr_benchmark_pp else 0.0
    return float(stats.norm.cdf((sr - sr_benchmark_pp) / se))


def sr_std_from_trials(trial_sharpes_ann) -> float:
    """Streuung (ddof=1) der annualisierten Sharpe Ratios einer Testfamilie."""
    x = np.asarray(trial_sharpes_ann, dtype=float)
    if len(x) < 2:
        raise ValueError("Mindestens zwei Varianten noetig, um eine Streuung zu schaetzen.")
    return float(np.std(x, ddof=1))


def expected_max_sharpe_under_null(n_trials: int, sr_std_across_trials: float) -> float:
    """Erwartete maximale Sharpe Ratio unter H0 bei n_trials unabhaengigen
    Versuchen (Bailey & López de Prado 2014, Euler-Mascheroni-Naeherung).
    Einheit des Ergebnisses = Einheit von sr_std_across_trials."""
    if n_trials <= 1:
        return 0.0
    z1 = stats.norm.ppf(1.0 - 1.0 / n_trials)
    z2 = stats.norm.ppf(1.0 - 1.0 / (n_trials * np.e))
    return float(sr_std_across_trials * ((1.0 - EULER_MASCHERONI) * z1 + EULER_MASCHERONI * z2))


def compute_dsr(
    returns: np.ndarray,
    *,
    n_trials: int,
    sr_std_across_trials_ann: float,
    periods_per_year: int = 252,
) -> dict:
    """Deflated Sharpe Ratio der berichteten Variante.

    returns                  : periodische Renditen (z. B. taeglich) der Variante
    n_trials                 : ehrlich gezaehlte Anzahl getesteter Varianten
    sr_std_across_trials_ann : Streuung der ANNUALISIERTEN Sharpe Ratios ueber die
                               Testfamilie (Pflicht, kein Default; s. sr_std_from_trials)
    """
    if sr_std_across_trials_ann is None or not np.isfinite(sr_std_across_trials_ann) \
            or sr_std_across_trials_ann < 0:
        raise ValueError("sr_std_across_trials_ann muss explizit und >= 0 angegeben werden.")
    r = np.asarray(returns, dtype=float)
    sr_pp = sharpe_ratio_pp(r)
    se_pp = sharpe_se_pp(r, sr_pp)
    sr0_pp = expected_max_sharpe_under_null(n_trials, deannualize(sr_std_across_trials_ann, periods_per_year))
    dsr = (1.0 if sr_pp > sr0_pp else 0.0) if se_pp == 0 else float(stats.norm.cdf((sr_pp - sr0_pp) / se_pp))
    return {
        "sharpe_ratio_ann": round(annualize(sr_pp, periods_per_year), 4),
        "sharpe_se_ann": round(annualize(se_pp, periods_per_year), 4),
        "expected_max_sharpe_under_null_ann": round(annualize(sr0_pp, periods_per_year), 4),
        "dsr": round(dsr, 4),
        "significant_at_95": bool(dsr > 0.95),
        "n_trials_used": int(n_trials),
        "sr_std_across_trials_ann": round(float(sr_std_across_trials_ann), 4),
        "n_obs": int(len(r)),
        "hinweis": "DSR prueft 'wahre Sharpe > Max-Sharpe unter H0', NICHT 'besser als Benchmark'.",
    }


# ── Selbsttests mit bekannten Erwartungswerten ─────────────────────────────────

def selftest(seed: int = 7) -> dict:
    """Prueft die Implementierung gegen Groessen mit bekanntem Erwartungswert.
    Bricht mit AssertionError ab, wenn eine Abweichung die Toleranz uebersteigt."""
    rng = np.random.default_rng(seed)
    out = {}

    # T1: Erwartetes Maximum von N unabhaengigen Standardnormalen (exakt bekannt:
    #     N=5 -> 1,16296; N=10 -> 1,53875). Naeherung laut Literatur auf ~3-5 %.
    for n, exact in ((5, 1.16296), (10, 1.53875)):
        approx = expected_max_sharpe_under_null(n, 1.0)
        rel = abs(approx - exact) / exact
        assert rel < 0.05, f"E[max] N={n}: {approx:.4f} vs exakt {exact} (rel {rel:.3f})"
        out[f"T1_emax_N{n}"] = {"naeherung": round(approx, 4), "exakt": exact, "rel_abw": round(rel, 4)}

    # T2: Standardfehler — Streuung der geschaetzten Sharpe Ratio ueber viele
    #     Simulationen muss dem mittleren analytischen SE entsprechen
    #     (iid normal, T=3848 wie im Regime-Backtest, wahre SR_ann = 0,75).
    T, sims = 3848, 1500
    mu, sd = deannualize(0.75), 1.0
    X = rng.normal(mu * sd, sd, size=(sims, T))
    srs = X.mean(axis=1) / X.std(axis=1, ddof=1)
    se_emp = float(np.std(srs, ddof=1))
    se_ana = float(np.mean([sharpe_se_pp(X[i]) for i in range(0, sims, 15)]))
    rel = abs(se_ana - se_emp) / se_emp
    assert rel < 0.10, f"SE analytisch {se_ana:.5f} vs empirisch {se_emp:.5f}"
    out["T2_se_pp"] = {"analytisch": round(se_ana, 5), "empirisch": round(se_emp, 5),
                       "annualisiert": round(annualize(se_ana), 4), "rel_abw": round(rel, 4)}

    # T3: Kalibrierung unter H0 (wahre SR = 0): PSR ist ~gleichverteilt,
    #     Anteil PSR > 0,95 muss nahe 5 % liegen.
    X0 = rng.normal(0.0, 1.0, size=(2000, 1000))
    frac = float(np.mean([psr(x) > 0.95 for x in X0]))
    assert 0.03 <= frac <= 0.07, f"Falsch-Positiv-Rate {frac:.3f} ausserhalb [0,03; 0,07]"
    out["T3_fp_rate_H0"] = {"anteil_psr_gt_0_95": round(frac, 4), "erwartet": 0.05}

    # T4: Einheiten-Regression gegen v1-Fehler: SE annualisiert muss in der
    #     Groessenordnung sqrt(252/T) liegen, nicht sqrt(1/T).
    se_ann = annualize(sharpe_se_pp(X[0]))
    assert 0.2 < se_ann < 0.32, f"SE_ann {se_ann:.4f} unplausibel (v1-Fehler lieferte ~0,02)"
    out["T4_se_ann_plausibel"] = round(se_ann, 4)

    out["bestanden"] = True
    return out


if __name__ == "__main__":
    if "--selftest" in sys.argv:
        import json
        print(json.dumps(selftest(), indent=2, ensure_ascii=False))
    else:
        rng = np.random.default_rng(42)
        example = rng.normal(loc=0.0006, scale=0.012, size=756)  # ~3 Jahre taeglich
        res = compute_dsr(example, n_trials=10, sr_std_across_trials_ann=0.3)
        print("Deflated Sharpe Ratio — Beispiel (synthetisch):")
        for k, v in res.items():
            print(f"  {k}: {v}")
        print("\nSelbsttest: python3 deflated_sharpe_ratio.py --selftest")
