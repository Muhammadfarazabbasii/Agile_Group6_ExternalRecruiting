import { Fragment, useCallback, useEffect, useState } from "react";
import { api } from "../api.js";

// US-03 panel: the negotiation rounds (versions) of one framework contract, each with its price limits (rates).
// The Sourcing Manager creates versions, moves them on and edits rates while a version is DRAFT or IN_NEGOTIATION.
// Everybody can read the versions and compare any two of them.
// Changes go through `run` from the Suppliers page: errors show at the top and the audit trail reloads.

const VERSION_HELP = {
  DRAFT: "Being prepared, rates can be changed",
  IN_NEGOTIATION: "In negotiation, rates can be changed",
  ACTIVE: "The agreed price limits, read only",
  SUPERSEDED: "Replaced by a newer active version, read only, kept for history",
};

export default function ContractVersions({ contract, canEdit, run }) {
  const [versions, setVersions] = useState(null);
  const [catalogue, setCatalogue] = useState(null);
  const [message, setMessage] = useState("");
  const [openRatesId, setOpenRatesId] = useState(null);
  const [editingId, setEditingId] = useState(null);
  const [pickedFrom, setPickedFrom] = useState(null);
  const [pickedTo, setPickedTo] = useState(null);
  const [comparison, setComparison] = useState(null);

  const load = useCallback(async () => {
    try {
      setVersions(await api.versions(contract.id));
      setMessage("");
    } catch (e) {
      setMessage(e.message);
    }
  }, [contract.id]);

  useEffect(() => {
    load();
  }, [load]);

  useEffect(() => {
    api.catalogue().then(setCatalogue).catch(() => setCatalogue(null));
  }, []);

  // Two version numbers to compare. By default the last two versions.
  const numbers = versions ? versions.map((v) => v.version_number) : [];
  const from = numbers.includes(pickedFrom) ? pickedFrom : numbers[numbers.length - 2];
  const to = numbers.includes(pickedTo) ? pickedTo : numbers[numbers.length - 1];

  useEffect(() => {
    if (from === undefined || to === undefined) {
      setComparison(null);
      return undefined;
    }
    let cancelled = false;
    api
      .compareVersions(contract.id, from, to)
      .then((result) => !cancelled && setComparison(result))
      .catch((e) => !cancelled && setMessage(e.message));
    return () => {
      cancelled = true;
    };
  }, [contract.id, from, to, versions]);

  // Runs a change through the page (errors, audit trail), then reloads this panel's versions.
  async function act(action) {
    const ok = await run(action);
    await load();
    return ok;
  }

  function activate(version) {
    const current = versions.find((v) => v.status === "ACTIVE");
    const note = current ? ` Version ${current.version_number} will be set to SUPERSEDED.` : "";
    if (window.confirm(`Activate version ${version.version_number} of ${contract.reference}?${note}`)) {
      act(() => api.changeVersionStatus(version.id, "ACTIVE"));
    }
  }

  if (!versions) {
    return (
      <div className="version-panel">
        <h3>Versions of {contract.reference}</h3>
        {message ? <div className="error" role="alert">{message}</div> : <p className="muted">Loading versions...</p>}
      </div>
    );
  }

  const terminated = contract.status === "TERMINATED";

  return (
    <div className="version-panel">
      <h3>Versions of {contract.reference}</h3>
      <p className="muted">
        Each negotiation round is a version with its price limits (maximum daily rate per role and seniority level).
        Only one version can be ACTIVE. Activating a new version sets the previous active one to SUPERSEDED.
      </p>
      {message && <div className="error" role="alert">{message}</div>}

      {versions.length === 0 && <p className="muted">No versions yet.</p>}
      {versions.length > 0 && (
        <div className="scroll">
          <table>
            <thead>
              <tr>
                <th>No.</th>
                <th>Date</th>
                <th>Status</th>
                <th>Rates</th>
                <th>Travel cap</th>
                <th></th>
              </tr>
            </thead>
            <tbody>
              {versions.map((v) => (
                <Fragment key={v.id}>
                  <tr className={v.status === "SUPERSEDED" ? "inactive" : ""}>
                    <td>{v.version_number}</td>
                    <td>{v.version_date}</td>
                    <td>
                      <VersionPill status={v.status} />
                    </td>
                    <td>{v.rates.length}</td>
                    <td>{formatMoney(v.travel_surcharge_cap)}</td>
                    <td className="actions">
                      <button onClick={() => setOpenRatesId(openRatesId === v.id ? null : v.id)}>
                        {openRatesId === v.id ? "Hide rates" : "Rates"}
                      </button>
                      {canEdit && v.status === "DRAFT" && (
                        <button onClick={() => act(() => api.changeVersionStatus(v.id, "IN_NEGOTIATION"))}>
                          Start negotiation
                        </button>
                      )}
                      {canEdit && v.editable && (
                        <button className="primary" onClick={() => activate(v)}>
                          Activate
                        </button>
                      )}
                    </td>
                  </tr>
                  {openRatesId === v.id && (
                    <tr>
                      <td colSpan={6}>
                        {editingId === v.id ? (
                          <RateEditor
                            version={v}
                            catalogue={catalogue}
                            onCancel={() => setEditingId(null)}
                            onSave={async (body) => {
                              const ok = await act(() => api.saveRates(v.id, body));
                              if (ok) setEditingId(null);
                              return ok;
                            }}
                          />
                        ) : (
                          <RateTable version={v} canEdit={canEdit} onEdit={() => setEditingId(v.id)} />
                        )}
                      </td>
                    </tr>
                  )}
                </Fragment>
              ))}
            </tbody>
          </table>
        </div>
      )}
      <p className="muted legend">
        {Object.entries(VERSION_HELP).map(([k, text]) => `${k}: ${text}`).join(" · ")}
      </p>

      {canEdit && !terminated && (
        <>
          <h3>New negotiation round</h3>
          <NewVersionForm
            previousNumber={versions.length ? versions[versions.length - 1].version_number : undefined}
            onCreate={(body) => act(() => api.createVersion(contract.id, body))}
          />
        </>
      )}
      {terminated && <p className="muted">The framework contract is terminated, so no new versions can be created.</p>}

      {numbers.length >= 2 && (
        <>
          <h3>Compare versions</h3>
          <div className="compare-controls">
            <label>
              From version
              <select value={from} onChange={(e) => setPickedFrom(Number(e.target.value))}>
                {numbers.map((n) => (
                  <option key={n} value={n}>{n}</option>
                ))}
              </select>
            </label>
            <label>
              To version
              <select value={to} onChange={(e) => setPickedTo(Number(e.target.value))}>
                {numbers.map((n) => (
                  <option key={n} value={n}>{n}</option>
                ))}
              </select>
            </label>
          </div>
          {comparison && <CompareTable comparison={comparison} />}
        </>
      )}
    </div>
  );
}

