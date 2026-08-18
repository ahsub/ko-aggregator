"""
regime_v2_backtest.py

REKONSTRUKTION (18.08.2026-Session, aus Chatverlauf wiederhergestellt,
da das Original nie committed wurde). Siehe Hinweis-Block am Dateiende
für Konfidenzeinstufung der einzelnen Abschnitte -- NICHT ungeprüft
committen, bevor der Testlauf gegen ~/regime_v2_output/regime_v1_v2_panel.csv
(lokal bei Axel vorhanden) die identischen Kennzahlen reproduziert.

Kontext: Die multivariate Voranalyse vom 18.08.2026 (Korrelation/VIF/
Feature-Importance, s. voranalyse_regime.py) zeigte GEX als zweitwichtigsten
Klassifikator für market_regime_str (Feature-Importance 0.287, hinter VVIX
0.189, vor NFCI). Diese Datei prueft KONKRET, ob eine einfache GEX<0-
Zusatzregel etwas verbessert -- NICHT nur, ob ein ML-Modell GEX "nuetzlich
findet".

WICHTIG: Dies ist ein isolierter Test. Es wird NICHTS an
market_aggregator.py veraendert. Ziel ist eine Ja/Nein/Teilweise-Antwort,
ob sich der Aufwand einer Produktions-Aenderung ueberhaupt lohnt -- und
falls ja, wie eine moegliche Regel aussehen koennte (als Diskussionsgrundlage,
nicht als fertiger Patch).

v1 (Produktionsformel, market_aggregator.py Z.8510-8540, exakt repliziert):
    ratio = VIX3M / VIX
    ratio < 0.98              -> STRESS_UNSTABLE
    0.98 <= ratio < 1.05      -> POST_PANIC_REVERSION
    ratio >= 1.05, VIX > 25   -> BULL_FRAGILE
    ratio >= 1.05, VIX <= 25  -> BULL_QUIET

v2 (Testregel, NICHT produktiv): wie v1, ABER zusaetzlich:
    ratio >= 1.05 (also v1 sagt BULL_*) UND gex < 0
        -> STRESS_UNSTABLE (ueberschreibt v1)
    (GEX-Schwelle 0 identisch zur bestehenden Konvention in
     score_options_collar()/apply_macro_risk_overlay(), NICHT neu erfunden)

Zwei Auswertungen:
    A) 2022-Fokus: wie oft reklassifiziert v2 BULL_* -> STRESS_UNSTABLE,
       und was ist der tatsaechliche Forward-Return/Forward-Vol/Forward-
       Max-Drawdown an diesen Tagen? (Validiert, ob die Reklassifikation
       oekonomisch sinnvoll ist, nicht nur "andersartig".)
    B) Trennschaerfe gesamt (2011-2026): Vergleich v1 vs v2 -- sortiert ein
       "STRESS"-Label die Tage tatsaechlich nach hoeherem Risiko als ein
       "BULL"-Label? Gemessen an der Rangfolge von fwd_vol_21d/63d und
       fwd_maxdd_21d/63d je Regime-Klasse (idealerweise STRESS_UNSTABLE
       am riskantesten, BULL_QUIET am wenigsten riskant).

METHODIK-KORREKTUR waehrend der Original-Session (18.08.2026): Der erste
Testlauf nutzte Forward-RETURN als Trennschaerfe-Kriterium fuer Analyse B --
falsches Kriterium fuer eine Risiko-Regime-Klassifikation, da STRESS-Phasen
historisch oft V-foermigen Erholungen vorausgehen (Volatility Risk Premium).
Hohe Forward-Returns nach STRESS_UNSTABLE sind daher oekonomisch erwartbar,
kein Fehlschlag der Regel. Korrigiert auf Forward-Volatilitaet + Forward-
Max-Drawdown als primaeres Kriterium (s. analysis_b_separation() unten).
"""

from __future__ import annotations

import json
import sys
from pathlib import Path

import numpy as np
import pandas as pd
import requests

sys.path.insert(0, str(Path(__file__).parent))
# ACHTUNG: voranalyse_regime.py ist selbst nicht committed / hier nicht
# rekonstruiert -- dieser Import schlaegt fehl, bis diese Datei ebenfalls
# im selben Verzeichnis vorliegt.
from voranalyse_regime import fetch_yf_series, fetch_dix_gex_full_history, compute_regime_labels

REGIME_ORDER = ["STRESS_UNSTABLE", "POST_PANIC_REVERSION", "BULL_FRAGILE", "BULL_QUIET"]


