"""DhanRadar — Compliance Audit module (architecture Global §4, B26).

Records and gates; produces no content. Owns the immutable 7-yr
`ai_recommendation_audit` trail (every served label → `(label, model_used,
disclaimer_version)`, non-neg #9), the `disclaimers` version registry, and the
daily R2 archival of the audit table. Writes are FIRE-AND-FORGET and isolated in
their own DB session so an audit failure can never break or corrupt the serving
path — but a never-lose-a-row design (DEFAULT partition, no hard FKs) keeps the
trail complete.
"""
