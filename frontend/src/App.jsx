import { useCallback, useEffect, useState } from "react";
import { api, setUser } from "./api.js";

const USERS = {
  SOURCING_MANAGER: { name: "Anna", role: "SOURCING_MANAGER", label: "Sourcing Manager (can edit)" },
  HIRING_MANAGER: { name: "Ben", role: "HIRING_MANAGER", label: "Hiring Manager (read only)" },
};

export default function App() {
  const [userKey, setUserKey] = useState("SOURCING_MANAGER");
  const [levels, setLevels] = useState([]);
  const [categories, setCategories] = useState([]);
  const [roles, setRoles] = useState([]);
  const [audit, setAudit] = useState([]);
  const [showInactive, setShowInactive] = useState(false);
  const [filterCategory, setFilterCategory] = useState("");
  const [error, setError] = useState("");

  const canEdit = userKey === "SOURCING_MANAGER";

  const loadAll = useCallback(async () => {
    try {
      const [lv, cat, rl] = await Promise.all([api.seniorityLevels(), api.categories(), api.roles()]);
      setLevels(lv);
      setCategories(cat);
      setRoles(rl);
      setAudit(canEdit ? await api.auditLog() : []);
      setError("");
    } catch (e) {
      setError(e.message === "Failed to fetch" ? "Cannot reach the backend. Is it running on port 8000?" : e.message);
    }
  }, [canEdit]);

  useEffect(() => {
    setUser(USERS[userKey]);
    loadAll();
  }, [userKey, loadAll]);

  // Runs an API action, shows errors, then reloads the data.
  async function run(action) {
    try {
      await action();
      setError("");
    } catch (e) {
      setError(e.message);
    }
    await loadAll();
  }

  const visibleCategories = categories.filter((c) => showInactive || c.active);
  const activeCategories = categories.filter((c) => c.active);
  const visibleRoles = roles.filter(
    (r) => (showInactive || r.active) && (!filterCategory || r.category_id === filterCategory)
  );

  return (
    <div className="page">
      <header>
        <div>
          <h1>Role catalogue</h1>
          <p className="muted">US-01 · Group 6 External Recruiting</p>
        </div>
        <label className="user-switch">
          Logged in as
          <select value={userKey} onChange={(e) => setUserKey(e.target.value)}>
            {Object.entries(USERS).map(([key, u]) => (
              <option key={key} value={key}>
                {u.label}
              </option>
            ))}
          </select>
        </label>
      </header>

      {error && <div className="error">{error}</div>}
      {!canEdit && <div className="info">You can look at the catalogue, but only a Sourcing Manager can change it.</div>}

      <section className="card">
        <h2>Seniority levels</h2>
        <p className="muted">Fixed list, cannot be changed.</p>
        <div className="chips">
          {levels.map((l) => (
            <span className="chip" key={l.code}>
              {l.label} <small>({l.code})</small>
            </span>
          ))}
        </div>
      </section>

      <label className="checkbox">
        <input type="checkbox" checked={showInactive} onChange={(e) => setShowInactive(e.target.checked)} />
        Show deactivated entries
      </label>

      <section className="card">
        <h2>Role categories</h2>
        {canEdit && <AddForm placeholder="New category, e.g. Development" button="Add category" onAdd={(name) => run(() => api.createCategory(name))} />}
        <table>
          <thead>
            <tr>
              <th>Name</th>
              <th>Status</th>
              {canEdit && <th></th>}
            </tr>
          </thead>
          <tbody>
            {visibleCategories.length === 0 && (
              <tr>
                <td colSpan={3} className="muted">No categories yet.</td>
              </tr>
            )}
            {visibleCategories.map((c) => (
              <tr key={c.id} className={c.active ? "" : "inactive"}>
                <td>{c.name}</td>
                <td>{c.active ? "Active" : "Deactivated"}</td>
                {canEdit && (
                  <td className="actions">
                    <button onClick={() => rename(c.name, (n) => run(() => api.renameCategory(c.id, n)))}>Rename</button>
                    {c.active ? (
                      <button className="danger" onClick={() => {
                        if (window.confirm(`Deactivate "${c.name}" and all its roles?`)) run(() => api.deactivateCategory(c.id));
                      }}>Deactivate</button>
                    ) : (
                      <button onClick={() => run(() => api.activateCategory(c.id))}>Activate</button>
                    )}
                  </td>
                )}
              </tr>
            ))}
          </tbody>
        </table>
      </section>

      <section className="card">
        <h2>Roles</h2>
        {canEdit && (
          <AddForm
            placeholder="New role, e.g. Java Developer"
            button="Add role"
            categories={activeCategories}
            onAdd={(name, categoryId) => run(() => api.createRole(categoryId, name))}
          />
        )}
        <label className="inline">
          Filter by category
          <select value={filterCategory} onChange={(e) => setFilterCategory(e.target.value)}>
            <option value="">All</option>
            {categories.map((c) => (
              <option key={c.id} value={c.id}>{c.name}</option>
            ))}
          </select>
        </label>
        <table>
          <thead>
            <tr>
              <th>Role</th>
              <th>Category</th>
              <th>Status</th>
              {canEdit && <th></th>}
            </tr>
          </thead>
          <tbody>
            {visibleRoles.length === 0 && (
              <tr>
                <td colSpan={4} className="muted">No roles yet.</td>
              </tr>
            )}
            {visibleRoles.map((r) => (
              <tr key={r.id} className={r.active ? "" : "inactive"}>
                <td>{r.name}</td>
                <td>{r.category_name}</td>
                <td>{r.active ? "Active" : "Deactivated"}</td>
                {canEdit && (
                  <td className="actions">
                    <button onClick={() => rename(r.name, (n) => run(() => api.renameRole(r.id, n)))}>Rename</button>
                    {r.active ? (
                      <button className="danger" onClick={() => run(() => api.deactivateRole(r.id))}>Deactivate</button>
                    ) : (
                      <button onClick={() => run(() => api.activateRole(r.id))}>Activate</button>
                    )}
                  </td>
                )}
              </tr>
            ))}
          </tbody>
        </table>
      </section>

      {canEdit && (
        <section className="card">
          <h2>Audit trail</h2>
          <p className="muted">Latest 50 changes: who, when, what.</p>
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
        </section>
      )}
    </div>
  );
}

function rename(currentName, onSave) {
  const name = window.prompt("New name:", currentName);
  if (name !== null && name.trim() !== "" && name.trim() !== currentName) onSave(name.trim());
}

// Small form: a text field, an optional category dropdown, and a button.
function AddForm({ placeholder, button, categories, onAdd }) {
  const [name, setName] = useState("");
  const [categoryId, setCategoryId] = useState("");
  const needsCategory = Array.isArray(categories);

  function submit(e) {
    e.preventDefault();
    if (!name.trim()) return;
    if (needsCategory && !categoryId) return;
    onAdd(name.trim(), categoryId);
    setName("");
  }

  return (
    <form className="add-form" onSubmit={submit}>
      {needsCategory && (
        <select value={categoryId} onChange={(e) => setCategoryId(e.target.value)} required>
          <option value="">Select category</option>
          {categories.map((c) => (
            <option key={c.id} value={c.id}>{c.name}</option>
          ))}
        </select>
      )}
      <input value={name} onChange={(e) => setName(e.target.value)} placeholder={placeholder} maxLength={100} />
      <button type="submit" className="primary">{button}</button>
    </form>
  );
}