function VersionPill({ status }) {
  return <span className={`pill st-${status.toLowerCase()}`} title={VERSION_HELP[status]}>{status}</span>;
}

function formatMoney(value) {
  return value == null ? <span className="muted">-</span> : `${value} EUR`;
}

function RateTable({ version, canEdit, onEdit }) {
  return (
    <div>
      <p className="muted">Travel surcharge cap: {formatMoney(version.travel_surcharge_cap)}</p>
      {version.rates.length === 0 ? (
        <p className="muted">No rates yet.</p>
      ) : (
        <table>
          <thead>
            <tr>
              <th>Role</th>
              <th>Seniority</th>
              <th>Maximum daily rate</th>
            </tr>
          </thead>
          <tbody>
            {version.rates.map((r) => (
              <tr key={`${r.role_id}-${r.seniority}`}>
                <td>{r.role_name}</td>
                <td>{r.seniority}</td>
                <td>{r.max_daily_rate} {r.currency}</td>
              </tr>
            ))}
          </tbody>
        </table>
      )}
      {canEdit && version.editable && (
        <div className="form-actions mt">
          <button onClick={onEdit}>Edit rates</button>
        </div>
      )}
    </div>
  );
}

// Replaces all rates of a version. Roles come from the catalogue (US-01), so the IDs match the other groups.
function RateEditor({ version, catalogue, onSave, onCancel }) {
  const roleOptions = buildRoleOptions(catalogue, version.rates);
  const [cap, setCap] = useState(version.travel_surcharge_cap == null ? "" : String(version.travel_surcharge_cap));
  const [rows, setRows] = useState(() =>
    version.rates.map((r) => ({ role_id: r.role_id, seniority: r.seniority, rate: String(r.max_daily_rate) }))
  );
  const [problem, setProblem] = useState("");
  const [busy, setBusy] = useState(false);

  const update = (index, field, value) =>
    setRows((list) => list.map((row, i) => (i === index ? { ...row, [field]: value } : row)));
  const addRow = () =>
    setRows((list) => [...list, { role_id: roleOptions[0] ? roleOptions[0].id : "", seniority: "SENIOR", rate: "" }]);
  const removeRow = (index) => setRows((list) => list.filter((_, i) => i !== index));

  async function save() {
    if (rows.some((r) => !r.role_id || !(Number(r.rate) > 0))) {
      setProblem("Every row needs a role and a rate above zero. Remove the rows you do not need.");
      return;
    }
    const seen = new Set(rows.map((r) => `${r.role_id}|${r.seniority}`));
    if (seen.size !== rows.length) {
      setProblem("Each role and seniority level can only appear once.");
      return;
    }
    setProblem("");
    setBusy(true);
    await onSave({
      travel_surcharge_cap: cap.trim() === "" ? null : Number(cap),
      rates: rows.map((r) => ({ role_id: r.role_id, seniority: r.seniority, max_daily_rate: Number(r.rate) })),
    });
    setBusy(false);
  }

  if (catalogue === null) {
    return (
      <div>
        <p className="muted">The role list could not be loaded, so rates cannot be edited right now.</p>
        <button onClick={onCancel}>Close</button>
      </div>
    );
  }

  return (
    <div className="rate-editor">
      {problem && <div className="error" role="alert">{problem}</div>}
      <label className="inline" htmlFor={`cap-${version.id}`}>
        Travel surcharge cap (EUR, optional)
        <input
          id={`cap-${version.id}`}
          type="number"
          min="0"
          step="0.01"
          value={cap}
          onChange={(e) => setCap(e.target.value)}
        />
      </label>
      {rows.map((row, i) => (
        <div className="rate-row" key={i}>
          <select aria-label="Role" value={row.role_id} onChange={(e) => update(i, "role_id", e.target.value)}>
            {roleOptions.map((o) => (
              <option key={o.id} value={o.id}>{o.label}</option>
            ))}
          </select>
          <select aria-label="Seniority" value={row.seniority} onChange={(e) => update(i, "seniority", e.target.value)}>
            <option value="JUNIOR">JUNIOR</option>
            <option value="SENIOR">SENIOR</option>
            <option value="EXPERT">EXPERT</option>
          </select>
          <input
            aria-label="Maximum daily rate in EUR"
            type="number"
            min="0.01"
            step="0.01"
            placeholder="Max. daily rate (EUR)"
            value={row.rate}
            onChange={(e) => update(i, "rate", e.target.value)}
          />
          <button type="button" className="danger" onClick={() => removeRow(i)}>Remove</button>
        </div>
      ))}
      <div className="form-actions mt">
        <button type="button" onClick={addRow} disabled={roleOptions.length === 0}>Add rate</button>
        <button type="button" className="primary" onClick={save} disabled={busy}>Save rates</button>
        <button type="button" onClick={onCancel}>Cancel</button>
      </div>
    </div>
  );
}

