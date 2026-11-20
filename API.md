# Group 6 External Recruiting API (v0.1.0, Sprint 1)

Machine-readable spec: `openapi.json` (OpenAPI 3). Base URL for now: `http://localhost:8000` (cloud URL follows in Sprint 2).
All bodies are JSON. IDs are UUID strings. Seniority levels are codes: `JUNIOR`, `SENIOR`, `EXPERT`.

## Who may call what

Reading is open to everyone. Changing data needs the header `X-User-Role: SOURCING_MANAGER` (and `X-User-Name: <name>` for the audit trail).
This is a development stand-in, real authentication follows. Wrong role gives `403`.

## For other groups (read only)

| Method | Path | Returns |
|---|---|---|
| GET | `/api/catalogue` | Active role categories with their active roles (`id`, `name`) plus the seniority levels. Use these IDs as `roleId` and `seniorityLevel`. |
| GET | `/api/seniority-levels` | `[{code, label}]` in order JUNIOR, SENIOR, EXPERT |
| GET | `/health` | `{"status": "ok"}` |

Example `GET /api/catalogue`:

```json
{
  "categories": [
    { "id": "d37aab43-bb8c-4791-b386-f36d0478cea1", "name": "Development",
      "roles": [ { "id": "7c1e...", "name": "Java Developer" } ] }
  ],
  "seniority_levels": [
    { "code": "JUNIOR", "label": "Junior" },
    { "code": "SENIOR", "label": "Senior" },
    { "code": "EXPERT", "label": "Expert" }
  ]
}
```

## Catalogue management (Sourcing Manager only for changes)

| Method | Path | Body | Notes |
|---|---|---|---|
| GET | `/api/role-categories?active=true` | | `active` filter optional |
| POST | `/api/role-categories` | `{"name": "Development"}` | 201, 409 if name exists |
| PATCH | `/api/role-categories/{id}` | `{"name": "Software"}` | rename |
| POST | `/api/role-categories/{id}/deactivate` | | also deactivates its roles |
| POST | `/api/role-categories/{id}/activate` | | roles stay inactive |
| GET | `/api/roles?active=true&category_id=...` | | filters optional |
| POST | `/api/roles` | `{"category_id": "...", "name": "Java Developer"}` | 409 if duplicate or category inactive |
| PATCH | `/api/roles/{id}` | `{"name": "Backend Developer"}` | rename |
| POST | `/api/roles/{id}/deactivate` | | cannot be used in new requests |
| POST | `/api/roles/{id}/activate` | | 409 if category inactive |
| GET | `/api/audit-log?limit=50` | | Sourcing Manager only, newest first |

## Error format

```json
{ "detail": "A role category with this name already exists" }
```

Codes: `403` wrong role, `404` unknown ID, `409` conflict (duplicate or inactive parent), `422` invalid input (for example empty name).

## Still to be agreed with other groups

Event schemas, supplier and expert IDs, volume unit, cloud URL (see messages to Groups 1, 2, 3, 4, 5, 7).
