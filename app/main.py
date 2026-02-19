from __future__ import annotations

from datetime import datetime
from io import StringIO
import csv

from fastapi import FastAPI, Request, Form, Depends
from fastapi.responses import HTMLResponse, RedirectResponse, Response, PlainTextResponse
from fastapi.staticfiles import StaticFiles
from fastapi.templating import Jinja2Templates

from sqlmodel import select

from .config import APP_NAME, ALLOWED_EMAIL_DOMAINS, ADMIN_BOOTSTRAP_EMAIL, ADMIN_BOOTSTRAP_PASSWORD
from .db import init_db, get_session
from .models import User, OrderSession, OrderItem
from .auth import hash_password, verify_password, set_login_cookie, clear_login_cookie, get_user_id_from_request
from .utils import now_utc, fmt_dt, euro

app = FastAPI(title=APP_NAME)
app.mount("/static", StaticFiles(directory="app/static"), name="static")
templates = Jinja2Templates(directory="app/templates")
templates.env.globals.update(app_name=APP_NAME, fmt_dt=fmt_dt, euro=euro)

def flash(request: Request) -> dict | None:
    # simple flash via query params ?ok=... or ?err=...
    if request.query_params.get("ok"):
        return {"kind": "ok", "message": request.query_params["ok"]}
    if request.query_params.get("err"):
        return {"kind": "error", "message": request.query_params["err"]}
    return None

def ensure_bootstrap_admin() -> None:
    with get_session() as session:
        existing = session.exec(select(User).where(User.email == ADMIN_BOOTSTRAP_EMAIL)).first()
        if not existing:
            admin = User(
                email=ADMIN_BOOTSTRAP_EMAIL,
                full_name="HIVE Manager (bootstrap)",
                password_hash=hash_password(ADMIN_BOOTSTRAP_PASSWORD),
                is_admin=True,
            )
            session.add(admin)
            session.commit()

@app.on_event("startup")
def on_startup() -> None:
    init_db()
    ensure_bootstrap_admin()

def get_current_user(request: Request) -> User | None:
    uid = get_user_id_from_request(request)
    if not uid:
        return None
    with get_session() as session:
        return session.get(User, uid)

def require_user(request: Request) -> User:
    user = get_current_user(request)
    if not user:
        raise_redirect = RedirectResponse(url="/login?err=Please+log+in", status_code=302)
        # FastAPI expects an exception, but easiest is to return response from routes; here we raise.
        # We'll handle by raising RuntimeError and catching? Simpler: in each route do manual checks.
        raise RuntimeError("AUTH_REQUIRED")
    return user

def email_domain_ok(email: str) -> bool:
    if not ALLOWED_EMAIL_DOMAINS:
        return True
    parts = email.lower().split("@")
    if len(parts) != 2:
        return False
    return parts[1] in ALLOWED_EMAIL_DOMAINS

def is_session_editable(s: OrderSession) -> bool:
    if s.status != "open":
        return False
    return now_utc() <= s.deadline_at

@app.get("/", response_class=HTMLResponse)
def dashboard(request: Request):
    user = get_current_user(request)
    if not user:
        return RedirectResponse("/login", status_code=302)

    with get_session() as session:
        if user.is_admin:
            sessions = session.exec(select(OrderSession).order_by(OrderSession.created_at.desc())).all()
        else:
            sessions = session.exec(select(OrderSession).order_by(OrderSession.created_at.desc())).all()

    return templates.TemplateResponse("dashboard.html", {
        "request": request,
        "current_user": user,
        "sessions": sessions,
        "flash": flash(request),
    })

@app.get("/login", response_class=HTMLResponse)
def login_page(request: Request):
    return templates.TemplateResponse("login.html", {"request": request, "current_user": None, "flash": flash(request)})

