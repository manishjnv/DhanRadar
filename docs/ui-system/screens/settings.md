# Screen — Settings

**Purpose.** Account, notifications, appearance, brokers, security — grouped, low-risk defaults.

## Layout
Two-pane: section nav (left) + form (right). Mobile: grouped inset lists (iOS) / grouped (Android).

## Components
- SectionNav
- grouped controls (toggle/select/field)
- Save
- Security panel

## API requirements
- `GET/PATCH /v1/users/me/settings`
- `/notifications`
- `/security (2FA)`

## Data model (entities)
- users
- preferences
- sessions

## Loading states
Field skeletons on load.

## Error states
Save failure → keep local changes, retry banner; never silently drop edits.

## Responsive rules
Two-pane → single-column section navigation on mobile.

## Analytics events
- `settings_view`
- `setting_change`
- `2fa_enable`
- `notification_toggle`
