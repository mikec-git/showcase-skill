---
name: showcase
description: Render HTML/SVG mockups, slideshows, demos, or before/after comparisons, serve them on localhost for preview, and optionally publish verified output to a shareable GitHub Pages URL. Use when the user asks to showcase, mockup, preview designs, render variants, build a slideshow, demo a layout, see how X would look, generate design options, compare design directions, publish/share a showcase, or invokes /showcase. Composes fresh design seeds for visual uniqueness across invocations, enforces a beauty bar, and runs mandatory Playwright verification so output is never broken or misaligned.
---

# Showcase

Generate one or more polished HTML artifacts (mockups, slides, demos, before/afters, landing snippets), serve them on a localhost port, verify them in a real browser, and report the URL back to the user. When the user explicitly asks to publish or share the showcase, publish the verified static output to their configured GitHub Pages showcase repository.

This skill exists because LLM-generated HTML/SVG drifts in three predictable ways: (1) it renders broken or misaligned without anyone noticing, (2) it converges to the same visual tropes invocation after invocation, (3) it settles for "fine" instead of "considered". The workflow below makes all three failure modes structurally hard.

## Workflow

1. **Parse intent** from the user's prompt:
   - **Artifact type**: `mockup` | `slides` | `demo` | `before-after` | `landing`. Infer from verbs (`mockup`, `present`, `walk me through`, `compare`, `landing page`). Default = `mockup`.
   - **Subject**: what is being shown (e.g. "macOS menu-bar popover", "Q3 roadmap", "search redesign before/after").
   - **Variant count**: how many side-by-side options. Default: 3 for `mockup` and `before-after`, 1 for `slides` and `demo`. Honor explicit count in prompt.
   - **Native-platform hint**: if subject mentions macOS / iOS / NSWindow / menu bar / popover / SwiftUI / AppKit, set `nativePlatform = "macos"` (or similar). This forces one variant to use the platform's HIG seed (see below) for accuracy.
   - **Publish intent**: only set `publish = true` when the user explicitly asks for a public/shared/published link. Never publish by default.
   - **Publish retention**: when publishing, infer `temp` if the user says temporary, expiring, for N days, share for review, or similar. Infer `persistent` if the user says permanent, keep, portfolio, archive, or similar. If publishing is requested and retention is not inferable, ask whether it should be temporary or persistent. Default temporary duration = 7 days when the user does not specify N.
   - If any of the above is genuinely ambiguous, ask one focused question. Do not ask if you can infer. **Style is the exception - never infer it; capture it in step 2.**

2. **Style intake** - capture the visual direction before composing seeds, so style is a decision, not a guess:
   - **Skip (ask nothing)** when the direction is already pinned: the user named an aesthetic / brand / colors / fonts, pasted or linked a reference, opted out ("surprise me", "you pick", "whatever looks best"), this is a trivial re-render of a prior showcase (reuse `styleIntake` from its `manifest.json`), or `nativePlatform` is set with no other direction.
   - **Otherwise ask once** (never block; silence or refusal defaults to "surprise me"). Phrase it tool-agnostically: if your interface has a multiple-choice control, present the options as selectable items; otherwise ask in plain text as a short numbered menu accepting a number, a name, or free-text adjectives.
     - **Q1 - direction** (pick one): `Editorial` (`editorial-mono`) · `Brutalist` (`brutalist-grid`) · `Swiss minimalist` (`swiss-minimalist`) · `Soft pastel` (`soft-pastel`) · `Glass dark` (`glassmorphism-dark`) · `Newsprint` (`newsprint`) · `Match a reference` (emulate a site / screenshot / brand / product) · `Surprise me` (you pick) · `Other` (describe in 2-3 adjectives; also covers `aurora-gradient`, `risograph`, `tactile-paper`).
     - **Q2 - reference** (only when Q1 = `Match a reference`): ask for a URL, a screenshot/image, brand colors, 2-3 adjectives, or a named product (Linear / Notion / Stripe). Emulate the _feel_, never copy or clone assets.
   - **Record** the answer in `manifest.json` under `styleIntake`: `{ askedAt, direction, namedSeed, reference: { url, imagePath, brandColors, adjectives, product }, freeText }`. For a `url`, keep the link and optionally screenshot it to read palette/type/density - do not scrape or clone. Save any reference image under `<output-dir>/refs/` and never ship it. This binds the seed axes in step 3 (see `## Design seeds` → Style intake → seed axes).

