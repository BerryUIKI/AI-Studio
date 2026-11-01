# Berry AI Studio Launcher Hub — UI/UX Design Specification

Date: 2026-10-03. Status: design specification; implementation pending.
Parent PRD: [Launcher Hub PRD](LAUNCHER_HUB_PRD.md).

---

## 1. Overall Layout Structure

```
┌─────────────────────────────────────────────────────────────────┐
│  Titlebar (drag region)                    [GPU: RTX 4090 6G/24G] │ ← Window title + GPU indicator
├──────┬──────────────────────────────────────────────────────────┤
│      │                                                          │
│  N   │                                                          │
│  A   │              MAIN CONTENT AREA                           │
│  V   │         (Launcher Hub / Canvas /                         │
│      │          ComfyUI / WebUI / Agents)                       │
│  R   │                                                          │
│  A   │                                                          │
│  I   │                                                          │
│  L   │                                                          │
│      │                                                          │
├──────┤                                                          │
│  ⚙️  │                                                          │
│  💻  │                                                          │
└──────┴──────────────────────────────────────────────────────────┘
   56px                    Remaining width
```

### Dimensions & Breakpoints
- **Navigation Rail width**: 56px collapsed (icon only), 200px expanded (icon + label).
- **Collapse behavior**: Click toggle button (☰) at rail top, or auto-collapse below 900px window width.
- **Minimum window size**: 800 × 600px.

---

## 2. Navigation Rail

### Visual Design

```
┌──────┐
│  ☰   │  ← Collapse/expand toggle (hamburger icon)
│      │
│  🏠  │  Home (Launcher Hub) ← Active: highlighted background + left accent bar
│  🎨  │  Canvas
│  🧩  │  ComfyUI  🟢         ← Green dot = engine running
│  🖼️  │  WebUI
│  🤖  │  Agents
│      │
│      │  ← Flexible spacer
│      │
│  ⚙️  │  Settings
│  💻  │  System
└──────┘
```

### States

| State | Visual Treatment |
| --- | --- |
| Default | Icon in `slate-400`, no background |
| Hover | Background `slate-800/50`, icon brightens to `slate-200` |
| Active (current view) | Background `slate-800`, left 2px accent bar in `indigo-500`, icon in `white` |
| Engine Running | Small 8px green circle (`emerald-500`) positioned bottom-right of the icon |
| Engine Error | Small 8px red circle (`red-500`) positioned bottom-right of the icon |
| Task Active (generating) | Green circle pulses with CSS animation (`animate-pulse`) |

### Expanded Rail

When expanded, labels appear to the right of icons with a smooth width transition (200ms ease-out):

```
┌────────────────────┐
│ ☰  Berry AI Studio │
│                    │
│ 🏠  Home           │
│ 🎨  Canvas         │
│ 🧩  ComfyUI    🟢  │
│ 🖼️  WebUI          │
│ 🤖  Agents         │
│                    │
│ ⚙️  Settings       │
│ 💻  System         │
└────────────────────┘
```

---

## 3. Launcher Hub View

### Header Section

```
┌──────────────────────────────────────────────────────────┐
│                                                          │
│                    🅱️  Berry AI Studio                    │  ← Logo + branding
│                                                          │
│         ┌──────────────────────────────────┐              │
│         │ 🔍 Search instances...            │              │  ← Search/filter bar
│         └──────────────────────────────────┘              │
│                                                          │
│   Personal ▾                        INSTANCES 4          │  ← Workspace selector + count
│                                                          │
└──────────────────────────────────────────────────────────┘
```

### Instance Card Grid

Cards are arranged in a responsive CSS Grid: `grid-template-columns: repeat(auto-fill, minmax(280px, 1fr))`.

#### Card Anatomy

```
┌─────────────────────────────┐
│                           ⋮ │  ← Three-dot context menu (top-right)
│                             │
│     🖥️                      │  ← Large icon (engine type)
│                             │
│                             │
│  ComfyUI                    │  ← Instance name
│  Stable · v0.38.2       🟢  │  ← Channel + version + status dot
└─────────────────────────────┘
```

#### Card Variants

**1. Built-in Workspace Card (Infinite Canvas)**
```
┌─────────────────────────────┐
│                             │
│     🎨                      │
│                             │
│  Infinite Canvas            │
│  Berry AI Studio            │  ← Always available, no status dot needed
└─────────────────────────────┘
```
- Click → Navigate to Canvas view.
- No three-dot menu.
- Visually distinguished: subtle gradient border or accent color.