@app.post("/login")
def login(request: Request, email: str = Form(...), password: str = Form(...)):
    email = email.strip().lower()
    with get_session() as session:
        user = session.exec(select(User).where(User.email == email)).first()
        if not user or not verify_password(password, user.password_hash):
            return RedirectResponse("/login?err=Invalid+credentials", status_code=302)

    response = RedirectResponse("/", status_code=302)
    set_login_cookie(response, user.id)
    return response

@app.get("/logout")
def logout():
    response = RedirectResponse("/login?ok=Logged+out", status_code=302)
    clear_login_cookie(response)
    return response

# ---- Change password ----

@app.get("/change-password", response_class=HTMLResponse)
def change_password_page(request: Request):
    user = get_current_user(request)
    if not user:
        return RedirectResponse("/login?err=Please+log+in", status_code=302)
    return templates.TemplateResponse("change_password.html", {
        "request": request,
        "current_user": user,
        "flash": flash(request),
    })

@app.post("/change-password")
def change_password(
    request: Request,
    current_password: str = Form(...),
    new_password: str = Form(...),
    confirm_password: str = Form(...),
):
    user = get_current_user(request)
    if not user:
        return RedirectResponse("/login?err=Please+log+in", status_code=302)

    if not verify_password(current_password, user.password_hash):
        return RedirectResponse("/change-password?err=Current+password+is+incorrect", status_code=302)

    if len(new_password) < 8:
        return RedirectResponse("/change-password?err=New+password+must+be+at+least+8+characters", status_code=302)

    if new_password != confirm_password:
        return RedirectResponse("/change-password?err=New+passwords+do+not+match", status_code=302)

    with get_session() as session:
        db_user = session.get(User, user.id)
        db_user.password_hash = hash_password(new_password)
        session.add(db_user)
        session.commit()

    return RedirectResponse("/?ok=Password+changed+successfully", status_code=302)

# ---- Admin user management ----

@app.get("/admin/users", response_class=HTMLResponse)
def admin_users_page(request: Request):
    user = get_current_user(request)
    if not user or not user.is_admin:
        return RedirectResponse("/?err=Admin+access+required", status_code=302)

    with get_session() as session:
        users = session.exec(select(User).order_by(User.full_name)).all()

    return templates.TemplateResponse("admin_users.html", {
        "request": request,
        "current_user": user,
        "users": users,
        "flash": flash(request),
    })

@app.post("/admin/users/new")
def admin_create_user(
    request: Request,
    full_name: str = Form(...),
    email: str = Form(...),
    password: str = Form(...),
    is_admin: bool = Form(False),
):
    user = get_current_user(request)
    if not user or not user.is_admin:
        return RedirectResponse("/?err=Admin+access+required", status_code=302)

    email = email.strip().lower()
    full_name = full_name.strip()
    if len(password) < 8:
        return RedirectResponse("/admin/users?err=Password+must+be+at+least+8+characters", status_code=302)
    if not email_domain_ok(email):
        return RedirectResponse("/admin/users?err=Email+domain+not+allowed", status_code=302)

    with get_session() as session:
        existing = session.exec(select(User).where(User.email == email)).first()
        if existing:
            return RedirectResponse("/admin/users?err=Account+already+exists", status_code=302)
        new_user = User(
            email=email,
            full_name=full_name,
            password_hash=hash_password(password),
            is_admin=is_admin,
        )
        session.add(new_user)
        session.commit()

    return RedirectResponse("/admin/users?ok=User+created", status_code=302)

@app.post("/admin/users/{target_user_id}/delete")
def admin_delete_user(request: Request, target_user_id: int):
    user = get_current_user(request)
    if not user or not user.is_admin:
        return RedirectResponse("/?err=Admin+access+required", status_code=302)
    if target_user_id == user.id:
        return RedirectResponse("/admin/users?err=Cannot+delete+yourself", status_code=302)

    with get_session() as session:
        target = session.get(User, target_user_id)
        if not target:
            return RedirectResponse("/admin/users?err=User+not+found", status_code=302)
        session.delete(target)
        session.commit()

    return RedirectResponse("/admin/users?ok=User+deleted", status_code=302)

