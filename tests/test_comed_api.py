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

    def __init__(self, *, documents=None, visit_diagnoses=None, plans=None, interaction=None, records=None):
        self.documents = documents if documents is not None else []
        self.visit_diagnoses = visit_diagnoses if visit_diagnoses is not None else []
        self.plans = plans if plans is not None else []
        self.interaction = interaction
        self.records = records
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
            catalogs = {
                "entity.vademecumDisease": "lookup_disease_all",
                "entity.vademecumSubstance": "lookup_substance_penisilin",
                "entity.operation": "lookup_operation_apendektomi",
                "entity.vademecumVaccine": "lookup_vaccine_all",
                "entity.vademecumDevice": "lookup_device_all",
                "entity.vademecumAddiction": "lookup_addiction_all",
                "closeness.familyHistory": "lookup_closeness",
            }
            if body["type"] in catalogs:
                wanted = comed_api.fold(body.get("filter", ""))
                rows = fx(catalogs[body["type"]])["data"]
                return self.ok([r for r in rows if not wanted or wanted in comed_api.fold(r["value"])])
            return self.ok(fx(f"lookup_{body['type']}")["data"])
        if path == "medical/examination/getPatientRecords":
            return self.ok(self.records if self.records is not None else fx("patient_records_empty")["data"])
        if path == "pharmacy/medication/orderInquiry":
            name = {3640: "drug_inquiry_parol", 6101: "drug_inquiry_allergodil"}[body["productId"]]
            return self.ok(fx(name)["data"])
        if path == "pharmacy/medication/calculateSteps":
            name = {3640: "calc_steps_parol", 6101: "calc_steps_allergodil"}[body["products"][0]["id"]]
            return self.ok(fx(name)["data"])
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


def run(bundle, comed, rounds=30):
    results = {}
    comed.rounds = []
    for _ in range(rounds):
        step = comed_api.plan_next(bundle, results, now=NOW)
        if step["done"]:
            return step
        assert step["calls"], "iş bitmeden boş tur"
        comed.rounds.append([call["path"] for call in step["calls"]])
        for call in step["calls"]:
            assert call["id"] not in results, f"aynı çağrı iki kez istendi: {call['id']}"
            results[call["id"]] = comed(call)
    raise AssertionError(f"planlayıcı {rounds} turda bitmedi")


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
        # COMED listesine yazılanlar öyküde tekrar edilmez; yazılamayanlar öyküde.
        self.assertIn("Özgeçmiş (HBYS listesinde yok)", story)
        self.assertNotIn("Penisilin", story)
        for leftover in ("Apendektomi (2012)", "Amlodipin 5 mg (Her gün)", "Tuzsuz Diyet",
                         "İşitme Cihazı", "Kan Nakli (2019)", "Fizik Tedavi (Haftada bir)"):
            self.assertIn(leftover, story)

    def test_complaint_start_date_is_also_top_level(self):
        """COMED ekranı Başlangıç Tarihi kutusunu üst düzey alandan okuyor."""
        top = self.exam["values"]["complaint_start_date"][0]["values"][0]
        child = self.exam["values"]["patient_complaint"][0]["children"]["complaint_start_date"][0]["values"][0]
        self.assertEqual(top, child)
        self.assertEqual((top["before"], top["type"]), (2, 2))  # 2 gün önce

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

    def test_drug_without_dose_uses_comed_default_dose_route_and_steps(self):
        bodies = saved(self.comed, "pharmacy/medication/saveOrders")
        allergodil = next(b["orders"][0] for b in bodies if b["orders"][0]["products"][0]["id"] == 6101)
        accepted = fx("accepted_drug_save")  # COMED ekranının Parol için kabul ettiği paket
        self.assertEqual((allergodil["products"][0]["dose"], allergodil["products"][0]["doseUnit"]), (10, "ml"))
        self.assertEqual(allergodil["route"], "İnhalasyon Yoluyla Uygulananlar")
        self.assertEqual(allergodil["plan"]["steps"], fx("calc_steps_allergodil")["data"]["steps"])
        parol = next(b["orders"][0] for b in bodies if b["orders"][0]["products"][0]["id"] == 3640)
        self.assertEqual(parol["route"], accepted["orders"][0]["route"])
        self.assertEqual(parol["plan"]["steps"], fx("calc_steps_parol")["data"]["steps"])
        report = [r for r in self.step["report"]["items"] if r["item"].startswith("Allergodil")][0]
        self.assertEqual(report["status"], "eklendi")
        self.assertIn("varsayılan dozu 10 ml", report["detail"])

    def test_profile_lists_match_what_comed_accepted(self):
        ours = {}
        for path in ("medical/examination/saveProfileDiseases", "medical/examination/saveProfileAllergies",
                     "medical/examination/saveProfileVaccines", "medical/examination/saveProfileDevices",
                     "medical/examination/saveProfileAddictions"):
            for body in saved(self.comed, path):
                for key, items in body.items():
                    if key != "forSeenVisitId":
                        ours.setdefault(key, []).extend(items)
        accepted = {}
        for body in fx("accepted_profile_saves"):
            for key, items in body.items():
                if isinstance(items, list) and not any("id" in i for i in items):
                    accepted.setdefault(key, []).extend(items)
        id_fields = {"diseases": "diseaseId", "allergies": "allergyId", "vaccines": "vaccineId",
                     "devices": "deviceId", "addictions": "addictionId"}
        for key, id_field in id_fields.items():
            mine = sorted((str(i[id_field]), i.get("closeness", ""), i["record"]["type"]) for i in ours.get(key, []))
            theirs = sorted((str(i[id_field]), i.get("closeness", ""), i["record"]["type"]) for i in accepted.get(key, []))
            self.assertEqual(mine, theirs, key)
        # "Apendektomi" katalogda 7 farklı kayıtla geçiyor: tahminle seçilmez.
        self.assertEqual(saved(self.comed, "medical/examination/saveProfileOperations"), [])

    def test_profile_writes_go_one_at_a_time(self):
        """Canlıda paralel özgeçmiş yazmaları COMED eşzamanlılık hatası verdi."""
        for round_paths in self.comed.rounds:
            profile = [p for p in round_paths if p.startswith("medical/examination/saveProfile")]
            self.assertLessEqual(len(profile), 1, round_paths)
        for body in [c["body"] for c in self.comed.calls if c["path"].startswith("medical/examination/saveProfile")]:
            items = [v for k, v in body.items() if isinstance(v, list)][0]
            self.assertEqual(len(items), 1)

    def test_fall_risk_form_matches_what_comed_accepted(self):
        docs = [b["documentProcesses"][0] for b in saved(self.comed, "forms/document/saveDocumentProcesses")]
        fall = next(d for d in docs if d["document"] == "fall_risk_form")
        accepted = fx("accepted_fall_save")["documentProcesses"][0]["values"]
        for code, value in accepted.items():
            self.assertEqual(fall["values"][code][0]["values"], value[0]["values"], code)
        self.assertFalse(fall["autoSign"])

    def test_report_lists_everything(self):
        statuses = {(r["section"], r["status"]) for r in self.step["report"]["items"]}
        self.assertIn(("Muayene", "oluşturuldu"), statuses)
        self.assertIn(("Tanı", "eklendi"), statuses)
        self.assertTrue(self.step["done"])
        self.assertFalse(self.step["failed"])


