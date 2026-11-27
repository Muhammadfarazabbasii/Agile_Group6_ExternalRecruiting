import { Fragment, useCallback, useEffect, useMemo, useState } from "react";
import { api } from "../api.js";

// US-03 and US-04 panel: the negotiation rounds (versions) of one framework contract.
// Each version has one maximum daily rate per role and seniority level, shown as a grid (roles x levels).
// A missing rate means "not allowed" for the supplier. The Sourcing Manager edits rates while a version is
// DRAFT or IN_NEGOTIATION. Everybody can read the versions and compare any two of them.
// Changes go through `run` from the Suppliers page: errors show at the top and the audit trail reloads.

const LEVELS = ["JUNIOR", "SENIOR", "EXPERT"];
const CURRENCY = "EUR";

const VERSION_HELP = {
  DRAFT: "Being prepared, rates can be changed",
  IN_NEGOTIATION: "In negotiation, rates can be changed",
  ACTIVE: "The agreed price limits, read only",
  SUPERSEDED: "Replaced by a newer active version, read only, kept for history",
};

// One short line per status, shown above the rates so it is clear whether they can be changed.
const STATUS_BANNER = {
  DRAFT: { tone: "info", text: "This version is being prepared. You can change its rates until you activate it." },
  IN_NEGOTIATION: {
    tone: "info",
    text: "This version is under negotiation. You can change its rates. Activating it replaces the version that is ACTIVE now.",
  },
  ACTIVE: { tone: "ok", text: "This is the version in force. Its rates are read only." },
  SUPERSEDED: { tone: "muted", text: "A newer version was activated. This one is kept for history and is read only." },
};

