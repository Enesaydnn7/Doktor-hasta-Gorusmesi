import unittest
from unittest.mock import patch

from fastapi.testclient import TestClient

import auth
import comed_integration
import main


class ComedIntegrationTests(unittest.TestCase):
    def test_normalizer_never_invents_mandatory_clinical_values(self):
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
        self.assertIn("weight", normalized["missing_required"])
        self.assertIn("fall_risk", normalized["missing_required"])

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
            "clinical_card_url": "http://goztepe.comedtest.mlpcare.com/card",
        }
        bundle = comed_integration.build_transfer_bundle(record, patient)

        self.assertFalse(bundle["auto_sign"])
        self.assertTrue(bundle["doctor_review_required"])
        self.assertEqual(
            [request.get("endpoint") or request.get("endpoint_group") for request in bundle["requests"]],
            [
                "forms/document/saveDocumentProcesses",
                "medical/examination/saveProfile*",
                "medical/treatment/savevisitdiagnoses",
            ],
        )

    def test_mobile_worklist_and_transfer_require_authenticated_user(self):
        token = auth.api_token_uret("dr-enes", "doctor")
        headers = {"Authorization": f"Bearer {token}"}
        patient = {
            "visit_id": "22207357",
            "clinical_card_id": "30416836",
            "patient_name": "Test Hasta",
            "clinical_card_url": "http://goztepe.comedtest.mlpcare.com/card",
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
            patch.object(main.db, "getir", return_value={"id": 55, "comed": {}}),
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


if __name__ == "__main__":
    unittest.main()
