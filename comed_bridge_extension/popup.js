const api = document.getElementById("api");
const user = document.getElementById("user");
const password = document.getElementById("password");
const button = document.getElementById("connect");
const status = document.getElementById("status");
const traceEnabled = document.getElementById("trace-enabled");
const clearDraft = document.getElementById("clear-draft");

chrome.storage.local.get(["apiBase", "username", "displayName", "token", "traceEnabled"], (saved) => {
  if (saved.apiBase) api.value = saved.apiBase;
  if (saved.username) user.value = saved.username;
  traceEnabled.checked = saved.traceEnabled !== false;
  if (saved.token) show(`${saved.displayName || "Doktor"} bağlı. COMED iş listesi eşitleniyor.`, true);
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
      body: JSON.stringify({
        username: user.value.trim(),
        password: password.value,
        client_type: "extension",
      }),
    });
    const payload = await response.json();
    if (!response.ok) throw new Error(payload.detail || "Giriş başarısız");
    if (payload.user?.role !== "doctor") throw new Error("Eklentiye doktor hesabıyla giriş yapın");
    await chrome.storage.local.set({
      apiBase: base,
      username: user.value.trim(),
      displayName: payload.user?.display_name || user.value.trim().split(";")[0],
      token: payload.access_token,
    });
    password.value = "";
    show(`${payload.user?.display_name || "Doktor"} bağlandı. COMED sekmesini yenileyebilirsiniz.`, true);
  } catch (error) {
    show(error.message);
  } finally {
    button.disabled = false;
  }
});

clearDraft.addEventListener("click", async () => {
  if (!confirm("Son Klinot aktarımının kaydedilmemiş form değişiklikleri temizlensin mi?")) return;
  clearDraft.disabled = true;
  try {
    const [tab] = await chrome.tabs.query({active: true, currentWindow: true});
    if (!tab?.id || !/^https?:\/\/goztepe\.comedtest\.mlpcare\.com\/tr-tr\/medical\//i.test(tab.url || "")) {
      throw new Error("Önce temizlenecek COMED hasta kartını açın");
    }
    const response = await chrome.tabs.sendMessage(tab.id, {type: "klinot-clear-last-transfer"});
    if (!response?.ok) throw new Error(response?.error || "Taslak temizlenemedi");
    show("Klinot taslağı temizleniyor; COMED kartı yenilenecek.", true);
  } catch (error) {
    show(error.message);
  } finally {
    clearDraft.disabled = false;
  }
});
