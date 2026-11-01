# Arabic interface verification — 2026-11-01

The interface uses the existing cream, ink, and terracotta palette, with bundled Amiri for the wordmark, headings, and manuscript editors, and Plex Arabic for controls.

Desktop shows the original and vocalized text side by side. Mobile stacks the result after a successful request. Word documents have a dedicated upload view with an Arabic file-picker label and drag and drop. Existing backend endpoints and document processing are unchanged.

Verification completed locally before publication:

- Hallmark static and browser render sweep: 0 Floor failures, 0 Reflex findings, 0 warnings. Both text and Word views checked across widths 320, 375, 414, 768, 1024, 1280, 1440, and 1920 pixels.
- Retained-field check: all 3 original fields, all 4 recorded links, and the original heading preserved. Download actions remain connected to the original endpoints.
- Fresh-context visual review: ship, no actionable findings. The old example control had a stronger border; the quieter replacement keeps its label beside the input.
- Browser workflow: real text vocalization, editable output, text download, real Word upload/download, mobile layout, API error recovery, URL mode restoration, no JavaScript page errors.
- Backend suite: 6 tests passed.

The review screenshots and before/after comparison are checkout-local Hallmark artifacts, excluded from Git.

## Dark mode

The masthead has an Arabic-labelled dark-mode toggle with a 44-pixel touch target and `aria-pressed`. The initial theme follows the system preference; an explicit choice persists in local storage and is applied by a same-origin script before the styles load. Storage restrictions do not prevent switching themes. Changes to the system theme are followed until a manual choice is made; stored choices synchronize between tabs.

Local Chromium checks passed for light and dark themes, text and Word views, at widths 320, 375, 768, and 1280 pixels, with no page overflow or header overlap. Keyboard activation, system-theme changes, reload persistence, unavailable storage, and real text generation followed by a theme switch passed. Existing backend suite: 14 tests passed. Both JavaScript files passed syntax checks.
