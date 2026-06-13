"""Login, logout, and first-run setup routes."""
from urllib.parse import unquote
import bcrypt
from fastapi import APIRouter, Depends, Form, Query, Request
from fastapi.responses import HTMLResponse, RedirectResponse
from sqlalchemy.orm import Session
from sqlalchemy.exc import IntegrityError

from app.database import get_db
from app.models import User
from app.templating import templates

router = APIRouter()

# Upper bound prevents bcrypt CPU exhaustion (bcrypt truncates at 72 bytes anyway)
_MAX_PASSWORD_LENGTH = 128


def _hash_password(password: str) -> str:
    return bcrypt.hashpw(password.encode(), bcrypt.gensalt()).decode()


def _verify_password(password: str, password_hash: str) -> bool:
    return bcrypt.checkpw(password.encode(), password_hash.encode())


# ── Login ────────────────────────────────────────────────────────────


@router.get("/login", response_class=HTMLResponse)
def login_page(request: Request, next: str = Query("")):
    # Already logged in → go home
    if request.session.get("user_id"):
        return RedirectResponse("/", status_code=303)
    return templates.TemplateResponse(request, "login.html", {"error": None, "next": next})


@router.post("/login", response_class=HTMLResponse)
def login_submit(
    request: Request,
    username: str = Form(...),
    password: str = Form(...),
    remember: str = Form(""),
    next: str = Form(""),
    db: Session = Depends(get_db),
):
    user = db.query(User).filter(User.username == username).first()
    if not user:
        # Constant-time: run bcrypt even on unknown usernames to prevent timing enumeration
        bcrypt.checkpw(b"dummy", bcrypt.hashpw(b"dummy", bcrypt.gensalt()))
        return templates.TemplateResponse(
            request, "login.html",
            {"error": "Invalid username or password", "next": next},
            status_code=401,
        )
    if not _verify_password(password, user.password_hash):
        return templates.TemplateResponse(
            request, "login.html",
            {"error": "Invalid username or password", "next": next},
            status_code=401,
        )

    # Rotate session to prevent fixation
    request.session.clear()
    request.session["user_id"] = user.id
    request.session["username"] = user.username
    request.session["is_admin"] = user.is_admin

    # "Remember me" sets a longer max_age via cookie config
    if remember:
        request.session["remember"] = True

    # Redirect to the original page or home — block protocol-relative URLs (//evil.com)
    redirect_to = unquote(next) if next and next.startswith("/") and not next.startswith("//") else "/"
    return RedirectResponse(redirect_to, status_code=303)


@router.post("/logout")
def logout(request: Request):
    request.session.clear()
    return RedirectResponse("/login", status_code=303)


# ── First-run setup ─────────────────────────────────────────────────


@router.get("/setup", response_class=HTMLResponse)
def setup_page(request: Request, db: Session = Depends(get_db)):
    # If users already exist, redirect away
    if db.query(User.id).first() is not None:
        return RedirectResponse("/", status_code=303)
    return templates.TemplateResponse(request, "setup.html", {"error": None})


@router.post("/setup", response_class=HTMLResponse)
def setup_submit(
    request: Request,
    username: str = Form(...),
    password: str = Form(...),
    password_confirm: str = Form(...),
    db: Session = Depends(get_db),
):
    # Guard: if users already exist, reject
    if db.query(User.id).first() is not None:
        return RedirectResponse("/", status_code=303)

    errors = []
    username = username.strip()
    if len(username) < 3:
        errors.append("Username must be at least 3 characters.")
    if len(password) < 8:
        errors.append("Password must be at least 8 characters.")
    if len(password) > _MAX_PASSWORD_LENGTH:
        errors.append(f"Password must be at most {_MAX_PASSWORD_LENGTH} characters.")
    if password != password_confirm:
        errors.append("Passwords do not match.")

    if errors:
        return templates.TemplateResponse(
            request, "setup.html",
            {"error": " ".join(errors)},
            status_code=400,
        )

    user = User(
        username=username,
        password_hash=_hash_password(password),
        is_admin=True,
    )
    db.add(user)
    try:
        db.commit()
    except IntegrityError:
        # Race condition: another request created the first user simultaneously
        db.rollback()
        return RedirectResponse("/", status_code=303)

    # Auto-login (clean session first)
    request.session.clear()
    request.session["user_id"] = user.id
    request.session["username"] = user.username
    request.session["is_admin"] = user.is_admin

    return RedirectResponse("/", status_code=303)
