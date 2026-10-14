import hashlib
import unittest
from pathlib import Path
from unittest.mock import patch

from fastapi.testclient import TestClient

import auth
import main
import pdf_report


ROOT = Path(__file__).resolve().parents[1]
COMED_HOST_IN_TESTS = "goztepetest.comed.mlpcare.com"


class BrowserStateRegressionTests(unittest.TestCase):
    def test_audio_analysis_state_is_declared_before_first_use(self):
        js = (ROOT / "static" / "app.js").read_text(encoding="utf-8")
        self.assertLess(js.index("let lastAudioId = null"), js.index("audio_id: lastAudioId"))
        self.assertLess(
            js.index("let lastTranscribeUsage = null"),
            js.index("stt_usage: lastTranscribeUsage"),
        )

    def test_static_scripts_are_versioned_to_bypass_stale_browser_cache(self):
        index = (ROOT / "templates" / "index.html").read_text(encoding="utf-8")
        admin = (ROOT / "templates" / "admin.html").read_text(encoding="utf-8")
        self.assertIn("/static/app.js?v={{ version }}", index)
        self.assertIn("/static/admin.js?v={{ version }}", admin)

    def test_doctor_score_uses_risk_aware_colors(self):
        css = (ROOT / "static" / "style.css").read_text(encoding="utf-8")
        # Rapor render katmani /admin ve /doctor panellerinde paylasilir.
        report_js = (ROOT / "static" / "report_view.js").read_text(encoding="utf-8")
        app_js = (ROOT / "static" / "app.js").read_text(encoding="utf-8")
        for name in ("score-low", "score-mid", "score-high"):
            self.assertIn(name, css)
            self.assertIn(name, report_js)
            self.assertIn(name, app_js)

    def test_admin_repairs_infinite_webm_duration(self):
        admin_js = (ROOT / "static" / "admin.js").read_text(encoding="utf-8")
        report_js = (ROOT / "static" / "report_view.js").read_text(encoding="utf-8")
        self.assertIn('preload="metadata"', admin_js)
        self.assertIn("audio.duration !== Infinity", report_js)
        self.assertIn("audio.currentTime = Number.MAX_SAFE_INTEGER", report_js)

    def test_legacy_pdf_names_are_normalized_in_browser(self):
        js = (ROOT / "static" / "admin.js").read_text(encoding="utf-8")
        self.assertIn('epikriz: "doktor"', js)
        self.assertIn('aliases[rawRec] || "doktor"', js)

    def test_admin_exposes_doctor_reviewed_comed_workflow(self):
        js = (ROOT / "static" / "admin.js").read_text(encoding="utf-8")
        report_js = (ROOT / "static" / "report_view.js").read_text(encoding="utf-8")
        html = (ROOT / "templates" / "admin.html").read_text(encoding="utf-8")
        css = (ROOT / "static" / "admin.css").read_text(encoding="utf-8")

        self.assertIn("COMED taslağı", report_js)
        self.assertIn("/admin/comed/transfer/", js)
        self.assertIn("Otomatik imza kapalıdır", report_js)
        self.assertIn("COMED taslağı bulunmuyor", report_js)
        self.assertIn("POST ile giden", report_js)
        self.assertIn("Eklentinin doldurduğu", report_js)
        self.assertIn("Operasyonel varsayılan", report_js)
        self.assertIn('["doktor", "hasta", "yonetim"].includes(sekme)', js)
        self.assertIn("COMED aktarımı", html)
        self.assertIn("comed-action-bar", css)

    def test_doctor_panel_shares_the_admin_report_layer(self):
        """Doktor paneli yonetici panelindeki tum rapor gorunumlerini kullanir."""
        html = (ROOT / "templates" / "doctor.html").read_text(encoding="utf-8")
        js = (ROOT / "static" / "doctor.js").read_text(encoding="utf-8")

        # Ortak render katmani doctor.js'ten ONCE yuklenmeli.
        self.assertLess(
            html.index("/static/report_view.js"),
            html.index("/static/doctor.js"),
        )
        self.assertIn("/static/admin.css", html)
        # Sekmeler yonetici panelindeki gibi detay icinde uretilir.
        for tab in ("doktor", "hasta", "yonetim", "comed", "transkript"):
            self.assertIn(f'"{tab}"', js)
        self.assertIn("bodyHTML(k, sekme)", js)
        self.assertIn("prepareAudioTimeline(slot)", js)
        self.assertIn("/doctor/audio/", js)
        self.assertIn("/doctor/pdf/", js)
        self.assertIn("comed-action-bar", js)
        # Ortak katmandaki esc/val/fmtUsd ile cakismamali.
        self.assertNotIn("function esc(", js)
        self.assertNotIn("const esc =", js)

    def test_doctor_audio_endpoint_supports_byte_range(self):
        """Ses oynatici takilmasin: doktor ucu da admin gibi 206 donmeli.

        Range destegi olmadan tarayici ses dosyasinda ileri/geri atlayamiyor
        ve oynatma kendi kendine duruyordu.
        """
        main_py = (ROOT / "main.py").read_text(encoding="utf-8")
        self.assertIn("def _audio_response(", main_py)
        self.assertIn("Accept-Ranges", main_py)
        # Iki uc da ayni yardimciyi kullanmali ki davranis ayrismasin.
        self.assertEqual(main_py.count("return _audio_response(request, data, mime"), 2)

    def test_doctor_panel_does_not_restart_playing_audio(self):
        """15 saniyelik arka plan yenilemesi calan kaydi kesmemeli."""
        js = (ROOT / "static" / "doctor.js").read_text(encoding="utf-8")
        self.assertIn("function audioPlaying(", js)
        self.assertIn("if (silent && audioPlaying()) return;", js)
        # Chrome, DOM'dan CIKARILAN medya dugumunu durdurur. Bu yuzden dugum
        # remove() edilmez, gorunmez park kabina TASINIR ve geri takilir.
        self.assertIn("function audioPark(", js)
        self.assertIn("park.appendChild(audio)", js)
        self.assertNotIn("audio.remove()", js)
        # Detay ve kayit listesi yeniden yazilmadan once park edilir.
        self.assertIn("parkLiveAudio(det)", js)
        self.assertIn("parkLiveAudio(list)", js)
        self.assertIn("restoreLiveAudio(det)", js)

    def test_doctor_worklist_looks_like_the_comed_worklist(self):
        """Is listesi COMED'deki gibi satir satir tablo olmali, kart degil."""
        js = (ROOT / "static" / "doctor.js").read_text(encoding="utf-8")
        css = (ROOT / "static" / "doctor.css").read_text(encoding="utf-8")
        html = (ROOT / "templates" / "doctor.html").read_text(encoding="utf-8")

        # COMED is listesindeki sutunlar
        for column in ("Hasta", "Hasta no", "Protokol", "İşlem / bölüm", "Doktor", "Durum"):
            self.assertIn(f'<span role="columnheader">{column}</span>', js)
        self.assertIn('class="wl-table" role="table"', js)
        self.assertIn('class="wl-row', js)
        self.assertIn(".wl-head,.wl-row{display:grid", css)

        # Eski kart duzeni tamamen kalkmali
        for stale in ("CARD_COLORS", "patient-card", "patient-avatar", "pc-tag"):
            self.assertNotIn(stale, js, f"{stale} doctor.js'te kalmis")
            self.assertNotIn(stale, css, f"{stale} doctor.css'te kalmis")
        self.assertNotIn("worklist-grid", html)

        # Satira tiklayinca kayit listesi yine suzulur
        self.assertIn("rec-filter", js)
        self.assertIn("rec-filter", css)

    def test_extension_speed_scales_the_slow_waits_too(self):
        """Hiz ayari hissedilmeli: asil sure waitForDomQuiet'te geciyor.

        Onceki surumde yalnizca sleep() olceklendigi icin 2.5x bile fark
        yaratmiyordu (sleep toplami ~2.7 sn, DOM beklemeleri 1.5-12.7 sn).
        """
        content = (ROOT / "comed_bridge_extension" / "content.js").read_text(
            encoding="utf-8"
        )
        self.assertIn("function scaled(ms, floor)", content)
        # Asil kazanc: DOM sakinlesme beklemeleri de olceklenir.
        self.assertIn("const sessizlik = scaled(quietMs, 40);", content)
        self.assertIn("scaled(timeoutMs, 400)", content)
        # waitFor'un yoklama sikligi olceklenir ama ZAMAN ASIMI olceklenmez.
        self.assertIn("const poll = scaled(120, 40);", content)

    def test_speed_change_applies_mid_transfer(self):
        """Hiz, doldurma SURERKEN degistirilince hemen gecerli olmali.

        Beklemeler tek parca setTimeout olsaydi o an suren 3,5 saniyelik
        bekleme eski hizla biter, doktor "ayar tutmuyor" sanirdi.
        """
        content = (ROOT / "comed_bridge_extension" / "content.js").read_text(
            encoding="utf-8"
        )
        # sleep dilim dilim bekler, her dilimde fillSpeed yeniden okunur.
        self.assertIn("async function sleep(ms)", content)
        self.assertIn("while (kalan > 0)", content)
        self.assertIn("const hiz = fillSpeed || 1;", content)
        # waitForDomQuiet periyodik kontrol yapar, sabit timer kurmaz.
        self.assertIn("}, 30);", content)
        self.assertIn("const sessizlik = scaled(quietMs, 40);", content)
        self.assertNotIn("quietTimer = setTimeout(finish, quietMs)", content)
        # Degisiklik doktora bildirilir.
        self.assertIn("Doldurma hızı ${etiket}", content)

    def test_stuck_comed_transfer_can_be_retried(self):
        """Takilan aktarim dugmeyi sonsuza kadar pasif birakmamali.

        Eklenti kapaliysa ya da kopru yanit vermediyse aktarim "queued"da
        asili kaliyor ve doktor bir daha hic deneyemiyordu.
        """
        db_py = (ROOT / "db.py").read_text(encoding="utf-8")
        main_py = (ROOT / "main.py").read_text(encoding="utf-8")
        js = (ROOT / "static" / "doctor.js").read_text(encoding="utf-8")

        # Takilma SUNUCU saatiyle hesaplanir (tarayici saat dilimi yaniltmasin)
        self.assertIn("COMED_TRANSFER_STUCK_SECONDS", db_py)
        self.assertIn('data["stale"]', db_py)
        self.assertIn('data["age_seconds"]', db_py)
        # Birakma ucu
        self.assertIn("/doctor/api/comed/transfers/{transfer_id}/cancel", main_py)
        self.assertIn("Doktor aktarımı bıraktı", main_py)
        # Tamamlanmis aktarim yanlislikla birakilamaz
        self.assertIn('{"completed", "ready_for_review"}', main_py)
        # Panel: takildiysa kilit acilir, "Yeniden aktar" cikar
        self.assertIn("!transfer.stale", js)
        self.assertIn("Yeniden aktar", js)
        self.assertIn("data-comed-cancel", js)
        self.assertIn("comedVazgec", js)

    def test_card_always_opens_without_asking_the_doctor_for_anything(self):
        """Doktor hiçbir ek adım yapmamalı: kart her durumda açılmalı."""
        js = (ROOT / "static" / "doctor.js").read_text(encoding="utf-8")
        background = (ROOT / "comed_bridge_extension" / "background.js").read_text(
            encoding="utf-8"
        )
        # MV3 service worker uyanmasi icin sure uzatildi
        self.assertIn("BRIDGE_OPEN_TIMEOUT_MS = 7000", js)
        # Kopru yanit vermezse kart YINE DE acilir (eski calisan davranis),
        # ama adres bos ise acilmaz: bos adresle window.open bos sekme acar.
        self.assertIn('window.open(kartAdresi, "_blank")', js)
        self.assertIn("} else if (kartAdresi) {", js)
        # Eklenti dogrudan hedef adresle sekme acar (about:blank bos kaliyordu)
        self.assertIn("chrome.tabs.create({url: target.href", background)
        self.assertNotIn('url: "about:blank"', background)
        # Eklenti guncellenince Klinot PANELI sekmeleri kendiliginden yenilenir
        self.assertIn("chrome.runtime.onInstalled.addListener", background)
        self.assertIn("chrome.tabs.reload", background)
        self.assertIn("BRIDGE_PANEL_PAGES", background)
        for page in ("doktor-hasta-gorusmesi.onrender.com", "127.0.0.1:8000"):
            self.assertIn(page, background)
        # COMED sekmesi BILEREK yenilenmez: doldurulmus formda tarayici
        # "siteden ayrilmak istiyor musunuz?" diye soruyor ve doktorun
        # kaydedilmemis verisi riske giriyor.
        panel_pages = background[
            background.index("const BRIDGE_PANEL_PAGES"):background.index("chrome.runtime.onInstalled")
        ]
        self.assertNotIn(COMED_HOST_IN_TESTS, panel_pages)

    def test_transfer_reports_its_duration_and_speed(self):
        """Doktor hız ayarının etkisini tahmin değil rakamla görmeli."""
        content = (ROOT / "comed_bridge_extension" / "content.js").read_text(
            encoding="utf-8"
        )
        self.assertIn("Date.parse(startedAt)", content)
        self.assertIn("${gecen} sn · ${hizEtiketi} hız", content)
        # Balondaki kisa metin de olcumu gostersin
        self.assertIn("`Aktarım bitti${olcum}`", content)

    def test_doctor_can_transfer_again_after_it_finished(self):
        """Doktor COMED'de kaydı silip yeniden aktarabilmeli."""
        js = (ROOT / "static" / "doctor.js").read_text(encoding="utf-8")
        # Yalnizca GERCEKTEN suren aktarim dugmeyi kilitler
        self.assertIn("const locked = calisiyor;", js)
        self.assertIn("Tekrar aktar", js)
        # Bitmis aktarim artik kilitlemiyor
        self.assertNotIn("const locked = calisiyor || bitti;", js)

    def test_failed_bridge_does_not_cancel_the_queued_transfer(self):
        """REGRESYON TESTI: sekme acilamasa bile aktarim sirada kalmali.

        Sekme acma yalnizca bir kolayliktir; asil doldurmayi COMED
        sayfasindaki eklenti yapar. Aktarim "queued" kaldigi surece doktor
        COMED kartina kendi gecince is yurur. Bir ara surumde kopru yanit
        vermeyince aktarim iptal ediliyordu ve calisan tek yol da kapanmisti.
        """
        js = (ROOT / "static" / "doctor.js").read_text(encoding="utf-8")
        gonder = js[js.index("async function comedAktar("):js.index("async function pollTransfer(")]
        # Basarisiz acilista iptal ucu CAGRILMAMALI
        self.assertNotIn("/cancel", gonder)
        # Ve yoklama yine baslar: eklenti isi alinca panel durumu gorur
        self.assertIn("await pollTransfer(id, activeTransfer.id);", gonder)

    def test_doctor_bridge_always_answers_the_panel(self):
        """Kopru sessizce olmemeli; panel bosuna zaman asimi beklemesin."""
        bridge = (ROOT / "comed_bridge_extension" / "doctor_bridge.js").read_text(
            encoding="utf-8"
        )
        # Sahipsiz content script senkron hata atar; yakalanmazsa panel
        # yalnizca zaman asimi gorur.
        self.assertIn("} catch (error) {", bridge)
        self.assertIn("reply(requestId", bridge)
        # MV3 arka plan betigi uykudaysa bir kez yeniden denenir
        self.assertIn("ask(message, requestId, false)", bridge)

    def test_patient_waits_for_appointment_without_manual_refresh(self):
        """Hasta randevusu baglanana kadar uygulama kendisi denemeli."""
        dart = (ROOT / "mobile_app" / "lib" / "recorder_screen.dart").read_text(
            encoding="utf-8"
        )
        content = (ROOT / "comed_bridge_extension" / "content.js").read_text(
            encoding="utf-8"
        )
        self.assertIn("_randevuyuBeklemeyeAl", dart)
        self.assertIn("_worklistRetry", dart)
        self.assertIn("_maxWorklistTries", dart)
        self.assertIn("_worklistRetry?.cancel();", dart)  # dispose'da temizlenir
        # Beklerken ne oldugu yaziyor
        self.assertIn("_PatientAppointmentWaiting", dart)
        self.assertIn("Randevunuz aranıyor", dart)
        # Is listesi satirindan dogum tarihi de toplanir
        self.assertIn("birth_date:", content)

    def test_doctor_record_rows_identify_the_patient(self):
        """Kayit listesi COMED gibi: zebra satirlar ve hasta adi sutunu."""
        js = (ROOT / "static" / "doctor.js").read_text(encoding="utf-8")
        css = (ROOT / "static" / "doctor.css").read_text(encoding="utf-8")
        html = (ROOT / "templates" / "doctor.html").read_text(encoding="utf-8")
        self.assertIn("<span>Hasta bilgileri</span>", html)
        self.assertIn('class="rec-patient"', js)
        self.assertIn("rp-avatar", js)
        self.assertIn("function initials(", js)
        # Bir beyaz bir grimsi. Sira JS'ten gelir: suzgec seridi de listenin
        # cocugu oldugu icin nth-child sayimi kayiyordu.
        self.assertIn('data-zebra="${sira % 2}"', js)
        self.assertIn('#rec-list .rec-item[data-zebra="1"] .rec-row{background:', css)
        self.assertNotIn("nth-child(even)", css)
        # Hasta adiyla da aranabilmeli
        self.assertIn("${adSoyad}", js)

    def test_fill_speed_is_a_slider_in_the_popup_only(self):
        """Hiz ayari yalnizca eklenti penceresinde ve kaydiracli olmali."""
        content = (ROOT / "comed_bridge_extension" / "content.js").read_text(
            encoding="utf-8"
        )
        popup_js = (ROOT / "comed_bridge_extension" / "popup.js").read_text(
            encoding="utf-8"
        )
        popup_html = (ROOT / "comed_bridge_extension" / "popup.html").read_text(
            encoding="utf-8"
        )
        popup_css = (ROOT / "comed_bridge_extension" / "popup.css").read_text(
            encoding="utf-8"
        )
        # Kaydirac
        self.assertIn('type="range"', popup_html)
        self.assertIn('id="speed-slider"', popup_html)
        self.assertIn('speedSlider.addEventListener("input"', popup_js)
        self.assertIn("::-webkit-slider-thumb", popup_css)
        # COMED sayfasindaki balonda hiz ayari KALMAMALI
        self.assertNotIn("data-klinot-speed", content)
        self.assertNotIn("syncSpeedButtons", content)
        # Yine de content.js hizi storage'dan okuyup uygulamali
        self.assertIn("changes.fillSpeed", content)

    def test_doctor_panel_shows_the_model_like_admin(self):
        """Doktor paneli de hangi modelin kullanildigini gostermeli."""
        html = (ROOT / "templates" / "doctor.html").read_text(encoding="utf-8")
        main_py = (ROOT / "main.py").read_text(encoding="utf-8")
        self.assertIn('<div class="s-lbl">Model</div>', html)
        self.assertIn("{{ provider }}", html)
        self.assertIn("{{ stt_provider }}", html)
        # doctor.html'e provider gercekten geciriliyor mu?
        self.assertIn('"provider": config.label()', main_py)
        self.assertIn('"stt_provider": config.stt_label()', main_py)

    def test_family_history_is_never_left_empty(self):
        """Soygecmis zorunlu: veri yoksa bile Ozellik Yok/Goruldu isaretlenir."""
        content = (ROOT / "comed_bridge_extension" / "content.js").read_text(
            encoding="utf-8"
        )
        self.assertIn("async function markCardOption(", content)
        self.assertIn("async function markFamilyHistoryEmpty(", content)
        self.assertIn('FAMILY_EMPTY_LABELS = ["Özellik Yok"', content)
        self.assertIn("Görüldü", content)
        # Erken cikislarin hepsi bos birakmak yerine isaretlemeye dusmeli.
        self.assertNotIn('clickCardOption("Soygeçmiş"', content)
        self.assertNotIn('clickCardOption("Düşme Riski"', content)

    def test_comed_bridge_never_auto_signs_or_embeds_credentials(self):
        manifest = (ROOT / "comed_bridge_extension" / "manifest.json").read_text(
            encoding="utf-8"
        )
        content = (ROOT / "comed_bridge_extension" / "content.js").read_text(
            encoding="utf-8"
        )
        background = (ROOT / "comed_bridge_extension" / "background.js").read_text(
            encoding="utf-8"
        )
        trace = (ROOT / "comed_bridge_extension" / "page_trace.js").read_text(
            encoding="utf-8"
        )

        self.assertIn("goztepetest.comed.mlpcare.com", manifest)
        self.assertIn("ready_for_review", content)
        # Dogrulanmis POST sablonu akisi kaldirildi; tum alanlar form
        # doldurularak hazirlanir, kaydi ve imzayi doktor yapar.
        self.assertNotIn("klinot-comed-native-command-v1", content)
        self.assertNotIn("executeNativePosts", content)
        self.assertIn("function cardByTitle", content)
        self.assertIn("function inputByLabel", content)
        self.assertIn("function setValue", content)
        self.assertIn("fillDiagnoses", content)
        self.assertIn("async function fillFormDraft", content)
        self.assertNotIn('textOf(button) === "Kaydet ve İmzala"', content)
        self.assertNotIn("x-authentication-token", background.lower())
        self.assertIn('"world": "MAIN"', manifest)
        self.assertIn("klinot-comed-trace-v1", trace)
        # page_trace yalnizca gozlemcidir; COMED'e istek gondermez.
        self.assertNotIn("klinot-comed-native-command-v1", trace)
        self.assertNotIn("NATIVE_ENDPOINTS", trace)
        self.assertIn("data-klinot-comed-trace-installed", trace)
        self.assertNotIn("window.__klinotComedTrace", trace)
        self.assertNotIn("getAllCookieStores", trace)
        self.assertNotIn("document.cookie", trace)

    def test_session_fallback_secret_is_stable(self):
        expected = hashlib.sha256(
            f"klinik-admin-session\0{auth.ADMIN_USER}\0{auth.ADMIN_PASS}".encode()
        ).hexdigest()
        self.assertEqual(auth._fallback_secret, expected)


