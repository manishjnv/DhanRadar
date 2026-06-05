# Sidebar

**Purpose.** Primary app navigation (desktop). Becomes bottom tab bar on mobile, off-canvas on tablet.

## States
- default
- active item
- hover
- collapsed (icons only)
- badge (counts)

## Variants
- app (user)
- admin (red accent)
- ai-ops (orange accent)
- mobile bottom-tab

## Props (TypeScript)
```ts
interface SidebarProps { items: NavItem[]; active: string; variant?: 'app'|'admin'|'aiops'; collapsed?: boolean; }
```

## Accessibility
- <nav aria-label="Primary">
- active item aria-current="page"
- keyboard navigable; focus ring
- badges have accessible text

## Responsive behavior
Desktop ≥1024 full sidebar; tablet collapsed icons; mobile → 5-tab bottom nav (Markets/Discover/AI/Portfolio/Profile).

## Implementation notes
Active state from current route. Upgrade card pinned to footer (plan-aware). Admin/AI-Ops shells are visually distinct + role-gated.

## React mapping
```tsx
<Sidebar items={NAV} active={pathname} variant="app" />
```

## Tailwind mapping
`w-58 bg-bg border-r border-line` · item `rounded-lg px-3 py-2 text-sm aria-[current]:bg-blue/10 aria-[current]:text-blue`
