# Rewrite Suggestion UX — FE Feasibility Assessment

**Date:** 2026-03-25
**Reviewer:** FE architecture analysis of current codebase
**Files examined:** `frontend/src/App.jsx`, `frontend/src/components/Step4Edit.jsx`, `frontend/src/components/KeywordPanel.jsx`, `frontend/src/App.css`

---

## 1. Current implementation summary

### Layout

Step 4 renders a two-column flex layout (`.edit-layout`): the resume column on the left (`flex: 2`) and a sticky keyword panel on the right (`flex: 0 0 300px`). The keyword panel is position-sticky within the viewport using a CSS custom property (`--header-h`) to offset below the frozen page header.

### Left column — resume editing

Sections and roles are rendered by mapping over `resumeSections` (a structured array lifted into `App.jsx` state). Each role renders a single `<AutoTextarea>` component that holds **all bullets for that role as one multi-line string** — newline-delimited, with `• ` bullet prefixes added as a display-only transform (stripped back to raw text on every change).

`AutoTextarea` is a custom component wrapping a single `<textarea>` with:
- Auto-resize via `useLayoutEffect` (collapses to scroll height, clamped at 400 px max)
- A custom undo/redo stack (debounced 400 ms snapshots, stored in refs, up to 50 entries)
- Cursor position correction after the `• ` prefix rewrite (calculated per-line, corrected in `requestAnimationFrame`)
- A `requestAnimationFrame` patch to force-set `textarea.value` and re-measure height after each change

Because bullets are stored as lines within a single string, there is no per-bullet DOM node. The component receives `value = role.bullets.map(b => b.text).join('\n')` and on change calls `handleRoleTextChange`, which splits the string back by `\n` and re-maps onto the `bullets` array.

### Right column — keyword panel

`KeywordPanel` renders a `<ul>` with one `<li>` per keyword. Each `<li>` contains an icon span, a phrase span, and an ignore `<button>`. Keywords are classified matched/unmatched by regex-testing `resumeText` (all bullet text joined by space) on every render. Chips are plain `<li>` elements — no `draggable` attribute, no pointer event handlers beyond the ignore button's `onClick`.

### Flash animation system

When `resumeText` changes and a keyword transitions matched state, `Step4Edit` identifies which `.edit-role` divs are affected and appends a CSS animation class. This works by DOM traversal using `document.activeElement.closest('.edit-role')` and `querySelectorAll`.

---

## 2. Variant A: Drag keyword chip → section/role drop target

**Concept:** Make `<li>` chips draggable. Each `.edit-role` `<div>` (wrapping the role title input and its `AutoTextarea`) becomes a drop target. On drop, call the backend with the phrase and the full role text; backend returns a suggested rewrite.

### What needs to change

1. Add `draggable="true"` and `onDragStart` to each `<li>` in `KeywordPanel`. The drag payload is just the phrase string, set via `e.dataTransfer.setData('text/plain', phrase)`.
2. Add `onDragOver` (must call `e.preventDefault()`), `onDragEnter`, `onDragLeave`, and `onDrop` handlers to each `.edit-role` `<div>` in `Step4Edit`.
3. On drop, call a new backend endpoint (e.g., `POST /rewrite/suggest`) with `{ phrase, role_text }`. Backend uses BGE to identify the best bullet and returns a suggested rewrite.
4. Surface the suggestion (see section 4 for the inline card pattern, which is the natural pairing).
5. Track `dragOverRole` state (`{ si, ri } | null`) to highlight the active drop zone.

### Technical notes

- HTML5 Drag-and-Drop API is the correct choice — no library needed for this use case.
- Drop targets on `<div>` wrappers work cleanly; no conflict with the `<textarea>` inside.
- Safari desktop: HTML5 DnD works but `dataTransfer.setData` only reliably carries `'text/plain'`. Do not use custom MIME types.
- Mobile/touch: HTML5 DnD does not fire on touch screens (see constraint 1 in section 5).
- CSS: change `.kp-item` from `cursor: default` to `cursor: grab` on draggable chips.

