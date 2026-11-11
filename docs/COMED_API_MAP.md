# COMED API haritası — doğrudan POST ile aktarım

11 Kasım 2026'da Göztepe test COMED'inde, test hastası Enes Aydın (ziyaret
`22207362`) üzerinde ölçüldü. Kaynak: eklentinin 107 sn'lik tam aktarımı + elle
Kaydet sırasında alınan üç HAR kaydı (başlıklar betikle silinerek okundu).

Amaç: ekrana tıklamak yerine COMED ekranının kendi gönderdiği JSON paketlerini
sunucuda hazırlamak; eklenti yalnız "kurye" olarak bunları doktorun açık
oturumuyla göndersin.

## Erişim

- Adres: `https://goztepetestapi.comed.mlpcare.com/tr-tr/api/json/<uç>` — her
  çağrı `POST` + JSON gövde. Yanıt `{"data": ...}`.
- API **hastanenin iç ağında** (`10.102.103.189`). OneNotes sunucusu DNS'i bile
  çözemiyor → sunucudan COMED'e doğrudan çağrı **mümkün değil**. POST'u doktorun
  tarayıcısındaki eklenti atar.
- Kimlik: `x-Application-Key` + `x-authentication-token` başlıkları. Değerler
  yalnız COMED sayfasının belleğinde kalır; OneNotes sunucusuna **asla** gitmez.
- Oturumdaki doktor: istem/tanı paketlerinde `doctorId` / `sourcePersonnel.id`
  (test doktoru = `44524`, bölüm `37` Kardiyoloji, hastane `tenantId` = `131`).

## Kayıt uçları (aktarımda ölçülenler)

| İş | Uç | Gövde özü |
|---|---|---|
| Muayene formu + Sistem Sorgulama | `forms/document/saveDocumentProcesses` | `documentProcesses[0]` = `examination_v2`; Sistem Sorgulama aynı paketin `children[0]`'ı (`system_query_v2`). Yanıt `{"data":[<belge id>]}` |
| Düşme riski formu | `forms/document/saveDocumentProcesses` | ayrı paket, `document: "fall_risk_form"` |
| Tanı (her tanı ayrı) | `medical/treatment/savevisitdiagnoses` | `visitDiagnoses[{icdId, diagnosisType, isPrimaryDiagnosis, isBaseDiagnosis, sideType, visitId, doctorId, doctor{...}}]`, `setAutoDiagnosisTriage` |
| Hizmet istemi (EKG, EKO) | `medical/procedure/saveOrders` | `orders[{plan{...orderType:60, visitId, patientId}, procedure{<katalog kaydının tamamı>}, sourcePersonnel, sourceDepartment, targetPersonnel, targetDepartment, count}]` |
| Laboratuvar | `laboratory/saveOrders` | `orders[{plan{orderType:31, visitId, patientId}, testId}]` — birden çok tahlil tek pakette |
| Radyoloji (grafi) | `radiology/saveOrders` | `orders[{plan{orderType:33, executionNote}, testId, besidePatient, reportRequired}]` — açıklama (`executionNote`) zorunlu |
| İlaç | önce `pharmacy/medication/InteractionInquiry`, sonra `pharmacy/medication/saveOrders` | bkz. aşağı |
| Özgeçmiş | `medical/examination/saveProfile`, `saveProfileDiseases`, `saveProfileAllergies`, `saveProfileOperations`, `saveProfileAddictions`, `saveProfileDevices`, `saveProfileVaccines`, `saveRecordPersonnelSeens` | her bölüm ayrı paket |

**Asla çağrılmaz:** `forms/document/signDocumentProcess`, `unSignDocumentProcess`,
`deleteDocumentProcesses`, `*/stopOrders`, `*/delete*`. Kayıt her zaman
`autoSign: false`, `documentProcessState: 1` (imzasız taslak).

## İlaç güvenliği — atlanamaz adım

1. `pharmacy/medication/InteractionInquiry` ← `{"products":[<ürün id>], "visitId": ...}`
2. Yanıt: `{"data":{"id": <sorgu no>, "allergies":{...}, "conflictingAtcCodes":[...], "cumulativeDosage":[...], "maximumDosages":[...]}}`
3. **Alerji, çakışan ATC, kümülatif doz veya maksimum doz listesinden biri doluysa
   ilaç EKLENMEZ, doktora gösterilir.**
