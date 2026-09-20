const api = document.getElementById("api");
const user = document.getElementById("user");
const password = document.getElementById("password");
const button = document.getElementById("connect");
const status = document.getElementById("status");
const traceEnabled = document.getElementById("trace-enabled");

chrome.storage.local.get(["apiBase", "username", "token", "traceEnabled"], (saved) => {
  if (saved.apiBase) api.value = saved.apiBase;
  if (saved.username) user.value = saved.username;
  traceEnabled.checked = saved.traceEnabled !== false;
  if (saved.token) show("Köprü bağlı. COMED iş listesi eşitleniyor.", true);
});

traceEnabled.addEventListener("change", async () => {
  await chrome.storage.local.set({traceEnabled: traceEnabled.checked});
});

function show(text, ok = false) {
  status.textContent = text;
  status.className = ok ? "ok" : "bad";
}

button.addEventListener("click", async () => {
  button.disabled = true;
  status.className = "";
  status.textContent = "Bağlanıyor…";
  const base = api.value.trim().replace(/\/$/, "");
  try {
    const response = await fetch(`${base}/api/v1/mobile/auth/login`, {
      method: "POST",
      headers: {"Content-Type": "application/json", Accept: "application/json"},
      body: JSON.stringify({username: user.value.trim(), password: password.value}),
    });
    const payload = await response.json();
    if (!response.ok) throw new Error(payload.detail || "Giriş başarısız");
    await chrome.storage.local.set({
      apiBase: base,
      username: user.value.trim(),
      token: payload.access_token,
    });
    password.value = "";
    show("Bağlandı. COMED sekmesini yenileyebilirsiniz.", true);
  } catch (error) {
    show(error.message);
  } finally {
    button.disabled = false;
  }
});