### Effort estimate: **medium**

Wiring up DnD events and visual state is 0.5–1 day. The larger cost is the end-to-end suggestion flow: new backend endpoint, new frontend suggestion state per role, and UI to accept/reject. Total: 2–3 FE days plus backend work.

---

## 3. Variant B: Drag keyword chip → per-bullet frame

**Concept:** Replace the single `AutoTextarea` per role with a list of individual per-bullet elements (one `<div>` or `<textarea>` per bullet). Chips are dropped onto a specific bullet frame.

### Migration cost for the textarea split

`AutoTextarea` is tightly coupled to the single-string-per-role model in several ways:

1. **State model.** `handleRoleTextChange` splits on `\n` to reconstruct `bullets`. This is replaced by `handleBulletTextChange(si, ri, bi, newText)`. Straightforward refactor but touches the core edit path.
2. **Undo/redo.** The undo stack lives in refs inside one `AutoTextarea` instance, scoped to the whole role. Per-bullet textareas give each bullet an independent undo stack. Cross-bullet undo (e.g., undoing an injection that modified bullet 3) requires lifting undo state to role scope — significantly more complex.
3. **Auto-resize.** Moving from one to many textareas is straightforward — apply the same `useLayoutEffect` height logic per instance.
4. **Bullet prefix display.** Each per-bullet element renders its own `• ` prefix — simpler than the current per-line string transform.
5. **Flash animation.** Existing role-level flash still works unchanged. Can optionally be made bullet-granular.
6. **`roleValue` filtering.** The trailing-empty-line filter moves to the per-bullet render level.

### Drop target mechanics

Per-bullet elements are valid drop targets. The `onDrop` handler receives `{ si, ri, bi }` instead of `{ si, ri }`. Implementation is otherwise identical to Variant A.

### What Variant B breaks

- **Cross-bullet editing flow.** Users can no longer freely cut/paste across bullets within a single textarea. A new bullet requires an "add bullet" button or Enter-to-split handling. This is meaningful UX scope beyond the drag feature itself.
- **Undo semantics.** Per-bullet undo stacks are a reasonable substitute but cross-bullet undo is lost unless explicitly re-implemented.

### Effort estimate: **high**

The per-bullet migration alone is 1–1.5 days of careful refactoring. Per-bullet drop targets add 0.5 days. Add/remove/reorder bullet UX can expand scope further. Total FE estimate: 3–5 days including edge cases, not counting backend.

---

## 4. Alternative patterns

### Click-to-target

**Concept:** Clicking a keyword chip enters "targeting mode." The user then clicks a bullet (or role area) to designate it as the injection target.

**Feasibility with current structure:**
- Role-level targeting: feasible without any migration. Add `selectedChip` state, a new `onClick` callback prop on `KeywordPanel`, and `onClick` handlers on `.edit-role` divs. Visual feedback (chip highlight, cursor change on the resume column) is CSS-only.
- Bullet-level targeting: not feasible without the per-bullet split. A `click` event on a `<textarea>` yields a cursor position, not a bullet index. There is no sub-element structure within a textarea that can be clicked.

**Effort estimate: low** (role-level) / **medium** (bullet-level — requires Variant B migration first)

---

### Inline suggestion card

**Concept:** After a keyword is targeted, the backend auto-selects the best bullet and renders a suggestion card (original vs. suggested text, accept/dismiss controls) adjacent to the target role or bullet.

**Feasibility with current structure:** Good. This is additive — no changes to `AutoTextarea` or the per-bullet split are required. The legacy `Step4ReviewLegacy.jsx` implements almost exactly this pattern (suggestion card with hint text, editable textarea, accept checkbox) and is available as a reference. With the current model, cards appear below the role's textarea rather than inline with a specific bullet.

