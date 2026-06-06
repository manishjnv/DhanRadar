"""DhanRadar — Mutual Fund module (Phase 5, architecture Tier-C MF Module).

Owns CAS ingestion → ≤60s labelled report, holdings/snapshot analytics, and the
score-consumption bridge. Couples to the Rating Engine via its published interface
only (never recomputes the score) and gates CAS upload on DPDP `mf_analytics`
consent (B20). No numeric score reaches a client surface (non-neg #2).
"""
