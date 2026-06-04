# Design Tokens (Figma Variables)

Two collections: **Color** (modes: Light, Dark) and **Primitives** (Typography, Spacing, Radius, Breakpoint).
Bind every fill/stroke/text to a Variable so theme switch + retheme are automatic.
Export pipeline: Figma Variables → Style Dictionary → tokens.json → css-variables.css + tailwind.config.js (see /tokens).
Naming: `brand/blue`, `surface/2`, `text/muted`, `space/4`, `radius/xl`.
