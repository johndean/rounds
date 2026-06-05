# ADR-008 — WebSocket architecture: session-scoped pub/sub via Redis

- **Status:** Accepted
- **Date:** 2026-05-17 (bootstrap), refined 2026-06-05
- **Deciders:** johndean@vin.com
- **Related:** [ADR-006](./ADR-006-queue-processing.md), [ADR-001](./ADR-001-authentication.md)

## Context

Two surfaces need live updates from the worker tier:

1. **Upload / processing page** — must show "transcribing 38%", "normalizing", "ready" as the Celery pipeline progresses.
2. **Editor** — must reflect corrections from another tab, discrepancy resolutions from the worker, finalize events, etc.

Constraints:

- **No worker-to-browser direct path.** Workers run in a separate Railway container; they do not hold WebSocket connections.
- **Multi-replica API.** Even at one API container today, the design must not assume colocation between the worker emitting an event and the API holding the user's WebSocket.
- **Auth must be enforced.** A user must only see events for sessions they have access to.
- **Cheap.** WebSockets cost money in connection seconds + idle keep-alives. We don't pay for what we don't use.

## Decision

**Workers publish session-scoped events to a Redis pub/sub channel; a single bridge task in the FastAPI lifespan subscribes and fans out to connected WebSocket clients per session.**

- Channel naming: `session:{session_id}`.
- The bridge is started once at FastAPI lifespan (`app/main.py:79`) and runs for the life of the process.
- A `WSManager` tracks per-session client lists (`dict[session_id, set[WebSocket]]`). Connect adds, disconnect removes.
- The Redis subscriber feeds incoming messages into the manager's broadcast method.
- The WebSocket route is `/v1/ws/sessions/{session_id}` (`app/main.py:166`). It accepts the connection, registers, and reads keep-alive pings.
- **Authorization** today is "valid JWT user can subscribe to any session." A future ADR can supersede this with per-session ACL once the role model lands.

## Consequences

- **Positive.**
  - Worker → API → client fan-out works across processes.
  - One Redis channel per session = no cross-session leakage.
  - Adding a second API replica is a config change, not a code change (each replica subscribes to all channels; each broadcasts to its own connected clients).
  - The bridge is one task per process — negligible overhead when no sessions are active.
- **Negative.**
  - No user-scoped channel exists. If a user wants notifications across sessions (e.g. "any session you assigned has hit deadline"), they must subscribe to each session WebSocket individually. The QueueView polling fallback covers this gap today.
  - WebSocket reconnect doesn't replay missed events. If a client drops mid-render and reconnects, it has to call the REST API to refresh state.
  - Redis is a hard dependency. If Redis is down, live updates stop (REST still works).
- **Risks.**
  - Per-session WS connections multiplied across many concurrent editors could exhaust the API container's file descriptors at scale. We are far from this today.
  - The bridge task is the only Redis subscriber per process — if it dies silently, every WebSocket stops getting events. We don't currently have a health check on the bridge.

## Code locations

- `app/engines/ws_bridge.py` — `WSManager`, `start_ws_bridge`
- `app/main.py:79–82` — lifespan starts the bridge
- `app/main.py:166–182` — `/v1/ws/sessions/{session_id}` route
- `app/tasks/` — every progress-emitting task does `redis.publish(f"session:{sid}", json.dumps(event))`

## Alternatives considered

1. **Server-Sent Events (SSE)** — viable; rejected because the editor uses bidirectional WS for caption-stream interactions in the future plan.
2. **Direct worker-to-client via dedicated worker WebSocket server** — rejected because it would require workers to bind a port (Railway worker containers don't expose HTTP) and would duplicate the auth surface.
3. **Long-polling** — rejected as not real-time enough for "transcribing 38%" feel.
4. **A managed pub/sub (Pusher, Ably, Cloud Pub/Sub)** — rejected; Redis is already in the deploy footprint.

## When this ADR should be revisited

- When a user-scoped event becomes a frequent feature ask — then add a `user:{user_id}` channel.
- If multi-tab editor conflicts grow common — then the WebSocket gains a "broadcast my edit" path (today it's pull-only from the worker).
- If pipeline event volume per session grows past ~10/sec — then per-event ack + replay-on-reconnect become valuable.