3. **Compose design seeds** for visual uniqueness (see `## Design seeds`):
   - Read `~/.claude/showcases/.seed-history.json` (create if missing) for recently-used seeds and their axes.
   - Compose `N` fresh seeds, each defining all five axes (palette, typography, density, mood, motif). They must (a) not closely repeat any seed from the last 5 invocations and (b) differ from each other on ≥3 of the five axes.
   - If `nativePlatform` is set, one variant must use the platform's native direction (`apple-hig-macos`, etc.) regardless of novelty - accuracy to native chrome wins for that variant.
   - Append the composed seeds (name + axes) to seed history immediately (so concurrent invocations don't collide).

4. **Resolve output location**:
   - If invoked inside a git repo: `<repo-root>/.claude/showcases/<slug>-<YYYYMMDD-HHMMSS>/`
   - Else: `~/.claude/showcases/<slug>-<YYYYMMDD-HHMMSS>/`
   - `<slug>` is a kebab-case 2-4-word derivation of the subject.
   - Ensure `.claude/showcases/` is in `.gitignore`; add it if missing.

5. **Generate the artifact tree**:

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
   - Do not ship fake controls. Every visible button, link, tab, toggle, menu, slider, stepper, slideshow control, doc control, or share/download/print control must either be wired to behavior or intentionally disabled with a visible disabled state.
   - For `slides` and document-like shared artifacts, include real navigation: previous/next controls, keyboard arrow support, visible progress, and stable deep links or hash state when practical. If the artifact has a table of contents, tabs, filters, or collapsible sections, they must update visible state.
   - Add a short `interactions` array to `manifest.json` listing each user-facing control and the expected observable result, so verification has a concrete checklist.
   - Use the **beauty bar** rules (see below) for every page.

6. **Serve on localhost** (background):
   - Find first free TCP port `>= 3001` (skip 3000; reserved for primary repo dev server).
   - `cd <output-dir> && python3 -m http.server <port> --bind 127.0.0.1` run in background via `Bash(run_in_background: true)`.
   - Write the chosen port into `manifest.json`.

7. **Verify (MANDATORY loop, max 3 fix passes per variant)** - this is the accuracy gate:
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
   5. **Verify interactions**, using Playwright against real controls, before any screenshot pass:
      - Enumerate visible interactive elements with roles/selectors: `button`, `a[href]`, `input`, `select`, `textarea`, `summary`, `[role="button"]`, `[role="tab"]`, `[role="switch"]`, `[role="menuitem"]`, `[tabindex]:not([tabindex="-1"])`.
      - For each item in `manifest.json` `interactions`, perform the interaction and assert the expected visible state, URL/hash, active slide number, expanded/collapsed state, selected tab, copied/downloadable/printable affordance, or navigation target.
      - For slides and docs, test mouse/touch-equivalent controls plus keyboard: ArrowRight/ArrowLeft for slides, Escape for overlays/modals, Tab focus order for primary controls, and Enter/Space activation where relevant.
      - Treat inert controls, placeholder buttons, broken internal links, focus traps, missing active states, or controls that only animate without changing meaningful state as failures. Fix and re-verify.
   6. `mcp__playwright__browser_take_screenshot` at the artifact's intended viewport(s):
      - For `mockup` of native macOS: 1440×900 (full window context) AND a tight crop of the surface itself.
      - For `slides`: 1920×1080.
      - For `landing`: 1440×900, plus 390×844 mobile.
      - For `before-after`: side-by-side viewport.
   7. **Inspect the screenshot yourself** for _broken_ output: text clipped at edges, overlapping elements, broken layouts, low-contrast text, asymmetric padding. If any present → fix and re-verify. The checks script and this pass are the **not-broken** bar only - a clean page can still be generic. So before any variant passes, run the **anti-generic gate** (the real quality bar): answer in writing - (1) could this be _any_ company, no point of view? (2) centered hero + equal-card grid? (3) default purple / violet or blue-gradient primary? (4) flat hierarchy, nothing is loudest? (5) default friendly-SaaS corners + drop-shadow soup? (6) one neutral sans at default weights throughout? **2+ "yes" = FAIL** → regenerate that variant from a _different_ reference (see `## Beauty bar` → Avoid the AI-default look); do not just patch.

   If a variant fails 3 fix passes, surface it to the user with the screenshot and ask whether to regenerate with a different seed or accept the issue.

8. **Open in default browser** (only after all variants pass verification):
   - `open http://127.0.0.1:<port>` so the user sees it immediately.

9. **Optionally publish a shareable URL** (only when `publish = true`):
   - Treat publishing as public internet exposure. Before publishing, confirm there are no secrets, credentials, private customer data, local machine identifiers, or sensitive real user data in the output.
   - Use `scripts/showcase_publish.py` from this skill directory for setup, publishing, listing, and cleanup. The config path is `$SHOWCASE_PUBLISH_CONFIG` when set, otherwise `~/.config/showcase-skill/publish.json`.
   - On publish-flow startup, if a publish config exists, run:

     ```bash
     python3 <skill-dir>/scripts/showcase_publish.py list
     ```

     If any temporary showcases are expired, ask one concise question: `I found <N> expired temporary published showcase(s). Clean them up before publishing?` If yes, run:

     ```bash
     python3 <skill-dir>/scripts/showcase_publish.py cleanup --yes
     ```

   - If no publish config exists, ask where to create the local Pages worktree/folder. Prefer reusing this same GitHub repo on a `gh-pages` branch, with the Pages worktree separate from the skill source checkout. Suggest these paths, with the first available path as the recommendation:
     - `/Users/mchoi/repos/showcase-skill-pages` when `/Users/mchoi/repos/showcase-skill` exists.
     - `<skill-repo-parent>/<skill-repo-name>-pages` when the skill repo path can be detected.
     - `/Users/mchoi/repos/showcases` when the user wants a separate publishing repo.
     - `~/repos/showcases` when `~/repos` exists.
     - `~/showcases`.
     - A custom path if the user wants a different location.
   - Also ask which GitHub repo to use. Default to this skill's existing remote, e.g. `mikec-git/showcase-skill`, so published URLs look like `https://mikec-git.github.io/showcase-skill/temp/<slug>/`. Use a separate `<current-gh-user>/showcases` repo only if the user asks for a separate publishing repo.
   - Configure same-repo publishing with:

     ```bash
     python3 <skill-dir>/scripts/showcase_publish.py configure \
       --repo-path <chosen-path> \
       --worktree-from <skill-repo-path> \
       --github-repo <owner>/<showcase-skill-repo> \
       --branch gh-pages \
       --source-dir . \
       --enable-pages \
       --install-cleanup-workflow
     ```

     This creates the local `gh-pages` worktree if needed, pushes the Pages branch, enables GitHub Pages by API, and installs a scheduled cleanup workflow on the default branch. Use `--base-url <url>` instead of `--github-repo` when the user is not publishing to GitHub Pages.

   - Publish temporary output with:

     ```bash
     python3 <skill-dir>/scripts/showcase_publish.py publish \
       --source <output-dir> \
       --kind temp \
       --days <N> \
       --slug <slug>
     ```

   - Publish persistent output with:

     ```bash
     python3 <skill-dir>/scripts/showcase_publish.py publish \
       --source <output-dir> \
       --kind persistent \
       --slug <slug>
     ```

   - Temporary showcases remain live until cleanup removes them. The helper records `expires_at`; the optional cleanup workflow removes expired temp folders daily, and the skill also offers cleanup at the start of each publish flow.
   - On publish-flow teardown, if expired temporary showcases remain and cleanup was not already offered at startup, ask whether to clean them up before the final report. Do not block the final report when the user says no.

10. **Report** back with:
    - The localhost URL.
    - The public URL when publishing was requested.
    - One line per variant: seed name + the 3-axis differentiation tags (palette / typography / mood).
    - Inline screenshots if available via the tool surface.
    - Path to the output directory.
    - For temporary public links: the expiry date and cleanup command.
    - A note that the server is running in the background and how to stop it (`lsof -ti tcp:<port> | xargs kill`).

## Design seeds

A **seed** is a complete visual direction defined across five axes: **palette, typography, density, mood, motif**. The skill does not choose from a closed list - it **composes a fresh seed for every variant**, so output stays novel invocation after invocation. The named directions below are inspiration and reference points, not a menu.

Composing seeds:

1. Read `~/.claude/showcases/.seed-history.json` (create if missing) for recently-used seeds and their axes.
2. For each variant, compose a NEW seed by deciding all five axes. It must:
   - differ from the other variants in this invocation on ≥3 of the five axes;
   - not closely repeat any seed from the last 5 invocations - a fresh accent over the same palette + typography + mood is not a new seed;
   - obey the `## Beauty bar` rules without exception.
3. If `nativePlatform` is set, one variant must instead use the platform's native direction (e.g. the `apple-hig-macos` reference below) - fidelity to native chrome outranks novelty for that variant.
4. Give each seed a short kebab-case name describing it (e.g. `quiet-grid-warm`, `mono-terminal`, `aurora-dark`), then append the name + its five axes to seed history before generating any HTML (so concurrent invocations don't collide).

If the user explicitly requests a direction ("make it editorial", "in a brutalist style"), honor it for that variant and build the seed around it. If the **Style intake** step (workflow step 2) captured a direction in `manifest.json` → `styleIntake`, treat it as a **binding constraint** for the relevant variant(s) and map it per the subsection below.

### Style intake → seed axes

Map the captured `styleIntake` answer onto the five axes:

- **Named direction** (Editorial, Brutalist, ...): seed at least one variant from its row in Reference directions across all five axes; other variants still vary ≥3 axes. If the user wants a single consistent look, honor it for every variant.
- **Surprise me / you pick**: no external constraint - compose fresh, fully-committed seeds (no last-5 repeat; spread one stark / one warm / one soft).
- **Match a reference**: derive **palette** from the reference's brand / dominant colors (3-5, contrast-safe), **typography** from its serif-vs-sans + weight (mapped to a real font), **density** from its spacing, **mood** from its tone, **motif** from one device it uses, used once. Emulate the feel; never copy assets.
- **Free-text adjectives**: warm / analog → warm + serif + grain (`tactile-paper`); technical / terminal → mono + dense + dark; premium / quiet → restrained + generous + subtle; playful → pastel / riso + rounded.
- `nativePlatform` pins one variant to `apple-hig-macos`; the captured direction applies to the remaining variant(s).

Every resulting seed still obeys the `## Beauty bar` and the ≥3-axis differentiation rule.

### Reference directions (inspiration, not a closed set)

> These rows are **anchors to depart from, not a menu.** Several - `glassmorphism-dark`'s #7C5CFF, `aurora-gradient`'s lavender→peach, `soft-pastel` - are recognizable AI-default looks; do not use them verbatim unless the user explicitly asked. Depart from any single row on ≥2 axes.

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

Treat the directions above as starting points to combine, darken, warm, or depart from - not a checklist. Push for contrast between variants: pairing two stark/sans/dense directions (e.g. glassmorphism + brutalist) reads as similar despite different colors, so spread variants across the axes - one stark, one warm, one soft. What matters is that every variant is a deliberate, distinct, beauty-bar-compliant composition. Picking a row unchanged may pass the novelty check on a first invocation but still **fails the anti-generic gate** (see Beauty bar → Avoid the AI-default look) - commit and depart.

## Beauty bar (non-negotiable)

Every page must obey these. The **Avoid the AI-default look** rules below are the _taste_ gate - the correctness rules under them are necessary but not sufficient. The verification loop looks for violations.

**Avoid the AI-default look** (the taste gate)

- **Style is never "inferable."** Anchor every surface to a concrete reference - a prompt-named aesthetic or the captured Style intake - before composing. Never silently fall back to a generic style.
- **Banned defaults unless explicitly asked**: violet / indigo / purple primaries or `#6366f1`→`#8b5cf6` / `#7C5CFF` gradients; lavender→peach or blue→purple hero gradients; glassmorphism blur as the main motif; centered-hero + three-equal-feature-cards; three-equal-pricing-card rows; emoji icons (esp. rocket / lightning / sparkles); Inter-on-everything at default weights.
- **One focal point per surface**, obvious at a squint: the hero headline is the loudest element (clamp ~3-4.5rem, line-height ~1.05, tracking ~-0.02em); everything else recedes in size / weight / opacity. Max two emphasis levels. Reject evenly-weighted card grids unless the content is a genuinely uniform list.
- **Color as punctuation**: ~90% neutral surfaces, ONE accent reserved for the single most important action. No gradient on buttons or text; any gradient is tonal (two adjacent values of one hue) and used once.
- **Don't center the whole page**: a real grid (max-width ~1200-1280px) with a strong left spine; body copy left-aligned at 60-75ch; center only short symmetric moments. Replace equal feature cards with tiles sized by importance (bento / asymmetric).
- **Restraint over decoration**: each ornament (motif / grain / gradient / blur) appears at most once per surface and must earn its place - default to removing it. Keep one region of intentional empty space. Backgrounds = a solid surface, a subtle texture (<6% opacity), or one tonal wash; never blobs or mesh orbs.
- **Glassmorphism on at most ONE element**, only with real content behind it; otherwise opaque surfaces with a 3-level elevation model (base / raised / overlay).
- **Shadows only on elevated elements** (raised cards, dropdowns, detached sticky nav): a two-part contact + ambient shadow tinted toward the surface hue, never identical pure-black soft shadows everywhere. Separate flat surfaces with a hairline border + spacing instead.
- **One real type decision**: a characterful headline face + neutral body, or one family across its weight range with strong contrast (800 vs 400). Tune tracking, line-height, measure, tabular-nums. Never the default at default settings. Banned seed descriptors: "modern", "clean", "premium", "sleek", "minimal", "elegant" - name a specific real-world reference instead.
- **Real content only** - never lorem ipsum or placeholder orbs: a real or mocked screenshot, a true diagram, or typography-as-art. Banned copy: "seamlessly", "effortlessly", "supercharge", "unlock", "empower", "revolutionize", "game-changing", "the power of", rule-of-three filler. Lead with a concrete claim using real nouns / numbers; subheads add information, not synonyms. Rewrite anything that could paste onto a competitor unchanged.
- **Novelty is a tiebreaker, not the goal**: each variant must first be coherent and fully committed - the ≥3-axis rule applies only after coherence. A variant that hits the axis count but feels arbitrary FAILS. Prefer 1-2 excellent committed directions over N differently-mediocre ones.
- **Litmus test (per variant)**: name its single focal point, its single accent use, its single type idea, and one deliberate asymmetry. Any answer of "everything" or "the default" means it's slop - redo it.

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
- Shadow: only on elevated elements; a two-part contact + ambient layer, both physically plausible (small + diffuse) and tinted toward the surface hue, never identical pure-black shadows on everything or `0 0 20px rgba(0,0,0,0.5)` blur dumps.
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

## Publishing lifecycle

- Publishing is opt-in and only runs when the user explicitly asks for a public/shared/published URL.
- The publishing helper stores local setup in `$SHOWCASE_PUBLISH_CONFIG` or `~/.config/showcase-skill/publish.json`.
- The preferred publishing target is this same GitHub repo on a separate `gh-pages` branch checked out as a sibling local worktree. A separate publishing repo using `main` + `/docs` is still supported when requested.
- Published paths are `temp/<slug>/` or `persistent/<slug>/`.
- Temporary showcases are marked with `expires_at`; they are removed when the user accepts cleanup or when the optional daily cleanup workflow runs in the publishing repo.
- Persistent showcases have no expiry and are not cleaned up unless the user explicitly asks.

## File hygiene

- `<output-dir>` lives under `.claude/showcases/` and must be gitignored.
- Never write secrets into showcase output. Never include real user data unless the prompt explicitly asks (use realistic-looking fixtures instead).
- After the user is done reviewing, they can `trash <output-dir>` to clean up. Do not auto-clean.

## Guardrails

- Do not call this skill from inside another skill that has its own browser flow (avoid double-launching browsers).
- If the user only wants the HTML files (no server), they will say so - skip step 6 and 8.
- If the user asks to publish without a configured publishing repo, ask for setup choices before creating any GitHub repo or remote.
- If the publishing repo has uncommitted changes, stop and explain that it must be clean before publishing or cleanup.
- If Playwright is unavailable, fall back to static analysis (HTML parse, CSS link check, image existence) and clearly tell the user that runtime verification was skipped.
- If three fix passes can't clear the verification for a variant, **show the user the failing screenshot rather than silently shipping broken output**.

## Output

A short message in this shape:

```
Showcase ready: http://127.0.0.1:<port>
Public URL: https://<owner>.github.io/showcase-skill/temp/<slug>/ (expires <date>)

Variants:
- A · apple-hig-macos · system blur, SF Pro, native light/dark split
- B · editorial-mono  · Newsreader serif, rust accent, NYT density
- C · brutalist-grid  · JetBrains Mono, neon accent, hard 2px borders

Output: <output-dir>
Cleanup temp publishes: python3 <skill-dir>/scripts/showcase_publish.py cleanup --yes
Stop server: lsof -ti tcp:<port> | xargs kill
```
