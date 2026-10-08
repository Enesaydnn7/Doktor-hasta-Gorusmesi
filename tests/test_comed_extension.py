import json
import re
import unittest
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
EXTENSION = ROOT / "comed_bridge_extension"


class ComedExtensionTests(unittest.TestCase):
    def test_transfer_fills_the_form_and_never_posts_natively(self):
        """POST sablonu akisi kaldirildi; tum alanlar form doldurularak hazirlanir."""
        source = (EXTENSION / "content.js").read_text(encoding="utf-8")

        self.assertIn("function setValue", source)
        self.assertIn("async function fillFormDraft", source)
        for removed in (
            "klinot-comed-native-command-v1",
            "executeNativePosts",
            "nativePending",
            "POST şablonu yok",
            "POST tamamlanamadı",
            "Doğrulanmış COMED POST'ları gönderiliyor",
        ):
            self.assertNotIn(removed, source)

    def test_bridge_opens_the_patient_info_panel_to_read_identity(self):
        """COMED kimlik alanlarini panel ACILANA kadar DOM'a basmaz (lazy render).

        Canli COMED test ortaminda dogrulanan secicilier:
          acici   : button[data-test="co-button-icon-patient-profile"]
          kapatici: button[data-test="co-button-icon-close"]   (Escape calismaz)
        """
        source = (EXTENSION / "content.js").read_text(encoding="utf-8")

        self.assertIn("async function ensurePatientIdentityPanel", source)
        self.assertIn('[data-test="co-button-icon-patient-profile"]', source)
        self.assertIn('[data-test="co-button-icon-close"]', source)
        self.assertIn("await ensurePatientIdentityPanel();", source)
        # Panel her kosulda kapatilmali.
        self.assertIn("} finally {", source)
        # Yeni kartta yeniden denenebilmeli.
        self.assertIn("identityPanelTried = false;", source)
        # Gizli dugum taramasi da korunur.
        self.assertIn("function deepTextOf", source)
        self.assertIn("deepTextOf(document.body)", source)

    def test_patient_name_strips_comed_header_metadata(self):
        """COMED basligi isme cinsiyet/yas/dogum/hasta no yapistiriyor; ad temiz kalmali."""
        source = (EXTENSION / "content.js").read_text(encoding="utf-8")

        self.assertIn("function cleanPatientName", source)
        self.assertIn("cleanPatientName(headerText.match", source)
        # Ham 80 karakter kesme yontemi geri gelmemeli.
        self.assertNotIn("headerText.match(/^([^|\\n]{3,80})/)?.[1]?.trim()", source)

    def test_worklist_date_range_uses_the_real_comed_picker(self):
        """Tarih kutusu disabled bir input; takvimi yalnizca ikon dugmesi acar.

        Canli COMED test ortaminda dogrulanan yapi:
          div[data-test=co-date-time-picker]
            button[data-test=co-button-icon-calendar]  <- tetikleyici
            input (disabled, "07.10.2026 - 07.10.2026")
        """
        source = (EXTENSION / "content.js").read_text(encoding="utf-8")

        self.assertIn('[data-test="co-date-time-picker"]', source)
        self.assertIn('[data-test="co-button-icon-calendar"]', source)
        self.assertIn('textOf(element) === "3 Ay"', source)
        # Basari dogrulanmadan bayrak set edilmemeli; aksi halde tek bir erken
        # deneme ozelligi kalici olarak devre disi birakir.
        self.assertIn("if (rangeIsWide(picker.querySelector(\"input\"))) {", source)
        self.assertIn("function rangeIsWide", source)
        self.assertNotIn("dateRangeApplied = true;\n    try {", source)

    def test_single_bubble_shows_progress_without_opening_the_log(self):
        """TEK balon: hem hover'da hem islem sirasinda yana acilip adimi gosterir."""
        source = (EXTENSION / "content.js").read_text(encoding="utf-8")

        self.assertIn("function renderBridgeCaption", source)
        self.assertIn("renderBridgeCaption(box, text, state)", source)
        # Durum metni balonun kendi etiketine yazilir; ayri bir serit yok.
        self.assertIn("data-klinot-caption-text", source)
        self.assertNotIn("data-klinot-log-caption", source)
        self.assertIn('orb.dataset.live = panelOpen ? "0" : "1";', source)
        self.assertIn('[data-klinot-log-orb][data-live="1"]', source)
        # Son adim doktorun imzasidir; balon kendiliginden kapanmamali.
        self.assertIn("Lütfen kontrol edip Kaydet ve İmzala", source)
        self.assertIn("if (!isFinal) {", source)
        # Gunluk acikken balon kucuk kalir.
        self.assertIn('if (open) orb.dataset.live = "0";', source)

    def test_family_history_and_fall_risk_are_always_answered(self):
        """Ikisi de COMED'de zorunlu; bilgi yoksa 'yok' isaretlenmeli."""
        source = (EXTENSION / "content.js").read_text(encoding="utf-8")

        # Dusme riski: exists true degilse her durumda "Yok".
        self.assertIn('if (exists !== true) return clickCardOption("Düşme Riski", "Yok");', source)
        # Soygecmis: hicbir satir isaretlenemediyse "Ozellik Yok".
        self.assertIn('if (!added) return clickCardOption("Soygeçmiş", "Özellik Yok") ? 1 : 0;', source)
        self.assertIn('clickCardOption("Soygeçmiş", "Görüldü")', source)

    def test_diagnosis_side_dropdown_is_selected_and_closed(self):
        """Taraf Tipi listesi acik birakilmamali; "Ayrim Yok" secilip kapanmali."""
        source = (EXTENSION / "content.js").read_text(encoding="utf-8")

        self.assertIn("async function selectDropdownOption", source)
        self.assertIn('selectDropdownOption(fieldGroupByLabel("Taraf Tipi", card), side)', source)
        # Liste acik kalirsa Escape ile kapatilir.
        self.assertIn('key: "Escape"', source)
        self.assertIn("const stillOpen", source)
        # Eski kirilgan yontem geri gelmemeli.
        self.assertNotIn("sideInput?.click();", source)

    def test_bubble_grows_sideways_to_fit_its_text(self):
        """Balon sabit genislik yerine icerigi kadar yana acilir."""
        source = (EXTENSION / "content.js").read_text(encoding="utf-8")

        self.assertIn("width:max-content", source)
        # Sabit 196px genislik metni kesiyordu.
        self.assertNotIn("{width:196px;border-radius:28px}", source)
        self.assertIn("text-overflow:ellipsis", source)

    def test_caption_context_never_shows_toolbar_text_as_patient_name(self):
        """Is listesi sayfasinda sayfa basi arac cubugudur, hasta adi degil."""
        source = (EXTENSION / "content.js").read_text(encoding="utf-8")

        # Hasta adi yalnizca kart sayfasinda ve temizleyiciden gecerek okunur.
        self.assertIn("const patientName = match\n      ? cleanPatientName(", source)
        # Uzun baglam metni tek satirda kalacak sekilde kirpilir.
        self.assertIn("context.length > 54", source)

    def test_empty_worklist_never_replaces_stored_patients(self):
        """Boş ayrıştırma sayfa yüklenmemiş demektir; kayıtlı liste silinmemeli."""
        source = (EXTENSION / "content.js").read_text(encoding="utf-8")

        self.assertIn("replace: items.length > 0", source)
        self.assertNotIn("JSON.stringify({items, replace: true})", source)

    def test_operation_log_is_a_floating_chat_bubble(self):
        source = (EXTENSION / "content.js").read_text(encoding="utf-8")

        self.assertIn("data-klinot-log-orb", source)
        # Balon kenara yapışık değil; sohbet görüşmesi gibi ekrandan ayrık durur.
        self.assertIn('right: "20px"', source)
        self.assertIn("border-radius:28px", source)
        self.assertIn("@keyframes klinot-orb-in", source)
        self.assertIn("@keyframes klinot-pulse", source)
        self.assertIn('data-klinot-busy="1"', source)
        self.assertIn('[data-klinot-log-orb]:hover', source)
        self.assertIn("saveBridgeWidgetState({top})", source)
        self.assertNotIn("saveBridgeWidgetState({left, top})", source)
        self.assertIn("await fillFormDraft(transfer", source)
        self.assertIn("const editorAlreadyVisible", source)
        self.assertIn("controlSwitch.checked !== fields.is_control_suggested", source)
        self.assertIn("async function fillSystemInquiry", source)
        self.assertIn("waitForClinicalFormReady", source)
        self.assertIn("await waitFor(systemInquiryOpener, 30000)", source)
        self.assertIn("clearLastKlinotDraft", source)
        self.assertIn("LAST_DRAFT_SNAPSHOT_KEY", source)
        self.assertIn("capturePersistedDraftBaseline", source)
        self.assertIn("restorePersistedDraft", source)
        self.assertIn('removeCompactEntry("Özgeçmiş", key)', source)
        self.assertIn("removeDiagnosis(code)", source)
        self.assertIn("persisted_baseline: persistedBaseline", source)
        self.assertIn('message?.type !== "klinot-clear-last-transfer"', source)
        self.assertIn("SYSTEM_REVIEW_DEFAULTS", source)
        self.assertIn('labelNode.control', source)
        self.assertIn('input.click()', source)
        self.assertIn('.document-fill__footer button[data-test=\"co-button-Kaydet\"]', source)
        self.assertIn("if (!formResult.systemSaved)", source)
        self.assertIn("system_inquiry_saved", source)
        self.assertIn("fieldResults", source)
        self.assertIn("profileItemAlreadyPresent", source)
        self.assertIn("async function fillPainScore", source)
        self.assertIn('.co-popover input[type="range"]', source)
        self.assertIn('pain.start_date?.unit === "day"', source)
        self.assertIn('["Engellilik Durumu", profile.disabilities]', source)
        self.assertIn('normalized.age_group = age >= 65 ? "65_plus" : "under_65"', source)
        self.assertIn('textOf(item).includes("Düşme Hikayesi")', source)
        self.assertIn("for (const [label, selected, yes, no] of choices)", source)
        self.assertIn("if (!clickFieldOption(label, selected ? yes : no, popover)) return false", source)
        self.assertIn('const target = cells.slice(1).find', source)
        self.assertIn('[data-test="co-button-icon-arti"]', source)
        self.assertIn("const alreadyPresent", source)
        self.assertIn("closeKnownDuplicateProfileNotice", source)
        self.assertIn("profileEntryAlreadyPresent", source)
        self.assertIn("waitForDomQuiet", source)
        self.assertIn("Özgeçmiş son kontrolleri yapılıyor", source)
        self.assertIn("Aktarım bitti · Genel doktor kontrolü gerekli", source)
        self.assertIn("klinot_comed_bridge_log_v1", source)
        self.assertIn("İşlem günlüğü", source)
        self.assertIn("data-klinot-log-panel", source)
        self.assertNotIn("data-klinot-log-drag", source)
        self.assertIn("bridgeContext()", source)
        self.assertIn("parsePatientIdentity()", source)
        self.assertIn("schedulePatientIdentitySync", source)
        self.assertIn("new MutationObserver(schedulePatientIdentitySync)", source)
        self.assertIn("patient-clinical-card(?:", source)
        self.assertIn("data-klinot-log-panel-count", source)
        self.assertIn("Kontrol gerekli", source)
        self.assertIn("bridgeFieldStatus(field, ok)", source)
        self.assertIn("unresolved_count", source)
        self.assertIn("bu hastal[ıi]k hastaya ait bu protokol", source)
        self.assertIn("function isMainClinicalSaveButton", source)
        self.assertIn('".co-modal,.co-document-popup,[role=dialog],.document-fill__footer"', source)
        self.assertIn("sessionStorage.removeItem(ACTIVE_TRANSFER_KEY);\n    activeTransferId = null;", source)
        self.assertIn("sessionStorage.setItem(ACTIVE_TRANSFER_KEY, String(transfer.id));\n      activeTransferId = transfer.id;", source)
        self.assertIn("if (!activeTransferId || !isMainClinicalSaveButton(button)) return;", source)
        self.assertLess(source.index("const systemResult = await fillSystemInquiry"),
                        source.index('const complaintCard = cardByTitle("Yakınması")'))
        self.assertNotIn('textOf(button) === "Kaydet ve İmzala"', source)
        self.assertNotIn('textOf(button) === "Kaydet" && button.click', source)

    def test_page_tracer_only_observes_and_never_posts(self):
        """page_trace artik yalnizca gozlemci; COMED'e istek gondermez."""
        source = (EXTENSION / "page_trace.js").read_text(encoding="utf-8")
        self.assertIn('"x-authentication-token"', source)
        # POST calistirici tamamen kaldirildi.
        for removed in (
            "NATIVE_ENDPOINTS",
            "executeNativePosts",
            "klinot-comed-native-command-v1",
            "nativeFetch",
            "API_BASE",
        ):
            self.assertNotIn(removed, source)
        self.assertIn("klinot-comed-suppress-reload-prompt-once", source)
        self.assertIn('window.addEventListener("beforeunload"', source)
        self.assertIn("event.stopImmediatePropagation()", source)
        self.assertIn('data-klinot-comed-trace-installed', source)
        self.assertNotIn('window.__klinotComedTraceInstalled', source)
        self.assertNotIn('window.__klinotComedTraceEvents', source)
        self.assertNotIn("saveAndSign", source)

    def test_manifest_declares_current_version(self):
        """Eklenti sürümü uygulama sürümüyle aynı kalmalı (elle senkron tutma)."""
        manifest = json.loads((EXTENSION / "manifest.json").read_text(encoding="utf-8"))
        app_version = re.search(
            r'APP_VERSION\s*=\s*os\.getenv\(\s*"APP_VERSION"\s*,\s*"v([\d.]+)"',
            (ROOT / "config.py").read_text(encoding="utf-8"),
        )
        self.assertIsNotNone(app_version, "config.py içinde APP_VERSION bulunamadı")
        self.assertEqual(manifest["version"], app_version.group(1))
        self.assertIn("tabs", manifest["permissions"])
        scripts = [item for item in manifest["content_scripts"]
                   if "doctor_bridge.js" in item.get("js", [])]
        self.assertEqual(len(scripts), 1)

    def test_doctor_panel_reuses_comed_tab_and_resumes_after_login(self):
        background = (EXTENSION / "background.js").read_text(encoding="utf-8")
        doctor_bridge = (EXTENSION / "doctor_bridge.js").read_text(encoding="utf-8")
        doctor_panel = (ROOT / "static" / "doctor.js").read_text(encoding="utf-8")

        self.assertIn("chrome.tabs.query({})", background)
        self.assertIn("chrome.tabs.update(tab.id", background)
        self.assertIn("chrome.tabs.onUpdated.addListener", background)
        self.assertIn("pendingComedNavigation", background)
        self.assertIn("isComedAuthUrl(tab.url)", background)
        self.assertIn("klinot-open-comed", doctor_bridge)
        self.assertIn("klinot-doctor-comed-open-v1", doctor_panel)
        self.assertIn("openComedWithBridge", doctor_panel)
        self.assertNotIn("const opened=window.open(selectedPatient.clinical_card_url", doctor_panel)

    def test_popup_exposes_safe_draft_cleanup(self):
        popup = (EXTENSION / "popup.html").read_text(encoding="utf-8")
        popup_script = (EXTENSION / "popup.js").read_text(encoding="utf-8")
        self.assertIn('id="clear-draft"', popup)
        self.assertIn("klinot-clear-last-transfer", popup_script)
        self.assertIn("chrome.tabs.sendMessage", popup_script)
        self.assertIn("ICD ve özgeçmiş dâhil", popup_script)


if __name__ == "__main__":
    unittest.main()