4. Boşsa `saveOrders` gövdesine `interactionInquiries: [<sorgu no>]`,
   `maximumDoseSteps: []` konur.

İlaç kalemi: `products[{id, productName, dose, doseUnit, quantity, quantityUnit}]`,
`route` ("Ağız Yoluyla"), `weight/height/bsa`, `plan{dailyFrequencyType,
treatmentStartDate, steps[{dose, planDate}], executionNote}`. Günde 3 = 3 adım.

## Kimlik numaraları nereden gelir (okuma uçları)

| Ne | Uç |
|---|---|
| ICD kimliği (`icdId`) | `shared/lookups/geticds` |
| Hizmet katalog kaydı (EKG = `100122`) | `shared/order/getCatalogItems`, `shared/order/getPackageProcedures` |
| Laboratuvar `testId` | `laboratory/lis/getTests` (+ `laboratory/orderInquiry`) |
| Radyoloji `testId` | `radiology/lookups/getTestClasses` |
| İlaç ürün kimliği (Parol 500 mg = `3640`) | `pharmacy/searchProducts` |
| Ziyaret / hasta (`visitId`, `patientId`) | `shared/visit/getVisits`, iş listesi `medical/task/getTasks` |
| Form tanımı | `forms/document/getdocuments` `{"model":{"code":"examination_v2"}}` + `forms/parameter/getParameters` |
| Mevcut belge | `forms/document/getDocumentProcesses` |

Bu kimlikler hastane (tenant) kataloğuna özgüdür; başka hastanede aynı ad farklı
kimlik taşıyabilir → kimlik her seferinde aranır, sabit yazılmaz.

## `examination_v2` alanları

Değer biçimi: `"<alan>": [{"values": [<değer>], "children": {...}}]`.

`patient_complaint` (+ `children.complaint_start_date`), `patient_story`,
`treatment_note_v2`, `treatment_plan`, `is_control_suggested` (+ `control_date`),
`is_surgery_will_planned`, `patient_psychological_status_v2`,
`patient_psychology_explanation`, `pain_existence` (+ `pain_description`),
`pain_location`, `pain_score`, `pain_startdate`, `pain_frequency`,
`pain_speciality`, `pain_review_type` (+ das/nips/pas varyantları), `height`,
`weight`, `body_mass_index`, `body_surface_area`, `temperature_v2`, `pulse`,
`pressure_systolic`, `pressure_diastolic`, `spo2`, `exam_simple_textarea`,
`discharge_type`, `discharge_note`, `review_of_system_simple`.

`*_panel_summary` alanları (`patient_complaint_panel_summary`,
`treatment_plan_panel_summary`, `exam_panel_summary`,
`review_of_system_panel_summary`) ekranın ürettiği HTML/metin özetleridir —
POST'ta bunları da biz üretmeliyiz, yoksa kartın özet görünümü boş kalır.

Bu alan adları `comed_integration.normalize_draft()` çıktısındaki anahtarlarla
büyük ölçüde aynı (OneNotes taslağı zaten COMED şemasına göre kurulu).

Paket üst alanları: `document`, `title`, `documentDate`, `owner{id}`,
`client{id}`, `contextId`/`referenceId` (= ziyaret), `referenceType: "Visit"`,
`departmentId`, `type: 0`, `autoSign: false`, `autoSave: false`,
`protectionLevel`, `documentProcessState: 1`, `patientArrivalType`,
`arguments{isReviewOfSystemDocumentSaved}`, `children[]`.

## Ekranın yaptığı, POST'ta bizim yapmamız gereken kontroller

- Zorunlu alanlar (ekranda ölçüldü): Şikayet başlangıç tarihi, Nabız, Muayene
  Notu, Tedavi Notu, Sistem Sorgulama belgesi.
- Kaydet → "Muayene dokümanı ve epikriz imzalansın mı?" sorusu. "Hayır" =
  imzasız kayıt. POST'ta bu soru yok; her zaman imzasız kaydedilir.
