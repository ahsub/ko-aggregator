"""
Deflated Sharpe Ratio (DSR) — Backtest-Reporting-Ergänzung für UIQ

Quelle: Bailey & López de Prado (2014), zitiert und implementiert in
Pagliaro, A. (2026), "Regime-Aware LightGBM for Stock Market Forecasting",
Electronics 15(6):1334, Abschnitt 3.8.2. Verifiziert am Volltext 2026-08-18.

Zweck:
Der klassische Sharpe Ratio wird verzerrt, wenn man (wie beim GEX-Override-Test,
den Regime-Backtests etc.) mehrere Strategievarianten ausprobiert und die beste
berichtet ("Multiple Testing"-Problem). Der DSR korrigiert dafür, indem er die
erwartete MAXIMALE Sharpe Ratio unter der Nullhypothese (alle Varianten haben
in Wahrheit Erwartungswert null) von der beobachteten Sharpe Ratio abzieht.

Nächster Schritt (konkret):
1. N = Anzahl tatsächlich getesteter Strategie-/Parametervarianten festlegen
   (z.B. GEX-Override an/aus, Reduktionsstufen, Zeitfenster-Varianten der
   regime_v2_backtest.py-Läufe zusammenzählen — nicht nur die final berichtete
   Variante).
2. Tägliche (oder Perioden-) Returns der besten Variante aus dem bestehenden
   Backtest-Output extrahieren (numpy array).
3. compute_dsr() aufrufen, Ergebnis zusammen mit Sharpe/Max-Drawdown im
   Go/No-Go-Reporting für Dezember 2026 ausweisen.

Schwellenwert laut Quelle: DSR > 0.95 gilt als "statistisch robust nach
Mehrfachtest-Korrektur". Werte deutlich über 0 aber unter 0.95 sind ein
ehrliches Zwischenergebnis (siehe Pagliaro 2026: DSR 0.35-0.69, trotzdem
klar positiver Bootstrap-Sharpe) — kein Show-Stopper, aber transparent
auszuweisen.
"""

from __future__ import annotations

import numpy as np
from scipy import stats

EULER_MASCHERONI = 0.5772156649


def sharpe_ratio(returns: np.ndarray, periods_per_year: int = 252) -> float:
    """Annualisierte Sharpe Ratio aus einer Renditeserie (Excess Returns)."""
    mean = np.mean(returns)
    std = np.std(returns, ddof=1)
    if std == 0:
        return 0.0
    return (mean / std) * np.sqrt(periods_per_year)


def lo_sharpe_se(returns: np.ndarray, sr: float) -> float:
    """
    Autokorrelations-/Momentenkorrigierter Standardfehler der Sharpe Ratio
    nach Lo (2002), verwendet für die Deflated-Sharpe-Berechnung.
    """
    t = len(returns)
    skew = stats.skew(returns)
    kurt = stats.kurtosis(returns, fisher=False)  # "normal" kurtosis (Fisher=False -> nicht Excess)
    variance_sr = (1 + 0.5 * sr**2 - skew * sr + ((kurt - 3) / 4) * sr**2) / t
    return np.sqrt(max(variance_sr, 0.0))


def expected_max_sharpe_under_null(n_trials: int, sr_std_across_trials: float = 1.0) -> float:
    """
    Erwartete maximale Sharpe Ratio unter der Nullhypothese bei n_trials
    unabhängigen Strategieversuchen (Euler-Mascheroni-Approximation).

    sr_std_across_trials: Streuung der Sharpe Ratios über die getesteten
    Varianten hinweg. Falls unbekannt, konservativ 1.0 verwenden (siehe
    Bailey & López de Prado 2014 für Details zur Schätzung aus der Praxis).
    """
    if n_trials <= 1:
        return 0.0
    z1 = stats.norm.ppf(1 - 1.0 / n_trials)
    z2 = stats.norm.ppf(1 - 1.0 / (n_trials * np.e))
    return sr_std_across_trials * ((1 - EULER_MASCHERONI) * z1 + EULER_MASCHERONI * z2)


def compute_dsr(
    returns: np.ndarray,
    n_trials: int,
    periods_per_year: int = 252,
    sr_std_across_trials: float = 1.0,
) -> dict:
    """
    Berechnet die Deflated Sharpe Ratio für eine Renditeserie.

    Parameters
    ----------
    returns : np.ndarray
        Periodische (z.B. tägliche) Excess Returns der besten/berichteten
        Strategievariante.
    n_trials : int
        Gesamtzahl der im Entwicklungsprozess getesteten Varianten
        (Parametergrid, Ablationen, Zeitfenster etc. — NICHT nur die final
        berichtete Konfiguration).
    periods_per_year : int
        Annualisierungsfaktor (252 für tägliche Handelsdaten).
    sr_std_across_trials : float
        Geschätzte Streuung der Sharpe Ratios über alle getesteten Varianten.

    Returns
    -------
    dict mit:
        sharpe_ratio          — annualisierte Sharpe Ratio (unkorrigiert)
        sharpe_se             — Lo-korrigierter Standardfehler
        expected_max_sharpe   — erwartete max. Sharpe unter H0 bei n_trials
        dsr                   — Deflated Sharpe Ratio (Wahrscheinlichkeit,
                                 dass die wahre Sharpe Ratio > 0 ist, nach
                                 Mehrfachtest-Korrektur)
        significant_at_95     — bool, ob dsr > 0.95
    """
    returns = np.asarray(returns, dtype=float)
    sr = sharpe_ratio(returns, periods_per_year)
    se = lo_sharpe_se(returns, sr)
    sr0 = expected_max_sharpe_under_null(n_trials, sr_std_across_trials)

    if se == 0:
        dsr = 1.0 if sr > sr0 else 0.0
    else:
        dsr = stats.norm.cdf((sr - sr0) / se)

    return {
        "sharpe_ratio": round(sr, 4),
        "sharpe_se": round(se, 4),
        "expected_max_sharpe_under_null": round(sr0, 4),
        "dsr": round(dsr, 4),
        "significant_at_95": bool(dsr > 0.95),
        "n_trials_used": n_trials,
    }


if __name__ == "__main__":
    # Beispielaufruf mit synthetischen Daten — für den echten Einsatz die
    # Returns aus dem bestehenden regime_v2_backtest.py-Output einlesen.
    rng = np.random.default_rng(42)
    example_returns = rng.normal(loc=0.0006, scale=0.012, size=756)  # ~3 Jahre täglich

    result = compute_dsr(
        returns=example_returns,
        n_trials=250,  # Platzhalter — tatsächliche Anzahl UIQ-Varianten einsetzen
        periods_per_year=252,
    )

    print("Deflated Sharpe Ratio — Ergebnis:")
    for key, value in result.items():
        print(f"  {key}: {value}")
