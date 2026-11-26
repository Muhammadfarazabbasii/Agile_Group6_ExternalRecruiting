# Group 6 External Recruiting API (v0.1.0, Sprint 1)

Machine-readable spec: `openapi.json` (OpenAPI 3.1, 34 operations). Base URL locally: `http://localhost:8000`. After deployment on render.com the address changes; it is configuration, not code.
Live Swagger page while the backend runs: `http://localhost:8000/docs`.
All bodies are JSON. Our responses and requests use snake_case (agreed with Group 7, who use our names as they are). Everything we send to Group 7 is camelCase. IDs are text. Suppliers and framework contract references may be Group 7 IDs such as `sup-01`, everything else is a UUID. Dates are `YYYY-MM-DD`. Seniority levels are codes: `JUNIOR`, `SENIOR`, `EXPERT`.

Implemented so far: US-01 role catalogue, US-02 suppliers and framework contracts (including take-over from Group 7), US-03 contract versions with rates and comparison.
Interfaces for requests and events (US-06, US-07) are only a draft, see `openapi-draft-us06-us07.yaml`.

## Who may call what

Reading is open to everyone. Changing data needs the header `X-User-Role: SOURCING_MANAGER` (and `X-User-Name: <name>` for the audit trail).
This is a development stand-in, real authentication follows. Wrong role gives `403`.

## For other groups (read only)

| Method | Path | Returns |
|---|---|---|
| GET | `/api/catalogue` | Active role categories with their active roles (`id`, `name`) plus the seniority levels. Use these IDs as `roleId` and `seniorityLevel`. |
| GET | `/api/seniority-levels` | `[{code, label}]` in order JUNIOR, SENIOR, EXPERT |
| GET | `/api/suppliers?selectable=true` | Suppliers that can receive requests today (see rule below), each with its `id` = supplierId |
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

## Role catalogue (US-01)

Changes need the Sourcing Manager.

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

## Suppliers and framework contracts (US-02)

Changes need the Sourcing Manager.

### Supplier ID (to agree with Group 7)

The `id` of a supplier is the shared `supplierId`. It is text like `sup-01` (agreed form with Group 7: letters, digits, `. _ : -`, 1 to 64 characters, starting with a letter or digit).
- Default: Group 6 creates a UUID when the supplier is registered.
- If Group 7 already has an ID for this supplier, send it as `supplier_id` in `POST /api/suppliers`, or use the take-over below. We keep it unchanged.
- The ID cannot be changed afterwards.

### Rule: who can receive requests

A supplier is `selectable` only if both are true:
1. the supplier is active, and
2. it has a framework contract whose calculated status is `ACTIVE` today.

`not_selectable_reason` tells why not: `Supplier is deactivated`, `Framework contract has not started yet`, `Framework contract has expired`, `Framework contract is still a draft`, `Framework contract was terminated` or `No framework contract`.
US-07 (send request) uses the same rule.

### Contract status

A person sets `DRAFT`, `ACTIVE` or `TERMINATED`. The status you read is calculated from the dates every time, so no job is needed:

| Status | Meaning |
|---|---|
| `DRAFT` | Not signed off yet |
| `ACTIVE` | Set to active and today is between valid_from and valid_to (both days included) |
| `SCHEDULED` | Set to active, but valid_from is in the future |
| `EXPIRED` | Set to active, but valid_to has passed |
| `TERMINATED` | Ended by the Sourcing Manager, cannot be changed or activated again |

A supplier can have several contracts over time (for example renewals), but two `ACTIVE` contracts of the same supplier must not overlap in time (409).

### Endpoints

