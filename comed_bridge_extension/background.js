const DEFAULT_API = "http://localhost:8000";
const COMED_HOST = "goztepetest.comed.mlpcare.com";
const COMED_MEDICAL_PAGES = ["https://goztepetest.comed.mlpcare.com/tr-tr/medical/*"];
const PENDING_COMED_KEY = "pendingComedNavigation";
const DEV_HASH_KEY = "devExtensionHash";
// Panelden gelen bağlantı isteği yalnız bu kökenlerden kabul edilir.
const LINKABLE_ORIGINS = [
  "https://doktor-hasta-gorusmesi.onrender.com",
  "http://localhost:8000",
  "http://127.0.0.1:8000",
];

/* Eklenti guncellendiginde acik sekmelerdeki content script'ler sahipsiz
   kalir. Doktora "sayfayi yenileyin" dedirtmemek icin KLINOT PANELI
   sekmelerini kendimiz yeniliyoruz.

   COMED sekmeleri BILEREK yenilenmez: doldurulmus bir muayene formu varsa
   tarayici "siteden ayrilmak istiyor musunuz?" diye soruyor ve doktorun
   kaydedilmemis verisi riske giriyor. COMED tarafindaki kopru zaten doktorun
   bir sonraki sayfa gecisinde kendiliginden toparliyor. */
const BRIDGE_PANEL_PAGES = [
  "https://doktor-hasta-gorusmesi.onrender.com/*",
  "http://127.0.0.1:8000/*",
  "http://localhost:8000/*",
];

chrome.runtime.onInstalled.addListener(async () => {
  try {
    const tabs = await chrome.tabs.query({url: BRIDGE_PANEL_PAGES});
    for (const tab of tabs) {
      chrome.tabs.reload(tab.id, {bypassCache: false}).catch(() => {});
    }
  } catch (_) {
    // Sekme erisimi yoksa sessiz gec; kopru bir sonraki yenilemede toparlar.
  }
});

function parsedUrl(value) {
  try { return new URL(value); } catch (_) { return null; }
}

function isComedUrl(value) {
  return parsedUrl(value)?.hostname === COMED_HOST;
}

function isComedAuthUrl(value) {
  const url = parsedUrl(value);
  return url?.hostname === COMED_HOST && /\/auth\/?$/i.test(url.pathname);
}

function sameComedTarget(first, second) {
  const left = parsedUrl(first);
  const right = parsedUrl(second);
  if (!left || !right) return false;
  const path = (url) => url.pathname.replace(/\/+$/, "") || "/";
  return left.origin === right.origin && path(left) === path(right)
    && left.search === right.search;
}

async function sessionGet(key) {
  return (await chrome.storage.session.get(key))[key] || null;
}

async function sessionSet(key, value) {
  await chrome.storage.session.set({[key]: value});
}

async function sessionRemove(key) {
  await chrome.storage.session.remove(key);
}

