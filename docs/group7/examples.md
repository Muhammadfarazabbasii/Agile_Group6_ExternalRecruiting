# Sample payloads – Group 7 (Expert Supplier)

Example values for illustration only. Full contract: [`openapi.yaml`](openapi.yaml).

## Integration approach

| Consumer | How | What |
|---|---|---|
| Group 6 (External Recruiting) | REST calls in both directions | Framework contracts and max. daily rates, sourcing requests (in), offers (out), decisions (in) |
| Group 5 (People Analytics) | Pull: `GET /events?since=…` and list endpoints with `updatedSince` | Initial snapshot (call without `since`), then incremental updates |
| Groups 2, 3, 4 | Webhook push (`POST /webhooks`) or event feed | `ExpertAssigned`, `AssignmentExtended`, `ExpertReplaced`, `AssignmentEnded` |

**Identifiers.** External experts are not employees, so we expose a stable pseudonymised `pseudonymId` (e.g. `ext-7f3a9c`) instead of names. Request, department and role ids are taken over from Group 6 and the shared role catalogue; we do not create our own department ids.

## `GET /framework-contracts/fc-2027/max-daily-rates?roleId=role-backend`

```json
[
  { "participationId": "part-01", "supplierId": "sup-01", "roleId": "role-backend", "seniority": "SENIOR", "maxRate": { "amount": 900, "currency": "EUR" } },
  { "participationId": "part-02", "supplierId": "sup-02", "roleId": "role-backend", "seniority": "SENIOR", "maxRate": { "amount": 870, "currency": "EUR" } }
]
```

## `POST /offers` → `201`

```json
{
  "id": "off-311",
  "requestId": "req-104",
  "expertId": "exp-017",
  "supplierId": "sup-01",
  "contractId": "fc-2027",
  "dailyRate": { "amount": 850, "currency": "EUR" },
  "travelSurcharge": { "amount": 50, "currency": "EUR" },
  "status": "draft",
  "updatedAt": "2026-11-20T10:15:00Z"
}
```

If the daily rate is above the supplier's maximum for that role and level → `422` with `{ "code": "RATE_ABOVE_MAXIMUM" }`.

## Event: `ExpertAssigned` (from `GET /events` or webhook)

```json
{
  "eventId": "6c1e0a52-8a1f-4a5e-9b8e-2f0c4d7b9e11",
  "type": "ExpertAssigned",
  "occurredAt": "2026-11-20T10:42:00Z",
  "source": "group7-expert-supplier",
  "data": {
    "assignmentId": "asg-052",
    "offerId": "off-311",
    "requestId": "req-104",
    "expertPseudonymId": "ext-7f3a9c",
    "supplierId": "sup-01",
    "roleCategory": "Development",
    "roleId": "role-backend",
    "seniority": "SENIOR",
    "departmentId": "dep-it-04",
    "startDate": "2027-02-01",
    "endDate": "2027-06-30",
    "dailyRate": { "amount": 850, "currency": "EUR" }
  }
}
```

## Fields useful for Group 5 KPIs

- Requests per role category and role, time from request to first offer and to decision (`occurredAt` of `SourcingRequestReceived`, `OfferSubmitted`, `OfferAccepted`)
- Offers per request, acceptance rate per supplier
- Agreed daily rate vs. maximum daily rate per role and level
- Number and duration of active external assignments per department and role category
- Extensions, replacements and early ends