**What needs to change:**
- New `suggestions` state keyed by `${si}-${ri}` (or `${si}-${ri}-${bi}` if per-bullet): `{ phrase, original_text, suggested_text } | null`
- A new `SuggestionCard` component rendered conditionally below the role textarea
- Accept: write `suggested_text` into the correct bullet(s) in `resumeSections` and clear the suggestion
- Dismiss: clear the suggestion state only
- A new backend endpoint (shared with Variants A and B)

**Effort estimate: medium**

~1 FE day for suggestion state + card component + accept/dismiss wiring. No breaking changes to existing edit or flash logic. Backend endpoint is a separate dependency.

---

### Side-by-side diff

**Concept:** Show original bullet text on the left and the BGE-rewritten version on the right in a two-column diff view, with an "Accept" button.

**Feasibility with current structure:**
- Role-level (below textarea): feasible. The diff component appears below the role's `AutoTextarea`, showing the specific changed bullet alongside the suggested replacement. Simple `<div>` layout, no `<textarea>` replacement needed.
- True inline diff (highlighted within the textarea): not achievable with a `<textarea>`. Textareas do not support mixed inline formatting. Achieving per-line inline diff highlighting requires either `contenteditable` (high risk, see constraint 7 in section 5) or the per-bullet split.

**What needs to change (minimal, role-level):**
- Same backend endpoint and suggestion state as inline card
- A diff display component below the role textarea comparing original vs. suggested bullet text
- Accept: write suggested text into `resumeSections`

**Effort estimate: medium** (role-level diff below textarea) / **high** (true inline diff requiring `contenteditable` or per-bullet split)

---

## 5. Hard constraints for the UX researcher

1. **Drag-and-drop is desktop-only.** HTML5 DnD does not fire on touch devices. Any drag interaction (Variants A or B) excludes mobile users unless a touch polyfill (`mobile-drag-drop` or similar) is added. The polyfill adds complexity and its own cross-browser issues.

2. **Dropping onto a `<textarea>` is unreliable in Safari.** Safari intercepts drag events over `<textarea>` elements to support its native text-drop behavior. Variant B's per-bullet textareas as drop targets would malfunction in Safari. The safe pattern is a `<div>` drop target wrapping each bullet, with the `<textarea>` inside — or an overlay element that captures drops.

3. **Targeting a specific bullet within the current model is not possible.** The `AutoTextarea` is a single `<textarea>` with no per-bullet DOM structure. Click-to-target at bullet granularity, Variant B drop targets, and per-bullet inline diffs all require the per-bullet split migration first. This is the largest prerequisite for any bullet-level interaction.

4. **Undo/redo is per-textarea.** Splitting to per-bullet textareas fragments the undo scope. Cross-bullet undo (e.g., undoing a keyword injection that modified bullet 3 of role 2) requires lifting undo state to role or global scope — a non-trivial change. The UX researcher should decide whether cross-bullet undo is a requirement before committing to Variant B.

5. **A new backend endpoint is required for all variants.** Every interaction pattern described above converges on the same backend call: given a phrase and role text, return a suggested rewrite. This endpoint does not currently exist. All FE effort estimates assume it is available and returns a single suggested rewrite string.

6. **The inline suggestion card is the lowest-risk path.** It is purely additive, requires no changes to `AutoTextarea`, has a near-complete reference implementation in `Step4ReviewLegacy.jsx`, and works on both desktop and mobile. The only UX tradeoff is that suggestions appear below the role block rather than inline with the specific bullet.

7. **`contenteditable` should be avoided.** Replacing `AutoTextarea` with a `contenteditable` div to enable character-level inline diff highlighting is high risk. IME composition, paste normalization, undo, cursor tracking, and cross-browser quirks are all significantly harder to handle than in a `<textarea>`. Do not pursue this path unless there is a strong product requirement that cannot be met any other way.

8. **The two-column layout narrows on small viewports.** The keyword panel is fixed at 300 px. Below ~700 px viewport width, the columns stack. Any drag interaction across both columns on narrow screens or tablets needs explicit design consideration — the drop zone and chip source may not both be visible simultaneously.
