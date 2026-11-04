# Klinot — Doktor-Hasta Görüşmesi Platformu

Doktor-hasta görüşmesini sesten yazıya çevirip Gemini ile analiz eden, çıkan
muayene formu taslağını bir Chrome köprüsüyle hastanenin **COMED** sistemine
dolduran platform. Web paneli + Flutter mobil uygulama + Chrome eklentisi.

---

## 0. ÖNCE BUNU OKU — DOĞRU DİZİN

**Gerçek proje dizini:**
```
C:\Users\enes.aydin1\Documents\ChatGPT\Klinik-Analiz
```

`C:\Users\enes.aydin1\Desktop\Claude_Klinot` **BAYAT BİR KOPYADIR** —
30 Eylül 2026'da kalmış, `APP_VERSION = v2.10.0`, commit `3b8194d`.
Orada geliştirme yapma, orada yapılan değişiklik hiçbir yere gitmez.

Geçmiş konuşma dökümleri `Desktop\Claude_Klinot\_GECMIS\` altında duruyor
(00_HARITA.md + tarihli dosyalar). Oradaki `.md` dosyaları bazen `EPERM`
veriyor; o zaman `[System.IO.File]::Open(..., 'Open','Read','ReadWrite')` ile
kopyalayıp parçalara bölerek oku.

**Repo:** `github.com/Enesaydnn7/Doktor-hasta-Gorusmesi` (private)
**Canlı:** `https://doktor-hasta-gorusmesi.onrender.com` (Render, free plan)

---

## 1. MİMARİ

### Katmanlar

| Katman | Teknoloji | Görev |
|---|---|---|
| Backend | FastAPI + SQLite | STT → Gemini analiz → 3 rapor + COMED taslağı |
| Web panel | Jinja2 + vanilla JS | `/admin`, `/doctor`, `/legacy` |
| Mobil | Flutter (`mobile_app/`) | Kayıt → transkript → AI epikriz → PDF |
| Köprü | Chrome MV3 (`comed_bridge_extension/`) | COMED'e form + hizmet istemi doldurma |

### Veri akışı
```
ses → OpenAI STT (gpt-4o-transcribe-diarize)
    → Gemini rol tespiti (role_classifier.py)
    → 4 PARALEL Gemini çağrısı (hasta / doktor / yönetim / COMED taslağı)
    → normalize_draft() → build_transfer_bundle()
    → eklenti COMED formunu doldurur → İMZA HER ZAMAN DOKTORDA
```

### Dosyalar

- **`main.py`** (~1200 satır) — tüm uçlar tek dosyada. APIRouter'a bölünmeli (yapılmadı).
- **`db.py`** — SQLite katmanı. `sqlite3` **yalnızca burada** import ediliyor → Postgres geçişi kolay.
- **`auth.py`** — imzalı çerez (`klinik_session`, HMAC-SHA256), `patient_identity_hash`, OTP.
- **`llm.py`** — Gemini, `asyncio.gather` ile 4 rapor paralel.
- **`stt.py`** — OpenAI. ⚠️ ElevenLabs fonksiyonları **ölü kod** olarak duruyor (~120 satır).
- **`prompts.py`** — "ALTIN KURAL: sadece görüşmede geçen bilgi yazılır."
- **`comed_integration.py`** — taslak normalizasyonu, `build_transfer_bundle`, `requested_services`.
- **`config.py`** — `APP_VERSION`, `label()`, `stt_label()`, COMED adresleri.
- **`static/report_view.js`** — admin ve doktor panelinin **ortak** rapor render katmanı.
  `doctor.js` içine ikinci bir `esc()` tanımlama — çakışırsa tüm panel sessizce kırılır.
- Ölü kod: `mock_data.py`, `v9klinik-analiz-mvp-sesli/`, `gorusme`, `transcript_screen.dart`.

