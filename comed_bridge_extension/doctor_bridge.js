(() => {
  const REQUEST_SOURCE = "klinot-doctor-comed-open-v1";
  const RESULT_SOURCE = "klinot-doctor-comed-open-result-v1";

  window.addEventListener("message", (event) => {
    if (event.source !== window || event.origin !== location.origin) return;
    const message = event.data;
    if (message?.source !== REQUEST_SOURCE || !message.url) return;

    chrome.runtime.sendMessage({
      type: "klinot-open-comed",
      url: message.url,
      transferId: message.transfer_id || null,
    }, (response) => {
      window.postMessage({
        source: RESULT_SOURCE,
        request_id: message.request_id,
        ok: Boolean(response?.ok),
        reused: Boolean(response?.reused),
        waiting_for_login: Boolean(response?.waitingForLogin),
        error: response?.error || chrome.runtime.lastError?.message || null,
      }, location.origin);
    });
  });
})();
