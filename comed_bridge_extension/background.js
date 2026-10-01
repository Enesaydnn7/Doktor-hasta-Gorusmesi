const DEFAULT_API = "https://doktor-hasta-gorusmesi.onrender.com";
const COMED_HOST = "goztepe.comedtest.mlpcare.com";
const PENDING_COMED_KEY = "pendingComedNavigation";

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
    selected = await chrome.tabs.update(tab.id, {
      active: true,
      ...(sameComedTarget(tab.url, target.href) ? {} : {url: target.href}),
    });
    await chrome.windows.update(tab.windowId, {focused: true}).catch(() => {});
    if (sameComedTarget(tab.url, target.href)) await sessionRemove(PENDING_COMED_KEY);
  } else {
    selected = await chrome.tabs.create({url: "about:blank", active: true});
    await sessionSet(PENDING_COMED_KEY, {
      tabId: selected.id,
      url: target.href,
      createdAt: Date.now(),
    });
    selected = await chrome.tabs.update(selected.id, {url: target.href, active: true});
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
  if (!response.ok) throw new Error(payload.detail || payload.error || `HTTP ${response.status}`);
  return payload;
}

chrome.runtime.onMessage.addListener((message, _sender, sendResponse) => {
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
