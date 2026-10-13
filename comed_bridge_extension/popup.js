const api = document.getElementById("api");
const user = document.getElementById("user");
const password = document.getElementById("password");
const button = document.getElementById("connect");
const status = document.getElementById("status");
const loginStatus = document.getElementById("login-status");
const traceEnabled = document.getElementById("trace-enabled");
const clearDraft = document.getElementById("clear-draft");
const connectedView = document.getElementById("connected-view");
const loginView = document.getElementById("login-view");
const connectedName = document.getElementById("connected-name");
const connectedUser = document.getElementById("connected-user");
const switchAccount = document.getElementById("switch-account");
const cancelSwitch = document.getElementById("cancel-switch");
const speedButtons = document.getElementById("speed-buttons");
const speedNote = document.getElementById("speed-note");

/* Form doldurma hizi: content.js her bekleme suresini bu degere boler.
   Buyuk deger daha hizli doldurur. Ayni deger COMED sayfasindaki balonda da
   gosterilir; iki taraf chrome.storage uzerinden anlik esitlenir. */
const SPEED_VALUES = [0.5, 0.75, 1, 1.5, 2.5];
const DEFAULT_SPEED = 1;

function normalizeSpeed(value) {
  const number = Number(value);
  return SPEED_VALUES.includes(number) ? number : DEFAULT_SPEED;
}

function paintSpeed(value) {
  const speed = normalizeSpeed(value);
  let title = "";
  speedButtons.querySelectorAll("[data-speed]").forEach((item) => {
    const on = Number(item.dataset.speed) === speed;
    item.setAttribute("aria-pressed", String(on));
    if (on) title = item.title;
  });
  speedNote.textContent = title;
}

speedButtons.addEventListener("click", (event) => {
  const item = event.target.closest("[data-speed]");
  if (!item) return;
  const speed = normalizeSpeed(item.dataset.speed);
  paintSpeed(speed);
  chrome.storage.local.set({fillSpeed: speed});
});

const COMED_CARD_RE = /^https:\/\/goztepetest\.comed\.mlpcare\.com\/tr-tr\/medical\//i;

let connected = null;

/* Bir kez baglandiktan sonra kullanici adi/sifre alanlari gorunmez; yalnizca
   "bagli" bilgisi durur. Oturum dustugunde (401) background.js kayitli tokeni
   siler, bu da popup'i otomatik olarak giris ekranina dondurur. */
function paint() {
  const isConnected = Boolean(connected?.token);
  connectedView.classList.toggle("hidden", !isConnected);
  loginView.classList.toggle("hidden", isConnected);
  cancelSwitch.classList.toggle("hidden", !isConnected);
  if (isConnected) {
    connectedName.textContent = connected.displayName || "Doktor";
    connectedUser.textContent = connected.username || "";
  }
}

function show(text, ok = false) {
  const target = connected?.token ? status : loginStatus;
  target.textContent = text;
  target.className = ok ? "ok" : "bad";
}

chrome.storage.local.get(
  ["apiBase", "username", "displayName", "token", "traceEnabled", "fillSpeed"],
  (saved) => {
    if (saved.apiBase) api.value = saved.apiBase;
    if (saved.username) user.value = saved.username;
    traceEnabled.checked = saved.traceEnabled !== false;
    paintSpeed(saved.fillSpeed);
    connected = saved.token ? saved : null;
    paint();
  },
);

// Token baska bir yerde silinirse (ornegin 401 sonrasi) popup aninda giris
// ekranina doner. Hiz COMED sayfasindaki balondan degisirse burada da guncellenir.
chrome.storage.onChanged.addListener((changes, area) => {
  if (area !== "local") return;
  if (changes.fillSpeed) paintSpeed(changes.fillSpeed.newValue);
  if (!changes.token) return;
  if (!changes.token.newValue) {
    connected = null;
    paint();
    show("Klinot oturumu sona erdi. Tekrar bağlanın.", false);
  }
});

traceEnabled.addEventListener("change", async () => {
  await chrome.storage.local.set({traceEnabled: traceEnabled.checked});
});

switchAccount.addEventListener("click", () => {
  connected = null;
  password.value = "";
  paint();
  loginStatus.textContent = "Yeni Klinot hesabını girin.";
  loginStatus.className = "";
});

cancelSwitch.addEventListener("click", () => {
  chrome.storage.local.get(
    ["apiBase", "username", "displayName", "token"],
    (saved) => {
      connected = saved.token ? saved : null;
      paint();
    },
  );
});

button.addEventListener("click", async () => {
  button.disabled = true;
  loginStatus.className = "";
  loginStatus.textContent = "Bağlanıyor…";
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
    const saved = {
      apiBase: base,
      username: user.value.trim(),
      displayName: payload.user?.display_name || user.value.trim().split(";")[0],
      token: payload.access_token,
    };
    await chrome.storage.local.set(saved);
    password.value = "";
    connected = saved;
    paint();
    show(`${saved.displayName} bağlandı. COMED sekmesini yenileyebilirsiniz.`, true);
  } catch (error) {
    connected = null;
    paint();
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
    if (!tab?.id || !COMED_CARD_RE.test(tab.url || "")) {
      throw new Error("Önce temizlenecek COMED hasta kartını açın");
    }
    const response = await chrome.tabs.sendMessage(tab.id, {type: "klinot-clear-last-transfer"});
    if (!response?.ok) throw new Error(response?.error || "Taslak temizlenemedi");
    show("ICD ve özgeçmiş dâhil Klinot taslağı temizleniyor; kart otomatik yenilenecek.", true);
  } catch (error) {
    show(error.message);
  } finally {
    clearDraft.disabled = false;
  }
});
