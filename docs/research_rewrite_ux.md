# Rewrite Suggestion UX — Research Findings

**Date:** 2026-03-25
**Scope:** How major writing/resume tools surface AI rewriting suggestions; drag-and-drop usability evidence; evaluation of proposed interaction variants; recommendation for keyword injection UX.

---

## 1. How major tools surface suggestions

### 1.1 Writing and editing tools

| Tool | How suggestions are surfaced | Accept interaction | Reject interaction | User controls placement? | Drag-and-drop used? |
|---|---|---|---|---|---|
| **Grammarly** | Colored underline on the word/phrase in text; clicking the underline opens a floating suggestion card anchored to the problematic text | Click "Accept" button on card; or "Accept All" for a batch of high-confidence suggestions | Click "Dismiss" (trash icon) on card; or click away | No — Grammarly selects the placement; user can only accept or dismiss | No |
| **GitHub Copilot** | "Ghost text" — dimmed gray suggestion rendered inline at cursor position | Press `Tab` to accept full suggestion; `Cmd+→` to accept word-by-word | Press `Esc` or continue typing (implicit rejection) | No — AI places text at cursor; user navigates to desired location first | No |
| **Google Docs Smart Compose** | Ghost text rendered inline at cursor in lighter gray | Press `Tab` or `→` to accept | Continue typing (implicit rejection) | No — auto-placed at current cursor | No |
| **Notion AI** | Output appears in a floating panel below the selected block; full rewrite shown in preview | Three-button action bar: **Replace selection**, **Insert below**, **Discard** | Click "Discard" or press `Esc` | Yes — user chooses Replace vs Insert below | No |
| **Microsoft Copilot (Word)** | Side panel with AI-generated rewrite; tracked-changes overlay on accepted edits | Click "Keep it" / accept in tracked-changes flow | Click "Discard" | Partial — user highlights text first to scope placement | No |

### 1.2 Resume and ATS tools

| Tool | Keyword/suggestion surfacing | How user acts on a missing keyword | AI auto-places? | Drag-and-drop? |
|---|---|---|---|---|
| **Jobscan Power Edit** | Two-panel view: left = inline resume editor with live keyword highlighting (green/red on words as you type); right = keyword match panel with matched vs missing counts | User edits the left editor manually; clicking a missing keyword opens an AI bullet generator producing a full candidate sentence | No — placement is manual; AI only generates candidate phrases | No |
| **Teal** | Side panel showing matched and missing keywords from the pasted JD; resume editor on the left | User reads the keyword panel and edits their own text manually; separate AI bullet generator writes a full bullet per skill | No — placement is fully manual | No |
| **Rezi** | Conversational AI assistant embedded in the editor; chat prompt generates rewrites for a selected section | User types a prompt ("Add 'data analysis' to my experience at Company X") and AI rewrites the bullet; user accepts or regenerates | Yes for AI-generated content; user scopes via prompt | No |
| **Enhancv** | AI bullet-point generator per work experience card; keyword gap analysis in a separate tab | Click the AI button on a specific work card → AI generates 3–5 candidate bullets; user clicks one to insert it into that card | Yes — AI selects content within the user-chosen card | No |
| **Kickresume** | Section-level AI rewriter; scans the whole resume against a JD and suggests rewording | User triggers rewrite per section; AI returns a revised block; user accepts or edits inline | Yes at section level | Drag-and-drop used for reordering resume sections only — not for keyword injection |
| **ResumeWorded** | Keyword match score in right panel; missing keywords listed with colour-coded priority | User copies the keyword from the panel and manually pastes into their resume text | No | No |

### 1.3 Key cross-tool patterns identified

**Pattern 1 — Inline underline + floating card (Grammarly model)**
The suggestion is anchored to specific existing text. Works well for corrections but does not transfer to injection (adding new content to a user-chosen location), because there is no pre-existing text span to anchor to.

**Pattern 2 — Ghost text / Tab-accept (Copilot / Smart Compose model)**
The AI pre-places text at the cursor. The user accepts by pressing Tab. Demands very high AI confidence in placement and only works when there is a single unambiguous insertion point (the cursor). Not applicable where the user must choose which of N bullets receives the content.

**Pattern 3 — Preview panel + contextual action buttons (Notion AI model)**
AI output surfaces in a dedicated preview area; the user chooses whether to replace or insert below. The Replace/Insert split explicitly acknowledges placement as a user decision. Most relevant analogue to the resume use case.

**Pattern 4 — Side panel keyword list + manual edit (Jobscan / Teal model)**
The tool shows what is missing; the user figures out where and how to add it. Low-friction on the tool side but high-friction for the user. The dominant pattern in ATS tooling today.

