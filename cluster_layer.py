"""
cluster_layer.py — Cluster Volume Profile (LuxAlgo, 12.07.2026)
UIQ-Port: K-Means auf Preis×Volumen → k POC-Levels.

Berechnet pro Ticker:
  - K-Means (k=5, volumengewichtet) auf hl2 × 200 Bars
  - Pro Cluster: POC + Volumen + Preisspanne
  - nearestClusterPocDist: Abstand Kurs → nächster Cluster-POC in %
  - dominantClusterVol: Volumen des volumenstärksten Clusters
  - clusterDelta: (BuyVol - SellVol) / TotalVol im dominanten Cluster
  - priceAboveDominant: Kurs über oder unter dem Haupt-Cluster-Centroid

Lizenz: CC BY-NC-SA 4.0 (analog LuxAlgo-Original)
"""

import numpy as np
import logging

log = logging.getLogger("aggregator")

# ── Konfiguration ────────────────────────────────────────────────────────────
LENGTH     = 200   # Lookback-Fenster
K_CLUSTERS = 5     # Anzahl K-Means-Cluster
ITERATIONS = 50    # K-Means-Iterationen
NUM_BINS   = 20    # Volume-Profile-Bins pro Cluster


def _kmeans_vw(prices: np.ndarray, volumes: np.ndarray,
               k: int, iterations: int) -> np.ndarray:
    """Volumengewichteter K-Means. Gibt Cluster-Zuweisungen zurück."""
    n = len(prices)
    pmin, pmax = prices.min(), prices.max()
    if pmax <= pmin:
        return np.zeros(n, dtype=int)

    # Initialisierung: gleichmäßige Centroid-Verteilung
    centroids = np.linspace(pmin, pmax, k + 2)[1:-1]

    assignments = np.zeros(n, dtype=int)
    for _ in range(iterations):
        # Zuweisung: nächster Centroid
        dists = np.abs(prices[:, None] - centroids[None, :])
        assignments = np.argmin(dists, axis=1)

        # Update: VWAP-Centroid (volumengewichtet)
        for j in range(k):
            mask = assignments == j
            if mask.any() and volumes[mask].sum() > 0:
                centroids[j] = np.average(prices[mask], weights=volumes[mask])

    return assignments


def calc_cluster_vp(closes: list, highs: list, lows: list, volumes: list,
                    length: int = LENGTH, k: int = K_CLUSTERS,
                    iterations: int = ITERATIONS, num_bins: int = NUM_BINS) -> dict:
    """
    Berechnet Cluster Volume Profile für einen Ticker.
    Returns: dict mit nearestClusterPocDist, dominantClusterVol,
             clusterDelta, priceAboveDominant, clusterCentroids oder {}
    """
    n = len(closes)
    if n < length or len(highs) < length or len(lows) < length or len(volumes) < length:
        return {}
    try:
        c   = np.array(closes[-length:],  dtype=float)
        h   = np.array(highs[-length:],   dtype=float)
        l   = np.array(lows[-length:],    dtype=float)
        v   = np.array(volumes[-length:], dtype=float)
        hl2 = (h + l) / 2.0

        # K-Means auf hl2 mit Volumen-Gewichtung
        assignments = _kmeans_vw(hl2, v, k, iterations)

        current_close = float(c[-1])
        poc_levels    = []
        cluster_vols  = []
        cluster_highs = []
        cluster_lows  = []

        for c_id in range(k):
            mask = assignments == c_id
            if not mask.any():
                continue
            c_hl2 = hl2[mask]
            c_h   = h[mask]
            c_l   = l[mask]
            c_v   = v[mask]
            c_min = float(c_l.min())
            c_max = float(c_h.max())
            total_vol = float(c_v.sum())

            if c_max <= c_min or total_vol <= 0:
                continue

            # Volume Profile pro Cluster (20 Bins)
            bin_size  = (c_max - c_min) / num_bins
            bin_vols  = np.zeros(num_bins, dtype=float)
            for i in range(len(c_hl2)):
                wick_range = max(float(c_h[i]) - float(c_l[i]), 1e-10)
                for b in range(num_bins):
                    b_lo = c_min + b * bin_size
                    b_hi = b_lo + bin_size
                    intersect = max(0.0,
                        min(float(c_h[i]), b_hi) - max(float(c_l[i]), b_lo))
                    bin_vols[b] += float(c_v[i]) * intersect / wick_range

            poc_bin   = int(np.argmax(bin_vols))
            poc_price = c_min + (poc_bin + 0.5) * bin_size

            poc_levels.append(poc_price)
            cluster_vols.append(total_vol)
            cluster_highs.append(c_max)
            cluster_lows.append(c_min)

        if not poc_levels:
            return {}

        # Nächster Cluster-POC zum aktuellen Kurs
        poc_arr  = np.array(poc_levels)
        dists    = np.abs(poc_arr - current_close)
        nearest_idx  = int(np.argmin(dists))
        nearest_poc  = poc_levels[nearest_idx]
        nearest_dist = ((current_close - nearest_poc) / nearest_poc * 100
                        if nearest_poc > 0 else None)

        # Dominanter Cluster (meistes Volumen)
        dom_idx  = int(np.argmax(cluster_vols))
        dom_vol  = cluster_vols[dom_idx]
        dom_poc  = poc_levels[dom_idx]

        # Buy/Sell-Delta im dominanten Cluster (vereinfacht: close > open = buy)
        dom_mask  = assignments == [i for i in range(k)
                                    if (assignments == i).any()][min(dom_idx, k-1)]
        # Einfacher Delta-Proxy: Anteil bullisher Bars
        buy_vol  = float(sum(v[i] for i in range(length)
                             if dom_mask[i] and c[i] >= (c[i-1] if i>0 else c[i])))
        sell_vol = float(dom_vol - buy_vol)
        delta    = (buy_vol - sell_vol) / dom_vol if dom_vol > 0 else 0.0

        price_above_dominant = bool(current_close > dom_poc)

        return {
            "nearestClusterPocDist": round(nearest_dist, 2) if nearest_dist is not None else None,
            "dominantClusterVol":    round(dom_vol, 0),
            "clusterDelta":          round(delta, 3),   # -1 bis +1
            "priceAboveDominant":    price_above_dominant,
            "nearestClusterPoc":     round(nearest_poc, 4),
        }
    except Exception as e:
        log.debug(f"[CLUSTER_VP] Fehler: {e}")
        return {}


def run(results: list) -> dict:
    """Wird aus market_aggregator.main() aufgerufen."""
    enriched = 0
    errors   = 0

    for r in results:
        closes  = r.pop("_closes_cl",  None)
        highs   = r.pop("_highs_cl",   None)
        lows    = r.pop("_lows_cl",    None)
        volumes = r.pop("_volumes_cl", None)

        if closes and highs and lows and volumes:
            cv = calc_cluster_vp(closes, highs, lows, volumes)
            if cv:
                r.update(cv)
                enriched += 1
            else:
                errors += 1
        else:
            for k in ["nearestClusterPocDist","dominantClusterVol",
                      "clusterDelta","priceAboveDominant","nearestClusterPoc"]:
                r.setdefault(k, None)

    log.info(f"  [CLUSTER_VP] {enriched} Ticker enrichiert, {errors} Fehler")
    return {"ok": True, "enriched": enriched, "errors": errors}
