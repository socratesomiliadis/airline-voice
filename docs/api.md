# Reserved API surface

Only `GET /health` is implemented. It returns `{"status":"ok","mode":"scaffold"}`.
FastAPI also serves `/docs`, `/redoc`, and `/openapi.json`.

Every endpoint below is prefixed with `/api/v1`, returns HTTP `501`, and performs
no work. The JSON response is
`{"detail":{"code":"not_implemented","feature":"<module>.<handler>"}}`.
Domain request and response schemas are deliberately not defined yet.

| Method | Path | Reserved purpose |
| --- | --- | --- |
| GET | `/bookings` | List bookings |
| POST | `/bookings` | Book a flight |
| POST | `/bookings/{booking_id}/cancel` | Cancel a booking |
| POST | `/bookings/{booking_id}/reschedule` | Reschedule a booking |
| POST | `/baggage/inquiries` | Baggage inquiry |
| POST | `/requests` | Other customer requests |
| GET | `/conversations` | List conversations |
| GET | `/conversations/{conversation_id}` | Conversation detail |
| GET | `/knowledge/documents` | List knowledge documents |
| POST | `/knowledge/documents` | Ingest a knowledge document |
| POST | `/knowledge/search` | Search knowledge |
| POST | `/voice/sessions` | Create a voice session |
| POST | `/voice/webhooks/elevenlabs` | Receive an ElevenLabs webhook |
| GET | `/monitoring/events` | Monitoring event stream |
| POST | `/refinement/runs` | Start a refinement run |
| GET | `/refinement/iterations` | Iteration history |
| GET | `/refinement/evaluations` | Evaluation history |
| GET | `/refinement/changes` | Code and prompt changes |

ID path parameters currently use UUID parsing; malformed IDs receive FastAPI's
standard `422` validation response before reaching the placeholder. Webhook
signatures are not verified and requests are not accepted for processing.
