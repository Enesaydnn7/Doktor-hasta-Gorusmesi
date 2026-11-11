"""COMED API aktarım planlayıcısı (v4) testleri.

Sahte COMED, 11 Kasım 2026'da Göztepe test COMED'inde yakalanan GERÇEK
yanıtlarla (kişisel veriler temizlenmiş, tests/fixtures/comed_api) cevap verir.
Planlayıcının ürettiği kayıt paketleri, COMED'in aynı demo görüşmesi için
kabul ettiği paketlerle karşılaştırılır.
"""
import copy
import json
import re
import unittest
from datetime import datetime
from pathlib import Path

import comed_api
import comed_integration

ROOT = Path(__file__).resolve().parents[1]
FIX = ROOT / "tests" / "fixtures" / "comed_api"
NOW = datetime(2026, 11, 11, 18, 39, 0)


def fx(name):
    return json.loads((FIX / f"{name}.json").read_text(encoding="utf-8"))


def demo_bundle():
    record = json.loads((ROOT / "demo_records" / "comed_tam_test_kayit_4_2026-11-05.json").read_text(encoding="utf-8"))
    patient = {"visit_id": "22207362", "patient_no": "1300013", "clinical_card_id": ""}
    return comed_integration.build_transfer_bundle(record, patient)


def extension_allowlist():
    """page_trace.js'teki izin listesi: planlayıcı bunun dışına çıkmamalı."""
    source = (ROOT / "comed_bridge_extension" / "page_trace.js").read_text(encoding="utf-8")
    block = source.split("const WRITE_ENDPOINTS = new Set([", 1)[1].split("]);", 1)[0]
    writes = set(re.findall(r'"([^"]+)"', block))
    read = re.search(r"const READ_ENDPOINT = /(.+?)/;", source).group(1).replace("\\/", "/")
    forbidden = re.search(r"const FORBIDDEN_ENDPOINT = /(.+?)/i;", source).group(1)
    return writes, re.compile(read), re.compile(forbidden, re.I)


class FakeComed:
    """Yakalanan gerçek COMED yanıtlarıyla çalışan sahte COMED."""

    def __init__(self, *, documents=None, visit_diagnoses=None, plans=None, interaction=None):
        self.documents = documents if documents is not None else []
        self.visit_diagnoses = visit_diagnoses if visit_diagnoses is not None else []
        self.plans = plans if plans is not None else []
        self.interaction = interaction
        self.calls = []

    @staticmethod
    def ok(data):
        return {"ok": True, "status": 200, "data": {"data": data}}

    def __call__(self, call):
        path, body = call["path"], call["body"]
        self.calls.append(call)
        search = comed_api.fold(body.get("search", ""))
        if path == "shared/visit/getVisits":
            return self.ok(fx("visit")["data"])
        if path == "forms/document/getDocumentProcesses":
            if "id" in body.get("model", {}):
                saved = [c for c in self.calls if c["path"] == "forms/document/saveDocumentProcesses"]
                return self.ok([saved[-1]["body"]["documentProcesses"][0]] if saved else [])
            return self.ok(self.documents)
        if path == "forms/parameter/getParameters":
            name = "params_ros" if "ss_deri" in body["parameters"] else "params_exam"
            return self.ok(fx(name)["data"])
        if path == "core/public/getlookup":
            return self.ok(fx(f"lookup_{body['type']}")["data"])
        if path == "shared/order/getCatalogs":
            return self.ok(fx("catalogs")["data"])
        if path == "shared/lookups/geticds":
            return self.ok(fx(f"icd_{body['search']}")["data"])
        if path == "laboratory/lis/getTests":
            return self.ok([t for t in fx("lab_tests")["data"] if search and search in comed_api.fold(t["name"])])
        if path == "radiology/getTests":
            return self.ok([t for t in fx("radiology_tests")["data"] if search and search in comed_api.fold(t["name"])])
        if path == "pharmacy/searchProducts":
            name = {"parol": "drug_parol", "allergodil": "drug_allergodil"}.get(search)
            return self.ok(fx(name)["data"] if name else [])
        if path == "shared/order/getCatalogItems":
            return self.ok(fx("catalog_ekg")["data"] if "elektrokardiogram" in search else [])
        if path == "medical/order/getOrderPackage":
            return self.ok(fx("order_package_ekg")["data"])
        if path in ("laboratory/orderInquiry", "radiology/orderInquiry"):
            return self.ok({"id": body["testId"]})
        if path == "medical/treatment/getVisitDiagnoses":
            return self.ok(self.visit_diagnoses)
        if path == "shared/order/getPlans":
            return self.ok(self.plans)
        if path == "pharmacy/medication/InteractionInquiry":
            return self.ok(self.interaction or fx("interaction_parol")["data"])
        if path.endswith("saveDocumentProcesses"):
            return self.ok([25266472])
        if "save" in path.lower():
            return self.ok([{"id": 1}])
        raise AssertionError(f"beklenmeyen COMED çağrısı: {path}")