class PdfRegressionTests(unittest.TestCase):
    def test_all_report_types_accept_special_characters(self):
        reports = {
            "hasta": {
                "ozet": "Ağrı < 3 gün & giderek artıyor",
                "tani": "Gastrit > reflü?",
                "yapilacaklar": ["Aç & tok takibi", "1 < 2"],
                "ilaclar": ["İlaç A&B"],
                "kontrol": "2 < 3 hafta",
                "kapanis": "Acil belirti > beklemeyin",
            },
            "doktor": {
                "epikriz": {
                    "gorusmeTarihi": "01.09.2026 < kontrol",
                    "oyku": "Ağrı & yanma < 10 gündür",
                    "ozgecmis": {"kronik": ["A&B"], "ameliyatlar": ["Safra < 2019"]},
                    "soygecmis": ["Ülser & gastrit"],
                    "icd": [{"kod": "K29<test>"}],
                    "tedavi": ["Doz A&B"],
                    "kontrol": {},
                },
                "koclugu": {},
            },
            "yonetim": {
                "guvenlik": {"durum": "temiz", "tespitler": ["A&B < sorun yok"]},
                "skor": {},
                "verimlilikNotu": "Süre < hedef & güvenli",
                "degerlendirme": "A&B < C",
                "risk": "düşük < orta",
            },
        }
        for report_type, report in reports.items():
            with self.subTest(report_type=report_type):
                content, filename = pdf_report.build_pdf(report_type, report)
                self.assertTrue(content.startswith(b"%PDF-"))
                self.assertGreater(len(content), 1000)
                self.assertTrue(filename.endswith(".pdf"))


