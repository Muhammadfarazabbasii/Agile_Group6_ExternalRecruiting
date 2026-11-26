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
  // US-01 role catalogue
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

  // US-02 suppliers and framework contracts
  suppliers: () => request("/api/suppliers"),
  createSupplier: (name, supplier_id) => post("/api/suppliers", supplier_id ? { name, supplier_id } : { name }),
  renameSupplier: (id, name) => patch(`/api/suppliers/${id}`, { name }),
  deactivateSupplier: (id) => post(`/api/suppliers/${id}/deactivate`),
  activateSupplier: (id) => post(`/api/suppliers/${id}/activate`),
  createContract: (body) => post("/api/framework-contracts", body),
  updateContract: (id, body) => patch(`/api/framework-contracts/${id}`, body),
  activateContract: (id) => post(`/api/framework-contracts/${id}/activate`),
  terminateContract: (id) => post(`/api/framework-contracts/${id}/terminate`),

  // US-02 take-over from Group 7 (Expert Supplier)
  group7Suppliers: () => request("/api/group7/suppliers"),
  importGroup7Suppliers: (supplier_ids) => post("/api/group7/import-suppliers", { supplier_ids }),

  // US-03 contract versions (negotiation rounds) and their rates
  catalogue: () => request("/api/catalogue"),
  versions: (contractId) => request(`/api/framework-contracts/${contractId}/versions`),
  createVersion: (contractId, body) => post(`/api/framework-contracts/${contractId}/versions`, body),
  saveRates: (versionId, body) => request(`/api/contract-versions/${versionId}/rates`, { method: "PUT", body: JSON.stringify(body) }),
  changeVersionStatus: (versionId, status) => post(`/api/contract-versions/${versionId}/status`, { status }),
  compareVersions: (contractId, fromVersion, toVersion) =>
    request(`/api/framework-contracts/${contractId}/versions/compare?from_version=${fromVersion}&to_version=${toVersion}`),

  // shared audit trail, optionally only some entities
  auditLog: (entities = []) =>
    request("/api/audit-log" + (entities.length ? "?" + entities.map((e) => `entity=${encodeURIComponent(e)}`).join("&") : "")),
};
