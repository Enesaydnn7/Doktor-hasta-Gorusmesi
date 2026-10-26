"""İstem akışı: canlı COMED'de ölçülen davranışlar (26 Ekim 2026).

Bu dosyadaki kurallar, ``scripts/live_order_test.py`` ile content.js'ten
BİREBİR çıkarılan üretim kodu canlı COMED'de (hasta 22207363) koşturularak
bulundu. Test diyaloğu: EKG, EKO, akciğer grafisi, tam kan, CRP, troponin +
Parol/Augmentin/Ventolin/Nexium/Aferin.

Son koşu (14:42:53 → 14:44:03), COMED'in kendi istem listelerinden bağımsız
okunarak doğrulandı:

    Hizmet İstem : Elektrokardiogram (EKG)
    Tetkik İstem : CRP (kantitatif), Troponin I, Akciğer Grafisi (İki Yön)
    İlaç İstem   : PAROL Tablet 500 mg

Kalanlar katalog boşluğu: düz "Ekokardiyografi" yok (yalnız 3D/Fetal/Stres),
"Tam Kan Sayımı"nın katalog adı "Hemogram" ve o da pasif; Augmentin, Ventolin,
Nexium, Aferin COMED ilaç kataloğunda yok.
"""

import re
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]


class OrderFlowTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.content = (ROOT / "comed_bridge_extension" / "content.js").read_text(
            encoding="utf-8")

    def test_orders_live_in_their_own_function(self):
        """Canlı testte birebir çalıştırılabilsin diye ayrı fonksiyonda."""
        self.assertIn("async function fillOrders(fields, record)", self.content)
        self.assertIn("await fillOrders(fields, record);", self.content)

    def test_orders_come_after_the_form(self):
        """İstek: önce muayene formu, sonra istemler."""
        form_end = self.content.index('record("is_control_suggested", true);')
        call = self.content.index("await fillOrders(fields, record);")
        self.assertLess(form_end, call)

    def test_stale_service_row_is_retried(self):
        """ÖLÇÜLDÜ: ekran ilk açıldığında liste yeniden çiziliyor; ilk istem
        (EKG) kopuk satıra basılıp "istem penceresi açılmadı" diye düşüyordu.
        Tek başına denendiğinde pencere 0,5 sn'de açılıyordu."""
        self.assertIn("row.isConnected ? row : matchServiceRow(name)", self.content)
        self.assertIn("deneme < 2", self.content)

    def test_service_failures_are_handed_to_the_study_screen(self):
        """ÖLÇÜLDÜ: Akciğer Grafisi ve Troponin Hizmet İstem'de ek alan
        istiyor, Tetkik İstem'de ekleniyor. Hizmet'te vazgeçmek yerine devret."""
        self.assertIn('hizmetNotu: "istem penceresi açılmadı"', self.content)
        self.assertIn("Hizmet İstem'de ek zorunlu alan istiyor", self.content)
        self.assertIn("Tetkik İstem'de de bulunamadı", self.content)


class StudyScreenRecoveryTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.content = (ROOT / "comed_bridge_extension" / "content.js").read_text(
            encoding="utf-8")

    def test_list_view_is_turned_back_into_the_add_view(self):
        """ÖLÇÜLDÜ: Tetkik ekranı "Ekle"den sonra istem LİSTESİ görünümüne
        dönebiliyor; favori ağacı yok, sonraki 8 paket sessizce atlanıyordu.
        "Yeni Tetkik İstem" ekleme görünümünü geri getiriyor."""
        self.assertIn("async function ensureStudyAddView(", self.content)
        self.assertIn('[data-test="co-button-Yeni Tetkik İstem"]', self.content)
        self.assertIn("Tetkik paketi menüde görünmüyor", self.content)

    def test_screen_is_reopened_fresh_after_each_submitted_package(self):
        """ÖLÇÜLDÜ: bir paketin "Ekle"sinden sonra onay kutusu görünüşte
        tikleniyor ama alt istek paneli açılmıyor, "Ekle" pasif kalıyor."""
        self.assertIn("let ekranKirli = false;", self.content)
        self.assertIn("ekranKirli = true;", self.content)
        self.assertRegex(
            self.content,
            r"if \(ekranKirli\) \{\s*await closeOrderScreen\(\);\s*if \(!await openStudyScreen\(\)\)",
        )

    def test_package_header_is_awaited_before_matching(self):
        self.assertIn(r"/^Favoriler\s*:/i", self.content)

    def test_failed_package_ticks_are_cleared(self):
        self.assertIn("function untickStudyRows(", self.content)
        self.assertGreaterEqual(self.content.count("untickStudyRows(isaretli.map("), 3)


class AddedMeansSavedTests(unittest.TestCase):
    """"Eklendi" demek COMED listesine DÜŞTÜ demek olmalı.

    ÖLÇÜLDÜ: hata çıkmaması kaydedildiği anlamına gelmiyordu. Tam koşuda
    sayaç "3 tetkik eklendi" dedi, COMED'in istem listesine tek satır
    düşmedi. Doktora "eklendi" deyip eklememek en kötü sonuç.
    """

    @classmethod
    def setUpClass(cls):
        cls.content = (ROOT / "comed_bridge_extension" / "content.js").read_text(
            encoding="utf-8")

    def test_success_is_measured_on_the_order_list(self):
        self.assertIn("function studyOrderRows(", self.content)
        self.assertIn("function newStudyOrderCount(before)", self.content)
        self.assertIn("const listeOnce = studyOrderRows();", self.content)
        self.assertIn("COMED istem listesine düşmedi", self.content)

    def test_counter_only_counts_rows_that_landed(self):
        self.assertIn("result.added += Math.min(dusen, isaretli.length);", self.content)
        self.assertNotIn("result.added += isaretli.length;", self.content)


class LiveTestBundleTests(unittest.TestCase):
    """Canlı test paketi gerçekten üretim kodundan çıkarılmalı."""

    def test_bundle_extracts_the_production_order_flow(self):
        import importlib.util

        spec = importlib.util.spec_from_file_location(
            "live_order_test", ROOT / "scripts" / "live_order_test.py")
        module = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(module)
        bundle = module.bundle()
        for name in ("fillOrders", "fillServiceRequests", "fillDrugRequests",
                     "fillStudyRequests", "closeOrderScreen", "ensureStudyAddView",
                     "newStudyOrderCount", "matchStudyRow", "scoreDrugOption"):
            with self.subTest(fonksiyon=name):
                self.assertRegex(bundle, rf"\n  (async )?function {name}\(")
        # Chrome'a ozgu islevler saplanmali, gercek tanimlari pakete girmemeli.
        self.assertNotIn("chrome.runtime.sendMessage", bundle)
        self.assertIn("window.__klinot = {log,", bundle)


if __name__ == "__main__":
    unittest.main()
