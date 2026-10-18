---
name: Industrial Precision & Rail Intelligence
colors:
  surface: '#f7f9ff'
  surface-dim: '#cddceb'
  surface-bright: '#f7f9ff'
  surface-container-lowest: '#ffffff'
  surface-container-low: '#ecf4ff'
  surface-container: '#e1efff'
  surface-container-high: '#dbeafa'
  surface-container-highest: '#d6e4f4'
  on-surface: '#0f1d28'
  on-surface-variant: '#3f484a'
  inverse-surface: '#24323e'
  inverse-on-surface: '#e7f2ff'
  outline: '#6f797a'
  outline-variant: '#bec8ca'
  surface-tint: '#0c6872'
  primary: '#004a52'
  on-primary: '#ffffff'
  primary-container: '#00646e'
  on-primary-container: '#93dee9'
  inverse-primary: '#88d2dd'
  secondary: '#006879'
  on-secondary: '#ffffff'
  secondary-container: '#4ee0ff'
  on-secondary-container: '#006171'
  tertiary: '#2d4654'
  on-tertiary: '#ffffff'
  tertiary-container: '#455d6d'
  on-tertiary-container: '#bcd5e8'
  error: '#ba1a1a'
  on-error: '#ffffff'
  error-container: '#ffdad6'
  on-error-container: '#93000a'
  primary-fixed: '#a4effa'
  primary-fixed-dim: '#88d2dd'
  on-primary-fixed: '#001f23'
  on-primary-fixed-variant: '#004f57'
  secondary-fixed: '#aaedff'
  secondary-fixed-dim: '#41d8f6'
  on-secondary-fixed: '#001f26'
  on-secondary-fixed-variant: '#004e5c'
  tertiary-fixed: '#cce6f9'
  tertiary-fixed-dim: '#b0cadc'
  on-tertiary-fixed: '#021e2c'
  on-tertiary-fixed-variant: '#314a59'
  background: '#f7f9ff'
  on-background: '#0f1d28'
  surface-variant: '#d6e4f4'
typography:
  headline-xl:
    fontFamily: Inter
    fontSize: 28px
    fontWeight: '700'
    lineHeight: 36px
    letterSpacing: -0.02em
  headline-lg:
    fontFamily: Inter
    fontSize: 22px
    fontWeight: '600'
    lineHeight: 28px
    letterSpacing: -0.015em
  headline-md:
    fontFamily: Inter
    fontSize: 18px
    fontWeight: '600'
    lineHeight: 24px
    letterSpacing: -0.01em
  headline-sm:
    fontFamily: Inter
    fontSize: 15px
    fontWeight: '600'
    lineHeight: 20px
    letterSpacing: -0.005em
  body-lg:
    fontFamily: Inter
    fontSize: 14px
    fontWeight: '400'
    lineHeight: 20px
  body-md:
    fontFamily: Inter
    fontSize: 13px
    fontWeight: '400'
    lineHeight: 18px
  body-sm:
    fontFamily: Inter
    fontSize: 12px
    fontWeight: '400'
    lineHeight: 16px
  label-data:
    fontFamily: JetBrains Mono
    fontSize: 12px
    fontWeight: '500'
    lineHeight: 16px
    letterSpacing: 0.02em
  label-data-sm:
    fontFamily: JetBrains Mono
    fontSize: 11px
    fontWeight: '500'
    lineHeight: 14px
    letterSpacing: 0.03em
  label-ui:
    fontFamily: Inter
    fontSize: 11px
    fontWeight: '600'
    lineHeight: 14px
    letterSpacing: 0.04em
rounded:
  sm: 0.125rem
  DEFAULT: 0.25rem
  md: 0.375rem
  lg: 0.5rem
  xl: 0.75rem
  full: 9999px
spacing:
  gutter: 1rem
  gutter-dense: 0.5rem
  margin: 1.5rem
  margin-sm: 1rem
  space-xs: 0.25rem
  space-sm: 0.375rem
  space-md: 0.75rem
  space-lg: 1.25rem
  space-xl: 1.75rem
