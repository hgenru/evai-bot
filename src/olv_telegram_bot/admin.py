from __future__ import annotations

from typing import Annotated, Optional

import uvicorn
from fastapi import Depends, FastAPI, HTTPException, Query, Request, status
from fastapi.responses import HTMLResponse, RedirectResponse

from .config import Settings
from .db import get_session, init_db
from .models import User
from .vtuber_client import VtuberClient


def _auth_dependency(
    request: Request,
    token: Optional[str] = Query(default=None),
) -> None:
    settings = Settings()
    required = settings.admin_token.strip()
    if not required:
        # No token configured — allow access (dev mode)
        return
    supplied = token or request.headers.get("X-Admin-Token")
    if supplied != required:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Unauthorized")


Auth = Annotated[None, Depends(_auth_dependency)]


def create_app() -> FastAPI:
    app = FastAPI(title="OLV Admin", version="0.1.0")

    @app.on_event("startup")
    def _startup() -> None:
        init_db()

    @app.get("/", response_class=RedirectResponse, include_in_schema=False)
    def root(_: Auth):  # type: ignore[no-untyped-def]
        return RedirectResponse(url="/admin/users")

    @app.get("/admin/health")
    def health() -> dict[str, str]:  # type: ignore[no-untyped-def]
        return {"status": "ok"}

    @app.get("/admin/users", response_class=HTMLResponse)
    def list_users(_: Auth) -> str:  # type: ignore[no-untyped-def]
        with get_session() as session:
            users = session.query(User).order_by(User.created_at.desc()).all()
        rows = []
        for u in users:
            name = " ".join(filter(None, [u.first_name, u.last_name])) or (u.username or "-")
            reg_badge = "✅" if u.is_registered else "❌"
            rows.append(
                f"<tr>"
                f"<td>{u.id}</td>"
                f"<td>{u.tg_id}</td>"
                f"<td>{name}</td>"
                f"<td>{reg_badge}</td>"
                f"<td>"
                f"<form method='post' action='/admin/users/{u.id}/toggle-registered'>"
                f"<button type='submit'>Toggle Registered</button>"
                f"</form>"
                f"</td>"
                f"</tr>"
            )
        body = "".join(rows) or "<tr><td colspan='5'>No users yet</td></tr>"
        return f"""
        <html>
          <head>
            <meta charset='utf-8' />
            <title>OLV Admin — Users</title>
            <style>
              body {{ font-family: system-ui, sans-serif; padding: 20px; }}
              table {{ border-collapse: collapse; width: 100%; }}
              th, td {{ border: 1px solid #ddd; padding: 8px; }}
              th {{ background: #f6f6f6; text-align: left; }}
              button {{ padding: 6px 10px; }}
              nav a {{ margin-right: 12px; }}
            </style>
          </head>
          <body>
            <nav>
              <a href='/admin/users'>Users</a>
              <a href='/admin/vtuber'>VTuber Control</a>
            </nav>
            <h1>Users</h1>
            <table>
              <thead>
                <tr>
                  <th>ID</th>
                  <th>tg_id</th>
                  <th>Name</th>
                  <th>Registered</th>
                  <th>Actions</th>
                </tr>
              </thead>
              <tbody>
                {body}
              </tbody>
            </table>
          </body>
        </html>
        """

    @app.post("/admin/users/{user_id}/toggle-registered")
    def toggle_registered(user_id: int, _: Auth):  # type: ignore[no-untyped-def]
        with get_session() as session:
            user = session.get(User, user_id)
            if not user:
                raise HTTPException(status_code=404, detail="User not found")
            user.is_registered = not user.is_registered
            session.add(user)
            session.commit()
        return RedirectResponse(url="/admin/users", status_code=303)

    @app.get("/admin/vtuber", response_class=HTMLResponse)
    def vtuber_form(_: Auth) -> str:  # type: ignore[no-untyped-def]
        settings = Settings()
        return f"""
        <html>
          <head>
            <meta charset='utf-8' />
            <title>OLV Admin — VTuber Control</title>
            <style>
              body {{ font-family: system-ui, sans-serif; padding: 20px; max-width: 960px; }}
              form {{ margin: 16px 0; padding: 12px; border: 1px solid #ddd; }}
              label {{ display: block; margin: 6px 0; }}
              input[type=text], textarea {{ width: 100%; padding: 6px; }}
              small {{ color: #666; }}
              nav a {{ margin-right: 12px; }}
            </style>
          </head>
          <body>
            <nav>
              <a href='/admin/users'>Users</a>
              <a href='/admin/vtuber'>VTuber Control</a>
            </nav>
            <h1>VTuber Direct Control</h1>
            <p><b>API root:</b> {settings.vtuber_api_root}</p>
            <h2>List Sessions</h2>
            <form method='post' action='/admin/vtuber/sessions'>
              <button type='submit'>Get /v1/sessions</button>
            </form>

            <h2>Speak</h2>
            <form method='post' action='/admin/vtuber/speak'>
              <label>text (required):<br/>
                <textarea name='text' rows='4' placeholder='Привет! [motion:walk2b] ...'></textarea>
              </label>
              <label>client_uid (optional):<br/>
                <input type='text' name='client_uid' placeholder='target session uid'/>
              </label>
              <label>display_name (optional):
                <input type='text' name='display_name' placeholder='DJ'/>
              </label>
              <label>avatar (optional):
                <input type='text' name='avatar' placeholder='https://example/avatar.png'/>
              </label>
              <label>actions.motions (comma or space separated):
                <input type='text' name='motions' placeholder='walk2b, jump2b'/>
                <small>Имена должны совпадать с motionMap модели.</small>
              </label>
              <label>actions.expressions (comma/space; strings or ints):
                <input type='text' name='expressions' placeholder='joy, 3'/>
              </label>
              <label>
                <input type='checkbox' name='extract_emotions'/> extract_emotions (server auto‑extract)
              </label>
              <button type='submit'>POST /v1/direct-control/speak</button>
            </form>
          </body>
        </html>
        """

    @app.post("/admin/vtuber/sessions", response_class=HTMLResponse)
    async def vtuber_list_sessions(_: Auth) -> str:  # type: ignore[no-untyped-def]
        settings = Settings()
        client = VtuberClient(settings.vtuber_api_root)
        try:
            sessions = await client.list_sessions()
            items = "".join(f"<li>{s}</li>" for s in sessions) or "<li>no sessions</li>"
            body = f"<ul>{items}</ul>"
        except Exception as e:  # noqa: BLE001
            body = f"<pre style='color:#b00;'>Error: {e!s}</pre>"
        return f"""
        <html>
          <head>
            <meta charset='utf-8' />
            <title>Sessions — VTuber</title>
          </head>
          <body>
            <p><a href='/admin/vtuber'>&larr; Back</a></p>
            <h1>Sessions</h1>
            {body}
          </body>
        </html>
        """

    @app.post("/admin/vtuber/speak", response_class=HTMLResponse)
    async def vtuber_speak(request: Request, _: Auth) -> str:  # type: ignore[no-untyped-def]
        form = await request.form()
        text = str(form.get("text") or "").strip()
        client_uid = str(form.get("client_uid") or "").strip() or None
        display_name = str(form.get("display_name") or "").strip() or None
        avatar = str(form.get("avatar") or "").strip() or None
        motions_raw = str(form.get("motions") or "").strip()
        expr_raw = str(form.get("expressions") or "").strip()
        extract_emotions = form.get("extract_emotions") is not None

        def _split_list(s: str) -> list[str]:
            if not s:
                return []
            parts = [p for p in s.replace(",", " ").split() if p]
            return parts

        motions = _split_list(motions_raw)

        expressions: list[object] = []
        for p in _split_list(expr_raw):
            try:
                expressions.append(int(p))
            except ValueError:
                expressions.append(p)

        if not text:
            result_html = "<pre style='color:#b00;'>Error: text is required</pre>"
        else:
            settings = Settings()
            client = VtuberClient(settings.vtuber_api_root)
            try:
                resp = await client.speak(
                    text=text,
                    client_uid=client_uid,
                    display_name=display_name,
                    avatar=avatar,
                    motions=motions or None,
                    expressions=expressions or None,
                    extract_emotions=extract_emotions,
                )
                import json

                result_html = f"<pre>{json.dumps(resp, ensure_ascii=False, indent=2)}</pre>"
            except Exception as e:  # noqa: BLE001
                result_html = f"<pre style='color:#b00;'>Error: {e!s}</pre>"

        return f"""
        <html>
          <head>
            <meta charset='utf-8' />
            <title>Speak — VTuber</title>
          </head>
          <body>
            <p><a href='/admin/vtuber'>&larr; Back</a></p>
            <h1>Speak Result</h1>
            {result_html}
          </body>
        </html>
        """

    return app


async def run_admin() -> None:
    settings = Settings()
    app = create_app()
    config = uvicorn.Config(
        app,
        host=settings.admin_host,
        port=settings.admin_port,
        log_level="info",
    )
    server = uvicorn.Server(config)
    await server.serve()