@app.post("/admin/users/{target_user_id}/toggle-admin")
def admin_toggle_admin(request: Request, target_user_id: int):
    user = get_current_user(request)
    if not user or not user.is_admin:
        return RedirectResponse("/?err=Admin+access+required", status_code=302)
    if target_user_id == user.id:
        return RedirectResponse("/admin/users?err=Cannot+change+your+own+admin+status", status_code=302)

    with get_session() as session:
        target = session.get(User, target_user_id)
        if not target:
            return RedirectResponse("/admin/users?err=User+not+found", status_code=302)
        target.is_admin = not target.is_admin
        session.add(target)
        session.commit()

    return RedirectResponse("/admin/users?ok=Admin+status+toggled", status_code=302)

@app.get("/sessions/new", response_class=HTMLResponse)
def session_new_page(request: Request):
    user = get_current_user(request)
    if not user:
        return RedirectResponse("/login?err=Please+log+in", status_code=302)
    if not user.is_admin:
        return RedirectResponse("/?err=Only+admins+can+create+sessions", status_code=302)
    return templates.TemplateResponse("session_new.html", {"request": request, "current_user": user, "flash": flash(request)})

@app.post("/sessions/new")
def session_new(
    request: Request,
    title: str = Form(...),
    restaurant: str = Form(...),
    restaurant_url: str = Form(""),
    deadline_at: str = Form(...),
    notes: str = Form(""),
):
    user = get_current_user(request)
    if not user:
        return RedirectResponse("/login?err=Please+log+in", status_code=302)
    if not user.is_admin:
        return RedirectResponse("/?err=Only+admins+can+create+sessions", status_code=302)

    try:
        # datetime-local arrives as "YYYY-MM-DDTHH:MM"
        dt = datetime.fromisoformat(deadline_at)
    except Exception:
        return RedirectResponse("/sessions/new?err=Invalid+deadline", status_code=302)

    s = OrderSession(
        title=title.strip(),
        restaurant=restaurant.strip(),
        restaurant_url=(restaurant_url.strip() or None),
        deadline_at=dt,
        notes=(notes.strip() or None),
        created_by_user_id=user.id,
        status="open",
    )
    with get_session() as session:
        session.add(s)
        session.commit()
        session.refresh(s)

    return RedirectResponse(f"/sessions/{s.id}?ok=Session+created", status_code=302)

@app.get("/sessions/{session_id}", response_class=HTMLResponse)
def session_detail(request: Request, session_id: int):
    user = get_current_user(request)
    if not user:
        return RedirectResponse("/login?err=Please+log+in", status_code=302)

    with get_session() as session:
        s = session.get(OrderSession, session_id)
        if not s:
            return RedirectResponse("/?err=Session+not+found", status_code=302)

    editable = is_session_editable(s)
    can_close = user.is_admin or (user.id == s.created_by_user_id)
    return templates.TemplateResponse("session_detail.html", {
        "request": request,
        "current_user": user,
        "session": s,
        "editable": editable,
        "can_close": can_close,
        "flash": flash(request),
    })

@app.post("/sessions/{session_id}/close")
def session_close(request: Request, session_id: int):
    user = get_current_user(request)
    if not user:
        return RedirectResponse("/login?err=Please+log+in", status_code=302)

    with get_session() as session:
        s = session.get(OrderSession, session_id)
        if not s:
            return RedirectResponse("/?err=Session+not+found", status_code=302)
        if not (user.is_admin or user.id == s.created_by_user_id):
            return RedirectResponse(f"/sessions/{session_id}?err=Not+allowed", status_code=302)
        s.status = "closed"
        s.closed_at = now_utc()
        session.add(s)
        session.commit()

    return RedirectResponse(f"/sessions/{session_id}?ok=Session+closed", status_code=302)

# ---- HTMX partials ----