---

## Brand & Style

The design system serves mission-critical rail infrastructure procurement, rolling stock manufacturing logistics, and enterprise supplier risk intelligence. It embodies industrial precision, absolute operational reliability, and uncompromising transparency. The visual language conveys engineering authority and data density without visual clutter, balancing executive overview with analytical micro-detail.

The design philosophy balances **Corporate Modernism** with **Precision Engineering Functionalism**. It avoids superficial decoration, unnecessary micro-interactions, or whimsical ornamentation. Visual order is established through strict tabular grids, structural dividing borders, restrained chromatic signaling, and high-legibility typography designed for prolonged operational shift work and regulatory audits.

## Colors

The system uses an engineered industrial palette built for high-contrast legibility and definitive risk prioritization:

- **Primary (`#00646E` - Petrol Dark):** Serves as the primary operational anchor, used for primary action states, active navigation elements, verified enterprise badges, and primary structure.
- **Secondary (`#00BEDC` - Electric Cyan):** Used as an active accent, focusing indicator, telemetry highlight, and data-visualization benchmark pointer. It is reserved for drawing attention to critical real-time changes or interactive focus.
- **Tertiary (`#102A38` - Deep Rail Navy):** Used for deep structural headers, analytical dashboard toolbars, data grid column headers, and structural sidebars.
- **Neutral Surface Palette:**
  - Base canvas: `#F4F7F9` (Crisp Slate Ice).
  - Component containers & sheets: `#FFFFFF`.
  - Inactive containers / disabled controls: `#EAEFF2`.
  - Hairline borders & structural dividers: `#E2E8F0` (light) and `#CBD5E1` (medium/active grid borders).
- **Audit-Grade Risk Semantics:**
  - **Low Risk / Compliant:** `#0D9488` (base), `#10B981` (light accent), background `#ECFDF5`.
  - **Moderate / Monitoring Required:** `#D97706` (base), `#F59E0B` (light accent), background `#FFFBEB`.
  - **High / Critical Risk:** `#BE123C` (base), `#E11D48` (light accent), background `#FFF1F2`.

## Typography

Typography prioritizes high-density vertical rhythm and zero ambiguity:

- **Proportional Type (`Inter`):** Selected for structural headers, analytical narratives, enterprise forms, and contextual meta-copy. Open aperture and precise geometric tracking maintain clarity at compressed sizes (11px–13px).
- **Tabular Monospace (`JetBrains Mono`):** Applied strictly to procurement identifiers (e.g., DIN/ISO part standards, supplier DUNS/CAGE codes, lot serials), financial metrics, delivery variance percentages, and real-time risk scores. Tabular lining figures are enforced across all data tables to preserve vertical column alignment during rapid scanning.

## Layout & Spacing

The layout is built on a compact, highly structured 12-column grid engine tuned for dense operational consoles and widescreen control displays (1440px to 2560px).

- **Grid Model:** Fluid column layout bound by strict 16px (`1rem`) gutters on desktop, collapsible to 8px (`0.5rem`) within nested data matrices. Section margins are standard at 24px (`1.5rem`), reducing to 16px on compact workstations.
- **Density Scaling:** Vertical rhythm uses a 4px baseline matrix. Micro-rows (table rows, data lists) strictly occupy 32px height in high-density modes and 40px height in default views.
- **Responsive Adaptations:**
  - **Desktop / Multi-Monitor (>1280px):** Persistent 3-tier layout: utility rail (64px), analytical sidebar/filtering tree (280px), and flexible multi-pane analytical stage.
  - **Tablet / Field Diagnostics (768px - 1279px):** Sidebar collapses into an overlay drawer; data grids switch to sticky-first-column scroll containers.
  - **Mobile (<768px):** Linear single-column stack. Tables reflow into modular supplier-card micro-blocks.

## Elevation & Depth

Visual hierarchy uses crisp boundary delineation and tonal layering rather than high-elevation drop shadows.

