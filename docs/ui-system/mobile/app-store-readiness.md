# App Store & Play Store Readiness

## Compliance / policy
- **Financial app review:** clearly state "research/education, **not** investment advice"; no assured returns; disclaimers visible. (Apple 3.x / Google Financial Services policy.)
- **SEBI posture** surfaced in listing + onboarding (compliance架构). Provide a demo account for reviewers.
- **Privacy:** App Privacy "nutrition label" (iOS) + Data Safety form (Android) — declare data collected (account, usage, holdings via AA), purposes, no sale; link DPDP-aligned policy.
- **Account deletion:** in-app account + data deletion (Apple + Google requirement) → wired to DPDP erasure flow.
- **Permissions:** justify notifications, biometric, (no contacts/location unless needed).

## Technical readiness
- Crash-free rate ≥ 99.5% (Sentry); cold-start < 2s; no debug logging in release; ProGuard/R8 (Android), bitcode/dSYM (iOS).
- Universal/App Links verified; push entitlements; widget extensions signed.
- Accessibility (VoiceOver/TalkBack) pass; Dynamic Type / font scaling.
- Localization-ready (Hindi-first roadmap).

## Store assets
- Icon (all sizes), screenshots per device class (showing Score, AI explain, portfolio — with disclaimers), preview video, description (no performance promises), keywords, support URL, marketing URL, privacy policy URL.

## Release process
- TestFlight / Play Internal testing → closed beta → staged rollout (Play %), phased release (iOS).
- Versioning + changelog; crash monitoring on rollout; rollback plan (halt staged rollout).
- CI: fastlane (build, sign, upload) integrated with the pipeline (doc 06).

## Checklist
- [ ] Not-advice disclaimers in-app + listing
- [ ] Privacy labels + data-safety form + deletion flow
- [ ] Demo account for review
- [ ] Crash-free + perf budgets met
- [ ] Deep links verified; push tested
- [ ] A11y + Dynamic Type pass