**Pattern 5 — Per-card AI bullet generator (Enhancv model)**
The user navigates to the correct work experience card and clicks an AI trigger scoped to that card. AI generates candidate bullets. User picks one. Placement is determined by which card the user chose — they navigate to the right section first, then invoke AI within it. Eliminates the "wrong section" problem without drag-and-drop.

---

## 2. Drag-and-drop usability evidence

### 2.1 When drag-and-drop is appropriate

The Nielsen Norman Group identifies drag-and-drop as appropriate when:
- The object being moved is visually concrete (a file, a card, an image)
- Both source and target are simultaneously visible without scrolling
- No lower-cost alternative exists
- Users have been observed in testing to expect it

Canonical good examples: reordering Kanban cards, sorting playlist items, rearranging resume sections. All involve moving a whole block to a new position in a list.

### 2.2 Known usability problems (evidence-based)

**Discoverability.** Drag-and-drop is the most consistently documented discoverability failure in GUI research. If no visual cue (cursor change, grab handle, animation) signals draggability, users will not discover it. Research consistently shows users first attempt a click. UX Studio research notes that in palette-based UIs, "most testers couldn't figure out that objects from one column can be dragged to another column."

**Interaction cost.** NNG cites drag-and-drop as exemplifying GUI inefficiency: the user must acquire, hold, move, and release — four motor actions versus one click. Over distances of 400–800px (right-panel chip to left-panel bullet in a two-column layout), error rates increase and task times grow linearly with distance.

**Precision at drop target.** Research on drag-into-text targets shows users frequently miss by a line when aiming at a specific row. Bullet lines at 18–24px height are well below recommended touch target sizes (44px Apple HIG, 48px Material Design). Snap-to-target effects help only when drop zones are large enough to trigger the snap radius.

**Fat finger / touchscreen.** Finger contact area obscures the drop target. Touch interfaces require a hold-delay (150–200ms) to distinguish an intentional drag from scroll, adding latency. Apple HIG requires at least 1cm × 1cm of clear space around draggable areas — impossible at bullet granularity on a standard mobile viewport.

**No hover state on touch.** Drag affordance is conventionally communicated via cursor change on hover. Touch devices have no hover state. This compounds discoverability failure.

**Accessibility.** Drag-and-drop is not keyboard or screen-reader accessible without a separately implemented alternative. WCAG 2.5.7 (Level AA, WCAG 2.2) requires that all drag-and-drop functionality has an equivalent pointer-accessible alternative.

**Comparative study evidence.** A controlled usability study (Icons8, replicated across multiple age groups) found that click-based interactions produced significantly fewer errors and faster task completion than drag-and-drop equivalents. Users preferred click in every age group. NNG explicitly recommends considering alternatives such as menu-driven interactions and cites Gmail removing drag-and-drop on mobile in favour of a menu with better outcomes.

### 2.3 Drag-and-drop in resume tools — actual usage

In every tool surveyed, drag-and-drop appears only for **section reordering** (moving a whole Experience or Education block up or down). No surveyed tool uses drag-and-drop for keyword injection into text. This is an industry-wide UX judgement, not an oversight.

---

## 3. Evaluation of proposed variants

### Variant A: Drag keyword chip to section (BGE selects the bullet)

**The embedding model reliability problem.**
The user correctly identifies this risk. In production, no tool delegates the final sentence-selection step to an embedding model without human confirmation. GitHub Copilot — the highest-confidence AI text placer in the industry — only places text at the cursor position the user has already chosen. Delegating bullet selection to BGE means every incorrect embedding ranking is a visible user-facing error.

**The section drop zone implementation problem.**
The left column uses one textarea per role. A "section drop zone" requires visually overlaid regions on top of a live text editor. Native `<textarea>` elements do not support child nodes or overlaid hover regions. The architecture must change or fragile overlay divs must track textarea position dynamically.

**Drag discoverability problem applies in full.**
Cross-panel drag (chip in right panel → textarea in left panel) is not a pattern users encounter in mainstream tools. Without prominent onboarding or continuous animation cues, the majority of first-time users will click the chip and expect something to happen.

**Verdict:** Carries the full drag-and-drop usability penalty plus delegates placement to an unreliable AI component. Not recommended.

---

### Variant B: Drag keyword chip to bullet frame (user picks exact line)

**The user's granularity intuition is correct.**
Bullet-level targeting is the right goal. The user correctly recognises that section-level targeting is too coarse when BGE's sentence selection is unreliable. The Enhancv per-card model proves this instinct is shared by the industry.

**The drag mechanism fails at this granularity.**
Bullet frames at single-line height (16–24px) are below all touch target minimums. On desktop, a single-pixel misalignment drops into the wrong bullet. The visual clutter of per-bullet drag frames across a dense resume (15–30 bullets) would significantly degrade readability. NNG and Pencil & Paper both flag that multiple small, closely-spaced drop targets are a specific drag-and-drop failure mode.

