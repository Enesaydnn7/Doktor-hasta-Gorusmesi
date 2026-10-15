import unittest
import json
from pathlib import Path
from unittest.mock import patch

from fastapi.testclient import TestClient

import auth
import comed_integration
import main


ROOT = Path(__file__).resolve().parents[1]


class ComedIntegrationTests(unittest.TestCase):
    def test_documented_v4_scenario_covers_every_observed_required_field(self):
        scenario = json.loads(
            (ROOT / "docs" / "COMED_TRANSFER_SCHEMA.example.json").read_text(
                encoding="utf-8"
            )
        )
        normalized = comed_integration.normalize_draft(scenario)

        self.assertEqual(normalized["missing_required"], [])
        self.assertFalse(normalized["fields"]["auto_sign"])

    def test_normalizer_marks_operational_defaults_for_doctor_review(self):
        normalized = comed_integration.normalize_draft({
            "patient_complaint": "Bacak ağrısı",
            "complaint_start_date": {"value": 1, "unit": "week", "before": True},
            "patient_story": "Bir haftadır sürüyor.",
            "diagnoses": [{
                "code": "m25.56",
                "description": "Eklemde ağrı, bacak",
                "diagnosis_type": "preliminary",
            }],
            "auto_sign": True,
        })

        self.assertFalse(normalized["fields"]["auto_sign"])
        self.assertEqual(normalized["fields"]["diagnoses"][0]["code"], "M25.56")
        self.assertEqual(normalized["fields"]["vitals"]["pulse"], 100)
        self.assertFalse(normalized["fields"]["pain"]["exists"])
        self.assertFalse(normalized["fields"]["fall_risk"]["exists"])
        self.assertTrue(normalized["fields"]["profile"]["reviewed"])
        self.assertIn("vitals.pulse", normalized["fallback_fields"])
        self.assertIn("profile.reviewed", normalized["fallback_fields"])

    def test_complete_fall_risk_profile_and_pain_satisfy_observed_required_groups(self):
        normalized = comed_integration.normalize_draft({
            "patient_complaint": "Baş dönmesi",
            "complaint_start_date": {"value": 2, "unit": "day", "before": True},
            "profile": {
                "no_known_history": True,
                "no_known_family_history": True,
            },
            "fall_risk": {
                "exists": True,
                "age_group": "65_plus",
                "history": False,
                "medications": True,
                "addiction": False,
                "gait_balance_disorder": False,
                "vision_disorder": False,
                "oriented": True,
                "general_health_normal": True,
            },
            "pain": {"exists": False},
            "vitals": {"weight": 70, "height": 170, "pulse": 72},
            "exam_simple_textarea": "Genel durum iyi.",
            "diagnoses": [{"code": "R42", "diagnosis_type": "preliminary"}],
            "treatment_note_v2": "Semptom takibi.",
            "treatment_plan_label": "Ayaktan takip ve tedavi",
            "is_surgery_will_planned": False,
        })

        self.assertNotIn("profile", normalized["missing_required"])
        self.assertNotIn("family_history", normalized["missing_required"])
        self.assertNotIn("fall_risk", normalized["missing_required"])
        self.assertNotIn("pain", normalized["missing_required"])
        self.assertNotIn("pulse", normalized["missing_required"])

    def test_normalizes_every_lookup_family_psychology_and_diagnosis_option(self):
        normalized = comed_integration.normalize_draft({
            "profile": {
                "diseases": ["Hipertansiyon"],
                "pharmacy_products": [{"name": "PAROL", "description": "Gerektikçe"}],
                "family_history": ["Babada hipertansiyon"],
                "parents_related": False,
                "education": "Lisans",
            },
            "psychological_status": {
                "states": ["Sakin", "Model seçeneği"],
                "description": "Koopere",
            },
            "pain": {
                "exists": True,
                "qualities": ["Keskin", "Uydurma"],
                "rhythm": "Sürekli",
            },
            "diagnoses": [{
                "code": "r52",
                "diagnosis_type": "differential",
                "side": "left",
                "primary": True,
                "first_diagnosis_date": "20.09.2026",
            }],
        })
        fields = normalized["fields"]

        self.assertEqual(fields["profile"]["diseases"][0]["name"], "Hipertansiyon")
        self.assertEqual(fields["profile"]["pharmacy_products"][0]["description"], "Gerektikçe")
        self.assertEqual(fields["profile"]["family_history"][0]["relationship"], "Babası")
        self.assertEqual(fields["psychological_status"]["states"], ["Sakin"])
        self.assertEqual(fields["pain"]["qualities"], ["Keskin"])
        self.assertEqual(fields["diagnoses"][0]["diagnosis_type"], "differential")
        self.assertEqual(fields["diagnoses"][0]["side"], "left")
        self.assertTrue(fields["diagnoses"][0]["primary"])
        self.assertEqual(fields["diagnoses"][0]["first_diagnosis_date"], "20.09.2026")

    def test_invalid_comed_choice_values_are_rejected(self):
        normalized = comed_integration.normalize_draft({
            "treatment_plan_label": "Modelin uydurduğu seçenek",
            "profile": {"marital_status": "Bilinmiyor"},
        })

        self.assertEqual(
            normalized["fields"]["treatment_plan_label"],
            "Ayaktan takip ve tedavi",
        )
        self.assertIn("treatment_plan_label", normalized["fallback_fields"])
        self.assertIsNone(normalized["fields"]["profile"]["marital_status"])

    def test_height_in_metres_is_normalized_for_comed_centimetre_field(self):
        for raw in (1.72, "1,72", "1.72 m"):
            with self.subTest(raw=raw):
                normalized = comed_integration.normalize_draft({
                    "vitals": {"height": raw},
                })
                self.assertEqual(normalized["fields"]["vitals"]["height"], 172)

        normalized = comed_integration.normalize_draft({
            "vitals": {"height": 168},
        })
        self.assertEqual(normalized["fields"]["vitals"]["height"], 168)

    def test_system_review_summary_uses_detailed_positive_findings(self):
        normalized = comed_integration.normalize_draft({
            "review_of_system": {
                "Genel Sistem Sorgusu": ["Halsizlik"],
                "Solunum Sistemi": ["Nefes darlığı"],
            },
        })
        summary = normalized["fields"]["review_of_system_simple"]

        self.assertIn("Genel Sistem Sorgusu: Halsizlik", summary)
        self.assertIn("Solunum Sistemi: Nefes darlığı", summary)
        self.assertNotIn("özellik yok olarak hazırlandı", summary.casefold())

    def test_contextual_system_findings_are_mapped_to_exact_comed_options(self):
        normalized = comed_integration.normalize_draft({
            "review_of_system_simple": (
                "Genel Sistem Sorgusu: Halsizlik; Genitoüriner Sistem: Son günlerde sık idrara çıkma; "
                "Deri: Kollarda kaşıntı; Solunum Sistemi: Merdiven çıkarken nefes darlığı; "
                "Sinir Sistemi: Bazen denge bozukluğu; Kas - İskelet Sistemi: Bacaklarda kas ağrısı; "
                "Dolaşım Sistemi: Zaman zaman çarpıntı; Gastrointestinal Sistem: Hafif bulantı; "
                "Komplikasyon: Komplikasyon olmadı"
            ),
            "review_of_system": {
                "Genel Sistem Sorgusu": ["Halsizliğim var"],
                "Genitoüriner Sistem": ["Son günlerde sık idrara çıkıyorum"],
                "Deri": ["Özellik Yok"],
                "Solunum Sistemi": ["Özellik Yok"],
                "Sinir Sistemi": ["Bazen denge bozukluğu yaşıyorum"],
                "Kas - İskelet Sistemi": ["Özellik Yok"],
                "Dolaşım Sistemi": ["Zaman zaman çarpıntım oluyor"],
                "Gastrointestinal Sistem": ["Özellik Yok"],
                "Komplikasyon": ["Komplikasyon Yok"],
            },
        })
        review = normalized["fields"]["review_of_system"]

        self.assertEqual(review["Genel Sistem Sorgusu"], ["Halsizlik"])
        self.assertEqual(review["Genitoüriner Sistem"], ["Sık idrara çıkma"])
        self.assertEqual(review["Deri"], ["Kaşıntı"])
        self.assertEqual(review["Solunum Sistemi"], ["Nefes darlığı"])
        self.assertEqual(review["Sinir Sistemi"], ["Denge bozukluğu"])
        self.assertEqual(review["Kas - İskelet Sistemi"], ["Kas ağrısı"])
        self.assertEqual(review["Dolaşım Sistemi"], ["Çarpıntı"])
        self.assertEqual(review["Gastrointestinal Sistem"], ["Bulantı"])
        self.assertEqual(review["Komplikasyon"], ["Komplikasyon Yok"])

    def test_real_profile_data_wins_over_conflicting_no_known_flags(self):
        normalized = comed_integration.normalize_draft({
            "profile": {
                "no_known_history": True,
                "no_known_family_history": True,
                "addictions": [{"name": "Sigara", "description": "Günde 10 adet"}],
                "family_history": [{
                    "relationship": "Annesi",
                    "condition": "Diyabet",
                    "description": "Annede diyabet",
                }],
            },
        })

        profile = normalized["fields"]["profile"]
        self.assertFalse(profile["no_known_history"])
        self.assertFalse(profile["no_known_family_history"])

    def test_transfer_bundle_targets_verified_comed_post_groups(self):
        record = {
            "id": 42,
            "comed": {
                "patient_complaint": "Baş ağrısı",
                "diagnoses": [{"code": "R51", "diagnosis_type": "preliminary"}],
            },
        }
        patient = {
            "visit_id": "22207357",
            "clinical_card_id": "30416836",
            "clinical_card_url": "https://goztepetest.comed.mlpcare.com/card",
        }
        bundle = comed_integration.build_transfer_bundle(record, patient)

        self.assertFalse(bundle["auto_sign"])
        self.assertTrue(bundle["doctor_review_required"])
        self.assertEqual(bundle["schema_version"], 6)
        self.assertIn("fallback_fields", bundle)
        # Dogrulanmis POST sablonu akisi kaldirildi; alanlar yalnizca eklenti
        # tarafindan form doldurularak hazirlanir.
        self.assertEqual(bundle["execution_mode"], "extension_form_fill")
        self.assertNotIn("native_requests", bundle)
        self.assertEqual(
            [request.get("endpoint") or request.get("endpoint_group") for request in bundle["requests"]],
            [
                "forms/document/saveDocumentProcesses",
                "medical/examination/saveProfile*",
                "medical/treatment/savevisitdiagnoses",
                # Hizmet istemleri COMED'de ayri ekranda girilir.
                "medical/order/serviceRequest",
            ],
        )

    def test_transfer_repairs_stale_fall_risk_from_patient_transcript(self):
        record = {
            "id": 44,
            "transkript": (
                "Doktor: Son bir yıl içinde düştünüz mü?\n"
                "Hasta: Evet geçen ay evde bir kez düştüm. Bu nedenle düşme riskim var.\n"
                "Hasta: Bilincim açık ve çevreye uyumluyum."
            ),
            "comed": {"fall_risk": {"exists": False}},
        }
        bundle = comed_integration.build_transfer_bundle(
            record,
            {"visit_id": "22207357", "clinical_card_id": "30416836"},
        )
        fall_risk = bundle["requests"][0]["fields"]["fall_risk"]

        self.assertTrue(fall_risk["exists"])
        self.assertTrue(fall_risk["history"])
        self.assertTrue(fall_risk["gait_balance_disorder"])
        self.assertTrue(fall_risk["oriented"])

    def test_transfer_respects_explicit_patient_no_fall(self):
        record = {
            "id": 45,
            "transkript": (
                "Doktor: Düşme öykünüz var mı?\n"
                "Hasta: Hayır, hiç düşmedim ve düşme riskim yok."
            ),
            "comed": {"fall_risk": {"exists": True, "history": True}},
        }
        bundle = comed_integration.build_transfer_bundle(
            record,
            {"visit_id": "22207357", "clinical_card_id": "30416836"},
        )

        self.assertFalse(bundle["requests"][0]["fields"]["fall_risk"]["exists"])

    def test_trace_templates_no_longer_produce_native_posts(self):
        """POST sablonu akisi kaldirildi; iz kayitlari pakete etki etmemeli."""
        record = {
            "id": 42,
            "comed": {
                "patient_complaint": "Yeni baş ağrısı",
                "patient_story": "İki gündür sürüyor.",
                "vitals": {"weight": 74, "height": 168, "pulse": 76},
            },
        }
        patient = {"visit_id": "22207357", "clinical_card_id": "30416836"}
        template = {
            "method": "POST",
            "status": 200,
            "url": (
                "https://goztepetestapi.comed.mlpcare.com/tr-tr/api/json/"
                "forms/document/saveDocumentProcesses"
            ),
            "request_body": {"documentProcesses": [{"document": "examination_v2"}]},
        }
        with_template = comed_integration.build_transfer_bundle(
            record, patient, trace_templates=[template]
        )
        without_template = comed_integration.build_transfer_bundle(record, patient)

        # Eski cagiranlari kirmamak icin parametre korunur ama yok sayilir.
        self.assertEqual(with_template, without_template)
        self.assertNotIn("native_requests", with_template)
        self.assertEqual(with_template["execution_mode"], "extension_form_fill")

    def test_mobile_worklist_and_transfer_require_authenticated_user(self):
        token = auth.api_token_uret("dr-enes", "doctor")
        headers = {"Authorization": f"Bearer {token}"}
        patient = {
            "visit_id": "22207357",
            "clinical_card_id": "30416836",
            "patient_name": "Test Hasta",
            "clinical_card_url": "https://goztepetest.comed.mlpcare.com/card",
        }
        transfer = {
            "id": 8,
            "record_id": 55,
            "visit_id": patient["visit_id"],
            "clinical_card_url": patient["clinical_card_url"],
            "status": "queued",
            "bundle": {},
        }

        with (
            patch.object(main.db, "comed_worklist", return_value=[patient]),
            patch.object(
                main.db,
                "getir_for_doctor",
                return_value={"id": 55, "comed": {}},
            ),
            patch.object(main.db, "comed_trace_list", return_value=[]),
            patch.object(main.comed_integration, "build_transfer_bundle", return_value={"auto_sign": False}),
            patch.object(main.db, "comed_transfer_create", return_value=transfer),
            patch.object(main.db, "comed_transfer_pending", return_value=[transfer]) as pending,
            TestClient(main.app) as client,
        ):
            unauthorized = client.get("/api/v1/mobile/comed/worklist")
            worklist = client.get("/api/v1/mobile/comed/worklist", headers=headers)
            created = client.post(
                "/api/v1/mobile/comed/transfers",
                headers=headers,
                json={"record_id": 55, "patient": patient},
            )
            bridge_queue = client.get(
                "/api/v1/mobile/comed/bridge/transfers", headers=headers
            )

        self.assertEqual(unauthorized.status_code, 401)
        self.assertEqual(worklist.status_code, 200)
        self.assertEqual(worklist.json()["items"][0]["visit_id"], "22207357")
        self.assertEqual(created.status_code, 200)
        self.assertEqual(created.json()["status"], "queued")
        self.assertEqual(bridge_queue.status_code, 200)
        pending.assert_called_once_with(visit_id=None, requested_by="dr-enes")

    def test_comed_trace_capture_accepts_only_test_api_and_redacts_secrets(self):
        token = auth.api_token_uret("dr-enes", "doctor")
        headers = {"Authorization": f"Bearer {token}"}
        captured = []

        def save(events, captured_by):
            captured.extend(events)
            self.assertEqual(captured_by, "dr-enes")
            return len(events)

        with (
            patch.object(main.db, "comed_trace_add", side_effect=save),
            TestClient(main.app) as client,
        ):
            response = client.post(
                "/api/v1/mobile/comed/request-log",
                headers=headers,
                json={"events": [
                    {
                        "method": "POST",
                        "url": "https://goztepetestapi.comed.mlpcare.com/tr-tr/api/json/forms/document/saveDocumentProcesses?visit=1&token=hidden",
                        "status": 200,
                        "request_body": {"password": "hidden", "documentProcesses": [{"id": 7}]},
                        "response_body": {"access_token": "hidden", "success": True},
                    },
                    {
                        "method": "POST",
                        "url": "https://example.com/not-comed",
                        "status": 200,
                    },
                ]},
            )

        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.json()["accepted"], 1)
        self.assertEqual(len(captured), 1)
        self.assertNotIn("token=", captured[0]["url"])
        self.assertEqual(captured[0]["request_body"]["password"], "[REDACTED]")
        self.assertEqual(captured[0]["response_body"]["access_token"], "[REDACTED]")
        self.assertEqual(captured[0]["request_body"]["documentProcesses"][0]["id"], 7)

    def test_mobile_trace_list_is_scoped_to_authenticated_user(self):
        token = auth.api_token_uret("dr-enes", "doctor")
        headers = {"Authorization": f"Bearer {token}"}
        items = [{"id": 9, "captured_by": "dr-enes", "method": "POST"}]

        with (
            patch.object(main.db, "comed_trace_list", return_value=items) as trace_list,
            TestClient(main.app) as client,
        ):
            unauthorized = client.get("/api/v1/mobile/comed/request-log")
            response = client.get(
                "/api/v1/mobile/comed/request-log?limit=30&method=POST&path_contains=save",
                headers=headers,
            )

        self.assertEqual(unauthorized.status_code, 401)
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.json()["items"], items)
        trace_list.assert_called_once_with(
            limit=30,
            captured_by="dr-enes",
            method="POST",
            path_contains="save",
        )


if __name__ == "__main__":
    unittest.main()
