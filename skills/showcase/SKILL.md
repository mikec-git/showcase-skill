---
name: showcase
description: Render HTML/SVG mockups, slideshows, demos, or before/after comparisons and serve them on localhost for preview. Use when the user asks to showcase, mockup, preview designs, render variants, build a slideshow, demo a layout, see how X would look, generate design options, compare design directions, or invokes /showcase. Picks rotating design seeds for visual uniqueness across invocations, enforces a beauty bar, and runs mandatory Playwright verification so output is never broken or misaligned.
---

# Showcase

Generate one or more polished HTML artifacts (mockups, slides, demos, before/afters, landing snippets), serve them on a localhost port, verify them in a real browser, and report the URL back to the user.

This skill exists because LLM-generated HTML/SVG drifts in three predictable ways: (1) it renders broken or misaligned without anyone noticing, (2) it converges to the same visual tropes invocation after invocation, (3) it settles for "fine" instead of "considered". The workflow below makes all three failure modes structurally hard.

## Workflow

1. **Parse intent** from the user's prompt:
   - **Artifact type**: `mockup` | `slides` | `demo` | `before-after` | `landing`. Infer from verbs (`mockup`, `present`, `walk me through`, `compare`, `landing page`). Default = `mockup`.
   - **Subject**: what is being shown (e.g. "macOS menu-bar popover", "Q3 roadmap", "search redesign before/after").
   - **Variant count**: how many side-by-side options. Default: 3 for `mockup` and `before-after`, 1 for `slides` and `demo`. Honor explicit count in prompt.
   - **Native-platform hint**: if subject mentions macOS / iOS / NSWindow / menu bar / popover / SwiftUI / AppKit, set `nativePlatform = "macos"` (or similar). This forces one variant to use the platform's HIG seed (see below) for accuracy.
   - If any of the above is genuinely ambiguous, ask one focused question. Do not ask if you can infer.

