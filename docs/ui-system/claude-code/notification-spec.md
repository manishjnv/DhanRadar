# Notification Spec

Channels: push (web/mobile), email (SES + react-email), in-app center. Triggers: alert_events (price/score/risk/earnings), digests, billing. Fan-out via Celery `realtime`/`default` queues + Redis streams. Conservative defaults (material moves only) + digest option + "too many?" calibrator. Preferences per channel in Settings. Idempotent delivery; dedupe by event id. In-app: notification center component (see hi-fi/AI layer).