**The interaction is novel with no major-tool precedent.**
This exact pattern — chip dragged from a keyword panel to an individual bullet row — exists in no surveyed production tool. Its universal absence is evidence against it, not merely an opportunity gap.

**Verdict:** The targeting granularity goal (bullet-level) is correct and validated by industry practice. The delivery mechanism (drag-and-drop to small targets) fails on precision, touch viability, and discoverability grounds. The goal and the mechanism should be decoupled.

---

## 4. Recommendation

### Recommended pattern: Click-to-target + inline suggestion card (two-step click flow)

This pattern achieves bullet-level precision without drag-and-drop. It synthesises the Enhancv per-card model, the Notion AI action-button model, and the Jobscan AI phrase generator into a flow suited to the existing two-column layout.

#### Step-by-step interaction flow

**Step 1 — Keyword panel chip (right column)**
Missing keywords are shown as chips. Each chip has a "+" icon. Matched keywords are shown with a tick and greyed styling. No drag affordance is indicated.

**Step 2 — User clicks a missing keyword chip**
Clicking the chip does not inject anything. The chip enters an "active / targeting" state (distinct colour/border). The left column enters **targeting mode**:
- Each bullet in the resume acquires a subtle coloured left-border or row highlight, indicating it is a valid injection target.
- A persistent banner appears above the resume editor: "Click the bullet you want to add '[keyword]' to — or press Esc to cancel."
- The right panel dims non-active chips to reduce distraction.

**Step 3 — User clicks a specific bullet**
The user clicks anywhere in the bullet's row. This is a large, full-width click target — no precision beyond row-level is required. This replaces BGE's sentence selection entirely with a direct user choice.

**Step 4 — Suggestion card appears, anchored to the selected bullet**
A card surfaces adjacent to the targeted bullet, showing:
- The **original bullet text** (for reference).
- A **rewritten version** incorporating the keyword — generated by the rewrite engine scoped to this single bullet (BGE / LLM used only for rephrasing, not for placement selection).
- Three action buttons: **Use this** | **Edit** | **Skip**.

**Step 5 — User acts**
- **Use this** — the rewritten bullet replaces the original. The keyword chip in the right panel moves to "matched" state. Targeting mode exits.
- **Edit** — the suggestion text becomes editable inline before committing. User edits and confirms.
- **Skip** — the suggestion is dismissed. The chip returns to "missing" state. The user can target a different bullet or press Esc to deactivate the chip.

#### Addressing the "user changes their mind about section" problem

Because the user clicks the exact bullet, section ambiguity is eliminated. If the user wants the keyword in a 2019 role rather than the 2023 role, they click the 2019 bullet. Targeting mode remains active until the user clicks a bullet or presses Escape. No timeout; no penalty for taking time to scroll and decide.

#### Fallback: Add to Skills section

For token-like keywords (tool names, certifications, technology names) that do not embed naturally into a bullet narrative, provide a secondary action on the chip: **"Add to Skills"** — a one-click path that appends the keyword to a Skills section without requiring bullet targeting. This mirrors Jobscan's behaviour and eliminates the need to force a rewrite for every keyword type.

#### Comparison with proposed variants

| Criterion | Drag to section (A) | Drag to bullet (B) | Click-to-target (recommended) |
|---|---|---|---|
| Discoverability | Poor — cross-panel drag not signalled | Poor — no analogues in production tools | Good — clicking a chip is a natural first action |
| Touch / mobile | Poor (drag distance, no hover) | Very poor (bullet targets too small) | Good — full-row click targets can meet 44px minimum |
| Placement precision | Low — BGE decides bullet | Medium — user decides but can misfire on small targets | High — user explicitly clicks the exact bullet row |
| Dependency on BGE for placement | Yes | No | No — BGE used only for rewriting, not targeting |
| Cognitive load | High — two object classes, cross-panel drag | Very high — many small targets, motor precision required | Low — two sequential clicks |
| Analogue in production tools | None found | None found | Enhancv card model + Notion AI action buttons |
| Undo / error recovery | Hard | Hard | Easy — Skip or undo restores original text |
| Accessibility | Requires WCAG 2.5.7 alternative | Requires WCAG 2.5.7 alternative | Inherently pointer and keyboard accessible |
| FE implementation complexity | High (textarea overlay for drop zones) | Very high (per-bullet draggable frames) | Medium (per-bullet rows + popover card) |

---

## 5. Open questions for FE feasibility check

