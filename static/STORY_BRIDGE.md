# VYBE Story Bridge v1

The bridge accepts **every** roleplay event as a staged, append-only timeline entry. It does not automatically access ChatGPT conversations, modify the world clock, grant NPCs knowledge, or establish canon.

## Owner import

Open **Control → Story Bridge** and paste JSON in this format:

```json
{"events":[{"external_id":"scene-001-beat-001","fictional_time":"2027-09-06T08:15:00","event_type":"movement","summary":"Celestia enters the library","participants":["Celestia"],"location":"Library","visibility":"author","source":"chatgpt_roleplay","details":{"scene":"Chapter Zero"}}]}
```

Choose `visibility` per event: `author` (only director), `private` (limited participants), or `public` (observable). Visibility is metadata only: no automatic distribution to students occurs. `external_id` prevents duplicate imports. You can import up to 100 events per request.

## Authorized integration API

- `POST /api/bridge/events` with JSON `{ "events": [...] }`.
- `GET /api/bridge/events?after_id=0&limit=100` returns events and pagination cursor.
- `POST /api/bridge/events/{id}/approve` requires the owner session; it marks an event reviewed, not confirmed canon.

Authenticated browser sessions work automatically. For a future external connector, set a **long random** `VYBE_BRIDGE_TOKEN` in Render environment variables and send it in the `X-VYBE-Bridge-Token` header. Never paste this token into ChatGPT, source code, public GitHub, or client-side JavaScript. Protect the API over HTTPS. The bridge token can ingest/read events, but cannot approve them.

## Automatic ChatGPT sync

This release provides the receiving and retrieval API, **not** an automatic ChatGPT connector. Automatic transfer requires a supported custom integration with authorization and access to the roleplay conversation. Until then, copy event batches into the Control screen. Importing an event never moves Celestia, starts a scene, or reveals hidden facts.

## Persistence

Use a persistent Render disk or external database for `VYBE_DATA_DIR`; otherwise SQLite data can be lost during redeploy or instance replacement. Export backups before upgrading.