def run(bundle, comed, rounds=12):
    results = {}
    for _ in range(rounds):
        step = comed_api.plan_next(bundle, results, now=NOW)
        if step["done"]:
            return step
        assert step["calls"], "iş bitmeden boş tur"
        for call in step["calls"]:
            assert call["id"] not in results, f"aynı çağrı iki kez istendi: {call['id']}"
            results[call["id"]] = comed(call)
    raise AssertionError("planlayıcı 12 turda bitmedi")


def saved(comed, path):
    return [c["body"] for c in comed.calls if c["path"] == path]


class PlannerFullDemoTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.comed = FakeComed()
        cls.step = run(demo_bundle(), cls.comed)
        cls.exam = saved(cls.comed, "forms/document/saveDocumentProcesses")[0]["documentProcesses"][0]
        cls.accepted = fx("accepted_exam_save")["documentProcesses"][0]

    def test_every_call_is_inside_extension_allowlist(self):
        writes, read, forbidden = extension_allowlist()
        for call in self.comed.calls:
            self.assertFalse(forbidden.search(call["path"]), call["path"])
            self.assertTrue(call["path"] in writes or read.match(call["path"]),
                            f"eklenti izin listesinde yok: {call['path']}")

    def test_exam_document_is_unsigned_new_open_document(self):
        self.assertEqual(self.exam["document"], "examination_v2")
        self.assertNotIn("id", self.exam)
        self.assertFalse(self.exam["autoSign"])
        self.assertEqual(self.exam["documentProcessState"], 1)
        self.assertEqual(self.exam["referenceId"], 22207362)
        self.assertEqual(self.exam["owner"], {"id": 44524})
        child = self.exam["children"][0]
        self.assertEqual(child["document"], "system_query_v2")
        self.assertFalse(child["autoSign"])

    def test_exam_values_match_what_comed_accepted(self):
        same = ["treatment_plan", "is_control_suggested", "is_surgery_will_planned",
                "patient_psychological_status_v2", "patient_psychology_explanation", "pain_existence",
                "pain_location", "pain_score", "pain_frequency", "pain_speciality", "pain_review_type",
                "height", "weight", "body_mass_index", "body_surface_area", "pulse",
                "pressure_systolic", "pressure_diastolic", "spo2", "exam_simple_textarea",
                "review_of_system_simple", "treatment_note_v2"]
        for code in same:
            ours = self.exam["values"][code][0]["values"]
            theirs = self.accepted["values"][code][0]["values"]
            self.assertEqual(ours, theirs, code)
        self.assertEqual(self.exam["values"]["temperature_v2"][0]["values"], [36.8])
        complaint = self.exam["values"]["patient_complaint"][0]["values"][0]
        self.assertEqual(complaint["value"], self.accepted["values"]["patient_complaint"][0]["values"][0]["value"])
        story = self.exam["values"]["patient_story"][0]["values"][0]
        self.assertTrue(story.startswith("İki gündür göğüs ortasında"))
        self.assertIn("Alerji: Penisilin", story)

    def test_system_query_codes_match_what_comed_accepted(self):
        ours = self.exam["children"][0]["values"]
        theirs = self.accepted["children"][0]["values"]
        for code in comed_api.ROS_GROUPS.values():
            self.assertEqual([v["value"] for v in ours[code][0]["values"]],
                             [v["value"] for v in theirs[code][0]["values"]], code)

    def test_diagnoses_use_catalog_ids(self):
        bodies = saved(self.comed, "medical/treatment/savevisitdiagnoses")
        ids = sorted(b["visitDiagnoses"][0]["icdId"] for b in bodies)
        self.assertEqual(ids, [5409, 5808])
        first = next(b["visitDiagnoses"][0] for b in bodies if b["visitDiagnoses"][0]["icdId"] == 5409)
        accepted = fx("accepted_dx_save")["visitDiagnoses"][0]
        for key in ("diagnosisType", "isBaseDiagnosis", "isPrimaryDiagnosis", "sideType", "visitId", "doctorId"):
            self.assertEqual(first[key], accepted[key], key)

    def test_diagnoses_are_saved_before_exam_document(self):
        order = [c["path"] for c in self.comed.calls]
        self.assertLess(order.index("medical/treatment/savevisitdiagnoses"),
                        order.index("forms/document/saveDocumentProcesses"))

    def test_lab_orders_match_catalog(self):
        tests = [o["testId"] for o in saved(self.comed, "laboratory/saveOrders")[0]["orders"]]
        # Kayıt örneğindeki 5 tahlilin hepsi aynı katalog kimliğiyle seçiliyor.
        for test_id in ("1400", "1143", "1138", "353", "44"):
            self.assertIn(test_id, tests)
        self.assertIn("796", tests)  # Hemogram
        order = saved(self.comed, "laboratory/saveOrders")[0]["orders"][0]
        self.assertEqual(order["plan"]["orderType"], 31)

    def test_radiology_order_carries_required_note(self):
        order = saved(self.comed, "radiology/saveOrders")[0]["orders"][0]
        self.assertEqual(order["testId"], 1680)
        self.assertEqual(order["plan"]["executionNote"], "Nefes darlığı")
        self.assertEqual(order["plan"]["orderType"], 33)

    def test_ekg_procedure_order(self):
        order = saved(self.comed, "medical/procedure/saveOrders")[0]["orders"][0]
        self.assertEqual(order["procedure"]["id"], 100122)
        self.assertEqual(order["targetPersonnel"]["id"], 44524)
        self.assertEqual(order["count"], 1)

    def test_parol_is_tablet_500_not_cold_and_goes_through_interaction_check(self):
        body = saved(self.comed, "pharmacy/medication/saveOrders")[0]
        product = body["orders"][0]["products"][0]
        self.assertEqual(product["id"], 3640)
        self.assertEqual((product["dose"], product["doseUnit"]), (500, "mg"))
        self.assertEqual(len(body["orders"][0]["plan"]["steps"]), 3)
        self.assertEqual(body["interactionInquiries"], [2199272])
        order = [c["path"] for c in self.comed.calls]
        self.assertLess(order.index("pharmacy/medication/InteractionInquiry"),
                        order.index("pharmacy/medication/saveOrders"))

    def test_drug_without_dose_is_left_to_doctor(self):
        self.assertEqual(len(saved(self.comed, "pharmacy/medication/saveOrders")), 1)
        allergodil = [r for r in self.step["report"]["items"] if r["item"].startswith("Allergodil")]
        self.assertEqual(allergodil[0]["status"], "atlandı")

    def test_report_lists_everything(self):
        statuses = {(r["section"], r["status"]) for r in self.step["report"]["items"]}
        self.assertIn(("Muayene", "oluşturuldu"), statuses)
        self.assertIn(("Tanı", "eklendi"), statuses)
        self.assertTrue(self.step["done"])
        self.assertFalse(self.step["failed"])