async function openComedTarget(rawUrl, sender) {
  const target = parsedUrl(rawUrl);
  if (!target || target.hostname !== COMED_HOST || !/^https?:$/.test(target.protocol)) {
    throw new Error("Geçersiz COMED hasta kartı adresi");
  }

  const allTabs = await chrome.tabs.query({});
  const comedTabs = allTabs.filter((tab) => isComedUrl(tab.url));
  const sameWindow = comedTabs.filter((tab) => tab.windowId === sender?.tab?.windowId);
  const candidates = sameWindow.length ? sameWindow : comedTabs;
  const tab = candidates.sort((a, b) => {
    const score = (item) => item.url === target.href ? 3 : isComedAuthUrl(item.url) ? 1 : 2;
    return score(b) - score(a) || Number(b.active) - Number(a.active)
      || (b.lastAccessed || 0) - (a.lastAccessed || 0);
  })[0];

  let selected;
  if (tab) {
    await sessionSet(PENDING_COMED_KEY, {
      tabId: tab.id,
      url: target.href,
      createdAt: Date.now(),
    });
    const yonlendirilecek = !sameComedTarget(tab.url, target.href);
    if (yonlendirilecek) {
      /* COMED'de yarim kalmis bir form varsa tarayici "Siteden cikilsin mi?"
         kutusunu aciyor ve doktor her aktarimda onunla ugrasiyordu. Sekmeyi
         yonlendirmeden ONCE content.js'e haber verip bu tek cikisi
         sessizlestiriyoruz (page_trace.js'teki dinleyici halleder). */
      await chrome.tabs
        .sendMessage(tab.id, {type: "klinot-suppress-unload-prompt"})
        .catch(() => {});
    }
    selected = await chrome.tabs.update(tab.id, {
      active: true,
      ...(yonlendirilecek ? {url: target.href} : {}),
    });
    await chrome.windows.update(tab.windowId, {focused: true}).catch(() => {});
    if (sameComedTarget(tab.url, target.href)) await sessionRemove(PENDING_COMED_KEY);
  } else {
    // Dogrudan hedef adresle ac. Onceden "about:blank" acilip ardindan
    // yonlendiriliyordu; ikinci adim basarisiz olursa doktorun onunde BOS
    // bir sekme kaliyordu.
    selected = await chrome.tabs.create({url: target.href, active: true});
    await sessionSet(PENDING_COMED_KEY, {
      tabId: selected.id,
      url: target.href,
      createdAt: Date.now(),
    });
  }
  return {
    reused: Boolean(tab),
    tabId: selected.id,
    waitingForLogin: isComedAuthUrl(selected.url),
  };
}

chrome.tabs.onUpdated.addListener(async (tabId, changeInfo, tab) => {
  if (changeInfo.status !== "complete" || !isComedUrl(tab.url)) return;
  const pending = await sessionGet(PENDING_COMED_KEY);
  if (!pending || pending.tabId !== tabId) return;
  if (Date.now() - pending.createdAt > 30 * 60 * 1000) {
    await sessionRemove(PENDING_COMED_KEY);
    return;
  }
  if (isComedAuthUrl(tab.url)) return;
  if (!sameComedTarget(tab.url, pending.url)) {
    await chrome.tabs.update(tabId, {url: pending.url, active: true});
    return;
  }
  await sessionRemove(PENDING_COMED_KEY);
});

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
  if (response.status === 401) {
    // Klinot oturumu dustu. Kayitli tokeni silmek popup'i otomatik olarak
    // giris ekranina dondurur; aksi halde kullanici "bagli" gorunup her
    // istekte sessizce hata alirdi.
    await chrome.storage.local.remove("token");
    throw new Error("Klinot oturumu sona erdi. Eklentiden tekrar bağlanın.");
  }
  if (!response.ok) throw new Error(payload.detail || payload.error || `HTTP ${response.status}`);
  return payload;
}

/* ---- Yerel geliştirme: eklenti kendini diskten yeniler ----
   Paketlenmemiş eklentinin kodu değişince doktorun chrome://extensions'a
   gidip "yenile"ye basması gerekiyordu. Yerel sunucu (KLINOT_DEV=1)
   dosyaların parmak izini verir; değişmişse eklenti kendini yeniden yükler,
   açık COMED sekmelerine betikleri sayfa yenilenmeden yeniden enjekte eder.
   Yalnız API adresi localhost iken çalışır; canlıda hiçbir etkisi yoktur. */
let devCheckRunning = false;

/** Yalnız yerel geliştirmede: arka plan hatasını yerel sunucu günlüğüne yaz. */
async function devLog(message) {
  try {
    const {apiBase} = await settings();
    if (!/^http:\/\/(localhost|127\.0\.0\.1):\d+$/.test(apiBase)) return;
    await fetch(`${apiBase}/dev/log`, {method: "POST", body: String(message).slice(0, 2000)});
  } catch (_) {
    // Günlük yazılamazsa sessiz geç.
  }
}