- Her POST'tan sonra ilgili `get...` ucu ile geri okunup kaydın düştüğü doğrulanır
  (v2.35.0 dersi: sayaç değil, COMED'in kendi listesi).

## Bu ölçümde görülen sorun

- Eski eklenti bu aktarımda **EKO'yu eklemedi** (yalnız EKG `procedure/saveOrders`).

## Test ortamı temizliği

Bu ölçüm Enes Aydın (V-22207362) üzerinde gerçek kayıt bıraktı: muayene belgesi
`25266469` (imzasız), düşme riski `25266437`, 2 tanı, EKG, 6 tahlil, akciğer
grafisi, Parol, Allergodil ve özgeçmiş kayıtları.

## 11 Kasım akşamı canlıda doğrulananlar (Console testleri 1–9)

Doğrudan API ile, ekrana tıklamadan, test hastası Enes Aydın'da:

| Ne | Sonuç |
|---|---|
| `shared/visit/getVisits` ile ziyaret okuma | ✅ hasta, doktor, bölüm, `clientId`, `patientArrivalType` |
| `forms/document/getDocumentProcesses` ile belge listesi | ✅ |
| `shared/lookups/geticds` + `medical/treatment/savevisitdiagnoses` | ✅ I20.9 eklendi, ekranda göründü |
| `forms/document/saveDocumentProcesses` ile YENİ muayene belgesi | ✅ belge 25266472 — şikayet, öykü, vitaller, muayene/tedavi notu, ağrı, psikoloji, Sistem Sorgulama ekranda dolu |

Ölçülen kurallar (yanlış tahminler düzeltilerek):

1. **Tanı şartı:** ziyarette tanı yokken muayene belgesi kaydı 500 döner:
   `MISSING_DIAGNOSIS_ERROR_2` "Lütfen tanı giriniz." → önce tanı, sonra belge.
2. **Açık belge = `documentProcessState == 1`.** Doktor kartı temizleyince belge
   0'a düşüyor; 0'daki belgeyi güncellemek 200 döner ama ekranda GÖRÜNMEZ.
   İmzalı eski belgeler de 0'da. `deleteNote` dolu olan belge silinmiştir.
   İmza bilgisi `signedVersions` dizisinde (boş = imzasız).
3. Seçenek kodları kurumdan okunur, sabit yazılmaz:
   `forms/parameter/getParameters` → `items[{item: etiket, value: kod}]`
   (tedavi planı, psikolojik durum, Sistem Sorgulama grupları);
   `core/public/getlookup {type: pain_frequency|pain_speciality}` → `{key, value}`.
4. Hizmet istemi paketi COMED'den hazır gelir:
   `medical/order/getOrderPackage {procedureId, testId, visitId}` →
   `data.procedureOrder.order`; üzerine kaynak/hedef doktor-bölüm eklenir.
5. Ziyaretin bugünkü istemleri: `shared/order/getPlans` (`title` ile çift istem kontrolü).
6. VKİ ve VYA COMED'de DuBois formülüyle: 82 kg/174 cm → 27.08 / 1.97.

Uygulama: `comed_api.py` (planlayıcı), `page_trace.js` (yürütücü),
`content.js` → `runApiTransfer` (kurye), testler `tests/test_comed_api.py`.

## 11 Kasım 20:47 — v4 ilk canlı aktarım (yerel sunucu + "Klinot v4 API (test)")

Demo kaydı #4, test hastası Enes Aydın (V-22207362), doktor panelinden
"Tekrar aktar". COMED'deki iş ~4 sn (20:47:16 → 20:47:19), 54 çağrı, 6 tur.
Eski ekran-doldurma yolu aynı kaydı 107 sn'de yapıyor ve EKO'yu ekleyemiyordu.

- ✅ Muayene belgesi 25266476 + Sistem Sorgulama (F5 sonrası ekranda tam)
- ✅ Tanı I20.9, J30.4
- ✅ Laboratuvar 8 (CRP, Troponin I, CK-MB, Hemogram, Kreatinin, ALT, AST, AKŞ)
- ✅ Radyoloji: Akciğer Grafisi (İki Yön) · ✅ Hizmet: EKG, Transözofageal EKO
- ✅ İlaç: PAROL Tablet 500 mg (InteractionInquiry temiz) · ⏸ Allergodil: doz yok, doktora
- İstem Tarihçesi: 12 yeni istem Aktif; 18:39'daki eski istemler Durduruldu, çift yok.
  `shared/order/getPlans` (isOnline=true) durdurulmuş istemleri DÖNMÜYOR.

Açık konu: şikayet başlangıç tarihi COMED'de doğru saklanıyor (geri okuma
`{"before": 2, "type": 2}`) ama ekranda "Başlangıç Tarihi" kutusu boş görünüyor.