class PlannerSafetyTests(unittest.TestCase):
    def test_existing_profile_items_are_not_added_twice(self):
        records = copy.deepcopy(fx("patient_records_empty")["data"])
        records["allergies"] = [{"allergyId": 5422, "record": {"title": "Penisilin"}}]
        records["diseases"] = [{"diseaseId": 10004, "closeness": "f", "record": {"title": "KAH"}}]
        comed = FakeComed(records=records)
        run(demo_bundle(), comed)
        self.assertEqual(saved(comed, "medical/examination/saveProfileAllergies"), [])
        family = [i for b in saved(comed, "medical/examination/saveProfileDiseases")
                  for i in b["diseases"] if i.get("closeness")]
        self.assertEqual([(i["diseaseId"], i["closeness"]) for i in family], [(43, "m")])

    def test_existing_drug_order_is_reported_as_existing(self):
        comed = FakeComed(plans=[{
            "title": "PAROL Tablet 500 mg 20 tabletlik ambalaj [Parasetamol] 1 adet, 500 mg", "orderType": 1}])
        step = run(demo_bundle(), comed)
        products = [b["orders"][0]["products"][0]["id"] for b in saved(comed, "pharmacy/medication/saveOrders")]
        self.assertNotIn(3640, products)
        parol = [r for r in step["report"]["items"] if r["item"].startswith("Parol")][0]
        self.assertEqual(parol["status"], "mevcut")

    def test_time_units_use_comed_enum(self):
        start = comed_api._relative_date({"value": 3, "unit": "week"}, NOW)
        self.assertEqual((start["before"], start["type"]), (3, 7))
        self.assertEqual(comed_api._relative_date({"value": 1, "unit": "month"}, NOW)["type"], 3)
        self.assertEqual(comed_api._relative_date({"value": 5, "unit": "hour"}, NOW)["type"], 5)

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
        products = [b["orders"][0]["products"][0]["id"] for b in saved(comed, "pharmacy/medication/saveOrders")]
        self.assertNotIn(3640, products)   # uyarı alan Parol eklenmedi
        self.assertIn(6101, products)      # uyarısız Allergodil eklendi
        parol = [r for r in step["report"]["items"] if r["item"].startswith("Parol")][0]
        self.assertIn("alerji", parol["detail"])

    def test_no_diagnosis_means_no_exam_save(self):
        bundle = demo_bundle()
        bundle["requests"][0]["fields"]["diagnoses"] = []
        comed = FakeComed()
        step = run(bundle, comed)
        documents = [b["documentProcesses"][0]["document"]
                     for b in saved(comed, "forms/document/saveDocumentProcesses")]
        self.assertNotIn("examination_v2", documents)  # düşme riski formu tanıya bağlı değil
        muayene = [r for r in step["report"]["items"] if r["section"] == "Muayene"][0]
        self.assertIn("tanı", muayene["detail"])

    def test_failed_existing_state_read_blocks_every_write(self):
        class BrokenPlans(FakeComed):
            def __call__(self, call):
                if call["path"] == "shared/order/getPlans":
                    self.calls.append(call)
                    return {"ok": False, "status": 500, "data": None, "error": "zaman aşımı"}
                return super().__call__(call)
        comed = BrokenPlans()
        step = run(demo_bundle(), comed)
        self.assertTrue(step["failed"])
        self.assertIn("hiçbir şey yazılmadı", step["message"])
        writes = [c for c in comed.calls if "save" in c["path"].lower() or "Inquiry" in c["path"]]
        self.assertEqual(writes, [])

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
