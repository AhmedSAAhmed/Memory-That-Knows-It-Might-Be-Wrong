# Brand theme - Navy look for the UI

Factory reference. Tokens taken from the Navy Astro theme (navy-astro.pages.dev). Implemented in `app/ui/navy.css`; change tokens there, not here and there.

| Token | Value | Use |
|---|---|---|
| `--background` | `oklch(98.8% .006 275)` | page |
| `--foreground` | `oklch(20% .04 275)` | ink |
| `--muted` | `oklch(97.2% .01 275)` | panels |
| `--muted-foreground` | `oklch(48% .03 275)` | secondary text |
| `--faint-foreground` | `oklch(64% .025 275)` | `///` eyebrows, hints |
| `--border` | `oklch(91% .016 275)` | hairlines |
| `--mist` / `--lilac` / `--frost` | `oklch(95% .02 275)` / `oklch(91% .045 280)` / `oklch(94% .025 245)` | soft fills, chips |
| `--primary` | `oklch(52% .22 268)` | buttons, confidence bars |
| `--inverse` | `oklch(16% .05 270)` | dark band / header |

- Font: **Switzer** 400/500/600 from Fontshare; mono for ids and numbers.
- Section labels: small mono eyebrow `/// Label` in faint foreground.
- Headings: tight, medium weight, one word in *italic* for emphasis.
- Corners: small (`.375rem`), hairline borders, no heavy shadows.
