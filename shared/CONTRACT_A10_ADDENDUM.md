# Contract A10 (implemented): production API

Base: `/api/v1` (JSON). Auth: httpOnly cookie `vaak_session` (Secure, SameSite=Lax), set by `POST /auth/google`.
Errors: `{"error":{"code","message"}}`. Unsafe methods reject a cross-site `Origin` (403 `BAD_ORIGIN`).

| Endpoint | Success | Errors |
|---|---|---|
| `POST /auth/google {credential}` | 200 user | 400 `INVALID_INPUT`, 401 `INVALID_CREDENTIAL`, 409 `EMAIL_CONFLICT`, 429 (10/min/IP) |
| `POST /auth/logout` | 200 `{ok}` | |
| `GET/PATCH/DELETE /me` | user / user / `{ok}` | 400 `INVALID_INPUT`, 401 |
| `POST /meetings {title?}` | 201 `{id,title,host_id,host_name,active,created_at,ended_at,join_url}` | 400, 429 (20/h) |
| `GET /meetings/{id}` | same shape | 400 `INVALID_MEETING_ID`, 404 `MEETING_NOT_FOUND` |
| `POST /meetings/{id}/join {display_name?,lang?}` | `{livekit_token,livekit_url,participant_id,meeting_id}` | 404, **410 `MEETING_ENDED`**, 502 `MEDIA_UNAVAILABLE` |
| `POST /meetings/{id}/end` | `{ok}` (idempotent) | 403 `FORBIDDEN` (not host) |
| `POST /meetings/{id}/invite {user_id}` | `{sent,recipient,delivered}` | 403 `NOT_FRIENDS`/`FORBIDDEN`, 410 |
| `GET /me/meetings?cursor=` | `{items:[{id,title,started_at,ended_at,duration_s,participant_count,role,active}],next_cursor}` (20/page) | 400 `INVALID_CURSOR` |
| `DELETE /me/meetings/{id}` | `{ok}` (hides for me only) | |
| `GET /friends` | `[{id,email,name,display_name,picture,default_lang,presence}]` presence = online / in_meeting / offline | |
| `GET /friends/requests` | inbound `{id,direction,from_user,created_at}`, outbound `{id,direction,to_email,to_user,created_at}` | |
| `GET /users/search?email=` | user card + `relationship` (friend/pending_out/pending_in/none) | 404 `USER_NOT_FOUND`, 400 `CANNOT_ADD_SELF`, 429 (20/min) |
| `POST /friends/requests {email}` | request, or `{accepted:true}` if they had already asked you | 409 `ALREADY_FRIENDS`/`REQUEST_PENDING` |
| `POST /friends/requests/{id}/accept` / `.../decline` | `{ok}` (decline also cancels your own outbound request) | 404 |
| `DELETE /friends/{user_id}` | `{ok}` | 404 `NOT_FRIENDS` |

Meeting lifecycle: a meeting is **active** until the host ends it, or until nobody has been inside for 10 minutes.
Meeting ID = LiveKit room name = `room_id` in A3-A9, format `xxx-xxxx-xxx` (a-z0-9, from `secrets`).

`WS /ws/user` (cookie auth; close 4401 not signed in, 4403 bad origin, 4429 too many tabs). Server events:
`{"type":"presence","user_id","presence"}` (friends only), `{"type":"friend_request"}`, `{"type":"friend_accepted","user_id"}`,
`{"type":"friend_removed","user_id"}`, `{"type":"invite","meeting_id","title","join_url","from_user":{id,display_name,picture}}`,
`{"type":"meeting_ended","meeting_id"}`. Client may send the text `ping` and gets `pong`.

Additions to A3: `WS /ws/room/{room_id}` and `/ws/audio/...` send `{"type":"meeting_ended"}` and close with code **4410** when the
meeting is ended (or unknown when `A10_STRICT_ROOMS=1`). `/v1/rooms/{id}/join` (legacy, unauthenticated) returns 404 in strict mode.