// Active roles from the catalogue. A role that is deactivated but still has a rate in this version is kept in the list.
function buildRoleOptions(catalogue, currentRates) {
  const options = [];
  for (const category of catalogue ? catalogue.categories : []) {
    for (const role of category.roles) {
      options.push({ id: role.id, label: `${category.name}: ${role.name}` });
    }
  }
  for (const rate of currentRates) {
    if (!options.some((o) => o.id === rate.role_id)) {
      options.push({ id: rate.role_id, label: `${rate.role_name} (deactivated)` });
    }
  }
  return options;
}

function NewVersionForm({ previousNumber, onCreate }) {
  const hasPrevious = previousNumber !== undefined;
  const [date, setDate] = useState(todayIso());
  const [status, setStatus] = useState("DRAFT");
  const [copy, setCopy] = useState(false);
  const [busy, setBusy] = useState(false);

  async function submit(e) {
    e.preventDefault();
    if (!date) return;
    setBusy(true);
    await onCreate({ version_date: date, status, copy_previous: hasPrevious && copy });
    setBusy(false);
  }

  return (
    <form className="contract-form" onSubmit={submit}>
      <label htmlFor="new-version-date">
        Negotiation date
        <input id="new-version-date" type="date" value={date} onChange={(e) => setDate(e.target.value)} required />
      </label>
      <label htmlFor="new-version-status">
        Start as
        <select id="new-version-status" value={status} onChange={(e) => setStatus(e.target.value)}>
          <option value="DRAFT">Draft</option>
          <option value="IN_NEGOTIATION">In negotiation</option>
        </select>
      </label>
      <label className="checkbox">
        <input
          type="checkbox"
          checked={hasPrevious && copy}
          disabled={!hasPrevious}
          onChange={(e) => setCopy(e.target.checked)}
        />
        {hasPrevious ? `Copy rates and travel cap of version ${previousNumber}` : "No earlier version to copy from"}
      </label>
      <div className="form-actions">
        <button type="submit" className="primary" disabled={busy}>Create version</button>
      </div>
    </form>
  );
}

