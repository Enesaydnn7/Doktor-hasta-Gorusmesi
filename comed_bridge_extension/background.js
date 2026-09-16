const DEFAULT_API = "https://doktor-hasta-gorusmesi.onrender.com";

async function settings() {
  const value = await chrome.storage.local.get(["apiBase", "token", "username"]);
  return {
    apiBase: (value.apiBase || DEFAULT_API).replace(/\/$/, ""),
    token: value.token || "",
    username: value.username || "",
  };
}

async function klinotFetch(path, options = {}) {
  const current = await settings();
  if (!current.token) throw new Error("Klinot köprüsü bağlı değil");
  const response = await fetch(`${current.apiBase}${path}`, {
    ...options,
    headers: {
      Accept: "application/json",
      Authorization: `Bearer ${current.token}`,
      ...(options.body ? {"Content-Type": "application/json"} : {}),
      ...(options.headers || {}),
    },
  });
  const payload = await response.json().catch(() => ({}));
  if (!response.ok) throw new Error(payload.detail || payload.error || `HTTP ${response.status}`);
  return payload;
}

chrome.runtime.onMessage.addListener((message, _sender, sendResponse) => {
  if (message?.type !== "klinot-request") return false;
  klinotFetch(message.path, message.options)
    .then((data) => sendResponse({ok: true, data}))
    .catch((error) => sendResponse({ok: false, error: error.message}));
  return true;
});
