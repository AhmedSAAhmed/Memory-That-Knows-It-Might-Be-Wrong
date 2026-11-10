"""Gradio theme matching the Navy tokens in navy.css."""
from __future__ import annotations

from pathlib import Path

import gradio as gr

CSS_PATH = Path(__file__).with_name("navy.css")

HEAD = (
    '<link rel="preconnect" href="https://api.fontshare.com">'
    '<link rel="stylesheet" '
    'href="https://api.fontshare.com/v2/css?f[]=switzer@400,500,600&display=swap">'
)

# Navy is a light theme: keep Gradio from switching to dark mode on dark-OS visitors.
FORCE_LIGHT_JS = """
() => {
  const light = () => document.body.classList.remove('dark');
  light();
  new MutationObserver(light).observe(document.body, {attributes: true, attributeFilter: ['class']});
}
"""

FG = "oklch(20% .04 275)"
MUTED_FG = "oklch(48% .03 275)"
BORDER = "oklch(91% .016 275)"
BG = "oklch(98.8% .006 275)"
MUTED = "oklch(97.2% .01 275)"
PRIMARY = "oklch(52% .22 268)"
PRIMARY_HI = "oklch(60% .2 268)"
LILAC = "oklch(91% .045 280)"


def navy_theme() -> gr.themes.Base:
    return gr.themes.Base(
        font=["Switzer", "sans-serif"],
        font_mono=["ui-monospace", "SFMono-Regular", "Menlo", "monospace"],
        radius_size=gr.themes.sizes.radius_sm,
        spacing_size=gr.themes.sizes.spacing_md,
    ).set(
        body_background_fill=BG,
        body_text_color=FG,
        body_text_color_subdued=MUTED_FG,
        background_fill_primary="#ffffff",
        background_fill_secondary=MUTED,
        border_color_primary=BORDER,
        block_background_fill="#ffffff",
        block_border_color=BORDER,
        block_border_width="1px",
        block_shadow="none",
        block_label_text_color=MUTED_FG,
        block_title_text_color=FG,
        input_background_fill="#ffffff",
        input_border_color=BORDER,
        input_border_color_focus=PRIMARY,
        input_shadow="none",
        button_primary_background_fill=PRIMARY,
        button_primary_background_fill_hover=PRIMARY_HI,
        button_primary_text_color="#ffffff",
        button_primary_border_color=PRIMARY,
        button_secondary_background_fill=LILAC,
        button_secondary_text_color=FG,
        button_secondary_border_color=LILAC,
        color_accent=PRIMARY,
        color_accent_soft=LILAC,
        link_text_color=PRIMARY,
        checkbox_background_color_selected=PRIMARY,
        slider_color=PRIMARY,
    )
