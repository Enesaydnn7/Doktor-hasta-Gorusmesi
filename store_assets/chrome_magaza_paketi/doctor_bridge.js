/* Doktor panelinden gelen "COMED kartını aç" isteğini eklentinin arka plan
   betiğine taşır ve sonucu panele geri yollar.

   Bu köprü SESSİZCE ölmemeli: panel yanıt gelmezse yalnızca bir zaman aşımı
   bekler. İki bilinen durum var:

   1) Eklenti güncellenince açık sekmelerdeki content script'ler sahipsiz
      kalır; ``chrome.runtime`` erişimi senkron hata atar. Yakalanmazsa geri
      bildirim hiç gitmez ve panel yedi saniye boşuna bekler. Sekmeyi
      background.js zaten kendiliğinden yeniliyor (onInstalled); burada
      yalnızca o kısa aralıkta panelin beklemesini önlüyoruz.
   2) Manifest V3 arka plan betiği uykuya dalar; ilk mesaj bazen düşer.
      Bu yüzden bir kez daha deneniyor. */
(() => {
  const REQUEST_SOURCE = "klinot-doctor-comed-open-v1";
  const RESULT_SOURCE = "klinot-doctor-comed-open-result-v1";

  function reply(requestId, payload) {
    window.postMessage(
      {source: RESULT_SOURCE, request_id: requestId, ...payload},
      location.origin,
    );
  }

  /** Arka plan betiğine mesaj yollar; uykudaysa bir kez daha dener. */
  function ask(message, requestId, retry = true) {
    let settled = false;
    try {
      chrome.runtime.sendMessage(message, (response) => {
        if (settled) return;
        const lastError = chrome.runtime.lastError?.message || null;
        // Yanıt yoksa arka plan betiği uyanamamış olabilir: bir kez yinele.
        if (!response && lastError && retry) {
          setTimeout(() => ask(message, requestId, false), 400);
          return;
        }
        settled = true;
        reply(requestId, {
          ok: Boolean(response?.ok),
          reused: Boolean(response?.reused),
          waiting_for_login: Boolean(response?.waitingForLogin),
          error: response?.error || lastError || null,
        });
      });
    } catch (error) {
      // Sahipsiz content script ("Extension context invalidated") ya da
      // baska bir aksilik: panel bosuna beklemesin, hemen haber ver.
      settled = true;
      reply(requestId, {
        ok: false,
        reused: false,
        waiting_for_login: false,
        error: error?.message || "Klinot köprüsüne ulaşılamadı",
      });
    }
  }

  window.addEventListener("message", (event) => {
    if (event.source !== window || event.origin !== location.origin) return;
    const message = event.data;
    if (message?.source !== REQUEST_SOURCE || !message.url) return;
    ask(
      {
        type: "klinot-open-comed",
        url: message.url,
        transferId: message.transfer_id || null,
      },
      message.request_id,
    );
  });
})();
