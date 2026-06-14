import logging
from pathlib import Path

import re

import mistune
from fastapi import APIRouter, Request
from fastapi.responses import HTMLResponse

from app.templating import templates

logger = logging.getLogger(__name__)
router = APIRouter()

DOCS_DIR = Path(__file__).resolve().parent.parent.parent / "docs"

# Ordered list of docs with metadata for the index page
DOCS_CATALOG = [
    {
        "slug": "middleware-setup",
        "title": "Middleware Setup",
        "description": "Install, configure, and run the Mealie Barcode Middleware.",
        "icon": "ti-server",
        "group": "Getting Started",
    },
    {
        "slug": "barcode-workflow",
        "title": "How Barcode Scanning Works",
        "description": "End-to-end flow from scan to shopping list.",
        "icon": "ti-arrows-right-left",
        "group": "Getting Started",
    },
    {
        "slug": "web-dashboard",
        "title": "Web Dashboard",
        "description": "Navigate the UI: barcodes, items, settings, and activity.",
        "icon": "ti-browser",
        "group": "Getting Started",
    },
    {
        "slug": "hardware-build",
        "title": "Hardware Build Guide",
        "description": "Assemble the ESP32 + GM67 barcode scanner.",
        "icon": "ti-cpu",
        "group": "Hardware Scanner",
    },
    {
        "slug": "esphome-firmware",
        "title": "ESPHome Firmware",
        "description": "Flash and configure the ESP32 firmware via ESPHome.",
        "icon": "ti-bolt",
        "group": "Hardware Scanner",
    },
    {
        "slug": "scanner-configuration",
        "title": "Scanner Configuration (GM67)",
        "description": "Program the GM67 module with setup barcodes.",
        "icon": "ti-qrcode",
        "group": "Hardware Scanner",
    },
    {
        "slug": "mobile-apps",
        "title": "Mobile App Scanning",
        "description": "Use BinaryEye (Android) or iOS Shortcuts as scanners.",
        "icon": "ti-device-mobile",
        "group": "Phone Scanning",
    },
    {
        "slug": "troubleshooting",
        "title": "Troubleshooting",
        "description": "Common issues, diagnostics, and fixes.",
        "icon": "ti-lifebuoy",
        "group": "Reference",
    },
]

# Build grouped structure for the index template
_DOCS_GROUP_ORDER = ["Getting Started", "Hardware Scanner", "Phone Scanning", "Reference"]

def _build_docs_groups():
    groups = {g: [] for g in _DOCS_GROUP_ORDER}
    for doc in DOCS_CATALOG:
        groups[doc["group"]].append(doc)
    return [(g, groups[g]) for g in _DOCS_GROUP_ORDER if groups[g]]

_slug_to_meta = {d["slug"]: d for d in DOCS_CATALOG}

_md = mistune.create_markdown(escape=False, plugins=["table"])

_HEADING_RE = re.compile(r"<h(\d)(.*?)>(.*?)</h\1>", re.DOTALL)
_TAG_RE = re.compile(r"<[^>]+>")


def _slugify(text: str) -> str:
    """Turn heading text into a URL-friendly anchor ID."""
    text = _TAG_RE.sub("", text)  # strip inline HTML/tags
    text = text.lower().strip()
    text = re.sub(r"[^\w\s-]", "", text)  # remove punctuation
    text = re.sub(r"[\s_]+", "-", text)   # spaces/underscores → hyphens
    return text.strip("-")


def _render_with_toc(raw: str) -> tuple[str, list[dict]]:
    """Render markdown and inject id attrs into h2 headings.

    Returns (html, toc) where toc is a list of {id, text} for h2s only.
    """
    html = _md(raw)
    toc: list[dict] = []
    seen: dict[str, int] = {}

    def _replace_heading(m):
        level = int(m.group(1))
        attrs = m.group(2)
        inner = m.group(3)

        if level != 2:
            return m.group(0)  # leave non-h2 headings unchanged

        slug = _slugify(inner)
        # Handle duplicate slugs
        if slug in seen:
            seen[slug] += 1
            slug = f"{slug}-{seen[slug]}"
        else:
            seen[slug] = 0

        toc.append({"id": slug, "text": _TAG_RE.sub("", inner).strip()})
        return f'<h2 id="{slug}"{attrs}>{inner}</h2>'

    html = _HEADING_RE.sub(_replace_heading, html)
    return html, toc


@router.get("/docs", response_class=HTMLResponse)
def docs_index(request: Request):
    return templates.TemplateResponse(request, "docs.html", {
        "doc_groups": _build_docs_groups(),
    })


@router.get("/docs/{slug}", response_class=HTMLResponse)
def docs_detail(request: Request, slug: str):
    meta = _slug_to_meta.get(slug)
    if not meta:
        return templates.TemplateResponse(request, "404.html", status_code=404)

    md_path = DOCS_DIR / f"{slug}.md"
    if not md_path.is_file():
        return templates.TemplateResponse(request, "404.html", status_code=404)

    raw = md_path.read_text(encoding="utf-8")

    # Strip the first H1 heading — we render the title separately
    lines = raw.split("\n", 1)
    if lines[0].startswith("# "):
        raw = lines[1] if len(lines) > 1 else ""

    html_content, toc = _render_with_toc(raw)

    return templates.TemplateResponse(request, "doc_detail.html", {
        "doc_title": meta["title"],
        "doc_icon": meta["icon"],
        "doc_slug": slug,
        "doc_html": html_content,
        "toc": toc,
    })