def build_v1_v2(start: str = "2011-05-02") -> pd.DataFrame:
    print("[fetch] VIX/VIX3M...", file=sys.stderr)
    vix = fetch_yf_series("^VIX", start=start)
    vix3m = fetch_yf_series("^VIX3M", start=start)
    print("[fetch] GEX (squeezemetrics)...", file=sys.stderr)
    dg = fetch_dix_gex_full_history()
    print("[fetch] SPY (fuer Forward-Returns)...", file=sys.stderr)
    spy = fetch_yf_series("SPY", start=start)

    v1 = compute_regime_labels(vix, vix3m)
    df = pd.DataFrame(index=v1.index)
    df["vix"] = vix.reindex(df.index)
    df["vix3m"] = vix3m.reindex(df.index)
    df["ratio"] = df["vix3m"] / df["vix"]
    df["regime_v1"] = v1
    df["gex"] = dg["gex"].reindex(df.index).ffill()

    # -- v2: GEX<0-Zusatzregel (nur wenn v1 BULL_FRAGILE/BULL_QUIET sagt) --
    is_bull = df["regime_v1"].isin(["BULL_FRAGILE", "BULL_QUIET"])
    gex_negative = df["gex"] < 0
    override = is_bull & gex_negative
    df["regime_v2"] = df["regime_v1"]
    df.loc[override, "regime_v2"] = "STRESS_UNSTABLE"
    df["v2_overrode_v1"] = override

    # -- Forward-Returns fuer die Validierung --
    for h in (21, 63):
        df[f"fwd_return_{h}d"] = spy.reindex(df.index).shift(-h) / spy.reindex(df.index) - 1
        # Forward-Volatilitaet (annualisiert) ueber das jeweilige Fenster.
        # [REKONSTRUKTION, mittlere Konfidenz -- exakte Original-Formel
        # nicht woertlich im Chatverlauf gefunden, nur das Ergebnis-Feld
        # "fwd_vol_21d"/"fwd_vol_63d". Vor Produktivnutzung gegen
        # regime_v1_v2_panel.csv (lokal bei Axel) verifizieren.]
        daily_ret = spy.reindex(df.index).pct_change()
        df[f"fwd_vol_{h}d"] = (
            daily_ret.shift(-h).rolling(window=h, min_periods=h // 2)
            .std().shift(-(h - 1)) * np.sqrt(252)
        )
        df[f"fwd_maxdd_{h}d"] = _forward_max_drawdown(spy.reindex(df.index), h)

    return df.dropna(subset=["vix", "vix3m", "gex"])


def _forward_max_drawdown(price: pd.Series, h: int) -> pd.Series:
    """Maximaler Drawdown ueber die naechsten h Handelstage ab jedem
    Zeitpunkt. Direkteres 'wie schlimm wurde es'-Mass als Volatilitaet
    allein -- erfasst auch einseitige Abwaertsbewegungen ohne hohe Vol
    (z.B. ein grindender Baerenmarkt mit niedriger Tagesvolatilitaet,
    aber stetigem Verlust -- genau das 2022er-Muster aus dem Protokoll)."""
    result = pd.Series(index=price.index, dtype=float)
    values = price.values
    n = len(values)
    for i in range(n):
        window = values[i: i + h + 1]
        if len(window) < 2:
            result.iloc[i] = np.nan
            continue
        base = window[0]
        running_min = np.minimum.accumulate(window)
        dd = (running_min / base) - 1
        result.iloc[i] = dd.min()
    return result


def analysis_a_2022_focus(df: pd.DataFrame) -> dict:
    d22 = df[(df.index >= "2022-01-01") & (df.index <= "2022-12-31")]
    n_days = len(d22)
    n_override = int(d22["v2_overrode_v1"].sum())
    overridden = d22[d22["v2_overrode_v1"]]

    result = {
        "n_trading_days_2022": n_days,
        "n_reclassified_bull_to_stress": n_override,
        "pct_reclassified": round(100 * n_override / n_days, 1) if n_days else None,
        "regime_v1_distribution_2022": d22["regime_v1"].value_counts().to_dict(),
        "regime_v2_distribution_2022": d22["regime_v2"].value_counts().to_dict(),
    }
    if n_override > 0:
        result["reclassified_days_mean_fwd_return_21d"] = round(float(overridden["fwd_return_21d"].mean()), 4)
        result["reclassified_days_mean_fwd_return_63d"] = round(float(overridden["fwd_return_63d"].mean()), 4)
        result["reclassified_days_pct_negative_fwd_21d"] = round(
            100 * float((overridden["fwd_return_21d"] < 0).mean()), 1
        )
        # Volatilitaet + Max-Drawdown statt nur Return -- passenderes
        # Kriterium fuer eine RISIKO-Klassifikation (s. Modulkopf-Docstring)
        result["reclassified_days_mean_fwd_vol_21d"] = round(float(overridden["fwd_vol_21d"].mean()), 4)
        result["reclassified_days_mean_fwd_vol_63d"] = round(float(overridden["fwd_vol_63d"].mean()), 4)
        result["reclassified_days_mean_fwd_maxdd_21d"] = round(float(overridden["fwd_maxdd_21d"].mean()), 4)
        result["reclassified_days_mean_fwd_maxdd_63d"] = round(float(overridden["fwd_maxdd_63d"].mean()), 4)
        # Vergleichsgruppe: v1-BULL-Tage 2022, die NICHT reklassifiziert wurden
        not_overridden_bull = d22[d22["regime_v1"].isin(["BULL_FRAGILE", "BULL_QUIET"])
                                   & ~d22["v2_overrode_v1"]]
        if len(not_overridden_bull) > 0:
            result["non_reclassified_bull_days_mean_fwd_return_21d"] = round(
                float(not_overridden_bull["fwd_return_21d"].mean()), 4
            )
            result["non_reclassified_bull_days_mean_fwd_vol_21d"] = round(
                float(not_overridden_bull["fwd_vol_21d"].mean()), 4
            )
            result["non_reclassified_bull_days_mean_fwd_maxdd_21d"] = round(
                float(not_overridden_bull["fwd_maxdd_21d"].mean()), 4
            )
    return result


def analysis_b_separation(df: pd.DataFrame) -> dict:
    """Trennschaerfe-Test. WICHTIG (Korrektur nach erstem Lauf, 18.08.2026):
    Forward-RETURN ist das falsche Kriterium fuer eine Risiko-Regime-
    Klassifikation -- STRESS-Phasen gehen historisch oft V-foermigen
    Erholungen voraus (Volatility Risk Premium), hohe Forward-Returns nach
    STRESS_UNSTABLE sind daher oekonomisch erwartbar, kein Fehlschlag der
    Regel. Primaeres Kriterium jetzt: Forward-VOLATILITAET und Forward-MAX-
    DRAWDOWN -- das eigentliche 'wie riskant/instabil war die Phase danach'.
    Erwartete Reihenfolge (absteigend nach Risiko): STRESS_UNSTABLE >
    POST_PANIC_REVERSION > BULL_FRAGILE > BULL_QUIET. Forward-Return bleibt
    informativ im Output, aber NICHT mehr als Monotonie-Kriterium gewertet.

    [BUGFIX 18.08.2026, nach echtem Testlauf mit Axel: Die urspruengliche
    Rekonstruktion sortierte alle vier Metriken identisch mit
    ascending=False fuer den Monotonie-Check. Das ist fuer Volatilitaet
    korrekt (hoeherer Wert = riskanter, absteigend sortiert = riskantestes
    Regime zuerst), aber FALSCH fuer Max-Drawdown: dort ist "riskanter" =
    STAERKER NEGATIV = numerisch KLEINER, also braucht Max-Drawdown
    ascending=True fuer denselben "riskantestes Regime zuerst"-Vergleich.
    Der Bug fuehrte dazu, dass fwd_maxdd_21d faelschlich als "nicht
    monoton" gemeldet wurde, obwohl die Werte tatsaechlich korrekt
    geordnet waren (von Axel per Handrechnung bestaetigt). Nach dem Fix
    stimmen die Ergebnisse mit der bereits dokumentierten Original-Aussage
    in REGIME-BACKTEST-VALIDIERUNG.md ueberein: fwd_maxdd_21d korrekt
    geordnet in BEIDEN Versionen, fwd_vol_21d/fwd_vol_63d/fwd_maxdd_63d
    bleiben in beiden Versionen falsch geordnet.]
    """
    # Fuer Volatilitaet gilt: hoeherer (positiver) Wert = riskanter.
    # Fuer Max-Drawdown gilt: staerker negativer (kleinerer) Wert = riskanter.
    # "riskantestes Regime zuerst" braucht daher je nach Metrik eine
    # andere Sortierrichtung.
    ASCENDING_FOR_RISK_DESCENDING = {
        "fwd_vol_21d": False,
        "fwd_vol_63d": False,
        "fwd_maxdd_21d": True,
        "fwd_maxdd_63d": True,
    }
    result = {}
    for version in ("regime_v1", "regime_v2"):
        stats = {}
        for metric in ("fwd_vol_21d", "fwd_vol_63d", "fwd_maxdd_21d", "fwd_maxdd_63d"):
            grp = df.groupby(version)[metric].agg(["mean", "count"])
            grp = grp.reindex(REGIME_ORDER).dropna(how="all")
            stats[f"{metric}_by_regime"] = {
                k: {"mean": round(float(v["mean"]), 4), "n": int(v["count"])}
                for k, v in grp.iterrows() if not pd.isna(v["mean"])
            }
            # Monotonie-Check: ist STRESS_UNSTABLE tatsaechlich am riskantesten?
            means = grp["mean"].dropna()
            ascending = ASCENDING_FOR_RISK_DESCENDING[metric]
            is_monotonic_as_expected = list(means.index) == list(means.sort_values(ascending=ascending).index)
            stats[f"{metric}_monotonic_as_expected"] = bool(is_monotonic_as_expected)
        # Forward-Return weiterhin informativ mitgefuehrt, nicht als
        # Monotonie-Kriterium gewertet (s. Docstring oben).
        for h in (21, 63):
            grp = df.groupby(version)[f"fwd_return_{h}d"].agg(["mean", "count"])
            grp = grp.reindex(REGIME_ORDER).dropna(how="all")
            stats[f"fwd_return_{h}d_by_regime_informational"] = {
                k: {"mean": round(float(v["mean"]), 4), "n": int(v["count"])}
                for k, v in grp.iterrows() if not pd.isna(v["mean"])
            }
        result[version] = stats
    return result


def main():
    outdir = Path("./regime_v2_output")
    outdir.mkdir(exist_ok=True)

    df = build_v1_v2()
    df.to_csv(outdir / "regime_v1_v2_panel.csv")
    print(f"[done] Panel: {len(df)} Handelstage, {df.index.min().date()} bis {df.index.max().date()}",
          file=sys.stderr)

    a = analysis_a_2022_focus(df)
    b = analysis_b_separation(df)

    summary = {"analysis_a_2022_focus": a, "analysis_b_separation_full_history": b}
    with open(outdir / "summary_regime_v2.json", "w") as f:
        json.dump(summary, f, indent=2, default=str)

    print("\n" + "=" * 70)
    print("ANALYSE A -- 2022-Fokus")
    print("=" * 70)
    print(json.dumps(a, indent=2, default=str))
    print("\n" + "=" * 70)
    print("ANALYSE B -- Trennschaerfe gesamt (2011-2026)")
    print("=" * 70)
    print(json.dumps(b, indent=2, default=str))
    print("\nFERTIG.", file=sys.stderr)


if __name__ == "__main__":
    main()


# ============================================================================
# REKONSTRUKTIONS-HINWEIS (nicht Teil des Original-Skripts, hier zur
# Transparenz angehaengt -- vor Commit ggf. entfernen oder in eine separate
# Notiz auslagern):
#
# Diese Datei wurde am 18.08.2026 nachtraeglich aus dem Chatverlauf derselben
# Session rekonstruiert, da das Original nie ins Repo committed wurde.
#
# HOHE KONFIDENZ (woertlich aus str_replace-Edits im Chatverlauf
# rekonstruiert): build_v1_v2() Kernlogik, analysis_a_2022_focus()
# Return-Teil, main(), REGIME_ORDER, Modulkopf-Klassifikationsregeln
# (v1/v2), _forward_max_drawdown().
#
# MITTLERE KONFIDENZ (aus beschriebener Korrektur abgeleitet, nicht
# woertlich im Chatverlauf gefunden): analysis_b_separation() in der
# finalen Vol/Drawdown-Form, fwd_vol_Nd-Berechnung in build_v1_v2().
#
# FEHLENDE ABHAENGIGKEIT: voranalyse_regime.py (fetch_yf_series,
# fetch_dix_gex_full_history, compute_regime_labels) ist ebenfalls nicht
# committed und wird hier nicht mitgeliefert -- dieses Skript ist ohne
# diese Datei nicht lauffaehig.
#
# EMPFOHLENER NAECHSTER SCHRITT VOR COMMIT: Dieses Skript (nach Ergaenzung
# von voranalyse_regime.py) lokal ausfuehren und gegen die bereits
# vorliegenden ~/regime_v2_output/regime_v1_v2_panel.csv und
# summary_regime_v2.json abgleichen. Nur bei uebereinstimmenden Kennzahlen
# committen. Dokumentiertes Endergebnis der Original-Session zur Orientierung:
# GEX<0-Regel wurde NICHT in market_aggregator.py uebernommen (Entscheidung
# vom 18.08.2026, s. REGIME-BACKTEST-VALIDIERUNG.md, Nebenfund 3) --
# Monotonie-Flags fuer v1 und v2 waren identisch, GEX aenderte die
# Trennschaerfe nicht messbar.
# ============================================================================
