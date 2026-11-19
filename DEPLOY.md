# VYBE private mobile deployment

This project is NOT hosted yet. It needs a hosting account and persistent disk. The included Render blueprint uses a **paid Starter service and persistent disk**; review current Render prices before confirming.

1. Create a **private GitHub repository** and upload the source files in this folder (exclude `data/`, `.env`, test databases and secrets). GitHub's web interface works from iPhone Safari.
2. Sign into Render, choose New > Blueprint, connect the private GitHub repository, and select `render.yaml`.
3. Before deployment, enter a **long unique** `VYBE_PASSWORD`. Render generates `VYBE_SESSION_SECRET`. Keep `OPENAI_API_KEY` unset until you intentionally enable paid AI responses.
4. Confirm the Starter plan, attached persistent disk, and charges. Deploy, wait for the health check, and open the HTTPS URL Render provides.
5. Sign in using your password. In iPhone Safari use Share > Add to Home Screen.
6. Keep only **one** web instance. The worker is in-process and does not provide production-grade job guarantees. Do not scale replicas with SQLite.
7. Arrange off-platform backups of `/app/data` (database and media). Snapshot API alone is not an off-site backup. Test recovery before treating this as irreplaceable canon.

**Security limitations:** This is a single-owner password-gated alpha, not independently audited. The existing app needs CSRF protection, brute-force rate limiting, stronger durable queue semantics, and an improved PWA icon/offline experience before broader use. Never publish it without authentication or store secrets in the repository. Sandbox mode is initially paused. No automatic sync to ChatGPT exists.