@app.get("/sessions/{session_id}/items/blank", response_class=HTMLResponse)
def item_blank(request: Request, session_id: int):
    user = get_current_user(request)
    if not user:
        return HTMLResponse("", status_code=401)
    return HTMLResponse("")

@app.get("/sessions/{session_id}/items/new", response_class=HTMLResponse)
def item_new_form(request: Request, session_id: int):
    user = get_current_user(request)
    if not user:
        return HTMLResponse("", status_code=401)

    with get_session() as session:
        s = session.get(OrderSession, session_id)
        if not s:
            return HTMLResponse("Session not found", status_code=404)
        if not is_session_editable(s):
            return HTMLResponse("Locked", status_code=400)

    return templates.TemplateResponse("partials_item_form.html", {
        "request": request,
        "current_user": user,
        "session_id": session_id,
        "item": None,
        "action": f"/sessions/{session_id}/items/new",
        "error": None,
        "flash": None,
    })

@app.post("/sessions/{session_id}/items/new", response_class=HTMLResponse)
def item_create(
    request: Request,
    session_id: int,
    item_name: str = Form(...),
    quantity: int = Form(1),
    price_eur: str = Form(""),
    notes: str = Form(""),
):
    user = get_current_user(request)
    if not user:
        return HTMLResponse("", status_code=401)

    with get_session() as session:
        s = session.get(OrderSession, session_id)
        if not s:
            return HTMLResponse("Session not found", status_code=404)
        if not is_session_editable(s):
            return HTMLResponse("Locked", status_code=400)

        price_val = None
        if price_eur.strip():
            try:
                price_val = float(price_eur)
            except Exception:
                return templates.TemplateResponse("partials_item_form.html", {
                    "request": request, "current_user": user, "session_id": session_id,
                    "item": None, "action": f"/sessions/{session_id}/items/new",
                    "error": "Price must be a number (e.g., 9.50).",
                    "flash": None
                })

        item = OrderItem(
            session_id=session_id,
            user_id=user.id,
            item_name=item_name.strip(),
            quantity=max(1, int(quantity)),
            price_eur=price_val,
            notes=(notes.strip() or None),
        )
        session.add(item)
        session.commit()

    # Clear form + trigger table refresh
    return HTMLResponse('<div class="muted">Added ✓</div><script>htmx.trigger("#items-table","refresh");htmx.trigger("#summary","refresh");htmx.trigger("#order-text","refresh");</script>')

@app.get("/sessions/{session_id}/items/{item_id}/edit", response_class=HTMLResponse)
def item_edit_form(request: Request, session_id: int, item_id: int):
    user = get_current_user(request)
    if not user:
        return HTMLResponse("", status_code=401)

    with get_session() as session:
        s = session.get(OrderSession, session_id)
        item = session.get(OrderItem, item_id)
        if not s or not item or item.session_id != session_id:
            return HTMLResponse("Not found", status_code=404)
        if not is_session_editable(s):
            return HTMLResponse("Locked", status_code=400)
        if not (user.is_admin or item.user_id == user.id):
            return HTMLResponse("Not allowed", status_code=403)

    return templates.TemplateResponse("partials_item_form.html", {
        "request": request,
        "current_user": user,
        "session_id": session_id,
        "item": item,
        "action": f"/sessions/{session_id}/items/{item_id}/edit",
        "error": None,
        "flash": None,
    })