**2. Engine Instance Card (Installed)**
```
┌─────────────────────────────┐
│                           ⋮ │
│     🧩                      │
│                             │
│  ComfyUI                    │
│  Stable · v0.38.2       🟢  │
└─────────────────────────────┘
```
- Click → Start engine (if stopped) or navigate to engine view (if running).
- Three-dot menu: Configure, View Logs, Open Directory, Check Update, Uninstall/Unbind.
- Status dot colors: see Section 2 States table.

**3. Add New Card**
```
┌─────────────────────────────┐
│                             │
│     ＋                      │  ← Large plus icon
│                             │
│  New Instance               │
│  Set up a new environment   │
└─────────────────────────────┘
```
- Click → Opens AddEngineModal.
- Dashed border style to visually differentiate from instance cards.

**4. Agents Workspace Card**
```
┌─────────────────────────────┐
│                             │
│     🤖                      │
│                             │
│  AI Agents                  │
│  Workflow Automation        │
└─────────────────────────────┘
```
- Click → Navigate to Agents view.

#### Card Interaction States

| State | Visual |
| --- | --- |
| Default | `bg-slate-800/60`, `border border-slate-700/50` |
| Hover | `bg-slate-800`, `border-slate-600`, subtle lift (`shadow-lg`), slight scale (`scale-[1.02]`) |
| Active/Pressed | `scale-[0.98]`, `bg-slate-700` |
| Disabled | `opacity-50`, `cursor-not-allowed` |

---

## 4. Three-Dot Context Menu

```
┌──────────────────────┐
│ ⚙️  Configure         │
│ 📋  View Logs         │
│ 📁  Open Directory    │
│ ─────────────────── │
│ 🔄  Check for Update  │
│ ─────────────────── │
│ 🗑️  Uninstall         │  ← Red text for destructive action
└──────────────────────┘
```

- Positioned via floating UI (Radix / Headless UI pattern).
- Destructive actions (Uninstall) are separated by a divider and use red text.
- "Uninstall" for managed engines deletes the sandboxed directory.
- "Unbind" for external engines only removes the registration (with different label text).

---

## 5. Deployment Drawer

Slides in from the right side (width 480px, or 40% of window width, whichever is larger).

```
┌──────────────────────────────────────────┐
│  Installing ComfyUI                   ✕  │  ← Title + close button
├──────────────────────────────────────────┤
│                                          │
│  Step 3/5: Installing Python packages    │  ← Current step
│                                          │
│  ████████████████░░░░░░░░  62%           │  ← Overall progress bar
│                                          │
├──────────────────────────────────────────┤
│  $ pip install torch torchvision ...     │  ← Scrolling log terminal
│  Collecting torch==2.1.0                 │     (monospace font, dark bg)
│  Downloading torch-2.1.0-cp310...       │
│  Installing collected packages: ...      │
│  Successfully installed torch-2.1.0      │
│  $ pip install -r requirements.txt       │
│  ...                                     │
│                                     ▼    │  ← Auto-scroll indicator
├──────────────────────────────────────────┤
│              [ Cancel Installation ]     │  ← Cancel button (red outline)
└──────────────────────────────────────────┘
```

### Log Terminal Styling
- Background: `bg-slate-950` (darker than main bg).
- Font: `font-mono text-xs`.
- Text color: `text-slate-400` for stdout, `text-red-400` for stderr.
- Auto-scroll to bottom; clicking inside the log pauses auto-scroll; a "Jump to bottom" FAB appears when scrolled up.

---

## 6. GPU Status Indicator

### Titlebar Compact View

```
[ 🟢 RTX 4090 · 6.2G / 24G (25%) ]
```

- Color coding: green text < 50% VRAM usage, yellow 50–80%, red > 80%.
- Without GPU: `[ ☁️ Cloud Mode · No GPU ]` in `slate-500`.

### Hover Popover

