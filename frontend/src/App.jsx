import { useState } from "react";
import { setUser } from "./api.js";
import Catalogue from "./pages/Catalogue.jsx";
import Suppliers from "./pages/Suppliers.jsx";

const USERS = {
  SOURCING_MANAGER: { name: "Anna", role: "SOURCING_MANAGER", label: "Sourcing Manager (can edit)" },
  HIRING_MANAGER: { name: "Ben", role: "HIRING_MANAGER", label: "Hiring Manager (read only)" },
};

// One tab per feature. A new story adds a page file and one line here.
const TABS = [
  { key: "catalogue", label: "Role catalogue", story: "US-01", Page: Catalogue },
  { key: "suppliers", label: "Suppliers and contracts", story: "US-02", Page: Suppliers },
];

function tabFromHash() {
  const key = window.location.hash.replace("#", "");
  return TABS.some((t) => t.key === key) ? key : TABS[0].key;
}

export default function App() {
  const [userKey, setUserKey] = useState("SOURCING_MANAGER");
  const [tab, setTab] = useState(tabFromHash);

  // Set before the pages load their data, so the first request already carries the right user.
  setUser(USERS[userKey]);

  const canEdit = userKey === "SOURCING_MANAGER";
  const active = TABS.find((t) => t.key === tab) || TABS[0];
  const Page = active.Page;

  function openTab(key) {
    window.location.hash = key;
    setTab(key);
  }

  return (
    <div className="page">
      <header>
        <div>
          <h1>External Recruiting</h1>
          <p className="muted">Group 6 · Sprint 1</p>
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

      <nav className="tabs" aria-label="Sections">
        {TABS.map((t) => (
          <button
            key={t.key}
            type="button"
            className={t.key === active.key ? "tab current" : "tab"}
            aria-current={t.key === active.key ? "page" : undefined}
            onClick={() => openTab(t.key)}
          >
            {t.label} <small>{t.story}</small>
          </button>
        ))}
      </nav>

      {!canEdit && <div className="info">You can look at the data, but only a Sourcing Manager can change it.</div>}

      <Page userKey={userKey} canEdit={canEdit} />
    </div>
  );
}