@app.post("/sessions/{session_id}/items/{item_id}/edit", response_class=HTMLResponse)
def item_edit(
    request: Request,
    session_id: int,
    item_id: int,
    item_name: str = Form(...),
    quantity: int = Form(1),
    price_eur: str = Form(""),
    notes: str = Form(""),
):
    user = get_current_user(request)
    if not user:
        return HTMLResponse("", status_code=401)

    with get_session() as session:
        s = session.get(OrderSession, session_id)
        item = session.get(OrderItem, item_id)
        if not s or not item or item.session_id != session_id:
            return HTMLResponse("Not found", status_code=404)
        if not is_session_editable(s):
            return HTMLResponse("Locked", status_code=400)
        if not (user.is_admin or item.user_id == user.id):
            return HTMLResponse("Not allowed", status_code=403)

        price_val = None
        if price_eur.strip():
            try:
                price_val = float(price_eur)
            except Exception:
                return templates.TemplateResponse("partials_item_form.html", {
                    "request": request, "current_user": user, "session_id": session_id,
                    "item": item, "action": f"/sessions/{session_id}/items/{item_id}/edit",
                    "error": "Price must be a number (e.g., 9.50).",
                    "flash": None
                })

        item.item_name = item_name.strip()
        item.quantity = max(1, int(quantity))
        item.price_eur = price_val
        item.notes = (notes.strip() or None)
        item.updated_at = now_utc()
        session.add(item)
        session.commit()

    return HTMLResponse('<div class="muted">Saved ✓</div><script>htmx.trigger("#items-table","refresh");htmx.trigger("#summary","refresh");htmx.trigger("#order-text","refresh");</script>')

@app.post("/sessions/{session_id}/items/{item_id}/delete", response_class=HTMLResponse)
def item_delete(request: Request, session_id: int, item_id: int):
    user = get_current_user(request)
    if not user:
        return HTMLResponse("", status_code=401)

    with get_session() as session:
        s = session.get(OrderSession, session_id)
        item = session.get(OrderItem, item_id)
        if not s or not item or item.session_id != session_id:
            return HTMLResponse("Not found", status_code=404)
        if not is_session_editable(s):
            return HTMLResponse("Locked", status_code=400)
        if not (user.is_admin or item.user_id == user.id):
            return HTMLResponse("Not allowed", status_code=403)

        session.delete(item)
        session.commit()

    return HTMLResponse('<div class="muted">Deleted ✓</div><script>htmx.trigger("#items-table","refresh");htmx.trigger("#summary","refresh");htmx.trigger("#order-text","refresh");</script>')

@app.get("/sessions/{session_id}/items/table", response_class=HTMLResponse)
def items_table(request: Request, session_id: int):
    user = get_current_user(request)
    if not user:
        return HTMLResponse("", status_code=401)

    with get_session() as session:
        s = session.get(OrderSession, session_id)
        if not s:
            return HTMLResponse("Not found", status_code=404)
        items = session.exec(select(OrderItem).where(OrderItem.session_id == session_id).order_by(OrderItem.created_at.asc())).all()
        # fetch users in one go
        user_ids = sorted({i.user_id for i in items})
        users = {}
        if user_ids:
            rows_u = session.exec(select(User).where(User.id.in_(user_ids))).all()
            users = {u.id: u for u in rows_u}

    editable = is_session_editable(s)
    rows = []
    for it in items:
        u = users.get(it.user_id)
        can_edit = editable and (user.is_admin or it.user_id == user.id)
        rows.append({"item": it, "user": u, "can_edit": can_edit})

    return templates.TemplateResponse("partials_items_table.html", {
        "request": request,
        "current_user": user,
        "session_id": session_id,
        "rows": rows,
        "flash": None,
    })

@app.get("/sessions/{session_id}/summary", response_class=HTMLResponse)
def summary_partial(request: Request, session_id: int):
    user = get_current_user(request)
    if not user:
        return HTMLResponse("", status_code=401)

    with get_session() as session:
        items = session.exec(select(OrderItem).where(OrderItem.session_id == session_id)).all()
        user_ids = sorted({i.user_id for i in items})
        users = {}
        if user_ids:
            rows_u = session.exec(select(User).where(User.id.in_(user_ids))).all()
            users = {u.id: u for u in rows_u}

    totals_map = {}
    for it in items:
        u = users.get(it.user_id)
        if not u:
            continue
        key = u.id
        if key not in totals_map:
            totals_map[key] = {"full_name": u.full_name, "email": u.email, "count": 0, "subtotal": 0.0}
        totals_map[key]["count"] += int(it.quantity)
        if it.price_eur is not None:
            totals_map[key]["subtotal"] += float(it.price_eur) * int(it.quantity)

    totals = list(totals_map.values())
    totals.sort(key=lambda x: x["full_name"].lower())

    grand_total = sum(t["subtotal"] for t in totals)
    grand_count = sum(t["count"] for t in totals)

    return templates.TemplateResponse("partials_summary.html", {
        "request": request,
        "current_user": user,
        "totals": totals,
        "grand_total": grand_total,
        "grand_count": grand_count,
        "flash": None,
    })