```
┌──────────────────────────────────────┐
│  NVIDIA GeForce RTX 4090             │
│  Driver: 555.42.02                   │
│                                      │
│  🌡️ Temperature    52°C              │
│  ⚡ Utilization    38%               │
│  💾 VRAM           6.2G / 24.0G     │
│     ████████░░░░░░░░░░░░  25%       │
│                                      │
│  Per-Process VRAM:                   │
│  ┌────────────────────────────────┐  │
│  │ Berry Backend     0.1 GB      │  │
│  │ ComfyUI           5.8 GB      │  │
│  │ WebUI             0.0 GB      │  │
│  │ Other             0.3 GB      │  │
│  └────────────────────────────────┘  │
└──────────────────────────────────────┘
```

- Popover appears on hover with 200ms delay, disappears on mouse leave with 100ms delay.
- VRAM bar uses the same green/yellow/red color coding.

---

## 7. Exit Confirmation Dialog

Centered modal overlay with backdrop blur.

```
┌──────────────────────────────────────────┐
│                                          │
│  ⚠️  Engines Still Running               │
│                                          │
│  ComfyUI and WebUI are still running     │
│  in the background.                      │
│                                          │
│  ☐ Remember my choice                   │
│                                          │
│  ┌──────────────┐  ┌──────────────────┐  │
│  │ Keep Running  │  │  Close All & Exit │  │
│  └──────────────┘  └──────────────────┘  │
│                                          │
└──────────────────────────────────────────┘
```

- "Keep Running": secondary button style (outline).
- "Close All & Exit": primary button style (filled, slight red tint to indicate finality).
- Lists only Berry-managed engines; external engines are not mentioned.

---

## 8. Embedded Engine View

When navigating to ComfyUI or WebUI from the rail:

```
┌──────────────────────────────────────────────────────────┐
│  🧩 ComfyUI · 127.0.0.1:8188    [↗ Browser] [🔄] [📁]  │  ← Utility toolbar
├──────────────────────────────────────────────────────────┤
│                                                          │
│                   ┌─────────────────┐                    │
│                   │                 │                    │
│                   │  <iframe>       │                    │
│                   │  ComfyUI        │                    │
│                   │  Web Interface  │                    │
│                   │                 │                    │
│                   └─────────────────┘                    │
│                                                          │
└──────────────────────────────────────────────────────────┘
```

### Utility Toolbar Buttons
- **↗ Open in Browser**: Opens the engine URL in the system default browser.
- **🔄 Refresh**: Reloads the iframe.
- **📁 Open Directory**: Opens the engine's installation directory in the file explorer.

### Not Running State

If the engine is not running, instead of the iframe show:

```
┌──────────────────────────────────────────────────────────┐
│                                                          │
│                    🧩                                     │
│                                                          │
│              ComfyUI is not running                      │
│                                                          │
│              [ ▶ Start ComfyUI ]                         │
│                                                          │
│              or install a new instance                   │
│              from the Launcher Hub                       │
│                                                          │
└──────────────────────────────────────────────────────────┘
```

---

## 9. Color Palette & Theme Consistency

All new components follow the existing Berry AI Studio dark theme:

| Token | Value | Usage |
| --- | --- | --- |
| `bg-primary` | `slate-950` | Main application background |
| `bg-surface` | `slate-900` | Card backgrounds, panels |
| `bg-surface-hover` | `slate-800` | Hover states |
| `border-default` | `slate-700/50` | Card borders, dividers |
| `text-primary` | `slate-100` | Primary text |
| `text-secondary` | `slate-400` | Secondary/muted text |
| `accent` | `indigo-500` | Active nav item accent, primary buttons |
| `status-running` | `emerald-500` | Running engine indicator |
| `status-stopped` | `slate-500` | Stopped engine indicator |
| `status-update` | `amber-500` | Update available indicator |
| `status-error` | `red-500` | Error/failed indicator |
| `destructive` | `red-500` | Destructive action text/buttons |

---

## 10. Animation & Transition Specifications

| Element | Animation | Duration | Easing |
| --- | --- | --- | --- |
| Rail collapse/expand | Width transition | 200ms | `ease-out` |
| View switch | Opacity crossfade | 150ms | `ease-in-out` |
| Card hover lift | Transform + shadow | 150ms | `ease-out` |
| Status dot pulse | Scale 1→1.5→1 + opacity | 1500ms | `ease-in-out`, infinite |
| Deployment drawer slide | Transform translateX | 300ms | `ease-out` |
| Popover appear | Opacity + scale 0.95→1 | 150ms | `ease-out` |
| Popover disappear | Opacity + scale 1→0.95 | 100ms | `ease-in` |
