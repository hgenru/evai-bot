from __future__ import annotations

from typing import Annotated, Optional

import uvicorn
from fastapi import Depends, FastAPI, HTTPException, Query, Request, status
from fastapi.responses import HTMLResponse, RedirectResponse, JSONResponse

from .config import Settings
from .db import get_session, init_db
from .models import SurveyAnswer, SurveyRun, User, LivePollVote, LivePollState
from .vtuber_client import VtuberClient
from .surveys.engine import load_survey, SURVEYS_DIR
from pathlib import Path


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
              <a href='/admin/surveys'>Результаты регистрации</a>
              <a href='/admin/polls'>Опросы</a>
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

    @app.get("/admin/surveys/registration", response_class=RedirectResponse)
    def survey_registration_results(_: Auth):  # type: ignore[no-untyped-def]
        return RedirectResponse(url="/admin/surveys")

    @app.get("/admin/surveys", response_class=HTMLResponse)
    def survey_all_results(_: Auth) -> str:  # type: ignore[no-untyped-def]
        """Display results for the Registration survey with a copy-all button.
        Readable text is grouped by participants: one block per user with Q: A lines.
        """
        from collections import defaultdict, Counter
        import datetime as _dt

        # Only the registration survey is displayed on this page
        reg_path = Path(SURVEYS_DIR) / "registration.json"
        survey_files = [reg_path] if reg_path.exists() else []
        if not survey_files:
            return """
            <html><body><p>Registration survey not found.</p></body></html>
            """

        html_sections: list[str] = []

        # Aggregates for building participant-grouped plain text
        specs: dict[str, object] = {}
        all_runs: list[SurveyRun] = []
        answers_by_run: dict[int, list[SurveyAnswer]] = defaultdict(list)
        all_user_ids: set[int] = set()

        with get_session() as session:
            for sf in survey_files:
                key = sf.stem
                try:
                    spec = load_survey(key)
                except Exception as e:  # noqa: BLE001
                    html_sections.append(
                        f"<section><h2>{key}</h2><p style='color:#b00;'>Survey file error: {e!s}</p></section>"
                    )
                    continue
                specs[key] = spec
                # runs and answers for this survey
                runs = (
                    session.query(SurveyRun)
                    .filter((SurveyRun.survey_key == key) & (SurveyRun.completed_at.is_not(None)))
                    .all()
                )
                run_ids = [r.id for r in runs if r.id is not None]
                if run_ids:
                    answers = (
                        session.query(SurveyAnswer)
                        .filter(SurveyAnswer.run_id.in_(run_ids))
                        .all()
                    )
                else:
                    answers = []
                for a in answers:
                    if a.run_id is not None:
                        answers_by_run[a.run_id].append(a)
                all_runs.extend(runs)
                all_user_ids.update(r.user_id for r in runs)

                # HTML breakdown per survey (kept question-grouped for readability)
                by_q: dict[str, list[SurveyAnswer]] = defaultdict(list)
                for a in answers:
                    by_q[a.question_id].append(a)
                participants = len({r.user_id for r in runs})
                html_rows: list[str] = [f"<h2>{spec.title}</h2>", f"<p class='muted'>Participants (completed): {participants}</p>"]
                for q in spec.questions:
                    q_answers = by_q.get(q.id, [])
                    if q.type == "choice":
                        counts = Counter([a.answer_choice or "" for a in q_answers])
                        label_by_value = {c.value: c.label for c in (q.choices or [])}
                        rows = []
                        total = sum(counts.values()) or 1
                        for value, label in label_by_value.items():
                            n = counts.get(value, 0)
                            pct = (n * 100.0) / total if total else 0.0
                            rows.append(
                                f"<tr><td>{label}</td><td style='text-align:right;'>{n}</td><td style='text-align:right;'>{pct:.1f}%</td></tr>"
                            )
                        table = (
                            "<table><thead><tr><th>Option</th><th>Count</th><th>%</th></tr></thead>"
                            f"<tbody>{''.join(rows) if rows else '<tr><td colspan=3>—</td></tr>'}</tbody></table>"
                        )
                        html_rows.append(f"<section><h3>{q.prompt}</h3>{table}</section>")
                    else:
                        # Skip free-text answers in breakdown to keep the page compact.
                        continue
                html_sections.append("\n".join(html_rows))

            # Fetch all users for runs once
            users = {u.id: u for u in session.query(User).filter(User.id.in_(all_user_ids)).all()} if all_user_ids else {}

        # Build participant-grouped plain text
        # Order users by name (fallback id)
        def user_display(u: User) -> str:
            name = " ".join(filter(None, [u.first_name, u.last_name]))
            if name:
                return name
            if u.username:
                return u.username
            return f"user#{u.id}"

        # Build mapping of questions for quick label lookup
        qmap: dict[str, dict[str, object]] = {}
        for key, spec in specs.items():
            qmap[key] = {q.id: q for q in spec.questions}

        # runs per user sorted by created_at
        runs_by_user: dict[int, list[SurveyRun]] = defaultdict(list)
        for r in all_runs:
            runs_by_user[r.user_id].append(r)
        for uid in runs_by_user:
            runs_by_user[uid].sort(key=lambda r: r.created_at)

        plain_parts: list[str] = []
        # Sort users by display name
        ordered_user_ids = sorted(all_user_ids, key=lambda uid: user_display(users.get(uid)) if users.get(uid) else str(uid))
        for uid in ordered_user_ids:
            u = users.get(uid)
            if not u:
                continue
            plain_parts.append(user_display(u))
            for run in runs_by_user.get(uid, []):
                spec = specs.get(run.survey_key)
                if not spec:
                    continue
                answers_list = answers_by_run.get(run.id or -1, [])
                ans_by_q = {a.question_id: a for a in answers_list}
                for q in spec.questions:
                    a = ans_by_q.get(q.id)
                    if not a:
                        continue
                    if q.type == "choice":
                        label_by_value = {c.value: c.label for c in (q.choices or [])}
                        val = a.answer_choice or ""
                        out = label_by_value.get(val, val)
                    else:
                        out = (a.answer_text or "").replace("\n", " ").strip()
                    if out:
                        plain_parts.append(f"{q.prompt}: {out}")
            plain_parts.append("")

        plain_text = "\n".join(plain_parts)
        escaped = plain_text.replace("<", "&lt;")
        generated_at = _dt.datetime.utcnow().strftime("%Y-%m-%d %H:%M UTC")
        return f"""
        <html>
          <head>
            <meta charset='utf-8' />
            <title>Survey Results — Registration</title>
            <style>
              body {{ font-family: system-ui, sans-serif; padding: 20px; max-width: 1100px; }}
              table {{ border-collapse: collapse; width: 100%; margin: 10px 0 20px; }}
              th, td {{ border: 1px solid #ddd; padding: 6px; }}
              th {{ background: #f6f6f6; text-align: left; }}
              nav a {{ margin-right: 12px; }}
              section {{ margin-bottom: 22px; }}
              .muted {{ color: #666; }}
              .controls {{ margin: 12px 0; }}
              pre {{ white-space: pre-wrap; background: #f9f9f9; padding: 10px; border: 1px solid #eee; }}
            </style>
          </head>
          <body>
            <nav>
              <a href='/admin/users'>Users</a>
              <a href='/admin/surveys'>Результаты регистрации</a>
              <a href='/admin/polls'>Опросы</a>
              <a href='/admin/vtuber'>VTuber Control</a>
            </nav>
            <h1>Survey Results — Registration</h1>
            <p class='muted'>Generated at: {generated_at}</p>
            <div class='controls'>
              <button onclick="copyAll()">Copy all</button>
              <span id='copyStatus' class='muted' style='margin-left:8px;'></span>
            </div>
            <h2>Readable Text</h2>
            <pre id='readable'>{escaped}</pre>
            <h2>Breakdown</h2>
            {''.join(html_sections)}
            <textarea id='copySrc' style='position:absolute;left:-9999px;top:-9999px;'>{plain_text}</textarea>
            <script>
              async function copyAll() {{
                const ta = document.getElementById('copySrc');
                ta.select();
                ta.setSelectionRange(0, ta.value.length);
                let ok = false;
                try {{
                  await navigator.clipboard.writeText(ta.value);
                  ok = true;
                }} catch (e) {{
                  try {{
                    ok = document.execCommand('copy');
                  }} catch (e2) {{}}
                }}
                const s = document.getElementById('copyStatus');
                s.textContent = ok ? 'Copied to clipboard' : 'Copy failed';
                setTimeout(() => s.textContent = '', 2000);
              }}
            </script>
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

    # -------------------- Polls admin and Live view --------------------
    @app.get("/admin/polls", response_class=HTMLResponse)
    def polls_admin(_: Auth) -> str:  # type: ignore[no-untyped-def]
        # Collect all surveys and their choice questions
        entries: list[tuple[str, object]] = []
        for p in sorted(Path(SURVEYS_DIR).glob("*.json"), key=lambda x: x.stem):
            key = p.stem
            try:
                spec = load_survey(key)
                if any(q.type == "choice" for q in spec.questions):
                    entries.append((key, spec))
            except Exception:
                continue
        with get_session() as session:
            active = session.query(LivePollState).order_by(LivePollState.created_at.desc()).first()
        active_html = (
            f"<p><b>Активен:</b> {active.survey_key} / {active.question_id}</p>" if active else "<p><b>Активен:</b> —</p>"
        )
        # Simple select (пускай останется как резервный способ)
        opts_html = "".join(
            f"<option value='{key}'>{spec.title} ({key})</option>" for key, spec in entries
        ) or "<option value='' disabled>—</option>"

        # Quick actions list
        qa_blocks: list[str] = []
        for key, spec in entries:
            rows: list[str] = []
            for q in spec.questions:
                if q.type != "choice":
                    continue
                is_active = active and active.survey_key == key and active.question_id == q.id
                badge = " <span style='color:#22c55e'>(active)</span>" if is_active else ""
                rows.append(
                    f"<div style='border:1px solid #eee; padding:8px; margin:6px 0;'>"
                    f"<div style='margin-bottom:6px'><b>{q.prompt}</b>{badge}</div>"
                    f"<form style='display:inline-block;margin-right:8px' method='post' action='/admin/polls/start'>"
                    f"  <input type='hidden' name='survey_key' value='{key}' />"
                    f"  <input type='hidden' name='question_id' value='{q.id}' />"
                    f"  <button type='submit'>Start</button>"
                    f"</form>"
                    f"<form style='display:inline-block;margin-right:8px' method='post' action='/admin/polls/broadcast'>"
                    f"  <input type='hidden' name='survey_key' value='{key}' />"
                    f"  <input type='hidden' name='question_id' value='{q.id}' />"
                    f"  <button type='submit'>Broadcast</button>"
                    f"</form>"
                    f"<a href='/live/survey/{key}' target='_blank'>Viewer</a>"
                    f"</div>"
                )
            qa_blocks.append(
                f"<section style='margin:12px 0 18px;'>"
                f"  <h3 style='margin:0 0 6px;'>{spec.title} <small style='color:#666'>({key})</small></h3>"
                f"  {''.join(rows) if rows else '<p style="color:#666">Нет вопросов с вариантами</p>'}"
                f"</section>"
            )

        quick_html = "".join(qa_blocks)

        return f"""
        <html>
          <head>
            <meta charset='utf-8' />
            <title>Polls Admin</title>
            <style>
              body {{ font-family: system-ui, sans-serif; padding: 20px; max-width: 900px; }}
              form {{ margin: 12px 0; padding: 10px; border: 1px solid #ddd; }}
              label {{ display:block; margin:6px 0; }}
              input[type=text], select {{ width: 100%; padding: 6px; }}
              small {{ color:#666; }}
              nav a {{ margin-right: 12px; }}
              code {{ background:#f6f6f6; padding:2px 4px; }}
              h3 small {{ font-weight: normal; }}
            </style>
          </head>
          <body>
            <nav>
              <a href='/admin/users'>Users</a>
              <a href='/admin/surveys'>Результаты регистрации</a>
              <a href='/admin/polls'>Опросы</a>
              <a href='/admin/vtuber'>VTuber Control</a>
            </nav>
            <h1>Live Polls</h1>
            {active_html}
            <h2>Быстрые действия</h2>
            {quick_html}
            <form method='post' action='/admin/polls/start'>
              <h2>Start Poll</h2>
              <label>Survey key
                <select name='survey_key'>{opts_html}</select>
              </label>
              <label>Question ID (from JSON)
                <input type='text' name='question_id' placeholder='e.g. choice_1' />
              </label>
              <button type='submit'>Start</button>
            </form>
            <form method='post' action='/admin/polls/stop'>
              <h2>Stop Active</h2>
              <button type='submit'>Stop</button>
            </form>
            <form method='post' action='/admin/polls/broadcast'>
              <h2>Broadcast To Registered Users</h2>
              <label>Survey key
                <input type='text' name='survey_key' placeholder='must match JSON file key' />
              </label>
              <label>Question ID
                <input type='text' name='question_id' />
              </label>
              <button type='submit'>Send</button>
              <p><small>Uses Telegram HTTP API per user; may take time.</small></p>
            </form>
            <h2>Viewer Link</h2>
            <p>Open in OBS: <code>/live/survey/&lt;survey_key&gt;</code></p>
          </body>
        </html>
        """

    @app.post("/admin/polls/start")
    def polls_start(request: Request, _: Auth):  # type: ignore[no-untyped-def]
        import anyio
        async def _parse() -> dict[str, str]:
            data = await request.form()
            return {k: str(v) for k, v in data.items()}
        data = anyio.from_thread.run(_parse)
        survey_key = (data.get("survey_key") or "").strip()
        question_id = (data.get("question_id") or "").strip()
        if not survey_key or not question_id:
            raise HTTPException(status_code=400, detail="survey_key and question_id required")
        with get_session() as session:
            state = LivePollState(survey_key=survey_key, question_id=question_id, image_url=None)
            session.add(state)
            session.commit()
        return RedirectResponse(url="/admin/polls", status_code=303)

    @app.post("/admin/polls/stop")
    def polls_stop(_: Auth):  # type: ignore[no-untyped-def]
        with get_session() as session:
            for st in session.query(LivePollState).all():
                session.delete(st)
            session.commit()
        return RedirectResponse(url="/admin/polls", status_code=303)

    @app.post("/admin/polls/broadcast", response_class=HTMLResponse)
    def polls_broadcast(request: Request, _: Auth) -> str:  # type: ignore[no-untyped-def]
        import anyio
        import httpx
        async def _parse() -> dict[str, str]:
            data = await request.form()
            return {k: str(v) for k, v in data.items()}
        data = anyio.from_thread.run(_parse)
        survey_key = (data.get("survey_key") or "").strip()
        question_id = (data.get("question_id") or "").strip()
        if not survey_key or not question_id:
            return "<html><body><p style='color:#b00;'>survey_key and question_id required</p></body></html>"
        try:
            spec = load_survey(survey_key)
        except Exception as e:  # noqa: BLE001
            return f"<html><body><p style='color:#b00;'>Spec error: {e!s}</p></body></html>"
        q = next((qq for qq in spec.questions if qq.id == question_id and qq.type == "choice"), None)
        if not q or not q.choices:
            return "<html><body><p style='color:#b00;'>Question not found or not a choice question</p></body></html>"
        settings = Settings()
        api_base = f"https://api.telegram.org/bot{settings.bot_token}"
        text = f"{spec.title}\n\n{q.prompt}"
        kb = {
            "inline_keyboard": [
                [
                    {"text": c.label, "callback_data": f"livepoll:{spec.key}:{q.id}:{c.value}"}
                ]
                for c in q.choices
            ]
        }
        sent = 0
        errors = 0
        with get_session() as session:
            users = session.query(User).filter(User.is_registered.is_(True)).all()
        with httpx.Client(timeout=10) as client:
            for u in users:
                try:
                    client.post(
                        f"{api_base}/sendMessage",
                        json={"chat_id": u.tg_id, "text": text, "reply_markup": kb},
                    )
                    sent += 1
                except Exception:
                    errors += 1
        return f"<html><body><p>Broadcast done. Sent: {sent}; Errors: {errors}.</p></body></html>"

    @app.get("/live/survey/{survey_key}", response_class=HTMLResponse)
    def live_view(survey_key: str) -> str:  # type: ignore[no-untyped-def]
        try:
            spec = load_survey(survey_key)
        except Exception:
            return "<html><body><p>Survey not found.</p></body></html>"
        title = spec.title
        return f"""
        <html>
          <head>
            <meta charset='utf-8' />
            <title>{title}</title>
            <script src="https://cdn.jsdelivr.net/npm/chart.js"></script>
            <style>
              body {{ margin: 0; background: #000; color: #fff; font-family: system-ui, sans-serif; }}
              .wrap {{ display:flex; align-items:center; gap:24px; padding: 24px; }}
              img {{ max-height: 400px; border-radius: 8px; }}
              h1 {{ font-size: 24px; margin: 0 0 12px; }}
              .left {{ flex: 0 0 auto; }}
              .right {{ flex: 1 1 auto; }}
            </style>
          </head>
          <body>
            <div class='wrap'>
              <div class='left'><img id='pic' style='display:none' /></div>
              <div class='right'>
                <h1>{title}</h1>
                <canvas id='chart'></canvas>
              </div>
            </div>
            <script>
              const ctx = document.getElementById('chart').getContext('2d');
              let chart;
              async function fetchData() {{
                const r = await fetch('/live/api/survey/{survey_key}');
                if (!r.ok) return;
                const data = await r.json();
                // update image if provided
                const img = document.getElementById('pic');
                if (data.image_url) {{ img.src = data.image_url; img.style.display = 'block'; }} else {{ img.style.display = 'none'; }}
                const cfg = {{
                  type: 'bar',
                  data: {{
                    labels: data.labels,
                    datasets: [{{ label: 'Votes', data: data.counts, backgroundColor: '#3b82f6' }}]
                  }},
                  options: {{
                    responsive: true,
                    plugins: {{ legend: {{ display: false }} }},
                    scales: {{
                      x: {{ ticks: {{ color: '#ddd' }}, grid: {{ color: 'rgba(255,255,255,0.1)' }} }},
                      y: {{ beginAtZero:true, ticks: {{ color: '#ddd', precision:0 }}, grid: {{ color: 'rgba(255,255,255,0.1)' }} }}
                    }}
                  }}
                }};
                if (!chart) {{ chart = new Chart(ctx, cfg); }}
                else {{ chart.data.labels = data.labels; chart.data.datasets[0].data = data.counts; chart.update(); }}
              }}
              fetchData();
              setInterval(fetchData, 2000);
            </script>
          </body>
        </html>
        """

    @app.get("/live/api/survey/{survey_key}", response_class=JSONResponse)
    def live_api(survey_key: str):  # type: ignore[no-untyped-def]
        try:
            spec = load_survey(survey_key)
        except Exception:
            return JSONResponse({"labels": [], "counts": []})
        # default: first choice question
        q = next((qq for qq in spec.questions if qq.type == "choice"), None)
        with get_session() as session:
            state = (
                session.query(LivePollState)
                .filter(LivePollState.survey_key == survey_key)
                .order_by(LivePollState.created_at.desc())
                .first()
            )
        if state and state.question_id:
            q = next((qq for qq in spec.questions if qq.id == state.question_id and qq.type == "choice"), q)
        if not q or not q.choices:
            return JSONResponse({"labels": [], "counts": []})
        with get_session() as session:
            votes = session.query(LivePollVote).filter(
                (LivePollVote.survey_key == survey_key) & (LivePollVote.question_id == q.id)
            ).all()
        from collections import Counter
        counts = Counter([v.value for v in votes])
        labels = [c.label for c in (q.choices or [])]
        series = [counts.get(c.value, 0) for c in (q.choices or [])]
        # Choose image: prefer question.image_url, else survey.image_url
        q_image = getattr(q, "image_url", None)
        image_url = q_image or getattr(spec, "image_url", None)
        return JSONResponse({"labels": labels, "counts": series, "title": spec.title, "prompt": q.prompt, "image_url": image_url or ""})

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
              <a href='/admin/surveys'>Результаты регистрации</a>
              <a href='/admin/polls'>Опросы</a>
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