async function devReloadCheck() {
  if (devCheckRunning) return;
  devCheckRunning = true;
  try {
    const {apiBase} = await settings();
    if (!/^http:\/\/(localhost|127\.0\.0\.1):\d+$/.test(apiBase)) return;
    const response = await fetch(`${apiBase}/dev/extension-version`, {cache: "no-store"});
    if (!response.ok) return;
    const {hash} = await response.json();
    const loaded = await sessionGet(DEV_HASH_KEY);
    if (!loaded) {
      await sessionSet(DEV_HASH_KEY, hash);
    } else if (hash && hash !== loaded) {
      chrome.runtime.reload();
    }
  } catch (_) {
    // Yerel sunucu kapalıysa sessiz geç.
  } finally {
    devCheckRunning = false;
  }
}

/** Açık COMED sekmelerinde canlı içerik betiği yoksa enjekte et.

    Eklenti açılınca/yenilenince Chrome mevcut sekmelere içerik betiği
    koymaz; sayfa yenilenene kadar köprü yoktur. COMED sekmesini yenilemek
    doktorun doldurulmuş formunu riske attığı için betikleri burada koyuyoruz.
    Canlı bir betik "klinot-ping"e cevap verir; veremeyen sekmeye konur. */
async function ensureComedScripts() {
  let tabs = [];
  try {
    tabs = await chrome.tabs.query({url: COMED_MEDICAL_PAGES});
  } catch (error) {
    devLog(`COMED sekmeleri sorgulanamadı: ${error?.message || error}`);
    return;
  }
  if (!tabs.length) devLog("Açık COMED sekmesi bulunamadı");
  for (const tab of tabs) {
    const alive = await chrome.tabs
      .sendMessage(tab.id, {type: "klinot-ping"})
      .then((response) => Boolean(response?.ok))
      .catch(() => false);
    if (alive) continue;
    try {
      await chrome.scripting.executeScript({
        target: {tabId: tab.id}, files: ["page_trace.js"], world: "MAIN",
      });
      await chrome.scripting.executeScript({target: {tabId: tab.id}, files: ["content.js"]});
      devLog(`COMED sekmesine betikler enjekte edildi (sekme ${tab.id})`);
    } catch (error) {
      // Sekme o an erişilemezse bir sonraki denetimde tekrar denenir.
      devLog(`COMED sekmesine enjekte edilemedi (sekme ${tab.id}): ${error?.message || error}`);
    }
  }
}

chrome.alarms?.create("klinot-dev-tick", {periodInMinutes: 0.5});
chrome.alarms?.onAlarm.addListener((alarm) => {
  if (alarm.name !== "klinot-dev-tick") return;
  devReloadCheck();
  ensureComedScripts();
});
ensureComedScripts();
devReloadCheck();

chrome.runtime.onMessage.addListener((message, _sender, sendResponse) => {
  if (message?.type === "klinot-dev-tick") {
    devReloadCheck();
    sendResponse({ok: true});
    return false;
  }
  if (message?.type === "klinot-link-doctor") {
    const origin = parsedUrl(_sender?.tab?.url || "")?.origin || "";
    if (!LINKABLE_ORIGINS.includes(origin) || origin !== message.apiBase || !message.token) {
      sendResponse({ok: false, error: "Bu sayfadan bağlanılamaz"});
      return false;
    }
    chrome.storage.local.set({
      apiBase: origin,
      token: message.token,
      username: message.username || "",
      displayName: message.displayName || message.username || "",
    }).then(() => sendResponse({ok: true}));
    return true;
  }
  if (message?.type === "klinot-open-comed") {
    openComedTarget(message.url, _sender)
      .then((data) => sendResponse({ok: true, ...data}))
      .catch((error) => sendResponse({ok: false, error: error.message}));
    return true;
  }
  if (message?.type !== "klinot-request") return false;
  klinotFetch(message.path, message.options)
    .then((data) => sendResponse({ok: true, data}))
    .catch((error) => sendResponse({ok: false, error: error.message}));
  return true;
});
