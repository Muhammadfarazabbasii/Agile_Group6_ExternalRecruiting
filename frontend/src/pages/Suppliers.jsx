import { useCallback, useEffect, useRef, useState } from "react";
import { api } from "../api.js";

// US-02 page: supplier list, supplier detail with framework contracts, audit trail.
// The logged-in user (userKey, canEdit) comes from App.jsx.

const STATUS_HELP = {
  DRAFT: "Not signed off yet",
  ACTIVE: "Valid today",
  SCHEDULED: "Starts in the future",
  EXPIRED: "Valid-to date has passed",
  TERMINATED: "Ended by the Sourcing Manager",
};

export default function Suppliers({ userKey, canEdit }) {
  const [suppliers, setSuppliers] = useState([]);
  const [audit, setAudit] = useState([]);
  const [selectedId, setSelectedId] = useState(null);
  const [showInactive, setShowInactive] = useState(false);
  const [onlySelectable, setOnlySelectable] = useState(false);
  const [error, setError] = useState("");
  const latest = useRef(0);

  // keepError: after a failed action the error message must stay visible while the data reloads.
  // All requests start together, so they use the same user. An older answer is dropped when a newer load started.
  const loadAll = useCallback(async (keepError = false) => {
    const id = ++latest.current;
    try {
      const [list, auditRows] = await Promise.all([
        api.suppliers(),
        canEdit ? api.auditLog(["supplier", "framework_contract"]) : Promise.resolve([]),
      ]);
      if (id !== latest.current) return;
      setSuppliers(list);
      setAudit(auditRows);
      if (!keepError) setError("");
    } catch (e) {
      if (id !== latest.current) return;
      setError(e.message === "Failed to fetch" ? "Cannot reach the backend. Is it running on port 8000?" : e.message);
    }
  }, [canEdit]);

  useEffect(() => {
    loadAll();
  }, [userKey, loadAll]);

  // Runs an API action, shows errors, reloads the data. Returns true when the action worked.
  async function run(action) {
    let ok = true;
    try {
      await action();
      setError("");
    } catch (e) {
      setError(e.message);
      ok = false;
    }
    await loadAll(!ok);
    return ok;
  }

  const visible = suppliers.filter((s) => (showInactive || s.active) && (!onlySelectable || s.selectable));
  const selected = suppliers.find((s) => s.id === selectedId) || null;

  return (
    <>
      {error && <div className="error">{error}</div>}

      <section className="card">
        <h2>Suppliers</h2>
        <p className="muted">
          A supplier can receive requests only if it is active and has a framework contract that is valid today.
        </p>
        {canEdit && <AddSupplierForm onAdd={(name, supplierId) => run(() => api.createSupplier(name, supplierId))} />}
        {canEdit && <Group7Import onImported={() => loadAll()} />}
        <div className="filters">
          <label className="checkbox">
            <input type="checkbox" checked={showInactive} onChange={(e) => setShowInactive(e.target.checked)} />
            Show deactivated suppliers
          </label>
          <label className="checkbox">
            <input type="checkbox" checked={onlySelectable} onChange={(e) => setOnlySelectable(e.target.checked)} />
            Only suppliers that can receive requests
          </label>
        </div>
        <div className="scroll">
          <table>
            <thead>
              <tr>
                <th>Name</th>
                <th>Contract today</th>
                <th>Can receive requests</th>
                <th></th>
              </tr>
            </thead>
            <tbody>
              {visible.length === 0 && (
                <tr>
                  <td colSpan={4} className="muted">No suppliers to show.</td>
                </tr>
              )}
              {visible.map((s) => (
                <tr key={s.id} className={s.active ? "" : "inactive"}>
                  <td>
                    {s.name}
                    {!s.active && <span className="tag"> deactivated</span>}
                  </td>
                  <td>{s.current_contract ? <StatusPill status="ACTIVE" /> : <span className="muted">none</span>}</td>
                  <td>
                    {s.selectable ? (
                      <span className="yes">Yes</span>
                    ) : (
                      <span className="no" title={s.not_selectable_reason}>No · {s.not_selectable_reason}</span>
                    )}
                  </td>
                  <td className="actions">
                    <button onClick={() => setSelectedId(s.id === selectedId ? null : s.id)}>
                      {s.id === selectedId ? "Close" : "Open"}
                    </button>
                    {canEdit &&
                      (s.active ? (
                        <button
                          className="danger"
                          onClick={() => {
                            if (window.confirm(`Deactivate "${s.name}"? It can no longer receive requests.`))
                              run(() => api.deactivateSupplier(s.id));
                          }}
                        >
                          Deactivate
                        </button>
                      ) : (
                        <button onClick={() => run(() => api.activateSupplier(s.id))}>Activate</button>
                      ))}
                  </td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      </section>

      {selected && <SupplierDetail supplier={selected} canEdit={canEdit} run={run} />}

      {canEdit && (
        <section className="card">
          <h2>Audit trail</h2>
          <p className="muted">Latest 50 changes to suppliers and contracts: who, when, what.</p>
          <div className="scroll">
            <table>
              <thead>
                <tr>
                  <th>Time</th>
                  <th>User</th>
                  <th>Entity</th>
                  <th>Action</th>
                  <th>Detail</th>
                </tr>
              </thead>
              <tbody>
                {audit.length === 0 && (
                  <tr>
                    <td colSpan={5} className="muted">No changes yet.</td>
                  </tr>
                )}
                {audit.map((a) => (
                  <tr key={a.id}>
                    <td>{new Date(a.created_at).toLocaleString()}</td>
                    <td>{a.actor}</td>
                    <td>{a.entity}</td>
                    <td>{a.action}</td>
                    <td>{a.detail}</td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        </section>
      )}
    </>
  );
}

function StatusPill({ status }) {
  return (
    <span className={`pill st-${status.toLowerCase()}`} title={STATUS_HELP[status]}>
      {status}
    </span>
  );
}

function SupplierDetail({ supplier, canEdit, run }) {
  const [name, setName] = useState(supplier.name);
  const [editingId, setEditingId] = useState(null);
  const [copied, setCopied] = useState("");

  // Show the newest name when another supplier is opened or the data reloads.
  useEffect(() => {
    setName(supplier.name);
    setEditingId(null);
  }, [supplier.id, supplier.name]);

  function copyId() {
    const done = () => setCopied("Copied");
    const fail = () => setCopied("Select the ID and copy it by hand");
    if (navigator.clipboard && navigator.clipboard.writeText) navigator.clipboard.writeText(supplier.id).then(done, fail);
    else fail();
  }

  function saveName(e) {
    e.preventDefault();
    if (name.trim() && name.trim() !== supplier.name) run(() => api.renameSupplier(supplier.id, name.trim()));
  }

  return (
    <section className="card">
      <h2>{supplier.name}</h2>
      <dl className="facts">
        <dt>Supplier ID</dt>
        <dd>
          <code className="idtext">{supplier.id}</code>{" "}
          <button type="button" onClick={copyId}>Copy</button> <span className="muted">{copied}</span>
          <div className="muted">This is the ID we share with Group 7.</div>
        </dd>
        <dt>Status</dt>
        <dd>{supplier.active ? "Active" : "Deactivated"}</dd>
        <dt>Can receive requests</dt>
        <dd>{supplier.selectable ? "Yes" : `No · ${supplier.not_selectable_reason}`}</dd>
      </dl>

      {canEdit && (
        <form className="add-form" onSubmit={saveName}>
          <label className="inline" htmlFor="supplier-name">Name</label>
          <input id="supplier-name" value={name} onChange={(e) => setName(e.target.value)} maxLength={100} />
          <button type="submit" className="primary">Save name</button>
        </form>
      )}

      <h3>Framework contracts</h3>
      <div className="scroll">
        <table>
          <thead>
            <tr>
              <th>Reference</th>
              <th>Title</th>
              <th>Valid from</th>
              <th>Valid to</th>
              <th>Status</th>
              {canEdit && <th></th>}
            </tr>
          </thead>
          <tbody>
            {supplier.contracts.length === 0 && (
              <tr>
                <td colSpan={6} className="muted">No framework contract yet.</td>
              </tr>
            )}
            {supplier.contracts.map((c) =>
              editingId === c.id ? (
                <tr key={c.id}>
                  <td colSpan={6}>
                    <ContractForm
                      initial={c}
                      submitLabel="Save contract"
                      onCancel={() => setEditingId(null)}
                      onSave={async (body) => {
                        const ok = await run(() => api.updateContract(c.id, body));
                        if (ok) setEditingId(null);
                        return ok;
                      }}
                    />
                  </td>
                </tr>
              ) : (
                <tr key={c.id} className={c.status === "EXPIRED" || c.status === "TERMINATED" ? "inactive" : ""}>
                  <td>{c.reference}</td>
                  <td>{c.title || <span className="muted">-</span>}</td>
                  <td>{c.valid_from}</td>
                  <td>{c.valid_to}</td>
                  <td>
                    <StatusPill status={c.status} />
                  </td>
                  {canEdit && (
                    <td className="actions">
                      {c.status !== "TERMINATED" && <button onClick={() => setEditingId(c.id)}>Edit</button>}
                      {c.status === "DRAFT" && <button onClick={() => run(() => api.activateContract(c.id))}>Activate</button>}
                      {c.status !== "TERMINATED" && (
                        <button
                          className="danger"
                          onClick={() => {
                            if (window.confirm(`Terminate contract ${c.reference}? This cannot be undone.`))
                              run(() => api.terminateContract(c.id));
                          }}
                        >
                          Terminate
                        </button>
                      )}
                    </td>
                  )}
                </tr>
              )
            )}
          </tbody>
        </table>
      </div>
      <p className="muted legend">
        {Object.entries(STATUS_HELP).map(([k, v]) => `${k}: ${v}`).join(" · ")}
      </p>

      {canEdit && (
        <>
          <h3>Add a framework contract</h3>
          <ContractForm
            submitLabel="Add contract"
            showStatus
            resetOnSave
            onSave={(body) => run(() => api.createContract({ ...body, supplier_id: supplier.id }))}
          />
        </>
      )}
    </section>
  );
}

// Used to add a contract and to edit one. Dates are plain YYYY-MM-DD.
function ContractForm({ initial, submitLabel, showStatus, resetOnSave, onSave, onCancel }) {
  const [reference, setReference] = useState(initial ? initial.reference : "");
  const [title, setTitle] = useState(initial ? initial.title || "" : "");
  const [validFrom, setValidFrom] = useState(initial ? initial.valid_from : "");
  const [validTo, setValidTo] = useState(initial ? initial.valid_to : "");
  const [status, setStatus] = useState("DRAFT");
  const key = initial ? initial.id : "new";

  async function submit(e) {
    e.preventDefault();
    if (!reference.trim() || !validFrom || !validTo) return;
    const body = { reference: reference.trim(), valid_from: validFrom, valid_to: validTo };
    // When editing, an empty title removes it. When adding, an empty title is simply left out.
    if (initial || title.trim()) body.title = title.trim();
    if (showStatus) body.status = status;
    const ok = await onSave(body);
    if (ok && resetOnSave) {
      setReference("");
      setTitle("");
      setValidFrom("");
      setValidTo("");
      setStatus("DRAFT");
    }
  }

  return (
    <form className="contract-form" onSubmit={submit}>
      <label htmlFor={`ref-${key}`}>
        Reference
        <input id={`ref-${key}`} value={reference} onChange={(e) => setReference(e.target.value)} placeholder="e.g. fc-2027" maxLength={100} required />
      </label>
      <label htmlFor={`title-${key}`}>
        Title (optional)
        <input id={`title-${key}`} value={title} onChange={(e) => setTitle(e.target.value)} placeholder="e.g. IT Expert Services 2027" maxLength={200} />
      </label>
      <label htmlFor={`from-${key}`}>
        Valid from
        <input id={`from-${key}`} type="date" value={validFrom} onChange={(e) => setValidFrom(e.target.value)} required />
      </label>
      <label htmlFor={`to-${key}`}>
        Valid to
        <input id={`to-${key}`} type="date" value={validTo} min={validFrom || undefined} onChange={(e) => setValidTo(e.target.value)} required />
      </label>
      {showStatus && (
        <label htmlFor={`status-${key}`}>
          Status
          <select id={`status-${key}`} value={status} onChange={(e) => setStatus(e.target.value)}>
            <option value="DRAFT">Draft</option>
            <option value="ACTIVE">Active</option>
          </select>
        </label>
      )}
      <div className="form-actions">
        <button type="submit" className="primary">{submitLabel}</button>
        {onCancel && <button type="button" onClick={onCancel}>Cancel</button>}
      </div>
    </form>
  );
}

// Name field plus an optional supplier ID, for a supplier that Group 7 already knows.
function AddSupplierForm({ onAdd }) {
  const [name, setName] = useState("");
  const [supplierId, setSupplierId] = useState("");

  async function submit(e) {
    e.preventDefault();
    if (!name.trim()) return;
    const ok = await onAdd(name.trim(), supplierId.trim());
    if (ok) {
      setName("");
      setSupplierId("");
    }
  }

  return (
    <form className="add-form" onSubmit={submit}>
      <input id="new-supplier-name" value={name} onChange={(e) => setName(e.target.value)} placeholder="New supplier name" maxLength={100} aria-label="New supplier name" />
      <input
        id="new-supplier-id"
        value={supplierId}
        onChange={(e) => setSupplierId(e.target.value)}
        placeholder="Supplier ID from Group 7, e.g. sup-01 (optional)"
        aria-label="Supplier ID from Group 7, optional"
      />
      <button type="submit" className="primary">Add supplier</button>
    </form>
  );
}

// US-02: look at what Group 7 has and take over the chosen suppliers with their framework contracts.
function Group7Import({ onImported }) {
  const [open, setOpen] = useState(false);
  const [rows, setRows] = useState(null);
  const [chosen, setChosen] = useState([]);
  const [results, setResults] = useState(null);
  const [message, setMessage] = useState("");
  const [busy, setBusy] = useState(false);

  async function load() {
    setBusy(true);
    setMessage("");
    setResults(null);
    try {
      setRows(await api.group7Suppliers());
      setChosen([]);
    } catch (e) {
      setRows(null);
      setMessage(e.message === "Failed to fetch" ? "Cannot reach our backend." : e.message);
    }
    setBusy(false);
  }

  function toggleOpen() {
    const next = !open;
    setOpen(next);
    if (next && rows === null) load();
  }

  async function doImport() {
    setBusy(true);
    setMessage("");
    try {
      setResults(await api.importGroup7Suppliers(chosen));
      onImported();
      setRows(await api.group7Suppliers());
      setChosen([]);
    } catch (e) {
      setMessage(e.message);
    }
    setBusy(false);
  }

  const toggle = (id) => setChosen((c) => (c.includes(id) ? c.filter((x) => x !== id) : [...c, id]));

  return (
    <div className="g7-panel">
      <button type="button" onClick={toggleOpen} aria-expanded={open}>
        {open ? "Hide Group 7 suppliers" : "Take over suppliers from Group 7"}
      </button>
      {open && (
        <div className="g7-body">
          <p className="muted">
            Suppliers and framework contracts as Group 7 (Expert Supplier) has them. Choose the suppliers that become pre-selected
            suppliers of ours. The same IDs are used on both sides. Nothing is changed if a supplier or contract already exists.
          </p>
          <button type="button" onClick={load} disabled={busy}>Refresh</button>
          {message && <div className="error" role="alert">{message}</div>}
          {rows && (
            <div className="scroll">
              <table>
                <thead>
                  <tr>
                    <th></th>
                    <th>Supplier (Group 7)</th>
                    <th>Group 7 status</th>
                    <th>Framework contracts and how we would register them</th>
                  </tr>
                </thead>
                <tbody>
                  {rows.length === 0 && (
                    <tr><td colSpan={4} className="muted">Group 7 has no suppliers.</td></tr>
                  )}
                  {rows.map((r) => (
                    <tr key={r.supplier_id} className={r.already_registered ? "inactive" : ""}>
                      <td>
                        <input
                          type="checkbox"
                          aria-label={`Take over ${r.name}`}
                          disabled={r.already_registered}
                          checked={chosen.includes(r.supplier_id)}
                          onChange={() => toggle(r.supplier_id)}
                        />
                      </td>
                      <td>
                        {r.name} <code className="idtext">{r.supplier_id}</code>
                        {r.already_registered && <span className="tag"> already ours</span>}
                      </td>
                      <td>{r.group7_status || "-"}</td>
                      <td>
                        {r.contracts.length === 0 && <span className="muted">no framework contract</span>}
                        {r.contracts.map((c) => (
                          <div key={c.reference}>
                            <strong>{c.reference}</strong> {c.valid_from} to {c.valid_to}
                            {" · "}
                            {c.problem ? <span className="no">{c.problem}</span> : <>Group 7: {c.participation_status} in {c.group7_contract_status} contract, we register <StatusPill status={c.mapped_status} /></>}
                          </div>
                        ))}
                      </td>
                    </tr>
                  ))}
                </tbody>
              </table>
            </div>
          )}
          <button type="button" className="primary" disabled={busy || chosen.length === 0} onClick={doImport}>
            Take over {chosen.length || ""} selected
          </button>
          {results && (
            <ul className="g7-results" aria-label="Import result">
              {results.map((r) => (
                <li key={r.supplier_id}>
                  <strong>{r.name || r.supplier_id}</strong>: {r.message}
                  <ul>
                    {r.contracts.map((c) => (
                      <li key={c.reference}>{c.reference}: {c.message}</li>
                    ))}
                  </ul>
                </li>
              ))}
            </ul>
          )}
        </div>
      )}
    </div>
  );
}
