# Copilot Instructions — mealie-barcode-middleware

## Stack
- Backend: FastAPI, SQLAlchemy + SQLite, Jinja2 templates
- Frontend: Tabler UI v1.4.0 (vendored locally in `app/static/vendor/tabler/`), vanilla JS
- CSP: `script-src 'self'; style-src 'self'` — NO inline scripts or inline styles

## Tabler UI Rules (MUST follow)

### Buttons
- **`btn-sm` only inside `<table>` rows** — table action buttons use `btn-sm` with icon + text. Outside tables (card footers, page headers, modals), always use default size.
- Icon-only buttons **MUST** have `btn-icon` class: `btn btn-icon btn-primary`, `btn btn-icon btn-ghost-secondary`, etc.
- Buttons with both icon + text: do NOT add `btn-icon`.

### Terminology
- Use **"Linked"** (not "Mapped") in all user-visible text: badges, column headers, card titles, tabs.
- Internal code (variable names, DB columns, URL paths) can still use `mapped`/`mapping`.

### Page Titles
- **No icons** in `<h2 class="page-title">` — text only.

### Styling
- **NEVER** use inline `style="..."` attributes — use CSS classes in `app/static/css/app.css`.
- Always check stock Tabler CSS classes before writing custom CSS.

### Bootstrap / JS
- Tabler does **NOT** expose `bootstrap` as a global object.
- `new bootstrap.Modal()`, `new bootstrap.Toast()`, etc. will **fail**.
- Use `data-bs-*` attributes for all Bootstrap component interactions.
- To open a modal programmatically: create a hidden trigger `<button class="d-none" data-bs-toggle="modal" data-bs-target="#id">` and `.click()` it.
- To close a modal: use a button with `data-bs-dismiss="modal"`.

### Avatars
- Inside `.avatar`, do NOT add the standalone `icon` class to `<i>` tags.

## Architecture Notes
- SSE fan-out via `asyncio.Queue` in `/events`
- Scheduler: APScheduler `BackgroundScheduler`
- Docs are registered manually in `DOCS_CATALOG` in `app/routers/docs.py`

## Git
- User often amends and force-pushes — use `--force-with-lease`