class PlannerSafetyTests(unittest.TestCase):
    def test_existing_diagnosis_and_order_are_not_added_twice(self):
        comed = FakeComed(
            visit_diagnoses=[{"icd": {"code": "I20.9", "id": 5409}}],
            plans=[{"title": "Elektrokardiogram (EKG)", "orderType": 60}],
        )
        step = run(demo_bundle(), comed)
        dx = [b["visitDiagnoses"][0]["icdId"] for b in saved(comed, "medical/treatment/savevisitdiagnoses")]
        self.assertEqual(dx, [5808])
        self.assertEqual(saved(comed, "medical/procedure/saveOrders"), [])
        self.assertIn({"section": "Hizmet", "item": "Elektrokardiogram (EKG)", "status": "mevcut"},
                      step["report"]["items"])

    def test_open_document_is_updated_not_duplicated(self):
        open_doc = {"id": 25266469, "document": "examination_v2", "documentProcessState": 1,
                    "signedVersions": [], "values": {"discharge_note": [{"values": ["eski"]}]},
                    "children": [], "owner": {"id": 44524}, "client": {"id": 701300013}}
        comed = FakeComed(documents=[open_doc])
        run(demo_bundle(), comed)
        doc = saved(comed, "forms/document/saveDocumentProcesses")[0]["documentProcesses"][0]
        self.assertEqual(doc["id"], 25266469)
        self.assertEqual(doc["values"]["discharge_note"], [{"values": ["eski"]}])
        self.assertIn("patient_complaint", doc["values"])

    def test_closed_signed_or_deleted_documents_are_never_touched(self):
        docs = [
            {"id": 1, "document": "examination_v2", "documentProcessState": 0, "signedVersions": []},
            {"id": 2, "document": "examination_v2", "documentProcessState": 1, "signedVersions": [{"id": 9}]},
            {"id": 3, "document": "examination_v2", "documentProcessState": 1, "signedVersions": [],
             "deleteNote": "test"},
        ]
        comed = FakeComed(documents=docs)
        run(demo_bundle(), comed)
        doc = saved(comed, "forms/document/saveDocumentProcesses")[0]["documentProcesses"][0]
        self.assertNotIn("id", doc)

    def test_allergy_warning_stops_the_drug(self):
        comed = FakeComed(interaction={"allergies": {"3640": [{"name": "Parasetamol"}]},
                                       "conflictingAtcCodes": [], "cumulativeDosage": [],
                                       "id": 7, "maximumDosages": []})
        step = run(demo_bundle(), comed)
        self.assertEqual(saved(comed, "pharmacy/medication/saveOrders"), [])
        parol = [r for r in step["report"]["items"] if r["item"].startswith("Parol")][0]
        self.assertIn("alerji", parol["detail"])

    def test_no_diagnosis_means_no_exam_save(self):
        bundle = demo_bundle()
        bundle["requests"][0]["fields"]["diagnoses"] = []
        comed = FakeComed()
        step = run(bundle, comed)
        self.assertEqual(saved(comed, "forms/document/saveDocumentProcesses"), [])
        muayene = [r for r in step["report"]["items"] if r["section"] == "Muayene"][0]
        self.assertIn("tanı", muayene["detail"])

    def test_no_sign_or_delete_endpoint_ever(self):
        comed = FakeComed()
        run(demo_bundle(), comed)
        for call in comed.calls:
            self.assertNotRegex(call["path"], re.compile("sign|delete|stop|cancel", re.I))
            for doc in call["body"].get("documentProcesses", []):
                self.assertFalse(doc["autoSign"])