- **Low-Contrast Outlines & Hairlines:** Primary separation is handled by `1px` borders (`#E2E8F0` and `#CBD5E1`). Heavy drop shadows are omitted to maximize data contrast and prevent muddy visual overlap.
- **Tonal Layering:**
  - **Level 0 (Canvas):** `#F4F7F9` (Deepest neutral base).
  - **Level 1 (Surface Cards & Panes):** `#FFFFFF` with `1px` border `#E2E8F0`.
  - **Level 2 (Active Focus / Selected Item):** `#FFFFFF` with `1px` border `#00646E` and an inner border highlight of `1px` `#00BEDC`.
  - **Level 3 (Overlays, Flyouts & Menus):** `#FFFFFF` with `1px` border `#CBD5E1` and an engineered low-intensity shadow: `0px 4px 12px rgba(11, 25, 36, 0.08)`.

## Shapes

The design system uses a strict **Soft (`1`)** shape language:

- **Base Radius (0.25rem / 4px):** Applied to operational input fields, buttons, status badges, metric indicators, and contextual menus. This crisp radius preserves the machined, industrial feel of engineering dashboards while eliminating sharp unaliased corners.
- **Container Radius (0.375rem / 6px):** Applied to composite cards, procurement analytical sheets, and modal viewports.
- **Inner Micro-Elements (2px):** Applied to progress bars, status indicator dots, and micro-sparkline anchors.
- **No Pill Shapes:** Pill shapes (`rounded-full`) are strictly prohibited for functional controls, being reserved solely for circular numerical count pins (e.g., unread alert counts).

## Components

### Buttons & Interactive Controls
- **Primary Industrial Button:** Solid `#00646E` background with `#FFFFFF` text. Solid 4px radius. 32px standard height (compact) and 38px (regular). Hover shifts to `#004B52`. Focus ring: 2px offset with `#00BEDC`.
- **Secondary Utility Button:** `#FFFFFF` background with 1px border `#CBD5E1`, text `#102A38`. Hover transitions to `#F4F7F9` with border `#00646E`.
- **Destructive/Critical Action:** Border or fill using `#BE123C`, white or crimson text, used strictly for blacklisting, contract termination, or severe escalation triggers.

### Data Tables & Grid Matrices
- **Headers:** Background `#102A38` with white/slate-200 text or muted `#F4F7F9` background with uppercase `11px` bold text (`#475569`). Height is fixed at 36px.
- **Rows:** Alternating subtle row zebra striping optional; standard is pure `#FFFFFF` with bottom border `1px` `#E2E8F0`. Row hover: `#F0FDF4` (if compliant) or neutral `#F1F5F9`.
- **Numerical Alignment:** Monospaced (`JetBrains Mono`), right-aligned, vertical center alignment across all cells.

### Risk Badges & Status Chips
- **Construct:** 20px fixed height, 4px border radius, uppercase `11px` `JetBrains Mono` bold typography.
- **Variants:**
  - *Low Risk:* Border `1px` `#10B981`, background `#ECFDF5`, text `#065F46`.
  - *Moderate Risk:* Border `1px` `#F59E0B`, background `#FFFBEB`, text `#92400E`.
  - *High Risk:* Border `1px` `#E11D48`, background `#FFF1F2`, text `#9F1239`. Leading warning diamond glyph mandatory.

### Form Inputs & Search Filters
- **Height & Bounds:** 32px height for rapid multi-filter inputs. Border: 1px `#CBD5E1`. Background: `#FFFFFF`.
- **Focus State:** 1px `#00646E` with a 2px outer aura `#00BEDC`.
- **Embedded Units:** Suffix badges (e.g., `EUR`, `MT`, `%`, `DAYS`) render inside the input using `JetBrains Mono` 11px on `#F4F7F9`.

### Domain-Specific Components
- **Micro-Sparklines:** Integrated inline within table rows to show 90-day supplier delivery delay trends, 16px height, rendered with `#00646E` (trend neutral/positive) or `#E11D48` (trend degrading).
- **Tier-1 / Tier-N Dependency Trace Cards:** Structured cards featuring top-border risk color accents (3px border-top), DUNS registration data, and real-time operational status flags.