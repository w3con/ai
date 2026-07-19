---
name: browser-verify-raf-background-tab
description: When verifying a canvas/animation web app via claude-in-chrome, rAF-driven renders don't fire until the tab is foregrounded
metadata:
  type: reference
---

When checking a web app through the claude-in-chrome tools, any rendering that is
scheduled via `requestAnimationFrame` (the standard way a live-preview canvas coalesces
redraws) will **not run while the automation tab sits in the background**. The browser
throttles/pauses rAF for non-visible tabs, so the DOM state updates (an image loads, a
control's value changes) but the canvas never repaints — it stays at its default size and
looks broken, even though nothing is actually wrong with the app.

**How to spot it:** the load handler clearly ran (e.g. the drop-hint got hidden, params
updated), yet `canvas.width/height` are still the default 300×150 and the picture is blank.

**How to fix it:** take a `computer` screenshot of the tab — that action brings the tab to
the foreground, rAF resumes, and the queued render executes. After the screenshot the
canvas is correctly sized and drawn. Alternatively drive a synchronous render path, but the
screenshot is the cheapest trigger.

Also useful in the same setting: programmatic `<a download>` clicks from
`javascript_tool` often do **not** land a file in ~/Downloads (download suppressed without a
real user gesture). To verify an export, hook `URL.createObjectURL` to capture the Blob
in-page and inspect it there (read PNG dimensions via `createImageBitmap`, parse JSON via
`blob.text()`), rather than looking for the file on disk. Give `canvas.toBlob` a generous
wait (~2s at full export size) before restoring the hook.

Learned building the halftone-lab app in the paper-rastr project, 2026-07-17.