class DrugChoiceTests(unittest.TestCase):
    products = fx("drug_parol")["data"]

    def choose(self, name, dose=None):
        product, _ = comed_api.choose_drug(name, dose, self.products)
        return product["id"] if product else None

    def test_parol_rules_from_live_comed(self):
        self.assertEqual(self.choose("Parol", "500 mg"), 3640)
        self.assertEqual(self.choose("Parol"), 3640)          # form yok -> tablet
        self.assertEqual(self.choose("Parol 500 mg"), 3640)   # doz adın içinde
        self.assertEqual(self.choose("Parol Cold"), 3647)     # açıkça istendi
        self.assertIsNone(self.choose("Parol", "325 mg"))     # 325 mg yalnız COLD'da
        self.assertIsNone(self.choose("Aspirin"))

    def test_name_match_requires_certainty(self):
        tests = fx("lab_tests")["data"]
        item, _ = comed_api.match_by_name("CRP (Kantitatif)", tests)
        self.assertEqual(item["id"], "1143")
        item, _ = comed_api.match_by_name("Kreatinin (Serum)", tests)
        self.assertEqual(item["id"], "1400")
        item, _ = comed_api.match_by_name("Demir", tests)
        self.assertEqual(item["id"], "348")  # parantez dışı ad tek adayla eşleşiyor
        item, why = comed_api.match_by_name("Vitamin", tests)
        self.assertIsNone(item, why)  # B12 mi D3 mü belli değil: seçilmez


if __name__ == "__main__":
    unittest.main()
