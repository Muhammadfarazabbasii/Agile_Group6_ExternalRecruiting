// All calls to the Python backend live here.
// The "user" is sent as headers. This is a development stand-in for a real login.

let currentUser = { name: "Anna", role: "SOURCING_MANAGER" };

export function setUser(user) {
  currentUser = user;
}

async function request(path, options = {}) {
  const res = await fetch(path, {
    ...options,
    headers: {
      "Content-Type": "application/json",
      "X-User-Role": currentUser.role,
      "X-User-Name": currentUser.name,
    },
  });
  if (!res.ok) {
    let message = `Error ${res.status}`;
    try {
      const data = await res.json();
      if (typeof data.detail === "string") message = data.detail;
      else if (Array.isArray(data.detail)) message = data.detail.map((d) => d.msg).join(", ");
    } catch {
      // response had no JSON body, keep the default message
    }
    throw new Error(message);
  }
  return res.json();
}

const post = (path, body) => request(path, { method: "POST", body: body ? JSON.stringify(body) : undefined });
const patch = (path, body) => request(path, { method: "PATCH", body: JSON.stringify(body) });

export const api = {
  seniorityLevels: () => request("/api/seniority-levels"),
  categories: () => request("/api/role-categories"),
  createCategory: (name) => post("/api/role-categories", { name }),
  renameCategory: (id, name) => patch(`/api/role-categories/${id}`, { name }),
  deactivateCategory: (id) => post(`/api/role-categories/${id}/deactivate`),
  activateCategory: (id) => post(`/api/role-categories/${id}/activate`),
  roles: () => request("/api/roles"),
  createRole: (category_id, name) => post("/api/roles", { category_id, name }),
  renameRole: (id, name) => patch(`/api/roles/${id}`, { name }),
  deactivateRole: (id) => post(`/api/roles/${id}/deactivate`),
  activateRole: (id) => post(`/api/roles/${id}/activate`),
  auditLog: () => request("/api/audit-log"),
};