1. **Per-bullet DOM structure.** The left column currently uses one `<textarea>` per role. Native `<textarea>` cannot host per-line visual overlays or per-bullet click targets. Can each bullet become its own component (or a custom element) so each bullet row is a separate DOM node with a wrapping element that can receive click handlers and targeting-mode styling? This is the largest architectural implication of the recommendation.

2. **Chip state machine.** The keyword chip needs at least three states: `missing` (default), `targeting` (user has activated this chip and is choosing a bullet), and `matched`. Confirm whether the existing chip component supports this or needs new CSS classes and interaction handlers.

3. **Suggestion card positioning and scroll.** The suggestion card anchored to a bullet must position correctly relative to a bullet row inside a scrollable left column. Verify that the popover handles the case where the anchor element is near the bottom of the viewport (card should flip upward) and that scroll position does not break the anchor binding.

4. **Mobile layout — stacked columns.** On mobile, the panels likely stack vertically. When the user clicks a chip in the lower keyword panel and must then scroll up to click a bullet, the "active chip" state must persist across scroll. A sticky "injecting: [keyword]" indicator fixed to the top of the viewport during targeting mode would prevent the user from losing track of which chip is active.

5. **Backend call timing.** Step 4 fires a rewrite call for one bullet + one keyword. If this takes >1.5s, the card should show a loading skeleton. Evaluate whether the rewrite can be pre-triggered speculatively when the user clicks the chip (Step 2) — possibly using the highest-similarity bullet as a default target — while still allowing the user to override by clicking a different bullet before the card is shown.

6. **Multi-keyword injection session.** Users will commonly want to inject 3–8 missing keywords in sequence. After a "Use this" acceptance, confirm that: the chip panel updates immediately, targeting mode resets, the next chip is ready to click, and the left column text reflects the accepted edit — all without a full re-render of the resume editor state.

7. **Undo scope.** After "Use this" replaces a bullet, the user needs a reliable undo path to the original. Confirm whether native undo history is sufficient or whether explicit before/after state snapshots must be stored in application state (necessary if the replacement is done programmatically).

8. **"Add to Skills" append logic.** Confirm that the skills section has a defined data model field that can receive appended terms programmatically, and that appending a keyword does not trigger a full resume re-parse on the backend.

---

*Sources consulted:*

- [Drag–and–Drop: How to Design for Ease of Use — Nielsen Norman Group](https://www.nngroup.com/articles/drag-drop/)
- [Drag-and-Drop UX: Guidelines and Best Practices — Smart Interface Design Patterns](https://smart-interface-design-patterns.com/articles/drag-and-drop-ux/)
- [Drag & Drop UX Design Best Practices — Pencil & Paper](https://www.pencilandpaper.io/articles/ux-pattern-drag-and-drop)
- [Drag & Drop: Think Twice — Dave Feldman / Medium](https://medium.com/@dfeldman/drag-drop-think-twice-49e7bf3e6b31)
- [Drag and Drop vs. Click: Usability Studies Revealed — Icons8 Blog](https://blog.icons8.com/articles/drag-and-drop-vs-click-are-they-rivals-usability-studies-revealed/)
- [Fat Finger Syndrome and Mobile Usability Testing — UX24/7](https://ux247.com/mobile-usability-testing-fat-finger-syndrome/)
- [The 7 Commandments of Designing Drag and Drop Interfaces — UX Studio](https://www.uxstudioteam.com/ux-blog/drag-and-drop-interface)
- [20+ GenAI UX Patterns — Sharang Sharma / UX Collective](https://uxdesign.cc/20-genai-ux-patterns-examples-and-implementation-tactics-5b1868b7d4a1)
- [Where should AI sit in your UI? — UX Collective](https://uxdesign.cc/where-should-ai-sit-in-your-ui-1710a258390e)
- [Grouped Writing Suggestions — Grammarly Blog](https://www.grammarly.com/blog/product/grouped-writing-suggestions/)
- [Notion AI: Everything you can do](https://www.notion.com/help/guides/everything-you-can-do-with-notion-ai)
- [Inline Suggestions from GitHub Copilot in VS Code](https://code.visualstudio.com/docs/copilot/ai-powered-suggestions)
- [Use Smart Compose and Smart Reply — Google Docs Help](https://support.google.com/docs/answer/9643962?hl=en)
- [Jobscan Power Edit](https://www.jobscan.co/power-edit)
- [Kickresume AI Resume Rewriter](https://www.kickresume.com/en/ai-resume-rewrite/)
- [Teal Resume Builder](https://www.tealhq.com/tools/resume-builder)
- [Enhancv AI Resume Builder](https://enhancv.com/ai-resume-builder/)
- [Interaction-Required Suggestions for Control, Ownership, and Awareness in Human-AI Co-Writing — arXiv 2504.08726](https://arxiv.org/html/2504.08726)
