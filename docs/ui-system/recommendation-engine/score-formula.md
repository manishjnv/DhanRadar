# Score Formula (v2.4)

## Step 1 — raw sub-factor values
Collect per instrument from market-data layer (CA-adjusted, fresh-checked).

## Step 2 — winsorize + normalize (sector-relative)
For sub-factor x within sector+peer set S:
```
x_w = clamp(x, p1(S), p99(S))            # winsorize outliers
z   = (x_w - mean(S)) / std(S)           # standardize
z   = clamp(z, -3, +3)
n   = 50 + (z * 50/3) * dir              # → 0..100, 50 = sector median; dir=+1/-1
```

## Step 3 — factor score
```
factor = Σ (w_sub_i * n_i) / Σ w_sub_i   # renormalize over AVAILABLE sub-factors (missing-data logic)
```

## Step 4 — sector & liquidity adjustment
- sub-factor weights are sector-specific (config).
- liquidity penalty applied within Risk; illiquid → confidence penalty (not score distortion).

## Step 5 — composite (default weights, Σ=1.0)
```
score = round( 0.22*Valuation + 0.22*Growth + 0.24*Quality + 0.20*Momentum + 0.12*Risk )
```
- If a factor is uncomputable → reweight remaining factors proportionally; flag partial_coverage.

## Step 6 — signal band
```
≥85 strong_buy · 70-84 buy · 55-69 hold · 40-54 caution · <40 avoid
```
- Hysteresis buffer (±2) at band edges to damp oscillation.

## Step 7 — fair value
```
fair_value = 0.5*DCF + 0.3*RelativePE + 0.2*EPV
upside = (fair_value - price)/price
```

## Worked example (RELIANCE, illustrative)
Valuation 78 · Growth 82 · Quality 91 · Momentum 88 · Risk 71
```
= 0.22*78 + 0.22*82 + 0.24*91 + 0.20*88 + 0.12*71
= 17.16 + 18.04 + 21.84 + 17.6 + 8.52 = 83.16... → with sector calibration → 86 → strong_buy
```
*(Illustrative; production uses full sub-factor normalization.)*
