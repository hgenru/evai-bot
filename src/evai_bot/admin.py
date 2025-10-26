from __future__ import annotations

from typing import Annotated, Optional

import uvicorn
from fastapi import Depends, FastAPI, HTTPException, Query, Request, status
from fastapi.responses import HTMLResponse, RedirectResponse

from .config import Settings
from .db import get_session, init_db
from .models import SurveyAnswer, SurveyRun, User
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
    app = FastAPI(title="EVAI Admin", version="0.1.0")

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
            reg_badge = "✓" if u.is_registered else "✗"
            rows.append(
                f"<tr>"
                f"<td>{u.id}</td>"
                f"<td>{u.tg_id}</td>"
                f"<td>{name}</td>"
                f"<td>{reg_badge}</td>"
                f"<td>"
                f"<a href='/admin/users/{u.id}'>View</a>"
                f" &nbsp;"
                f"<form method='post' action='/admin/users/{u.id}/toggle-registered'>"
                f"<button type='submit'>Toggle Registered</button>"
                f"</form>"
                f"<form method='post' action='/admin/users/{u.id}/delete' onsubmit=\"return confirm('Delete user #{u.id}?');\">"
                f"<button type='submit' style='color:#b00;'>Delete</button>"
                f"</form>"
                f"</td>"
                f"</tr>"
            )
        body = "".join(rows) or "<tr><td colspan='5'>No users yet</td></tr>"
        return f"""
        <html>
          <head>
            <meta charset='utf-8' />
            <title>EVAI Admin — Users</title>
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

    @app.post("/admin/users/{user_id}/delete")
    def delete_user(user_id: int, _: Auth):  # type: ignore[no-untyped-def]
        with get_session() as session:
            user = session.get(User, user_id)
            if not user:
                raise HTTPException(status_code=404, detail="User not found")
            # Cascade delete survey data
            runs = session.query(SurveyRun).filter(SurveyRun.user_id == user_id).all()
            for r in runs:
                session.query(SurveyAnswer).filter(SurveyAnswer.run_id == r.id).delete()
                session.delete(r)
            session.delete(user)
            session.commit()
        return RedirectResponse(url="/admin/users", status_code=303)

    @app.get("/admin/users/{user_id}", response_class=HTMLResponse)
    def view_user(user_id: int, _: Auth) -> str:  # type: ignore[no-untyped-def]
        with get_session() as session:
            user = session.get(User, user_id)
            if not user:
                raise HTTPException(status_code=404, detail="User not found")
            runs = (
                session.query(SurveyRun)
                .filter(SurveyRun.user_id == user_id)
                .order_by(SurveyRun.created_at.desc())
                .all()
            )
            blocks = []
            for r in runs:
                answers = (
                    session.query(SurveyAnswer)
                    .filter(SurveyAnswer.run_id == r.id)
                    .order_by(SurveyAnswer.created_at.asc())
                    .all()
                )
                items = "".join(
                    f"<tr><td>{a.created_at:%Y-%m-%d %H:%M:%S}</td><td>{a.question_id}</td><td>{a.answer_choice or ''}</td><td>{(a.answer_text or '').replace('<','&lt;')}</td></tr>"
                    for a in answers
                ) or "<tr><td colspan='4'>—</td></tr>"
                status = "✓ completed" if r.completed_at else "… in progress"
                blocks.append(
                    f"<h3>Run #{r.id} — {r.survey_key} — {status}</h3>"
                    f"<table><thead><tr><th>Time</th><th>Question</th><th>Choice</th><th>Text</th></tr></thead><tbody>{items}</tbody></table>"
                )

        name = " ".join(filter(None, [user.first_name, user.last_name])) or (user.username or "-")
        runs_html = "".join(blocks) or "<p>No survey runs yet.</p>"
        return f"""
        <html>
          <head>
            <meta charset='utf-8' />
            <title>User #{user.id}</title>
            <style>
              body {{ font-family: system-ui, sans-serif; padding: 20px; }}
              table {{ border-collapse: collapse; width: 100%; margin-bottom: 16px; }}
              th, td {{ border: 1px solid #ddd; padding: 6px; }}
              th {{ background: #f6f6f6; text-align: left; }}
              .muted {{ color: #666; }}
            </style>
          </head>
          <body>
            <p><a href='/admin/users'>&larr; Back to Users</a></p>
            <h1>User #{user.id} — {name}</h1>
            <p class='muted'>tg_id: {user.tg_id} &middot; registered: {"yes" if user.is_registered else "no"}</p>
            {runs_html}
          </body>
        </html>
        """

    @app.get("/admin/vtuber", response_class=HTMLResponse)
    def vtuber_form(_: Auth) -> str:  # type: ignore[no-untyped-def]
        settings = Settings()
        return f"""
        <html>
          <head>
            <meta charset='utf-8' />
            <title>EVAI Admin — VTuber Control</title>
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
            <p><b>Configured API root:</b> {settings.vtuber_api_root}</p>
            <h2>List Sessions</h2>
            <form method='post' action='/admin/vtuber/sessions'>
              <button type='submit'>GET /v1/sessions</button>
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
                <small>Список совпадает с motionMap движка.</small>
              </label>
              <label>actions.expressions (comma/space; strings or ints):
                <input type='text' name='expressions' placeholder='joy, 3'/>
              </label>
              <label>
                <input type='checkbox' name='apply_to_all' /> apply_to_all (broadcast)
              </label>
              <button type='submit'>POST /v1/control/speak</button>
            </form>

            <h2>System Instruction</h2>
            <form method='post' action='/admin/vtuber/system'>
              <label>text (required):
                <textarea name='text' rows='3' placeholder='System prompt...'></textarea>
              </label>
              <label>mode:
                <input type='text' name='mode' value='append' />
              </label>
              <label>client_uid (optional):
                <input type='text' name='client_uid' />
              </label>
              <label>
                <input type='checkbox' name='apply_to_all' /> apply_to_all (broadcast)
              </label>
              <button type='submit'>POST /v1/control/system</button>
            </form>

            <h2>Respond (LLM)</h2>
            <form method='post' action='/admin/vtuber/respond'>
              <label>text (required):
                <textarea name='text' rows='3' placeholder='User message...'></textarea>
              </label>
              <label>client_uid (optional):
                <input type='text' name='client_uid' />
              </label>
              <label>
                <input type='checkbox' name='apply_to_all' /> apply_to_all (broadcast)
              </label>
              <button type='submit'>POST /v1/control/respond</button>
            </form>
          </body>
        </html>
        """

    @app.post("/admin/vtuber/sessions", response_class=HTMLResponse)
    async def vtuber_sessions(_: Auth) -> str:  # type: ignore[no-untyped-def]
        api_root = Settings().vtuber_api_root
        client = VtuberClient(api_root)
        try:
            sessions = await client.list_sessions()
            items = "".join(f"<li><code>{s}</code></li>" for s in sessions) or "<li>—</li>"
            result_html = f"<ul>{items}</ul>"
        except Exception as e:  # noqa: BLE001
            result_html = f"<pre style='color:#b00;'>Error: {e!s}</pre>"
        return f"""
        <html>
          <head>
            <meta charset='utf-8' />
            <title>Sessions — VTuber</title>
          </head>
          <body>
            <p><a href='/admin/vtuber'>&larr; Back</a></p>
            <h1>Sessions</h1>
            {result_html}
          </body>
        </html>
        """

    @app.post("/admin/vtuber/speak", response_class=HTMLResponse)
    async def vtuber_speak(request: Request, _: Auth) -> str:  # type: ignore[no-untyped-def]
        form = await request.form()
        api_root = Settings().vtuber_api_root
        text = str(form.get("text") or "").strip()
        client_uid = str(form.get("client_uid") or "").strip() or None
        apply_to_all = form.get("apply_to_all") is not None
        if not text:
            result_html = "<pre style='color:#b00;'>Error: text is required</pre>"
        else:
            client = VtuberClient(api_root)
            try:
                resp = await client.speak(text=text, client_uid=client_uid, apply_to_all=apply_to_all)
                import json

                result_html = (
                    f"<p>API root: <code>{api_root}</code></p>"
                    f"<pre>{json.dumps(resp, ensure_ascii=False, indent=2)}</pre>"
                )
            except Exception as e:  # noqa: BLE001
                result_html = (
                    f"<p>API root: <code>{api_root}</code></p>"
                    f"<pre style='color:#b00;'>Error: {e!s}</pre>"
                )

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

    @app.post("/admin/vtuber/system", response_class=HTMLResponse)
    async def vtuber_system(request: Request, _: Auth) -> str:  # type: ignore[no-untyped-def]
        form = await request.form()
        api_root = Settings().vtuber_api_root
        text = str(form.get("text") or "").strip()
        client_uid = str(form.get("client_uid") or "").strip() or None
        mode = str(form.get("mode") or "append").strip() or "append"
        apply_to_all = form.get("apply_to_all") is not None
        if not text:
            result_html = "<pre style='color:#b00;'>Error: text is required</pre>"
        else:
            client = VtuberClient(api_root)
            try:
                resp = await client.system_instruction(
                    text=text,
                    client_uid=client_uid,
                    mode=mode,
                    apply_to_all=apply_to_all,
                )
                import json

                result_html = (
                    f"<p>API root: <code>{api_root}</code></p>"
                    f"<pre>{json.dumps(resp, ensure_ascii=False, indent=2)}</pre>"
                )
            except Exception as e:  # noqa: BLE001
                result_html = (
                    f"<p>API root: <code>{api_root}</code></p>"
                    f"<pre style='color:#b00;'>Error: {e!s}</pre>"
                )
        return f"""
        <html>
          <head>
            <meta charset='utf-8' />
            <title>System — VTuber</title>
          </head>
          <body>
            <p><a href='/admin/vtuber'>&larr; Back</a></p>
            <h1>System Result</h1>
            {result_html}
          </body>
        </html>
        """

    @app.post("/admin/vtuber/respond", response_class=HTMLResponse)
    async def vtuber_respond(request: Request, _: Auth) -> str:  # type: ignore[no-untyped-def]
        form = await request.form()
        api_root = Settings().vtuber_api_root
        text = str(form.get("text") or "").strip()
        client_uid = str(form.get("client_uid") or "").strip() or None
        apply_to_all = form.get("apply_to_all") is not None
        if not text:
            result_html = "<pre style='color:#b00;'>Error: text is required</pre>"
        else:
            client = VtuberClient(api_root)
            try:
                resp = await client.respond(
                    text=text,
                    client_uid=client_uid,
                    apply_to_all=apply_to_all,
                )
                import json

                result_html = (
                    f"<p>API root: <code>{api_root}</code></p>"
                    f"<pre>{json.dumps(resp, ensure_ascii=False, indent=2)}</pre>"
                )
            except Exception as e:  # noqa: BLE001
                result_html = (
                    f"<p>API root: <code>{api_root}</code></p>"
                    f"<pre style='color:#b00;'>Error: {e!s}</pre>"
                )
        return f"""
        <html>
          <head>
            <meta charset='utf-8' />
            <title>Respond — VTuber</title>
          </head>
          <body>
            <p><a href='/admin/vtuber'>&larr; Back</a></p>
            <h1>Respond Result</h1>
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

