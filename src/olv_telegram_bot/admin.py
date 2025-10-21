from __future__ import annotations

from typing import Annotated, Optional

import uvicorn
from fastapi import Depends, FastAPI, HTTPException, Query, Request, status
from fastapi.responses import HTMLResponse, RedirectResponse

from .config import Settings
from .db import get_session, init_db
from .models import User


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
            </style>
          </head>
          <body>
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

