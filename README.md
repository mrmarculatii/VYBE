# VYBE: Eidolon University (foundation build)

A private FastAPI + SQLite fictional social network. Initial world date: 2027-09-06 08:00. Celestia is player-controlled. Author-only divine canon is intentionally **not** stored in NPC-visible data.

## Start locally

```bash
cd vybe
python -m pip install -r requirements.txt
export VYBE_PASSWORD='choose-a-long-unique-password'
export VYBE_SESSION_SECRET="$(python -c 'import secrets; print(secrets.token_hex(32))')"
python -m uvicorn server:app --host 127.0.0.1 --port 8000
```

Open http://127.0.0.1:8000. For a real private phone deployment, host behind HTTPS, set `VYBE_COOKIE_SECURE=1`, use a persistent disk for `VYBE_DATA_DIR`, and provision secrets on the server. Run exactly one worker process with `VYBE_WORKER=1`; disable it on other web replicas. Back up `data/vybe.sqlite3` using SQLite's online backup API and save the `data/media` folder. Do not publish the source with real secrets.

Optional: `OPENAI_API_KEY` enables generated NPC replies for scheduled messages; `VYBE_AI_MODEL` chooses model (default `gpt-4.1-mini`). Without a key, pending replies will be processed but no NPC messages will be fabricated. AI calls incur costs. Keep the world paused until you intend time to pass. The worker runs only while the server is online. No durable cloud scheduler is provisioned.

## What works

Private password login and session cookies, seeded persistent cast and feed, player posts, reactions, comments, following, individual messages, photo uploads, stories with in-world expiry, manual clock controls, queued context-sensitive reply attempts, optional server-side AI replies, event review, staged world-log entries, JSON export.

## Important limitations

This is an early functional foundation, **not** the complete specification. No production deployment, no groups, no actual video support, no full autonomous post generation, no robust per-character schedules, no social graph evolution, no long-term summarization, no push notifications, no conflict-aware story sync, no full JSON world-bible import, no automatic two-way ChatGPT sync, no undo for database mutations, no complete role-based knowledge permissions, no OAuth, no tested production security audit, no dedicated rate/cost limiter. Stories and chat are basic. Media metadata and image uploads are persistent. Staged story entries are not yet interpreted as executable canon. The login is appropriate for a single private owner only after HTTPS and secrets configuration.

## Architecture

`server.py`: HTTP API, SQLite persistence, session auth, world clock, scheduled event worker and optional AI call. `static/index.html`: responsive single-page UI. `data/`: persistent SQLite database and media (not bundled as production data).

## Deployment checklist

1. Choose a persistent host with HTTPS (e.g. VPS or a container host with mounted persistent volume).
2. Set `VYBE_PASSWORD`, `VYBE_SESSION_SECRET`, `VYBE_COOKIE_SECURE=1`, `VYBE_DATA_DIR` and optionally `OPENAI_API_KEY` as server environment secrets.
3. Install requirements and launch one `uvicorn server:app --host 0.0.0.0 --port $PORT` process.
4. Keep the service running for delayed replies; use one worker only.
5. Back up the SQLite file using its backup API and media directory; test restoration.
6. Add a reverse proxy, HTTPS, rate limiting, CSRF protection, monitoring and cloud backups before exposing the service publicly.

## Living World Addendum: foundation upgrade

New: Pre-Chapter-One Sandbox state (paused on first migration), 7-day per-NPC schedule records, authenticated Director API endpoints for schedule inspection, manual time, story-mode activation, event staging/promotion/approval, database snapshots and restore, and confirmed-canon-only JSON export. Added basic PWA manifest and offline shell fallback. `python -m pytest -q test_living_world.py` verifies authentication, sandbox state, schedule seeding, duplicate-event rejection, canon approval boundaries, snapshots and clock validation.

**Important boundaries:** Director endpoints are backend APIs, not yet a polished Director Panel UI. Schedule records do not yet drive reply selection or location conflicts. Story-mode activation does not enable automatic ChatGPT sync. Snapshots cover the SQLite database but not media files. Restoring snapshots changes live data and should only be done after a separate backup. The current queue uses a single in-process worker and is not production-grade durable processing. Existing `/api/sync` legacy flow does not enforce the new canon approval model; use `/api/director/canon-events` instead. The initial HTML app is not yet a complete installable PWA: proper icon assets, push, and offline data UX remain pending. No AI secret is stored in the project. Do not deploy this as a public-facing production service without a security review.

### Director API

After login, use `POST /api/director/story-mode` with `{"activate":true}` to enter pending-canon mode (clock remains paused). `POST /api/director/canon-events` stages an event. Sandbox events require explicit `POST /api/director/canon-events/{event_id}/promote`, then `POST /api/director/canon-events/{event_id}/approve`. `GET /api/director/canon-export` exports only confirmed canon. `POST /api/director/snapshot` and `GET /api/director/snapshots` manage database backups; `POST /api/director/snapshots/{id}/restore` restores one. `POST /api/director/set-time` accepts `{"fictional_time":"2027-09-06T08:00:00"}`. `GET /api/director/schedules` lists schedule templates.
