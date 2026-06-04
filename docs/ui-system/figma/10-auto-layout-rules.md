# Auto-Layout Rules

- Every component + frame uses auto-layout; spacing via the 4px token scale (gap = space/2, space/3, space/4…).
- Resizing: fill-container for content regions, hug-contents for chips/badges/buttons.
- Padding from radius/spacing tokens; never magic numbers.
- Nested auto-layout for rows (logo + text + value + score). Min width constraints prevent overflow.
- Responsive: use Figma variants per breakpoint (desktop/tablet/mobile) for layout that restructures (tables→cards, sidebar→tab bar).