| Method | Path | Body | Notes |
|---|---|---|---|
| GET | `/api/suppliers?active=&selectable=` | | Filters optional. Each supplier includes its contracts |
| POST | `/api/suppliers` | `{"name": "TechCorp", "supplier_id": "sup-01, optional"}` | 201. 409 if name or ID exists |
| GET | `/api/suppliers/{id}` | | 404 if unknown |
| PATCH | `/api/suppliers/{id}` | `{"name": "TechCorp GmbH"}` | rename |
| POST | `/api/suppliers/{id}/deactivate` | | cannot receive requests anymore |
| POST | `/api/suppliers/{id}/activate` | | |
| GET | `/api/framework-contracts?supplier_id=` | | |
| POST | `/api/framework-contracts` | `{"supplier_id": "...", "reference": "fc-2027", "title": "IT Expert Services 2027 (optional)", "valid_from": "2026-01-01", "valid_to": "2026-12-31", "status": "DRAFT"}` | `status` is `DRAFT` (default) or `ACTIVE`. 409 if this supplier already has this reference (the same reference is allowed for different suppliers) or the contract overlaps an active one. 422 if valid_to is before valid_from |
| GET | `/api/framework-contracts/{id}` | | |
| PATCH | `/api/framework-contracts/{id}` | `{"reference": "...", "title": "...", "valid_from": "...", "valid_to": "..."}` | All fields optional. An empty `title` removes it. 409 if terminated |
| POST | `/api/framework-contracts/{id}/activate` | | DRAFT to ACTIVE. 409 on overlap or if terminated |
| POST | `/api/framework-contracts/{id}/terminate` | | Cannot be undone |

### Take over from Group 7 (Sourcing Manager only)

We call Group 7's API (`GET /suppliers`, `GET /framework-contracts`, address in `GROUP7_BASE_URL`, default `http://localhost:8080/api/v1`). Their contract is in `docs/group7/openapi.yaml`.

| Method | Path | Body | Notes |
|---|---|---|---|
| GET | `/api/group7/suppliers` | | Their suppliers with the framework contracts they take part in, already mapped to our statuses. `already_registered` shows if we have the supplier. 502 if Group 7 cannot be reached |
| POST | `/api/group7/import-suppliers` | `{"supplier_ids": ["sup-01", "sup-02"]}` | Per supplier `created`, `existing`, `skipped` or `not_found`, and per contract `imported` or `skipped` with the reason. Existing data is never changed. Repeating is safe |

Mapping: Group 7 supplier `id` = our supplier `id`. Group 7 contract `id` = our contract `reference`. `startDate`/`endDate` = `valid_from`/`valid_to`. `title` = `title`. Status from contract status and participation status, see README ("Decisions we made on our own"). Every take-over is written to the audit trail with action `IMPORT`.

Group 7 always includes the participations in `GET /framework-contracts`, so we read only that list. A contract is matched by the pair (contract ID, supplier ID), as Group 7 offers carry both. Their offers are not used yet (US-07).

Example `GET /api/suppliers?selectable=true`:

```json
[
  {
    "id": "db02ed83-fedf-4855-bf0c-9f420ff84b80",
    "name": "TechCorp",
    "active": true,
    "selectable": true,
    "not_selectable_reason": null,
    "current_contract": {
      "id": "14081584-42fe-450f-9189-1cbae83fe6f6",
      "supplier_id": "db02ed83-fedf-4855-bf0c-9f420ff84b80",
      "reference": "FWA-2026-001",
      "valid_from": "2026-01-01",
      "valid_to": "2026-12-31",
      "status": "ACTIVE"
    },
    "contracts": [ "... same contract objects ..." ]
  }
]
```

## Contract versions and negotiation (US-03)

A framework contract can have many versions, one per negotiation round. A version carries the price limits of that round: the maximum daily rate per role and seniority level (EUR) and an optional travel surcharge cap. Changes need the Sourcing Manager. Reading is open to everyone.

### Version status

| Status | Meaning | Who sets it |
|---|---|---|
| `DRAFT` | Being prepared | Created as draft (default) |
| `IN_NEGOTIATION` | Being negotiated | Person, from `DRAFT` |
| `ACTIVE` | The agreed price limits | Person, from `DRAFT` or `IN_NEGOTIATION` |
| `SUPERSEDED` | Replaced by a newer active version | Automatic only, when a newer version is activated |

