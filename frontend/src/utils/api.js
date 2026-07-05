const BASE = import.meta.env.VITE_API_URL || "http://localhost:8000/api";

async function request(path, options = {}) {
  const res = await fetch(`${BASE}${path}`, options);
  if (!res.ok) {
    const err = await res.json().catch(() => ({ detail: res.statusText }));
    throw new Error(err.detail || "Request failed");
  }
  return res.json();
}

export const api = {
  uploadInvoices: (files) => {
    const fd = new FormData();
    files.forEach((f) => fd.append("files", f));
    return request("/upload-invoice", { method: "POST", body: fd });
  },

  uploadLedger: (sessionId, files) => {
    const fd = new FormData();
    files.forEach((f) => fd.append("files", f));
    return request(`/upload-ledger?session_id=${sessionId}`, { method: "POST", body: fd });
  },

  runMatch: (sessionId) =>
    request(`/match?session_id=${sessionId}`, { method: "POST" }),

  getResult: (sessionId) =>
    request(`/match/${sessionId}`),

  overrideMatch: (matchId, status, note = "") =>
    request(`/match/${matchId}/override`, {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ status, note }),
    }),

  getSessions: () => request("/sessions"),

  exportUrl: (sessionId, fmt = "json") =>
    `${BASE}/match/${sessionId}/export?fmt=${fmt}`,
};