class AdminMediaEndpointTests(unittest.TestCase):
    def setUp(self):
        self.client = TestClient(main.app)
        response = self.client.post(
            "/admin/login",
            data={"user": auth.ADMIN_USER, "password": auth.ADMIN_PASS},
        )
        self.assertEqual(response.status_code, 200)

    def test_audio_supports_full_head_and_partial_range_requests(self):
        audio = b"0123456789"
        with patch.object(
            main.db, "ses_getir", return_value=(audio, "audio/webm", "görüşme.webm")
        ):
            full = self.client.get("/admin/ses/99")
            head = self.client.head("/admin/ses/99")
            partial = self.client.get(
                "/admin/ses/99", headers={"Range": "bytes=2-5"}
            )
            invalid = self.client.get(
                "/admin/ses/99", headers={"Range": "bytes=99-"}
            )

        self.assertEqual(full.status_code, 200)
        self.assertEqual(full.content, audio)
        self.assertEqual(full.headers["accept-ranges"], "bytes")
        self.assertEqual(head.status_code, 200)
        self.assertEqual(head.headers["content-length"], str(len(audio)))
        self.assertEqual(partial.status_code, 206)
        self.assertEqual(partial.content, b"2345")
        self.assertEqual(partial.headers["content-range"], "bytes 2-5/10")
        self.assertEqual(invalid.status_code, 416)
        self.assertEqual(invalid.headers["content-range"], "bytes */10")

    def test_saved_demo_produces_all_three_admin_pdfs(self):
        records = main.db.liste()
        for audio_name in (
            "gastrit_demo_kayit_2_2026-08-27.webm",
            "klinot_1788972814701.m4a",
        ):
            demo = next(
                record for record in records if record["ses_ad"] == audio_name
            )
            for report_type in ("hasta", "doktor", "yonetim"):
                with self.subTest(audio_name=audio_name, report_type=report_type):
                    response = self.client.post(
                        f"/admin/pdf/{demo['id']}/{report_type}"
                    )
                    self.assertEqual(response.status_code, 200)
                    self.assertTrue(response.content.startswith(b"%PDF-"))
                    self.assertTrue(
                        response.headers["content-type"].startswith("application/pdf")
                    )

    def test_saved_demo_forces_legacy_or_unknown_epikriz_name_to_doctor_pdf(self):
        demo = next(
            record
            for record in main.db.liste()
            if record["ses_ad"] == "gastrit_demo_kayit_2_2026-08-27.webm"
        )
        for legacy_name in ("epikriz", "doktor_epikrizi", "undefined"):
            with self.subTest(legacy_name=legacy_name):
                response = self.client.post(
                    f"/admin/pdf/{demo['id']}/{legacy_name}"
                )
                self.assertEqual(response.status_code, 200)
                self.assertTrue(response.content.startswith(b"%PDF-"))


if __name__ == "__main__":
    unittest.main()
