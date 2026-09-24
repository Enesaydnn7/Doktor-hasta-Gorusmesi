import threading
import unittest
from unittest.mock import patch

import llm


class AnalyzeFlowTests(unittest.IsolatedAsyncioTestCase):
    async def test_reports_and_comed_draft_run_in_parallel(self):
        events = []
        progress_events = []
        usage = {"input": 1, "output": 1, "total": 2}
        barrier = threading.Barrier(4, timeout=3)

        def fake_gemini(system, _user):
            events.append(system)
            barrier.wait()
            return {"ok": True}, usage.copy()

        async def capture_progress(event):
            progress_events.append(event.copy())

        with (
            patch.object(llm, "_gemini", side_effect=fake_gemini),
        ):
            result = await llm.analyze_all("örnek görüşme", progress=capture_progress)

        self.assertCountEqual(events, [
            llm.prompts.SYSTEM_HASTA,
            llm.prompts.SYSTEM_DOKTOR,
            llm.prompts.SYSTEM_YONETIM,
            llm.prompts.SYSTEM_COMED,
        ])
        running = [event for event in progress_events if event["status"] == "running"]
        completed = [event for event in progress_events if event["status"] == "completed"]
        self.assertCountEqual([event["step"] for event in running], ["hasta", "doktor", "yonetim"])
        self.assertEqual(sorted(event["percent"] for event in completed), [33, 67, 100])
        self.assertEqual(result["comed"], {"ok": True})
        self.assertEqual(result["usage"]["calls"], 4)
        self.assertTrue(result["usage"]["parallel"])
        self.assertEqual(result["usage"]["total"], 8)

    def test_comed_is_reconciled_with_epicrisis_without_confusing_duration_and_score(self):
        transcript = (
            "Hasta: Ağrı iki saat önce başladı, şu anda 6 şiddetinde ve baskı şeklinde. "
            "Hipertansiyonum var, amlodipin kullanıyorum, penisiline alerjim var. "
            "2010 yılında apandisit ameliyatı oldum. Annemde diyabet vardı. "
            "Geçen ay evde bir kez düştüm, düşme riskim var. Bazen denge bozukluğu "
            "yaşıyorum; bilincim açık ve çevreye uyumluyum."
        )
        doctor = {"epikriz": {
            "agriSkoru": "6/10",
            "fizikMuayene": "Kalp ritmi düzenli, akciğer sesleri doğal.",
            "ozgecmis": {
                "kronik": ["Hipertansiyon"],
                "ameliyatlar": ["Apandisit ameliyatı (2010)"],
                "ilaclar": ["Amlodipin 5 mg"],
                "alerji": ["Penisilin"],
                "aliskanlik": ["Günde 10 sigara"],
            },
            "soygecmis": ["Annede diyabet"],
            "icd": [{"kod": "R07.4", "aciklama": "Göğüs ağrısı"}],
        }}
        comed = {
            "complaint_start_date": {"value": 2, "unit": "hour", "before": True},
            "pain": {"exists": True, "score": 2, "qualities": []},
            "fall_risk": {"exists": False},
            "profile": {},
            "exam_simple_textarea": "arter sesleri doğal",
        }

        reconciled = llm._reconcile_comed_with_epicrisis(transcript, doctor, comed)

        self.assertEqual(reconciled["pain"]["score"], 6)
        self.assertEqual(reconciled["pain"]["start_date"]["value"], 2)
        self.assertEqual(reconciled["pain"]["qualities"], ["Bastırıcı"])
        self.assertTrue(reconciled["fall_risk"]["exists"])
        self.assertTrue(reconciled["fall_risk"]["history"])
        self.assertTrue(reconciled["fall_risk"]["medications"])
        self.assertTrue(reconciled["fall_risk"]["gait_balance_disorder"])
        self.assertEqual(
            reconciled["exam_simple_textarea"],
            "Kalp ritmi düzenli, akciğer sesleri doğal.",
        )
        self.assertEqual(reconciled["profile"]["diseases"][0]["name"], "Hipertansiyon")
        self.assertEqual(reconciled["profile"]["family_history"], ["Annede diyabet"])
        self.assertFalse(reconciled["profile"]["no_known_history"])
        self.assertEqual(reconciled["diagnoses"][0]["code"], "R07.4")

    def test_explicit_patient_profile_and_fall_risk_survive_garbled_stt(self):
        transcript = """Doktor: Özgeçmişinizi soracağım.
Hasta: Hipertansiyonum var. Her gün Amblopidin 5 mg kullanıyorum. Penicilline alerjim var.
Hasta: Kalp primim var. İşitme kaybım var. 2020 yılında kan transfüzyonu yapıldı.
Hasta: Haftada bir fizik tedavi oluyorum ve düşük tuzlu diyet uyguluyorum.
Hasta: Günde 10 sigara içiyorum. Annemde diyabet var ve anne babam arasında akrabalık yok.
Doktor: Son bir yılda düştünüz mü?
Hasta: Evet, gençliğinde evde bir kez düştüm. Bu nedenle düşme riskim var.
Hasta: Bazen denge bozukluğu yaşıyorum, bilincim açık ve çevreye uyumluyum."""

        reconciled = llm._reconcile_comed_with_epicrisis(
            transcript,
            {},
            {"profile": {}, "fall_risk": {"exists": False}},
        )
        profile = reconciled["profile"]

        self.assertEqual(profile["pharmacy_products"][0]["name"], "Amlodipin")
        self.assertEqual(profile["disabilities"][0]["name"], "İşitme Kaybı")
        self.assertEqual(profile["transfusions"][0]["name"], "Kan Transfüzyonu")
        self.assertEqual(profile["therapies"][0]["name"], "Fizik Tedavi")
        self.assertEqual(profile["special_conditions"][0]["name"], "Düşük Tuzlu Diyet")
        self.assertEqual(profile["addictions"][0]["description"], "Günde 10 adet")
        self.assertEqual(profile["family_history"], ["Annede diyabet"])
        self.assertFalse(profile["parents_related"])
        self.assertTrue(reconciled["fall_risk"]["exists"])
        self.assertTrue(reconciled["fall_risk"]["history"])
        self.assertTrue(reconciled["fall_risk"]["gait_balance_disorder"])


if __name__ == "__main__":
    unittest.main()