2. **Pick design seeds** for visual uniqueness (see `## Design seeds`):
   - Read `~/.claude/showcases/.seed-history.json` (create if missing) for recently-used seed names.
   - Pick `N` seeds that (a) haven't been used in the last 5 invocations and (b) differ from each other on ≥3 orthogonal axes (palette, typography, density, mood, motif).
   - If `nativePlatform` is set, force exactly one variant to use the platform seed (`apple-hig-macos`, etc.) regardless of history - accuracy to native chrome matters more than novelty for that variant.
   - Append the picks to seed history immediately (so concurrent invocations don't collide).

3. **Resolve output location**:
   - If invoked inside a git repo: `<repo-root>/.claude/showcases/<slug>-<YYYYMMDD-HHMMSS>/`
   - Else: `~/.claude/showcases/<slug>-<YYYYMMDD-HHMMSS>/`
   - `<slug>` is a kebab-case 2-4-word derivation of the subject.
   - Ensure `.claude/showcases/` is in `.gitignore`; add it if missing.

4. **Generate the artifact tree**:

   ```
   <output-dir>/
     index.html              # variant picker / overview if N > 1, otherwise the artifact itself
     manifest.json           # subject, type, variant count, seed names, port, created_at
     variants/
       <seed-slug>/
         index.html
         style.css
         script.js           # only if interactive
         assets/             # SVGs, images
   ```

   - The root `index.html` (when N > 1) is a clean overview page that lists all variants with brief seed descriptions and links/iframes. It is itself a designed surface, not a bare list.
   - Each variant's `index.html` is a fully self-contained page. No CDNs unless explicitly required and offline-cached. Use system fonts or self-hosted webfonts.
   - Use the **beauty bar** rules (see below) for every page.

5. **Serve on localhost** (background):
   - Find first free TCP port `>= 3001` (skip 3000; reserved for primary repo dev server).
   - `cd <output-dir> && python3 -m http.server <port> --bind 127.0.0.1` run in background via `Bash(run_in_background: true)`.
   - Write the chosen port into `manifest.json`.

6. **Verify (MANDATORY loop, max 3 fix passes per variant)** - this is the accuracy gate:
   For each variant URL:
   1. `mcp__playwright__browser_navigate` to the variant URL.
   2. `mcp__playwright__browser_console_messages` - must be empty (or only deprecation notices). Errors = fix.
   3. `mcp__playwright__browser_snapshot` - confirms DOM rendered.
   4. `mcp__playwright__browser_evaluate` with a checks script that asserts:
      - No element has `getBoundingClientRect().width === 0 || height === 0` among elements tagged `data-checkpoint`.
      - `document.documentElement.scrollWidth <= window.innerWidth + 2` (no horizontal overflow).
      - All `<img>` and `<image>` have `complete && naturalWidth > 0`.
      - Computed text-color vs. background contrast ratio for every `data-checkpoint="text"` element is `>= 4.5` (WCAG AA).
      - Custom fonts (if any `@font-face`) report `document.fonts.status === "loaded"`.
   5. `mcp__playwright__browser_take_screenshot` at the artifact's intended viewport(s):
      - For `mockup` of native macOS: 1440×900 (full window context) AND a tight crop of the surface itself.
      - For `slides`: 1920×1080.
      - For `landing`: 1440×900, plus 390×844 mobile.
      - For `before-after`: side-by-side viewport.
   6. **Inspect the screenshot yourself.** Look for: text clipped at edges, overlapping elements, broken layouts, low-contrast text, asymmetric padding, generic-looking output. If any present → fix and re-verify.

   If a variant fails 3 fix passes, surface it to the user with the screenshot and ask whether to regenerate with a different seed or accept the issue.

7. **Open in default browser** (only after all variants pass verification):
   - `open http://127.0.0.1:<port>` so the user sees it immediately.

8. **Report** back with:
   - The localhost URL.
   - One line per variant: seed name + the 3-axis differentiation tags (palette / typography / mood).
   - Inline screenshots if available via the tool surface.
   - Path to the output directory.
   - A note that the server is running in the background and how to stop it (`lsof -ti tcp:<port> | xargs kill`).

## Design seeds

Each seed is a (palette, typography, density, mood, motif) combination. Pick seeds that have not been used recently and that differ from each other within an invocation. Never use the same seed twice in one invocation.

| Seed                 | Palette                                                                                   | Typography                                                           | Density     | Mood                        | Notes                                                                                                                                                        |
| -------------------- | ----------------------------------------------------------------------------------------- | -------------------------------------------------------------------- | ----------- | --------------------------- | ------------------------------------------------------------------------------------------------------------------------------------------------------------ |
| `apple-hig-macos`    | macOS system colors (semantic: label, secondaryLabel, controlAccentColor)                 | `-apple-system, BlinkMacSystemFont, "SF Pro Text"`                   | Native      | Native, restrained          | **Required when native macOS UI is the subject.** Use real NSStatusBar height (24px), popover corner radius (10px), `backdrop-filter: blur(40px)`, vibrancy. |
| `editorial-mono`     | Off-white #FAF8F3 base, ink-black #15140F, single accent (rust #C45A2C or oxford #2E3A50) | `Newsreader` or `Source Serif Pro` heading + `Inter` body            | Spacious    | Considered, editorial       | NYT/Bloomberg feel. Generous leading. Real rule lines.                                                                                                       |
| `brutalist-grid`     | Stark white + pure black + one neon accent (#FF3D00 or #00E676)                           | `JetBrains Mono` everywhere                                          | Dense       | Confrontational, structural | Heavy 2-3px borders. No shadows. Hard grid visible.                                                                                                          |
| `soft-pastel`        | Cream #FFF8F0, blush #FFD6CC, sage #C5D5C0, sand #E8D4B0                                  | `Geist` or `Inter`                                                   | Comfortable | Friendly, calm              | Rounded corners (12-16px). Subtle drop shadows.                                                                                                              |
| `glassmorphism-dark` | Slate #0E1116 base, frosted-white overlays, electric accent (#7C5CFF)                     | `Geist` or `Inter`                                                   | Comfortable | Modern, premium             | `backdrop-filter: blur(24px)` on cards. Subtle inner highlight.                                                                                              |
| `swiss-minimalist`   | Pure white + black, one primary (Helvetica red #D62B17 or Klein blue #0033A0)             | `Inter` or `Helvetica Neue`                                          | Comfortable | Precise, geometric          | 12-col grid visible at the meta level. Generous gutters.                                                                                                     |
| `newsprint`          | Newsprint cream #F4EEDD, ink #1A1612, red accent #B33A2E                                  | `Newsreader` everywhere                                              | Dense       | Authoritative, archival     | Column rules. Drop caps where appropriate.                                                                                                                   |
| `aurora-gradient`    | Off-white base, soft gradient hero band (lavender → peach), text in deep slate #1B2230    | `Geist Sans`                                                         | Spacious    | Modern SaaS, optimistic     | One gradient, used once. Otherwise calm.                                                                                                                     |
| `risograph`          | Two-spot color (fluoro pink #FF48B0 + cool mint #5CDCC1) on cream                         | `Space Grotesk` heading + `Inter` body                               | Comfortable | Print, tactile              | Subtle grain overlay (1% noise SVG). Slight color misregistration on accents.                                                                                |
| `tactile-paper`      | Kraft #E8DCC4, ink #2D241C, brick #A33D2A                                                 | `Source Serif Pro` + handwritten accent (`Caveat` for callouts only) | Comfortable | Warm, analog                | Paper-grain background SVG. Subtle deckle edges.                                                                                                             |

Picking algorithm:

1. Filter out seeds used in the last 5 invocations (from `.seed-history.json`).
2. If `nativePlatform` is set, pin the matching native seed (e.g. `apple-hig-macos`) as variant 1.
3. For remaining variants, pick seeds maximizing axis-distance: never pair `glassmorphism-dark` + `brutalist-grid` (both stark/sans/dense - too similar in mood despite color difference; prefer one stark + one warm + one soft).
4. Persist picks before generating any HTML.

If the user explicitly requests a seed ("make it editorial", "in a brutalist style"), honor that and skip rotation for that variant.

## Beauty bar (non-negotiable)

Every page must obey these. Verification step 6.6 looks for violations.

**Typography**

- One heading family + one body family (max two). Real font names, not "sans-serif".
- Body line-height 1.5-1.7. Heading line-height 1.05-1.25.
- Max measure for prose: 65ch.
- No more than 4 distinct font sizes on a single surface.

**Spacing**

- Use a strict 4px / 8px / 12px / 16px / 24px / 32px / 48px / 64px / 96px scale. No arbitrary values like `padding: 13px`.
- Component-edge padding ≥ font-size × 1.5.
- Vertical rhythm: section-to-section gap ≥ 48px on desktop.

**Color**

- Define a palette of 3-5 colors max (background, surface, text, secondary text, accent). Document them in a CSS `:root` block with semantic names.
- Text contrast ≥ 4.5:1 (validated automatically).
- No more than one gradient per page unless the seed explicitly calls for more.

**Surface treatment**

- Borders 1px solid with `oklch()` or `rgba()` low-opacity ink, not gray middle-tones, unless the seed specifies heavy borders.
- Shadow: max two layers, both physically plausible (small + diffuse), never `0 0 20px rgba(0,0,0,0.5)` blur dumps.
- Corner radius consistent per surface: pick one of {4, 8, 10, 12, 16, 20} and stick with it.

**Iconography**

- Use real icon sets (SF Symbols glyph names with system-ui fallback, or inline Lucide/Heroicons SVG paths). Never emoji as icon substitute except for explicitly emoji-flavored content.
- Icon sizes from the spacing scale (16, 20, 24, 32).

**Native-platform fidelity** (when `nativePlatform = "macos"`):

- NSStatusBar effective height: 24px.
- Menu-bar item title font: 13px `SF Pro Text`, system label color.
- Popover corner radius: 10px; background `backdrop-filter: blur(40px) saturate(180%)`; subtle 1px stroke `rgba(255,255,255,0.18)` in dark mode, `rgba(0,0,0,0.10)` in light.
- Use semantic system colors via custom properties: `--label: #000c` light / `#fffd` dark, `--secondaryLabel: #0008` / `#fff9`, `--controlAccent: #007AFF`.
- Render BOTH light and dark variants (split-screen or toggle), so the user sees both.

**Overview page (when N > 1)**

- Not a bare list - it's itself a designed page in `swiss-minimalist` or `editorial-mono` (consistent across invocations).
- Each variant rendered inline via `<iframe>` with a labeled caption listing the seed + 3-axis differentiators.

## Verification details

The checks script (passed to `browser_evaluate`):

```js
() => {
  const issues = [];
  document.querySelectorAll("[data-checkpoint]").forEach((el) => {
    const r = el.getBoundingClientRect();
    if (r.width === 0 || r.height === 0)
      issues.push(`zero-size: ${el.dataset.checkpoint}`);
  });
  if (document.documentElement.scrollWidth > window.innerWidth + 2) {
    issues.push(
      `hscroll: ${document.documentElement.scrollWidth}px > ${window.innerWidth}px`,
    );
  }
  document.querySelectorAll("img,image").forEach((el) => {
    if (!el.complete || el.naturalWidth === 0)
      issues.push(`broken-image: ${el.src || el.href?.baseVal}`);
  });
  // Contrast check for text checkpoints
  const parseRGB = (s) => s.match(/\d+/g)?.slice(0, 3).map(Number);
  const lum = ([r, g, b]) => {
    const f = (c) => {
      c /= 255;
      return c <= 0.03928 ? c / 12.92 : Math.pow((c + 0.055) / 1.055, 2.4);
    };
    return 0.2126 * f(r) + 0.7152 * f(g) + 0.0722 * f(b);
  };
  document.querySelectorAll('[data-checkpoint="text"]').forEach((el) => {
    const cs = getComputedStyle(el);
    const fg = parseRGB(cs.color);
    if (!fg) return;
    let bgEl = el;
    let bg;
    while (bgEl) {
      const c = getComputedStyle(bgEl).backgroundColor;
      const m = parseRGB(c);
      if (m && getComputedStyle(bgEl).backgroundColor !== "rgba(0, 0, 0, 0)") {
        bg = m;
        break;
      }
      bgEl = bgEl.parentElement;
    }
    if (!bg) return;
    const L1 = lum(fg),
      L2 = lum(bg);
    const ratio = (Math.max(L1, L2) + 0.05) / (Math.min(L1, L2) + 0.05);
    if (ratio < 4.5)
      issues.push(
        `contrast: ${ratio.toFixed(2)} on "${el.textContent.slice(0, 40)}"`,
      );
  });
  return {
    ok: issues.length === 0,
    issues,
    fontsLoaded: document.fonts?.status === "loaded",
  };
};
```

**Tag your HTML for the verifier.** Add `data-checkpoint="<name>"` to every load-bearing element (status item, popover, card, button group, footer). Add `data-checkpoint="text"` to every text element you care about for contrast. The verifier only checks tagged elements - untagged ones could still be broken, so be liberal.

## Server lifecycle

- One server per `<output-dir>`. The port is recorded in `manifest.json`.
- If a previous showcase for the same slug is still serving, reuse it: read `manifest.json`, check `lsof -ti tcp:<port>`, if alive then just re-open the URL instead of starting a new server.
- Provide stop instructions in the final report: `lsof -ti tcp:<port> | xargs kill`.
- On macOS, `open http://127.0.0.1:<port>` opens the user's default browser.

## File hygiene

- `<output-dir>` lives under `.claude/showcases/` and must be gitignored.
- Never write secrets into showcase output. Never include real user data unless the prompt explicitly asks (use realistic-looking fixtures instead).
- After the user is done reviewing, they can `trash <output-dir>` to clean up. Do not auto-clean.

## Guardrails

- Do not call this skill from inside another skill that has its own browser flow (avoid double-launching browsers).
- If the user only wants the HTML files (no server), they will say so - skip step 5 and 7.
- If Playwright is unavailable, fall back to static analysis (HTML parse, CSS link check, image existence) and clearly tell the user that runtime verification was skipped.
- If three fix passes can't clear the verification for a variant, **show the user the failing screenshot rather than silently shipping broken output**.

## Output

A short message in this shape:

```
Showcase ready: http://127.0.0.1:<port>

Variants:
- A · apple-hig-macos · system blur, SF Pro, native light/dark split
- B · editorial-mono  · Newsreader serif, rust accent, NYT density
- C · brutalist-grid  · JetBrains Mono, neon accent, hard 2px borders

Output: <output-dir>
Stop server: lsof -ti tcp:<port> | xargs kill
```
