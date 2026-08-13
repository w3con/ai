---
name: feedback-no-inline-styles
description: "User wants zero inline style=\"\" attributes in HTML; all CSS goes in dedicated stylesheet"
metadata: 
  node_type: memory
  type: feedback
  originSessionId: 87ee769e-ef7f-41f0-a97f-c9f358f52707
---

Never write `style=""` attributes in HTML for this project. All styling must go into the appropriate CSS file (e.g. `ceti.css` for CETI deck overrides).

**Why:** Explicit instruction — user rejected HTML writes that contained inline styles and said "никаких стилей в html, все в ceti.css" (no styles in HTML, all in ceti.css).

**How to apply:** When writing or editing slide HTML files, use only CSS class names. Add any new styles needed (typography, layout, spacing) as CSS classes in the companion stylesheet, not inline.