export default function ContractVersions({ contract, canEdit, run }) {
  const [versions, setVersions] = useState(null);
  const [catalogue, setCatalogue] = useState(null);
  const [message, setMessage] = useState("");
  const [openRatesId, setOpenRatesId] = useState(null);
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
    const note = current
      ? ` Version ${current.version_number} is ACTIVE now and will be set to SUPERSEDED (read only).`
      : " No other version is ACTIVE right now.";
    if (window.confirm(`Activate version ${version.version_number} of ${contract.reference}? Its rates become the ones in force.${note}`)) {
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
  const active = versions.find((v) => v.status === "ACTIVE");

  return (
    <div className="version-panel">
      <h3>Versions of {contract.reference}</h3>
      <p className="muted">
        {active
          ? `Version ${active.version_number} is in force. `
          : "No version is in force yet. "}
        Each version has one maximum daily rate per role and seniority level. A role and level without a rate is not
        allowed for the supplier.
      </p>
      {message && <div className="error" role="alert">{message}</div>}

      {versions.length === 0 && (
        <div className="empty">
          <strong>No negotiation rounds yet.</strong>
          <p className="muted">Create the first version below. It starts as a draft, so you can still change everything.</p>
        </div>
      )}
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
                    <td>{v.rates.length} {v.rates.length === 1 ? "rate" : "rates"}</td>
                    <td>{formatMoney(v.travel_surcharge_cap)}</td>
                    <td className="actions">
                      <button
                        aria-expanded={openRatesId === v.id}
                        onClick={() => setOpenRatesId(openRatesId === v.id ? null : v.id)}
                      >
                        {openRatesId === v.id ? "Hide rates" : "Show rates"}
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
                        <VersionRates
                          version={v}
                          catalogue={catalogue}
                          canEdit={canEdit}
                          onSave={(body) => act(() => api.saveRates(v.id, body))}
                        />
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
          <p className="muted">Pick two versions to see which maximum rates were added, removed or changed.</p>
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
  return value == null ? <span className="muted">-</span> : `${value} ${CURRENCY}`;
}

// ---------- rates of one version (US-04) ----------

const cellKey = (roleId, level) => `${roleId}|${level}`;

// Current values of the version as text for the inputs: { "roleId|LEVEL": "900" }.
function cellsFromVersion(version) {
  const cells = {};
  for (const r of version.rates) cells[cellKey(r.role_id, r.seniority)] = String(r.max_daily_rate);
  return cells;
}

// Roles grouped by category, from the catalogue (active roles only). Roles that are deactivated but still have a
// rate in this version are listed too, so that the rate can be seen and cleared.
function buildGroups(catalogue, rates) {
  const groups = [];
  const seen = new Set();
  for (const category of catalogue ? catalogue.categories : []) {
    const roles = category.roles.map((role) => {
      seen.add(role.id);
      return { id: role.id, name: role.name, deactivated: false };
    });
    if (roles.length) groups.push({ title: category.name, roles });
  }
  const orphans = [];
  for (const r of rates) {
    if (!seen.has(r.role_id)) {
      seen.add(r.role_id);
      orphans.push({ id: r.role_id, name: r.role_name, deactivated: true });
    }
  }
  if (orphans.length) groups.push({ title: "Deactivated roles", roles: orphans });
  return groups;
}

// Empty text means "not allowed". Compare numbers, so "900" and "900.00" count as the same.
const normalise = (text) => (text == null || String(text).trim() === "" ? null : Number(text));

function VersionRates({ version, catalogue, canEdit, onSave }) {
  const banner = STATUS_BANNER[version.status];
  const canChange = canEdit && version.editable;
  const [editing, setEditing] = useState(false);
  const [cells, setCells] = useState({});
  const [cap, setCap] = useState("");
  const [problems, setProblems] = useState([]);
  const [busy, setBusy] = useState(false);

  if (catalogue === null) {
    return (
      <div className="rates-panel">
        <div className="error" role="alert">The role list could not be loaded, so the rates cannot be shown or changed right now.</div>
      </div>
    );
  }

  const groups = buildGroups(catalogue, version.rates);
  // Without any role there is no row to enter a rate in. Roles that are deactivated still show, so their rates can be cleared.
  const anyRole = groups.some((g) => g.roles.length > 0);
  const savedCells = cellsFromVersion(version);
  const savedCap = version.travel_surcharge_cap == null ? "" : String(version.travel_surcharge_cap);

  function startEditing() {
    setCells(cellsFromVersion(version));
    setCap(savedCap);
    setProblems([]);
    setEditing(true);
  }

  // Counts changed cells and the cap, so the user sees how much is unsaved.
  const allKeys = new Set([...Object.keys(savedCells), ...Object.keys(cells)]);
  let changes = 0;
  for (const key of allKeys) {
    if (normalise(savedCells[key]) !== normalise(cells[key])) changes += 1;
  }
  if (normalise(savedCap) !== normalise(cap)) changes += 1;

  function discard() {
    if (changes > 0 && !window.confirm("Discard your unsaved changes to the rates?")) return;
    setEditing(false);
    setProblems([]);
  }

  function setCell(key, value) {
    setCells((current) => ({ ...current, [key]: value }));
  }

  async function save(event) {
    event.preventDefault();
    const found = [];
    const rates = [];
    for (const group of groups) {
      for (const role of group.roles) {
        for (const level of LEVELS) {
          const key = cellKey(role.id, level);
          const raw = (cells[key] ?? "").trim();
          if (raw === "") continue;
          if (role.deactivated) {
            found.push({ key, text: `${role.name} is deactivated, so it cannot have a rate. Clear its cells to save.` });
          } else if (!(Number(raw) > 0)) {
            found.push({ key, text: `${role.name} / ${level}: the rate must be above zero. Leave the cell empty if this is not allowed.` });
          } else {
            rates.push({ role_id: role.id, seniority: level, max_daily_rate: Number(raw), currency: CURRENCY });
          }
        }
      }
    }
    if (cap.trim() !== "" && !(Number(cap) >= 0)) {
      found.push({ key: "cap", text: "The travel surcharge cap must be zero or more, or left empty." });
    }
    if (found.length > 0) {
      setProblems(found);
      return;
    }
    setProblems([]);
    setBusy(true);
    const ok = await onSave({ travel_surcharge_cap: cap.trim() === "" ? null : Number(cap), rates });
    setBusy(false);
    if (ok) setEditing(false);
  }

  if (!editing) {
    const activeIds = new Set(groups.flatMap((g) => g.roles.filter((r) => !r.deactivated).map((r) => r.id)));
    const combinations = activeIds.size * LEVELS.length;
    const withRate = version.rates.filter((r) => activeIds.has(r.role_id)).length;
    return (
      <div className="rates-panel">
        <div className={`banner banner-${banner.tone}`}>{banner.text}</div>
        <p className="muted">
          Maximum daily rate in {CURRENCY} for each role and seniority level.
          {combinations > 0 && ` ${withRate} of ${combinations} combinations have a rate; the others are not allowed.`}
          {` Travel surcharge cap: ${savedCap === "" ? "none" : `${savedCap} ${CURRENCY}`}.`}
        </p>
        {!anyRole ? (
          <NoRolesNotice />
        ) : (
          <>
            {version.rates.length === 0 && canChange && (
              <div className="empty">
                <strong>No rates yet.</strong>
                <p className="muted">Until you enter rates, every role and level is not allowed for the supplier.</p>
              </div>
            )}
            <RateGridTable groups={groups} rates={version.rates} />
          </>
        )}
        {canChange && (
          <div className="form-actions mt">
            <button className="primary" onClick={startEditing}>
              {anyRole ? "Edit rates" : "Edit travel cap"}
            </button>
          </div>
        )}
      </div>
    );
  }

  const invalid = new Set(problems.map((p) => p.key));
  return (
    <form className="rates-panel" onSubmit={save} noValidate>
      <div className={`banner banner-${banner.tone}`}>{banner.text}</div>
      <p className="muted">
        Enter the maximum daily rate in {CURRENCY} for each role and level. Leave a cell empty if that role and level is
        not allowed for the supplier. Press Enter in a cell to save.
      </p>
      {problems.length > 0 && (
        <div className="error" role="alert">
          <strong>Please fix these before saving:</strong>
          <ul className="problem-list">
            {problems.map((p) => (
              <li key={p.key}>{p.text}</li>
            ))}
          </ul>
        </div>
      )}
      <label className="inline" htmlFor={`cap-${version.id}`}>
        Travel surcharge cap in {CURRENCY} (optional)
        <input
          id={`cap-${version.id}`}
          type="number"
          inputMode="decimal"
          min="0"
          step="0.01"
          value={cap}
          aria-invalid={invalid.has("cap")}
          onChange={(e) => setCap(e.target.value)}
        />
      </label>

      {!anyRole ? (
        <NoRolesNotice />
      ) : (
        <RateGridTable
          groups={groups}
          rates={version.rates}
          editing
          cells={cells}
          onCell={setCell}
          invalid={invalid}
        />
      )}

      <div className="form-actions mt">
        <button type="submit" className="primary" disabled={busy || changes === 0}>
          {busy ? "Saving..." : `Save rates${changes > 0 ? ` (${changes} change${changes === 1 ? "" : "s"})` : ""}`}
        </button>
        <button type="button" onClick={discard} disabled={busy}>Discard changes</button>
      </div>
    </form>
  );
}

// Shown instead of the grid when the role list is empty: a rate needs a role and a level to belong to.
function NoRolesNotice() {
  return (
    <div className="empty" role="status">
      <strong>No roles to price yet.</strong>
      <p className="muted">
        Maximum rates are entered per role and seniority level, so the role list needs at least one role. Add roles in
        the "Role catalogue" tab, then come back here. The travel surcharge cap can still be changed.
      </p>
    </div>
  );
}

// The grid: one row per role, one column per seniority level. Read mode shows the rate or "Not allowed".
function RateGridTable({ groups, rates, editing = false, cells = {}, onCell, invalid = new Set() }) {
  const byKey = {};
  for (const r of rates) byKey[cellKey(r.role_id, r.seniority)] = r;
  return (
    <div className="scroll">
      <table className="rate-grid">
        <caption>Maximum daily rate in {CURRENCY}</caption>
        <thead>
          <tr>
            <th scope="col">Role</th>
            {LEVELS.map((level) => (
              <th scope="col" key={level}>{capitalise(level)}</th>
            ))}
          </tr>
        </thead>
        <tbody>
          {groups.map((group) => (
            <Fragment key={group.title}>
              <tr className="rate-group">
                <th colSpan={LEVELS.length + 1} scope="colgroup">{group.title}</th>
              </tr>
              {group.roles.map((role) => (
                <tr key={role.id} className={role.deactivated ? "inactive-role" : ""}>
                  <th scope="row">
                    {role.name}
                    {role.deactivated && <span className="tag">deactivated</span>}
                  </th>
                  {LEVELS.map((level) => {
                    const key = cellKey(role.id, level);
                    if (editing) {
                      return (
                        <td key={level}>
                          <input
                            className="rate-cell"
                            type="number"
                            inputMode="decimal"
                            min="0"
                            step="0.01"
                            placeholder="not allowed"
                            aria-label={`${role.name}, ${capitalise(level)}: maximum daily rate in ${CURRENCY}`}
                            aria-invalid={invalid.has(key)}
                            value={cells[key] ?? ""}
                            onChange={(e) => onCell(key, e.target.value)}
                          />
                        </td>
                      );
                    }
                    const rate = byKey[key];
                    return (
                      <td key={level}>
                        {rate ? (
                          <span className="rate-value">{rate.max_daily_rate} {rate.currency}</span>
                        ) : (
                          <span className="not-allowed">Not allowed</span>
                        )}
                      </td>
                    );
                  })}
                </tr>
              ))}
            </Fragment>
          ))}
        </tbody>
      </table>
    </div>
  );
}

function capitalise(text) {
  return text.charAt(0) + text.slice(1).toLowerCase();
}

// ---------- new version ----------

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
          <option value="DRAFT">Draft (still being prepared)</option>
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
        {hasPrevious ? `Copy the rates and travel cap of version ${previousNumber} as a starting point` : "No earlier version to copy from"}
      </label>
      <div className="form-actions">
        <button type="submit" className="primary" disabled={busy}>Create version</button>
      </div>
    </form>
  );
}

// ---------- compare ----------

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
            <th>Level</th>
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
              <td>{capitalise(r.seniority)}</td>
              <td>{r.from_rate == null ? <span className="not-allowed">Not allowed</span> : `${r.from_rate} ${CURRENCY}`}</td>
              <td>{r.to_rate == null ? <span className="not-allowed">Not allowed</span> : `${r.to_rate} ${CURRENCY}`}</td>
              <td>
                <span className={`change change-${r.change}`}>
                  {CHANGE_LABEL[r.change]}
                  {r.delta ? ` (${r.delta > 0 ? "+" : ""}${r.delta} ${CURRENCY})` : ""}
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
