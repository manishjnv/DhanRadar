DhanRadar Development Instructions
Design Authority

The /design-system, /tokens, /components, /screens, /html, /figma, /ux and related design package folders are the primary UI/UX reference for DhanRadar.

These files establish:

Branding
Visual identity
Color palette
Typography
Spacing
Layout principles
Design language
Component patterns
Interaction patterns
Mobile responsiveness
Accessibility expectations

Maintain consistency with these assets.

Important Rule

The design package is a REFERENCE SYSTEM.

It is NOT a complete specification of every future screen, workflow, feature, component, or user journey.

Do not assume:

Every required page already exists.
Every component already exists.
Every workflow is already documented.
Existing screens are final.
When a matching design exists

If a screen, component, pattern, interaction, layout, or workflow already exists in the design package:

Reuse it.
Follow the established design language.
Reuse tokens and components.
Maintain visual consistency.
When no design exists

If a required page, component, workflow, or interaction does not exist:

Design a new solution.
Follow existing DhanRadar branding.
Follow existing design tokens.
Follow existing component patterns.
Maintain visual consistency.
Create reusable components whenever possible.
Document newly created components.

Do NOT block implementation because a design is missing.

Create the missing design and continue.

Design Evolution

The design package is a living system.

If implementation reveals a better pattern:

Improve the design.
Extend the component library.
Add new reusable components.
Update documentation.

Do not blindly copy outdated screens.

Prioritize:

usability
accessibility
scalability
maintainability
consistency

over pixel-perfect reproduction.

Engineering Authority

When implementation requirements conflict with the design package:

Prioritize:

Functional correctness
Accessibility
Performance
Mobile responsiveness
Security
Scalability
Design consistency

Document deviations.

New Components

When creating new components:

Use existing tokens
Use existing spacing rules
Use existing typography
Support dark mode
Support mobile
Support accessibility
Be reusable

Add them to:

/src/components

and update:

/design-system
/components

documentation.

New Pages

When creating new pages:

Use existing layouts where possible
Reuse existing navigation patterns
Reuse existing cards and widgets
Maintain visual hierarchy

If no design exists:

Create a production-quality page consistent with DhanRadar.

UI Consistency Goal

A user should not be able to tell which pages came from the original design package and which pages were created during implementation.

All pages should feel like a single cohesive product.

Development Priority

Build:

Working functionality
Reusable architecture
Consistent UX
Consistent visual language

Avoid implementing placeholder-only screens.

Prefer complete working experiences.