Only one version per framework contract can be `ACTIVE`. The database enforces this as well. Activating a version sets the previous `ACTIVE` one to `SUPERSEDED`. `ACTIVE` and `SUPERSEDED` versions are read only: their rates and cap cannot be changed (409). `SUPERSEDED` is final.

### Endpoints

| Method | Path | Body | Notes |
|---|---|---|---|
| GET | `/api/framework-contracts/{id}/versions` | | All versions, oldest first, each with its rates |
| POST | `/api/framework-contracts/{id}/versions` | `{"status": "DRAFT", "version_date": "2026-11-26", "copy_previous": true}` | 201. `version_date` defaults to today. `copy_previous: true` copies the rates and travel cap of the latest version; rates of deactivated roles are left out. 409 if there is no version to copy from or the contract is terminated |
| GET | `/api/contract-versions/{id}` | | One version with its rates. `editable` tells whether it can still be changed |
| PUT | `/api/contract-versions/{id}/rates` | `{"travel_surcharge_cap": 60, "rates": [{"role_id": "...", "seniority": "SENIOR", "max_daily_rate": 850}]}` | Replaces all rates and the cap. 422 for a role that does not exist or is deactivated, a role and level given twice, or a rate not above 0. 409 if the version is `ACTIVE` or `SUPERSEDED` |
| POST | `/api/contract-versions/{id}/status` | `{"status": "IN_NEGOTIATION"}` or `{"status": "ACTIVE"}` | 409 if the move is not allowed (for example from `ACTIVE` back to `IN_NEGOTIATION`, or from `SUPERSEDED`). Activation supersedes the previous active version |
| GET | `/api/framework-contracts/{id}/versions/compare?from_version=1&to_version=2` | | Rate by rate comparison by version number. Each row: `change` (`added`, `removed`, `changed`, `unchanged`), `from_rate`, `to_rate`, `delta` (to minus from). Also the travel cap of both versions |

Example version (`GET /api/contract-versions/{id}`):

```json
{
  "id": "3f0c...",
  "framework_contract_id": "14081584-42fe-450f-9189-1cbae83fe6f6",
  "version_number": 2,
  "version_date": "2026-11-26",
  "status": "ACTIVE",
  "travel_surcharge_cap": 60.0,
  "editable": false,
  "rates": [
    { "role_id": "7c1e...", "role_name": "Backend Developer", "seniority": "SENIOR", "max_daily_rate": 850.0, "currency": "EUR" }
  ]
}
```

Every change (create, copy, rates saved, status change, activation and supersede) is written to the audit trail with entity `contract_version`.

## Audit trail (all stories)

| Method | Path | Notes |
|---|---|---|
| GET | `/api/audit-log?limit=50&entity=supplier&entity=framework_contract&entity=contract_version` | Sourcing Manager only, newest first. `entity` is optional and can be repeated. Values so far: `role_category`, `role`, `supplier`, `framework_contract`, `contract_version`. Action `IMPORT` = taken over from Group 7 |

Every change (create, rename, deactivate, activate, terminate, date change, rates saved, status change, supersede) is stored with user, time, entity, action and detail.

## Error format

```json
{ "detail": "A role category with this name already exists" }
```

Codes: `403` wrong role, `404` unknown ID, `409` conflict (duplicate, overlap, inactive parent, terminated), `422` invalid input (for example empty name or wrong date order).

## Still to be agreed with other groups

Event schemas and expert IDs, volume unit, cloud URL (see messages to Groups 1, 2, 3, 4, 5, 7).
Agreed with Group 7: naming (camelCase for what we send, snake_case for our API as it is), role IDs from `GET /api/catalogue` (we are the only owner of the catalogue), and the status mapping for the take-over.
Open with Group 7: `/sourcing-requests` and the `RequestSent` event. Group 7 is waiting for our draft.