@app.get("/sessions/{session_id}/order_text", response_class=HTMLResponse)
def order_text_partial(request: Request, session_id: int):
    user = get_current_user(request)
    if not user:
        return HTMLResponse("", status_code=401)

    with get_session() as session:
        s = session.get(OrderSession, session_id)
        if not s:
            return HTMLResponse("Not found", status_code=404)
        items = session.exec(select(OrderItem).where(OrderItem.session_id == session_id).order_by(OrderItem.created_at.asc())).all()
        user_ids = sorted({i.user_id for i in items})
        users = {}
        if user_ids:
            rows_u = session.exec(select(User).where(User.id.in_(user_ids))).all()
            users = {u.id: u for u in rows_u}

    # Build a concise order text grouped by person
    by_person = {}
    for it in items:
        u = users.get(it.user_id)
        name = u.full_name if u else f"User {it.user_id}"
        by_person.setdefault(name, []).append(it)

    lines = []
    lines.append(f"{s.title} — {s.restaurant}")
    lines.append(f"Deadline: {fmt_dt(s.deadline_at)} | Status: {s.status}")
    lines.append("")
    for person in sorted(by_person.keys(), key=lambda x: x.lower()):
        lines.append(f"{person}:")
        for it in by_person[person]:
            note = f" ({it.notes})" if it.notes else ""
            qty = f"{it.quantity}x " if it.quantity != 1 else ""
            lines.append(f"  - {qty}{it.item_name}{note}")
        lines.append("")
    text = "\n".join(lines).strip()

    return templates.TemplateResponse("partials_order_text.html", {
        "request": request,
        "current_user": user,
        "text": text,
        "flash": None,
    })

@app.get("/sessions/{session_id}/export.csv")
def export_csv(request: Request, session_id: int):
    user = get_current_user(request)
    if not user:
        return RedirectResponse("/login?err=Please+log+in", status_code=302)

    with get_session() as session:
        s = session.get(OrderSession, session_id)
        if not s:
            return RedirectResponse("/?err=Session+not+found", status_code=302)
        items = session.exec(select(OrderItem).where(OrderItem.session_id == session_id).order_by(OrderItem.created_at.asc())).all()
        user_ids = sorted({i.user_id for i in items})
        users = {}
        if user_ids:
            rows_u = session.exec(select(User).where(User.id.in_(user_ids))).all()
            users = {u.id: u for u in rows_u}

    buf = StringIO()
    w = csv.writer(buf)
    w.writerow(["session_id", "session_title", "restaurant", "deadline_at", "status"])
    w.writerow([s.id, s.title, s.restaurant, fmt_dt(s.deadline_at), s.status])
    w.writerow([])
    w.writerow(["person_name", "person_email", "item_name", "quantity", "price_eur", "notes"])
    for it in items:
        u = users.get(it.user_id)
        w.writerow([
            (u.full_name if u else ""),
            (u.email if u else ""),
            it.item_name,
            it.quantity,
            (f"{it.price_eur:.2f}" if it.price_eur is not None else ""),
            (it.notes or ""),
        ])

    data = buf.getvalue().encode("utf-8")
    return Response(content=data, media_type="text/csv", headers={
        "Content-Disposition": f'attachment; filename="order_session_{session_id}.csv"'
    })