### Veritabanı
`kayitlar` (ses BLOB dahil), `comed_worklist`, `comed_transfers`,
`comed_trace_events`, `bekleyen_sesler`, `transcription_jobs`.
⚠️ DB'nin **%85'i ses** — taşırken sesler Storage'a alınmalı.
⚠️ Testler ve geliştirme **aynı** `kayitlar.db`'yi kullanıyor; test koşusu demo
verisini bozuyor (`scripts/seed_demo_worklist.py` ile tekrar seed'le).

### Modeller
- LLM: **Gemini 2.5 Flash** (`gemini-2.5-flash`), SDK `google-genai`
- STT: **OpenAI `gpt-4o-transcribe-diarize`**

---

## 2. COMED ENTEGRASYONU

```
Web : https://goztepetest.comed.mlpcare.com
API : https://goztepetestapi.comed.mlpcare.com      ← https, http DEĞİL
```
Doktor: `Kullanici.kayadr;Kullanici.aydin1|tracer` / `1`
(biçim: `<comed_kullanici>;<tracer_kullanici>|tracer`)

### Canlı ortamda ölçülerek bulunan COMED kuralları — BUNLARI UNUTMA

1. **Açılır alanların tıklama dinleyicisi alanın kendisinde değil, içindeki ok
   ikonunda.** Alana / çocuğuna / atasına tıklamak paneli açmaz.
2. **`data-test` değerleri benzersiz değil.** Sayfada iki `co-button-Ekle` var
   (biri tanı kartında, biri istem penceresinde). `querySelector` yanlışını alır
   — "Vazgeç" ile aynı hizadaki düğmeyi seç.
3. **Düğmeler salt `.click()` ile tepki vermiyor**, tam fare dizisi istiyor
   (`pointerover → mouseover → pointermove → mousemove → pointerdown → mousedown
   → pointerup → mouseup → click`). Hover olayları eksikse sessizce yutuluyor.
4. **"Hasta Bilgileri" paneli yalnızca hasta ADINA tıklayınca açılıyor.**
   12 ikon düğmesi denendi, hiçbiri açmıyor. Panel açılana kadar DOM'a hiç basmıyor.
5. **Tarih kutusu `disabled`** — tıklanamaz. Takvim ikonu (`co-button-icon-calendar`)
   tek tetikleyici. İş listesi varsayılan sadece BUGÜNÜ gösteriyor → köprü "3 Ay"
   seçiyor. Başarı bayrağı ancak `rangeIsWide()` doğrulandıktan sonra set edilmeli.
6. **Alanlar görünen TÜRKÇE metinle bulunuyor** ("Şikayeti", "Öykü", "Kaydet ve
   İmzala"). COMED tek kelime değiştirirse sessizce kırılır.
7. **Hizmet istemleri muayene formunda değil**, ayrı ekranda:
   `<kart adresi>?app-action=action-order-procedure`
8. **Liste varsayılan "Favoriler" sekmesinde** açılıyor; orada olmayan hizmet
   (örn. Ekokardiyografi) bulunamaz → "Genel" sekmesine geçip aramak gerek.
9. **Arama kutusu kirli kalıyor** — her hizmetten sonra temizlenmeli.
10. **Hizmet türüne göre pencere değişiyor:** "Hizmet" tipinde (EKG, EKO)
    *Uygulayan* zorunlu; "Radyoloji" tipinde (grafi) *Uygulayan* yok, yerine
    çekim yöntemi / vücut bölgesi var ve **açıklama zorunlu**.
11. **T.C. kimlik iş listesinde YOK** — ne ekranda ne API'de
    (`medical/task/getPhysicianTasks` dönen alanlar: `birthDate`, `patientId`,
    `patient`, `visitId`, `department`, `gender`). Bu COMED kısıtı, bizim hatamız değil.
    Kimlik sadece hasta kartındaki panelde. Köprü bunu **görünmez iframe** ile okuyor.
12. **Yeni sekme AÇMA.** Kimlik okuma görünmez `<iframe>` ile aynı sekmede yapılır;
    ayrı sekme açılırsa COMED yeniden giriş isteyebiliyor.
13. **Boş iş listesi sonucu hiçbir şeyi silmemeli** — sayfa yüklenmeden yapılan
    boş okuma eskiden doktorun listesini ve hasta eşleşmesini siliyordu.

---

## 3. SÜRÜM / DALLAR

| Dal | Commit | Sürüm |
|---|---|---|
| `main` | v2.38.4 | **v2.38.4** ← güncel |
| `mvp` | `2d6b671` | **v2.32.0** ← "bizim MVP sürümümüz" |
| `mvp-v2.10.3` (etiket) | `7660ef4` | eski demo |

**mvp dalına kullanıcı AÇIKÇA söylemeden dokunma.** Geçmişte izinsiz 3 kez
main'le eşitlendi, geri alınmak zorunda kalındı.

### Sürüm yükseltme — elle yapma
```powershell
python scripts\bump_version.py 2.32.0      # 9 dosyayı birden günceller
python scripts\bump_version.py --check     # tutarlılık denetimi
```
Sürüm **9 ayrı dosyada** yazıyor. Eskiden elle değiştiriliyordu ve desen
bulunamayınca **sessizce atlıyordu** → paket adı v2.25.0, içerik v2.23.0 çıktı.
`tests/test_version_consistency.py` bunu artık yakalıyor.

### Paketleme
```powershell
# ZIP (eklenti)
Compress-Archive -LiteralPath (Get-ChildItem comed_bridge_extension -File).FullName `
  -DestinationPath build_artifacts\klinot-comed-bridge-vX.Y.Z.zip -Force
# APK
cd mobile_app; flutter build apk --release; cd ..
Copy-Item mobile_app\build\app\outputs\flutter-apk\app-release.apk `
  build_artifacts\Klinot-vX.Y.Z.apk -Force
```
`build_artifacts`'ta **yalnız güncel sürüm** durur, eskisi silinir.
Her APK ~51 MB ve git delta yapamıyor → depo şişiyor. Geçmiş bir kez
`git filter-repo` ile 595 MB → 34 MB'a indirildi. Releases'e taşınmalı (yapılmadı).

### Testler
```powershell
python -m pytest -q --tb=line        # 200 passed, 2 skipped, 53 subtests
cd mobile_app; flutter test          # 12
```

---

## 4. NEREDE KALDIK (son durum: 22 Ekim 2026)

**Son iş: v2.33.0 — hizmet istemlerinde yanlış tetkik seçimi, STT Türkçe
bağlamı, analiz promptu güçlendirmesi. Kullanıcı HENÜZ DENEMEDİ.**

### CANLI TEST NASIL YAPILIR (v2.35.0) — "test geçti" demeden önce bunu yap

Eklentiyi Chrome'a yüklemeden **üretim kodunu** canlı COMED'de koşturmak için:

1. `python scripts/live_order_test.py > paket.js` — content.js'ten
   `fillOrders` ve kullandığı her şeyi BİREBİR çıkarır (elle kopyalama yok).
2. paket.js'i CORS + `Access-Control-Allow-Private-Network: true` başlıklı
   yerel bir sunucuyla sun (https COMED sayfası localhost'tan okuyabilsin).
3. Giriş yapılmış COMED sekmesinde: `fetch(...)` → `(0, eval)(kod)` →
   `window.__klinot.fillOrders(fields, record)`.
4. **Sonucu sayaçtan değil, COMED'in kendi istem listesinden doğrula.**
   v2.35.0'da sayaç "3 eklendi" deyip listeye hiç düşmediği görüldü.

COMED oturumu SEKMEYE özel; yeni sekme giriş ister. Şifreyi Claude girmez.

### HER İSTEM TEK EKRANA (v2.36.0) — kullanıcı kuralı
EKG ve EKO → **Hizmet İstem**; akciğer grafisi ve bütün laboratuvar/radyoloji →
**Tetkik İstem**. Bir istem iki ekranda denenmez. Model `screen` alanını yazar,
`comed_integration._service_screen` EKG/EKO/grafi kuralını sabitler.
Hizmet İstem alt listesi tetkikleri de gösterir — bu çift istem değildir.
Düz "EKO" → **Transözofageal ekokardiografi** (KESİN kullanıcı kuralı, 3 Kasım; 3D DEĞİL).
İlaç araması yalnız markayla yapılır; "Alergodil" → "Allergodil burun spreyi" (v2.38.0).
TÜRKÇE TUZAK: "ALLERGODIL".toLocaleLowerCase("tr-TR") = "allergodıl" — karşılaştırmadan önce ı → i katla (v2.38.1).
Hizmet İstem'de her hizmet önce ARANIR sonra tıklanır; aramasız tıklama 2. istemde pencereyi kapatıyor (v2.37.0).
İstem penceresinde Açıklama yok — `byPlaceholder("Açıklama")` kartın Psikolojik Durum alanını bulur, KULLANMA.

### COMED''de ÜÇ İSTEM EKRANI VAR (v2.34.0)

| Ekran | Adres |
| --- | --- |
| Hizmet İstem | `?app-action=action-order-procedure` (EKG gibi işlemler) |
| İlaç İstem | `?app-action=action-order-drug` |
| Tetkik İstem | `?app-action=action-order-study` (laboratuvar + radyoloji) |

"Tam Kan Sayımı katalogda yok" sonucunun sebebi üçüncüsünü bilmememizdi.
Bir istem bulunamıyorsa **önce doğru ekranda mı arıyoruz** diye bak.

Köprü önce Tetkik İstem''i, sonra Hizmet İstem''i dener. Hangi ekranda
olduğunu **katalog** söyler, modele sordurma.

Ad eşleştirmede model bilimsel adı yazar, COMED kısaltmayı kullanır
(ALT (SGPT), CRP (Kantitatif), HDL-Kolesterol). Parantez içindeki kısaltma
da aday olarak denenmeli. Ölçüm tabloları `docs/COMED_FORM_MAP.md`''de.

### ⚠️ DIŞ API PARAMETRESİ EKLERKEN (v2.33.0 dersi)

v2.33.0'da OpenAI dökümüne tek satırlık `prompt` eklendi ve **canlıda bütün
dökümü 503''e düşürdü** — her STT modeli bu parametreyi kabul etmiyor.
Görüşmeler kaybedildi.

Kural: **döküm/analiz, bir iyileştirme uğruna asla başarısız olmamalı.**
Opsiyonel parametre eklerken reddedilme yolunu da yaz (`_prompt_unsupported`
+ promptsuz tekrar deneme). Ve gerçek hataları (429/401/500) yutma.

Ayrıca: eski bir test bir şeyi YASAKLIYORSA önce **neden** yasakladığına bak.
`assertNotIn("prompt", kwargs)` boşuna konmamıştı.

### ⚠️ KATALOG EŞLEŞTİRME KURALI (iki kez aynı hatayı yaptık)

COMED kataloğunda aynı şeyin onlarca nitelikli türevi var ve **düz hali
bulunmayabiliyor**. "İlk eşleşmeyi al" kuralı iki kez klinik hata üretti:

| Doktor dedi | Yanlış seçilen | Neden tehlikeli |
| --- | --- | --- |
| "Parol" | PAROL COLD | fenilpropanolamin, yaşlı hipertansifte kontrendike |
| "EKO" | 3D ekokardiyografi | istenmeyen/pahalı farklı tetkik |

Kural: **tam eşleşme kazanır → söylenmeyen niteleyici VETO → emin değilsen
EKLEME, doktora bırak.** Hem `scoreDrugOption` hem `scoreServiceRow` bunu
uygular. Yeni bir katalog alanı eklerken aynısını yap.

Canlı ölçümler `docs/COMED_FORM_MAP.md`'de. Örnek: "Tam Kan Sayımı"
katalogda HİÇ YOK, "Ekokardiyografi"nin düz hali YOK.

v2.32.0'ın üç hatası (22 Ekim'de canlı COMED'de ölçüldü):
1. Arama kutusu bizzat eleniyordu — placeholder "Temel ilaçlar kategorisinde
   ara", kod ise "ara" geçenleri atıyordu.
2. `co-button-İlaç İstem` diye bir düğme YOK; 12 sn boşuna bekleniyordu.
3. `.co-input__label` içinde "Ana İlaç" etiketi YOK.

⚠️ **Ve bir hasta güvenliği hatası:** "ilk başlayan eşleşme" kuralı "Parol"
için **PAROL COLD** (grip ilacı, fenilpropanolamin, yaşlı hipertansifte
kontrendike) seçiyordu. Artık marka eki vetosu + doz eşleşmesi + eşik var;
emin olunamazsa ilaç HİÇ eklenmiyor. Karar tablosu `docs/COMED_FORM_MAP.md`.

**DERS: string arayan testler bu sınıf hatayı yakalamaz.** v2.32.0'ın testi
`startsWith(wanted)` arıyordu — yani hatayı şart koşuyordu. Eklenti
değişikliklerini canlı COMED'de ölçmeden "test geçti" deme.

- `requested_drugs`: ad + doz + günlük sıklık + gerekçe. Köprü
  `?app-action=action-order-drug` ekranında arama kutusundan ilacı seçip
  "Ekle" diyor. Doz/sıklık söylenmediyse COMED varsayılanı kalıyor.
- Doktor paneli: üstte arama + tarih aralığı, sayım şeridi en alta alındı.
- ⚠️ İlk iş: `klinot-comed-bridge-v2.32.0.zip` yüklenip "Parol yazıyorum,
  günde 3 kez" gibi bir görüşmeyle ilaç istemi baştan sona denenmeli.

### Önceki iş: EKG/EKO hizmet istemleri — TAMAMLANDI ve DOĞRULANDI

- v2.30.0'da özellik yazıldı ama canlıda EKG penceresi açılıp **takıldı**.
- v2.31.0'da üç kök sebep canlı COMED'de ölçülerek bulundu ve düzeltildi
  (ok ikonu dinleyicisi / iki `co-button-Ekle` / kirli arama kutusu), ayrıca
  Favoriler→Genel sekme yedeği eklendi.
- Düzeltilmiş akışla **gerçek bir EKG istemi oluşturuldu**, pencere kapandı,
  listeye düştü. `main`'e pushlandı, APK + ZIP üretildi.

✅ **Kullanıcı 22 Ekim 2026'da doğruladı: "şu an bir sorun yok, EKO EKG
çalışıyor."** Hizmet istemleri canlıda çalışır durumda.


### Temizlik borcu
Test sırasında COMED test ortamında bırakılanlar silinmeli:
- Enes Aydın (22207362): bir EKG istemi + yarım kalmış Akciğer Grafisi penceresi
- Ahmet Kılıçarslan (22207363): bir EKG istemi

---

## 5. ÇÖZÜLMEMİŞ İŞLER

### İşlevsel
1. **Hasta kimlik eşleşmesi hâlâ şüpheli.** 14 Ekim'in son mesajı buydu ve hiç
   yanıtlanmadı: *"eşleşmiyor, bazen kartın içine girip yenileyince eşliyor"*.
   v2.26/v2.27 (arka plan sekme → görünmez iframe) bunu hedefledi ama kullanıcı
   onayı yok. **Açık.**
2. **Radyoloji tipi istemler otomatik girilmiyor** — bilinçli karar. Köprü
   pencereyi kapatıp "doktor tamamlamalı" diyor. Sonraki aşama.
3. **Aktarım hızı tavana dayandı** — 19 sn'nin 9 sn'si COMED'in kendi kart
   yükleme süresi. Bizim kontrolümüzdeki kısım 4,2 sn. Daha fazlası mümkün değil.

### Güvenlik — 29 Eylül'den beri açık, HİÇ DÜZELTİLMEDİ
4. **`/analyze`, `/analyze/stream`, `/transcribe`, `/pdf`, `/legacy` kimlik
   doğrulamasız.** Linki bilen Gemini/OpenAI kotasını harcayabilir.
5. **`SESSION_SECRET` boşsa** imza anahtarı `ADMIN_USER`/`ADMIN_PASS`'ten
   türüyor; varsayılanlar `admin`/`admin` → saldırgan kendine admin çerezi üretebilir.
6. **`PATIENT_TEST_OTP_ENABLED=true`** → sabit OTP `000000`. SMS hiç bağlanmadı.
   **Gerçek hasta verisine geçmeden kapatılmalı.**
7. **`PATIENT_TCKN_CHECKSUM=false`** → uydurma TC kabul ediliyor (COMED test
   hastası `12345678912` resmi algoritmayı geçmediği için kapatıldı).
8. **Hasta, doktorun yönetim raporunu okuyabiliyor** —
   `GET /api/v1/mobile/records/{id}` filtresiz.
9. Doktor şifreleri **düz metin** (`"1"`). CSRF yok, CORS yok, rate limit yok.

### Teknik borç
10. `main.py` bölünmeli · ElevenLabs ölü kodu temizlenmeli · tanılar sessizce
    3'e kırpılıyor (`comed_integration.py:599`, uyarı yok) · testler ayrı DB
    kullanmalı · APK'lar Releases'e taşınmalı.

### Taşıma (Ubuntu + Supabase)
`docs/TASIMA.md` hazır: systemd, nginx + Let's Encrypt, 30 env değişkeninin
listesi, `db.py`'deki SQLite'a özgü 8 nokta, seslerin Storage'a taşınması.
Depoda gerçek sır yok → anahtarlar taşıma günü **Render panelinden elle** alınır.

---

## 6. ÇALIŞMA KURALLARI

- **Türkçe konuş.** Kullanıcı hızlı yazıyor, yazım hatalarına takılma.
- **Kullanıcı "basit bir şey" dediyse basit yap.** Geçmişte istenmeyen ekler
  (akciğer grafisi, mvp eşitleme, yeni sekme açma) defalarca geri alındı.
- **COMED değişikliklerini canlıda doğrula.** Chrome eklentisi + test ortamı
  zaten açık; tahmin etme, ölç. Bu projede DOM varsayımları sürekli yanlış çıktı.
- **İmzayı asla otomatikleştirme.** `auto_sign` her zaman `false`.
- **Doktoru uğraştırma:** yeni sekme açma, yeniden giriş isteme, popup çıkarma.
- İş PC'si: **CrowdStrike Falcon** aktif. Geçici script yazıp çalıştırıp silme
  döngüsü, PowerShell .NET yansıması ve toplu git yeniden yazımı uyarı tetikliyor.
  `EPERM` dosya kilitleri bundan; `[System.IO.File]` ile aş.
- PowerShell'de `Out-File -Encoding utf8` **BOM** ekliyor ve `manifest.json`'u
  kırıyor → `New-Object System.Text.UTF8Encoding($false)` kullan.