function CompareTable({ comparison }) {
  const c = comparison;
  return (
    <div className="scroll">
      <p className="muted">
        Travel surcharge cap: version {c.from_version} {formatMoney(c.travel_surcharge_cap_from)} → version{" "}
        {c.to_version} {formatMoney(c.travel_surcharge_cap_to)}
      </p>
      <table>
        <thead>
          <tr>
            <th>Role</th>
            <th>Seniority</th>
            <th>Version {c.from_version}</th>
            <th>Version {c.to_version}</th>
            <th>Change</th>
          </tr>
        </thead>
        <tbody>
          {c.rows.length === 0 && (
            <tr>
              <td colSpan={5} className="muted">Neither version has rates yet.</td>
            </tr>
          )}
          {c.rows.map((r) => (
            <tr key={`${r.role_id}-${r.seniority}`}>
              <td>{r.role_name}</td>
              <td>{r.seniority}</td>
              <td>{r.from_rate == null ? <span className="muted">-</span> : `${r.from_rate} EUR`}</td>
              <td>{r.to_rate == null ? <span className="muted">-</span> : `${r.to_rate} EUR`}</td>
              <td>
                <span className={`change change-${r.change}`}>
                  {CHANGE_LABEL[r.change]}
                  {r.delta ? ` (${r.delta > 0 ? "+" : ""}${r.delta} EUR)` : ""}
                </span>
              </td>
            </tr>
          ))}
        </tbody>
      </table>
    </div>
  );
}

const CHANGE_LABEL = { added: "added", removed: "removed", changed: "changed", unchanged: "unchanged" };

function todayIso() {
  const now = new Date();
  return new Date(now.getTime() - now.getTimezoneOffset() * 60000).toISOString().slice(0, 10);
}
