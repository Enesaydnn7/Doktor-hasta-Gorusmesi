# Klinot — Sistem Mimarisi ve Devir Dokümanı (v3.0.0)

> **Kime:** Projeyi devralacak / birlikte çalışacak yazılımcı.
> **Ne:** Sistemin baştan sona nasıl çalıştığı: mobil uygulama, sunucu (backend),
> doktor paneli, admin paneli, Chrome eklentisi ve "COMED'e aktar" akışı.
> **Tarih:** 6 Kasım 2026 · **Sürüm:** v3.0.0 (main = mvp = `2ce0e1f`)
> **Kaynak kod:** https://github.com/Enesaydnn7/Doktor-hasta-Gorusmesi (dal: `main`)
>
> Bu belge koddan doğrulanarak yazıldı. Parantez içindeki `dosya:satır`
> referansları v3.0.0 kodudur; kod değiştikçe satırlar kayabilir.

---

## İçindekiler

1. [Tek cümlede Klinot](#1-tek-cümlede-klinot)
2. [Büyük resim: parçalar ve kim kiminle konuşur](#2-büyük-resim)
3. [Dış servisler ve API'ler](#3-dış-servisler-ve-apiler)
4. [Hesaplar, roller ve giriş](#4-hesaplar-roller-ve-giriş)
5. [Uçtan uca akış: görüşmeden COMED formuna](#5-uçtan-uca-akış)
6. [Backend (sunucu)](#6-backend-sunucu)
7. [Veritabanı](#7-veritabanı)
8. [Analiz hattı: ses → metin → rapor → COMED taslağı](#8-analiz-hattı)
9. [Mobil uygulama (Flutter)](#9-mobil-uygulama)
10. [Doktor paneli](#10-doktor-paneli)
11. [Admin paneli](#11-admin-paneli)
12. [Chrome eklentisi](#12-chrome-eklentisi)
13. ["COMED'e aktar" adım adım](#13-comede-aktar-adım-adım)
14. [Chrome Web Store yayını](#14-chrome-web-store-yayını)
15. [Sürümleme, dallar, paketler](#15-sürümleme-dallar-paketler)
16. [Çalıştırma, test, deploy](#16-çalıştırma-test-deploy)
17. [Güvenlik kuralları (değişmez)](#17-güvenlik-kuralları)
18. [Bilinen eksikler / teknik borç](#18-bilinen-eksikler--teknik-borç)
19. [Linkler ve hesaplar özeti](#19-linkler-ve-hesaplar-özeti)

---

## 1. Tek cümlede Klinot

Doktor–hasta görüşmesi telefonla kaydedilir; ses yapay zekâ ile konuşmacı
ayrımlı metne çevrilir; aynı metinden **hasta özeti, doktor epikrizi, yönetim
raporu ve COMED form taslağı** üretilir; doktor web panelinden
**"COMED'e aktar"** dediğinde Chrome eklentisi bu taslağı doktorun açık COMED
(hastane bilgi sistemi) ekranına **bir insan gibi yazarak/tıklayarak** doldurur.
**Kaydetme ve imzalama her zaman doktordadır.**

---

## 2. Büyük resim

```
 ┌──────────────┐  ses + API (Bearer)   ┌──────────────────────────────┐
 │ Mobil uygulama│ ────────────────────► │  Klinot sunucusu (FastAPI)   │
 │  (Flutter)    │ ◄──── raporlar ────── │  Render · SQLite             │
 └──────────────┘                        │                              │
                                         │  ──► OpenAI (ses→metin)      │
 ┌──────────────┐  çerez oturumu         │  ──► Gemini (rapor+taslak)   │
 │ Doktor paneli │ ◄───────────────────► │                              │
 │  /doctor      │                       │                              │
 └──────┬───────┘                        │                              │
        │ "kartı aç" (tarayıcı içi mesaj) │                              │
        ▼                                │                              │
 ┌──────────────┐  API (Bearer, polling) │                              │
 │Chrome eklentisi│ ◄───────────────────► │                              │
 │  "Klinot"     │  iş al / durum bildir  └──────────────────────────────┘
 └──────┬───────┘
        │ DOM otomasyonu (yazma, tıklama) — API YOK
        ▼
 ┌──────────────┐
 │ COMED ekranı  │  doktorun kendi açık oturumu
 │ (Göztepe test)│  Kaydet / İmzala → DOKTOR
 └──────────────┘
```

| Parça | Teknoloji | Nerede | Görevi |
|---|---|---|---|
| Backend | Python 3, FastAPI, SQLite | Render (ücretsiz plan) | Ses→metin, analiz, kayıt, aktarım kuyruğu, web panelleri |
| Mobil | Flutter (Android/iOS) | `mobile_app/` · APK: `build_artifacts/Klinot-v3.0.0.apk` | Görüşmeyi kaydet, analize gönder, raporu gör |
| Doktor paneli | Jinja2 + vanilla JS | `/doctor` | İş listesi, kayıtlar, raporlar, ses, **COMED'e aktar** |
| Admin paneli | Jinja2 + vanilla JS | `/admin` | Tüm kayıtlar, maliyet, dinle, PDF, sil |
| Chrome eklentisi | Manifest V3 | `comed_bridge_extension/` · Chrome Web Store'da "Klinot" | COMED formunu doldurur, iş listesini sunucuya eşitler |
| Eski analiz sayfası | Jinja2 + JS | `/legacy` | Web'den kayıt/yükleme + analiz (test amaçlı) |

### En önemli mimari gerçek

**Sunucu ile eklenti API ile konuşur, eklenti ile COMED API ile konuşmaz.**

- Sunucu eklentiye kendiliğinden bir şey **göndermez** (push yok). Eklenti
  sunucuya düzenli aralıklarla **"benim için bekleyen iş var mı?"** diye sorar
  (polling) ve işi alır; bitince **durumu bildirir**.
- Eklenti COMED'e **hiçbir POST/API isteği atmaz**. COMED sayfasındaki
  kutulara yazar, düğmelere/toggle'lara tıklar, otomatik tamamlama listesinden
  seçer — doktor elle yapsa ne yapacaksa onu yapar. Doktorun kendi COMED
  oturumu kullanılır; COMED şifresi/tokenı Klinot sunucusuna **asla gitmez**.
- Eskiden "doğrulanmış POST şablonu" ile COMED'e doğrudan kayıt atan bir yol
  vardı; **kaldırıldı** (`comed_integration.py:788-800` yorumu). Pakette
  `execution_mode: "extension_form_fill"` yazar.

---

## 3. Dış servisler ve API'ler

| Servis | Kim çağırır | Ne için | Ayar |
|---|---|---|---|
| **OpenAI** `gpt-4o-transcribe-diarize` | Sunucu (`stt.py`) | Ses → konuşmacı ayrımlı Türkçe metin | `OPENAI_API_KEY`, `OPENAI_STT_MODEL` |
| **OpenAI** `gpt-transcribe` | Sunucu | Yedek: ana model boş dönerse | `OPENAI_STT_FALLBACK_MODEL` |
| **Google Gemini** `gemini-2.5-flash` | Sunucu (`role_classifier.py`, `llm.py`) | Doktor/Hasta rol eşleme + 4 rapor | `GEMINI_API_KEY`, `GEMINI_MODEL` |
| **SMS webhook** | Sunucu | Hasta girişi OTP kodu | `PATIENT_SMS_WEBHOOK_URL` (henüz bağlı değil) |
| **COMED** (Göztepe **test**) | **Yalnızca eklenti, ekran üzerinden** | Form doldurma | `COMED_WEB_BASE_URL`, `COMED_API_BASE_URL` |

- Mobil uygulama ve eklenti **dış AI servislerine doğrudan bağlanmaz**; her şey
  Klinot sunucusu üzerinden gider. API anahtarları yalnızca sunucuda (Render
  Environment) durur.
- ElevenLabs kodu (`stt.py`, `config.py`) **ölü koddur**, çağrılmıyor.
- COMED adresleri:
  - Web: `https://goztepetest.comed.mlpcare.com/tr-tr/medical`
  - API (yalnız iz/trace kaydı filtresi için): `https://goztepetestapi.comed.mlpcare.com/tr-tr/api/json`
  - Hasta kartı adresi: `{web}/hasta-tibbi-karti/{visit_id}/patient-clinical-card/` (`main.py:752-765`)

---

## 4. Hesaplar, roller ve giriş

Üç rol vardır: **admin**, **doctor**, **patient**.

| Rol | Nereden girer | Ne ile | Oturum |
|---|---|---|---|
| admin | `/admin/login` (web) | `ADMIN_USER` / `ADMIN_PASS` (varsayılan `admin`/`admin`) | Çerez, 12 saat |
| doctor | `/doctor/login` (web), mobil uygulama, Chrome eklentisi | **Aynı Klinot doktor hesabı** | Web: çerez 12 saat / "Beni hatırla" 30 gün · Mobil+eklenti: Bearer token 30 gün |
| patient | Yalnızca mobil uygulama | T.C. kimlik **veya** hasta no + doğum tarihi + SMS kodu | Bearer token 30 gün |

### Doktor hesabı ve COMED kullanıcı adı ilişkisi

- Doktor hesapları `DOCTOR_ACCOUNTS_JSON` ortam değişkeninden okunur; boşsa
  koddaki test hesabı kullanılır (`auth.py:26-65`).
- Kullanıcı adı biçimi COMED kullanıcı adını taklit eder:
  `<comed_kullanici>;<tracer_kullanici>|tracer`
  Test hesabı: **`Kullanici.kayadr;Kullanici.aydin1|tracer`** / şifre **`1`**
  (görünen ad: "Prof. Dr. Personel Kaya").
- Yani doktor, COMED'deki kullanıcı adıyla aynı biçimde bir **Klinot hesabıyla**
  girer. Ama **Klinot bu şifreyi COMED'e sormaz**; Klinot hesabı ayrıdır,
  şifresi COMED şifresi değildir.
- **Aynı kullanıcı adı her yerde birebir aynı kullanılmalı** (mobil, eklenti,
  doktor paneli). Çünkü bu metin veritabanında `owner_user`, `synced_by`,
  `requested_by`, `assigned_doctor_user` anahtarı olarak geçer; biri farklı
  olursa doktor kendi iş listesini/kayıtlarını göremez.
- Admin hesabı mobil uygulamaya, eklentiye ve doktor paneline **kabul edilmez**
  (`main.py:473-477`).

### Eklentiye giriş

Eklenti simgesine tıklanır → açılan pencerede **Klinot doktor hesabı**
(yukarıdaki kullanıcı adı ve şifre) girilir → `POST /api/v1/mobile/auth/login`
→ dönen Bearer token `chrome.storage.local`'a yazılır. **COMED şifresi
eklentiye yazılmaz**; COMED'e doktor Chrome'da kendisi, normal şekilde girer.

### Hasta girişi (mobil)

1. `POST /api/v1/mobile/auth/patient/otp/start` — T.C. kimlik (veya hasta no) +
   doğum tarihi. Sunucu `HMAC-SHA256` özetini çıkarır ve `comed_worklist`
   tablosundaki bir randevuyla eşleştirir. Eşleşme yoksa giriş olmaz.
2. SMS ile 6 haneli kod gönderilir (5 dk geçerli, 5 deneme).
3. `POST .../otp/verify` → Bearer token.

- **Ham T.C. kimlik numarası veritabanında saklanmaz**, yalnızca özeti tutulur.
- Kimlik özeti nereden geliyor: eklenti, doktor COMED'de hasta kartını
  açtığında (veya arka planda) kartın "Hasta Bilgileri" panelinden T.C. ve
  doğum tarihini okuyup `worklist/sync` ile gönderir; sunucu özetleyip ham
  değeri atar (`main.py:791-825`).
- Test ortamında `PATIENT_TEST_OTP_ENABLED=true` ise `000000` kodu geçer.
  Render'da `false`. SMS sağlayıcısı henüz bağlı değil.

### Oturum imzası

Tüm çerez ve tokenlar `SESSION_SECRET` ile HMAC-SHA256 imzalıdır, durumsuzdur
(sunucuda oturum tablosu yok). `SESSION_SECRET` boş bırakılırsa anahtar admin
şifresinden türetilir — **canlıda mutlaka dolu olmalı.**

---

## 5. Uçtan uca akış

```
1  Doktor COMED'e girer, iş listesini açar
     └─ Eklenti iş listesini okur → POST /api/v1/mobile/comed/worklist/sync
        (hasta adı, hasta no, protokol, visit_id, kart adresi, kimlik özeti)

2  Görüşme mobil uygulamada kaydedilir (doktor veya hasta telefonunda)
     └─ Hasta, iş listesinden seçilir (bu sayede kayıt hastaya bağlanır)

3  Ses sunucuya yüklenir → POST /api/v1/mobile/transcriptions  (202 + job_id)
     └─ Sunucu arka planda OpenAI'ye gönderir; uygulama job'u sorgular

4  Metin hazır → POST /api/v1/mobile/analyze/stream
     └─ Gemini: rol eşleme + 4 paralel rapor (hasta, doktor, yönetim, COMED)
     └─ Kayıt SQLite'a yazılır (ses dahil); kayıt doktora atanır

5  Doktor /doctor paneline girer → kaydı görür (Raporlar, ses, taslak)

6  "COMED'e aktar ve kartı aç"
     └─ Sunucu aktarım paketi üretir, comed_transfers'a "queued" yazar
     └─ Panel eklentiye "kartı aç" der → eklenti COMED kartını açar/öne getirir

7  Eklenti sunucudan işi çeker → formu ekranda doldurur
     └─ Durum: queued → filling → ready_for_review (veya failed)

8  Doktor COMED'de kontrol eder, düzeltir, KENDİSİ kaydeder ve imzalar
```

---

## 6. Backend (sunucu)

- Giriş noktası: **`main.py`** (FastAPI, ~1400 satır; tüm uçlar tek dosyada).
- Çalıştırma: `uvicorn main:app --host 0.0.0.0 --port $PORT` (`Procfile`, `render.yaml`).
- Canlı adres: **https://doktor-hasta-gorusmesi.onrender.com**
- Render ücretsiz plan: 15 dk boşta kalınca uyur, ilk açılış ~30-50 sn.

### Dosyalar

| Dosya | Görevi |
|---|---|
| `main.py` | Tüm HTTP uçları, yetki bağımlılıkları, analiz/aktarım orkestrasyonu |
| `config.py` | `.env` / ortam değişkenleri, `APP_VERSION` |
| `auth.py` | Admin/doktor/hasta hesapları, imzalı çerez ve Bearer token, OTP, kimlik özeti |
| `db.py` | SQLite şeması ve tüm sorgular, demo kayıt yükleme |
| `stt.py` | OpenAI ses→metin, konuşmacı segmentleri, prompt sızıntısı temizliği, 48 MB sınırı |
| `role_classifier.py` | Gemini ile konuşmacı A/B → Doktor/Hasta eşlemesi (sözcükler değişmez) |
| `llm.py` | Gemini çağrıları, 4 paralel rapor, deterministik düzeltmeler |
| `prompts.py` | `SYSTEM_HASTA`, `SYSTEM_DOKTOR`, `SYSTEM_YONETIM`, `SYSTEM_COMED` |
| `comed_integration.py` | COMED taslağını normalize etme, eşanlam/alias, zorunlu alan kontrolü, **aktarım paketi** |
| `pdf_report.py` | ReportLab ile PDF (epikriz, hasta raporu, yönetim) |
| `pricing.py` | Token/dakika başına tahmini maliyet |
| `api_resilience.py` | Dış API hatalarını kullanıcıya anlaşılır mesaja çevirme |
| `templates/`, `static/` | Web panelleri |
| `demo_records/` | Her açılışta veritabanına yeniden yüklenen kalıcı demo kayıtlar (ses dahil) |
| `scripts/` | `bump_version.py`, canlı test ve demo yardımcıları |
| `tests/` | ~320 test (`python -m pytest`) |

### HTTP uçları

**Web (çerez)**

| Uç | Yetki | Ne yapar |
|---|---|---|
| `GET /` | — | Rolüne göre `/admin`, `/doctor` ya da `/doctor/login`'e yönlendirir |
| `GET /legacy` | **yok** | Eski analiz sayfası |
| `POST /analyze`, `POST /analyze/stream` | **yok** ⚠ | Metinden analiz (stream: NDJSON ilerleme) |
| `POST /transcribe` | **yok** ⚠ | Ses→metin |
| `POST /pdf` | **yok** | Gönderilen JSON'dan PDF |
| `GET/POST /doctor/login`, `GET /doctor/logout` | — | Doktor girişi/çıkışı |
| `GET /doctor` | doktor | Doktor paneli |
| `GET /doctor/api/overview` | doktor | İş listesi + kayıtlar + istatistik |
| `GET /doctor/api/records/{kid}` | doktor | Tek kayıt (raporlar, taslak, son aktarım) |
| `POST /doctor/api/comed/transfers` | doktor | **Aktarım oluştur** |
| `GET /doctor/api/comed/transfers/{id}` | doktor | Aktarım durumu |
| `POST /doctor/api/comed/transfers/{id}/cancel` | doktor | Aktarımı bırak (failed) |
| `GET/HEAD /doctor/audio/{kid}` | doktor | Ses (Range destekli) |
| `GET /doctor/pdf/{kid}[/{rec}]` | doktor | PDF |
| `GET/POST /admin/login`, `/admin/logout` | — | Admin girişi |
| `GET /admin` | admin | Admin paneli |
| `GET /admin/kayit/{kid}`, `DELETE /admin/kayit/{kid}` | admin | Kayıt JSON / sil |
| `GET /admin/ses/{kid}` | admin | Ses |
| `POST /admin/pdf/{kid}/{rec}` | admin | PDF |
| `POST /admin/comed/transfer/{kid}` | admin | Admin adına aktarım (pratikte eklentiye ulaşmaz, bkz. §18) |
| `GET /admin/comed/request-log`, `/admin/comed-view` | admin | COMED iz kayıtları (debug) |
| `GET /gizlilik` | — | Gizlilik politikası (Chrome Web Store için zorunlu) |
| `GET /health` | — | Sürüm/model bilgisi |

**Mobil + eklenti API (`/api/v1/mobile/...`, Bearer token)**

| Uç | Rol | Ne yapar |
|---|---|---|
| `POST /auth/login` | — | Doktor girişi → token (mobil + **eklenti**) |
| `POST /auth/patient/otp/start`, `/otp/verify` | — | Hasta girişi |
| `GET /auth/session` | herkes | Token kontrolü |
| `GET /health` | — | Sağlık |
| `POST /transcriptions` | doktor/hasta | Ses yükle → STT işi (aynı ses = aynı iş, SHA256) |
| `GET /transcriptions/{job_id}` | doktor/hasta | İş durumu / metin |
| `POST /transcribe` | doktor/hasta | Eski senkron STT |
| `POST /analyze/stream` | doktor/hasta | Analiz (hasta yalnız hasta raporunu alır) |
| `POST /pdf/epikriz`, `/pdf/saglik-raporu` | doktor / hasta | PDF |
| `GET /comed/worklist` | doktor/hasta | Doktorun iş listesi / hastanın randevuları |
| `GET /comed/worklist/missing-identity` | doktor | Kimliği eksik hastalar (eklenti arka planda tamamlar) |
| `POST /comed/worklist/sync` | doktor | **Eklenti** iş listesini yükler |
| `POST /comed/transfers`, `GET /comed/transfers/{id}` | doktor | Mobilden aktarım |
| `GET /comed/bridge/transfers` | doktor | **Eklenti: bekleyen işlerim** |
| `POST /comed/bridge/transfers/{id}/status` | doktor | **Eklenti: durum bildir** |
| `POST/GET /comed/request-log` | doktor | Eklentinin temizlenmiş COMED iz kayıtları |
| `GET /records`, `GET /records/{kid}` | herkes (kendi) | Kayıtlar |

---

## 7. Veritabanı

SQLite, tek dosya: `kayitlar.db` (`DB_PATH` ile değişir). Şema `db.init()`
içinde oluşur ve eski kolonları kendi kendine taşır (migration kodu orada).

| Tablo | İçerik |
|---|---|
| `kayitlar` | Her analiz: transkript, `hasta`/`doktor`/`yonetim`/`comed` JSON, `usage`, **ses BLOB**, `ozet`, `source` (web/mobile), `metadata` (seçilen COMED hastası vb.), `owner_user`, `assigned_doctor_user`, `demo_key` |
| `bekleyen_sesler` | Analizden önce yüklenen geçici ses (en fazla 20) |
| `transcription_jobs` | Asenkron STT işi: `queued → processing → completed / failed` |
| `comed_worklist` | Doktor başına COMED iş listesi; PK `(visit_id, synced_by)`; `patient_identity_hash`, `patient_number_hash` |
| `comed_transfers` | Aktarım paketi (`bundle` JSON), `status`, `error`, `debug`, `requested_by` |
| `comed_trace_events` | Eklentinin yakaladığı, sırları temizlenmiş COMED API izleri (debug) |

### Kayıt kime görünür?

- `owner_user`: kaydı oluşturan hesap (mobilde giriş yapan kullanıcı).
- `assigned_doctor_user`: **hasta** kendi telefonundan kaydettiyse, o hastanın
  randevusunu iş listesine eşitleyen doktor (`db.comed_assigned_doctor`).
- Doktor paneli: `owner_user = doktor OR assigned_doctor_user = doktor`.

### ⚠ Veriler kalıcı değil

Render ücretsiz planda disk geçicidir: **her deploy / yeniden başlatmada
veritabanı sıfırlanır.** Bunu telafi etmek için `SEED_MANAGER_DEMO=true` iken
`demo_records/` içindeki kayıtlar (JSON + ses) her açılışta yeniden eklenir
(şu an 4 kayıt: gastrit, bacak ağrısı, göğüs ağrısı, "COMED tam test · Göğüs
ağrısı + rinit"). Gerçek kullanım için Postgres'e geçmek gerekir
(`docs/TASIMA.md`); yalnızca `db.py` değişir.

---

## 8. Analiz hattı

```
Ses (m4a/webm, ≤48 MB, mobilde 64 kbps)
 │ POST /api/v1/mobile/transcriptions → job_id (202)
 ▼
stt.py — OpenAI gpt-4o-transcribe-diarize (konuşmacı A/B segmentleri)
 │       yedek: gpt-transcribe (yalnız ana model boşsa)
 │       kısa Türkçe tıbbi prompt + prompt sızıntısı temizleme
 ▼
role_classifier.py — Gemini 1 çağrı: A/B → "Doktor:" / "Hasta:"
 │       sözcükler DEĞİŞTİRİLMEZ; başarısızsa konuşma sırası kullanılır
 ▼
llm.py analyze_all — Gemini 4 PARALEL çağrı (asyncio.gather)
 │   hasta    → sade dil sağlık özeti
 │   doktor   → detaylı epikriz (şikâyet, başlangıç tarihi, ağrı, öykü,
 │              özgeçmiş, soygeçmiş, muayene, tetkik, ön/kesin tanı + ICD,
 │              tedavi, plan, kontrol) + iletişim koçluğu
 │   yonetim  → güvenlik/üslup, doktor skoru, verimlilik, risk
 │   comed    → COMED formunun alan alan JSON taslağı
 │   TEMPERATURE=0 → aynı görüşme ≈ aynı çıktı
 ▼
_reconcile_comed_with_epicrisis — kural tabanlı düzeltme (görüşmede açıkça
 │   geçen özgeçmiş öğeleri, düşme riski vb. taslağa eksiksiz geçsin)
 ▼
db.kaydet → kayitlar (ses BLOB dahil)
```

- **Altın kural:** Görüşmede geçmeyen alan boş kalır / "belirtilmedi" yazar;
  uydurma yasak (prompt'larda ve normalize adımında uygulanır).
- `/analyze/stream` satır satır NDJSON gönderir: `progress` (adım + yüzde),
  10 sn'de bir `heartbeat`, sonunda `result` veya `error`.
- Maliyet her kayıtta `usage` içinde saklanır (Gemini token + OpenAI ses).

### COMED taslağı (`comed` JSON) neler içerir

Örnek şema: `docs/COMED_TRANSFER_SCHEMA.example.json`. Başlıca alanlar:

- `patient_complaint`, `complaint_start_date`, `patient_story` (öykü)
- `profile`: hastalıklar, ameliyatlar, kullandığı ilaçlar, alerjiler,
  alışkanlıklar, aşılar, cihazlar, transfüzyonlar, tedaviler, **soygeçmiş**,
  meslek, eğitim, medeni hal
- `review_of_system` (Sistem Sorgulama, 9 grup) + serbest metin
- `psychological_status`, `fall_risk` (düşme riski), `pain` (skor, yer,
  nitelik, ritim), `vitals` (kilo, boy, ateş, nabız, tansiyon, SpO2)
- `exam_simple_textarea` (fizik muayene), `diagnoses` (ICD, ön/kesin, taraf)
- `treatment_note_v2`, `treatment_plan_label`, `is_surgery_will_planned`
- `requested_services` (tetkik / laboratuvar / radyoloji / hizmet istemleri)
- `requested_drugs` (ilaç istemleri: ad, doz, sıklık)

`comed_integration.normalize_draft` bu taslağı COMED'in **birebir seçenek
adlarına** indirger (örn. "Aspirin" → "Asetilsalisilik asit", Sistem
Sorgulama eşanlamları, hizmet/ilaç adları), zorunlu alan eksiklerini
`missing_required` olarak işaretler.

---

## 9. Mobil uygulama

> Ayrıntı: `MOBILE_APP.md`, kod: `mobile_app/lib/`.

### Kimlik

| | |
|---|---|
| Ad | **Klinot** ("Klinik görüşme asistanı") |
| Paket | `com.klinot.klinot` |
| Sürüm | `3.0.0+62` (`pubspec.yaml`) |
| Sunucu | `https://doktor-hasta-gorusmesi.onrender.com` (`--dart-define=API_BASE_URL=...` ile değişir) |
| APK | `build_artifacts/Klinot-v3.0.0.apk` (~53 MB) — **debug anahtarıyla imzalı**, mağaza imzası yok |
| İzinler | İnternet, mikrofon, ekranı açık tutma |
| iOS | `ios/` projesi var; TestFlight için macOS + Xcode + Apple hesabı gerekir |

**Derleme:**

```powershell
cd mobile_app; flutter build apk --release; cd ..
Copy-Item mobile_app\build\app\outputs\flutter-apk\app-release.apk build_artifacts\Klinot-vX.Y.Z.apk -Force
```

Geliştirme: `flutter run --dart-define=API_BASE_URL=http://10.0.2.2:8000`
(emülatörden yerel sunucu). Test: `flutter test`.

### Ekranlar

| Dosya | Ekran |
|---|---|
| `app.dart` | Açılış: kayıtlı oturumu güvenli depodan geri yükler, `GET /auth/session` ile doğrular (401 → çıkış; internet yoksa oturum korunur) |
| `login_screen.dart` | **Doktor / Hasta** sekmeli giriş |
| `recorder_screen.dart` | Ana ekran: hasta seçimi, onay, kayıt, analiz ilerlemesi |
| `reports_screen.dart` | Rapor ekranı, PDF, COMED'e aktar |
| `api_client.dart` | Tüm sunucu çağrıları |
| `audio_recorder_service.dart` | Ses kaydı |
| `transcript_screen.dart` | **Ölü kod** (hiçbir yerden açılmıyor) |

### Giriş

- **Doktor sekmesi:** kullanıcı adı + şifre (Klinot doktor hesabı).
- **Hasta sekmesi:** T.C. kimlik (11 hane) + doğum tarihi (GG.AA.YYYY) →
  SMS kodu ekranı ("… numaralı telefona gönderildi"; test modunda
  "Test ortamı kodu: 000000" yazar) → 6 haneli kod.
- Oturum her zaman hatırlanır (30 gün), "Beni hatırla" kutusu yok.

### Kayıt ve analiz akışı

1. **Hasta seçimi:**
   - Doktor: kendi COMED iş listesinden "Hasta / protokol" açılır listesiyle
     seçer (liste tek kişiyse otomatik). Liste boşsa eklenti kurulum
     talimatı gösterilir.
   - Hasta: seçim yok; en yeni randevusu otomatik bağlanır. Randevu yoksa
     ~2,5 dk boyunca 6 sn'de bir tekrar dener.
2. **Onay anahtarı** (KVKK bilgilendirmesi) açılmadan kayıt başlamaz.
3. **Kayıt:** AAC `.m4a`, 64 kbps, 32 kHz, mono; seviye göstergesi, duraklat /
   devam, iptal; ekran açık tutulur. Uygulama çökerse son kayıt açılışta
   "Önceki kayıt cihazdan kurtarıldı" diye geri gelir.
4. **"Analiz et":**
   - "Ses kaydı metne dönüştürülüyor" → `POST /transcriptions` (3 deneme),
     sonra `GET /transcriptions/{job_id}` 3 sn'de bir (en çok 45 dk).
   - "Klinik raporlar hazırlanıyor" → `POST /analyze/stream`, yüzde halkası.
5. Sonuç gelince rapor ekranı açılır. **Görüşme metni uygulamada gösterilmez.**

### Rapor ekranı

| | Doktor | Hasta |
|---|---|---|
| Başlık | "AI epikriz" | "Sağlık raporum" |
| İçerik | Epikriz (tarih, şikâyet, başlangıç, ağrı, öykü, muayene, özgeçmiş, soygeçmiş, ön/kesin tanı + ICD, lab, tedavi, plan, kontrol) + **İletişim önerileri** | Sade özet: değerlendirme, yapılacaklar, ilaçlar, kontrol |
| PDF | AI epikriz PDF | Sağlık raporu PDF |
| COMED | **COMED'e aktar** (durumu 3 sn'de bir izler) + **COMED'de aç** | yok |
| Diğer | Yeni görüşme | Yeni görüşme |

### Uygulamada olmayanlar

- **Geçmiş kayıtlar ekranı yok**; rapor yalnız o an görülür (sonradan doktor
  panelinden bakılır). "Tekrar analiz et" her seferinde yeni kayıt oluşturur.
- Yönetici girişi yok (mobil admin hesabını reddeder).
- Arka planda / ekran kapalıyken kayıt garanti değil (foreground service yok).
- API hasta numarasıyla girişi destekliyor ama uygulama 11 hane istediği için
  bu yol kullanılamıyor.

### Hasta kaydı doktora nasıl düşer

Hasta kendi telefonundan kaydettiğinde kayıt `owner_user = hasta no` olur;
sunucu o hasta no + `visit_id` için iş listesini eşitleyen doktoru bulup
`assigned_doctor_user`'a yazar → kayıt **o doktorun panelinde** görünür.
Hastaya analiz sonucundan yalnız hasta raporu döner.

---

## 10. Doktor paneli

**Adres:** https://doktor-hasta-gorusmesi.onrender.com/doctor
(`/` adresi de oturuma göre buraya yönlendirir.)

### Giriş

`/doctor/login` — Kullanıcı adı, şifre, **"Beni hatırla"** (varsayılan
işaretli, 30 gün). Admin bilgileriyle girilmez. Aynı hesap mobil uygulama ve
eklentide de kullanılır.

### Ekranda neler VAR

**Üst kısım:** doktorun adı, Çıkış.

**Arama ve süzgeç:** tek arama kutusu (ad, hasta no, protokol, visit_id,
işlem, bölüm, özet, kayıt no), tarih aralığı, **Yenile**. Panel ayrıca 15
saniyede bir sessizce kendini yeniler (ses çalarken yenilemez).

**COMED iş listesi tablosu** — Hasta (ad, doğum tarihi), Hasta no, Protokol,
İşlem/bölüm, Doktor, Durum. Durum rozetleri: *Kayıt bekleniyor · N rapor hazır
· Aktarılıyor · Kontrol bekliyor · COMED tamam*. Satıra tıklayınca o hastanın
kayıtları süzülür. **Bu liste yalnızca eklentiden gelir** (doktor COMED iş
listesini açınca eklenti eşitler).

**Görüşme kayıtları listesi** — No, Hasta bilgileri, Tarih/Saat, Özet, Ses
var/yok, COMED durumu, **Raporlar** düğmesi.

**Kayıt detayı (Raporlar'a basınca):**

- Bilgi şeridi: kayıt no, tarih, token, maliyet, analiz süresi
- **Ses oynatıcı** (görüşmenin kaydı, ileri/geri sarılabilir)
- **COMED eylem çubuğu:**

  | Durum | Düğme |
  |---|---|
  | Hiç aktarılmadı / başarısız | **COMED'e aktar ve kartı aç** |
  | Aktarım bitti (kontrol bekliyor) / tamamlandı | **Tekrar aktar** |
  | 75 sn'den uzun ilerlemedi (takıldı) | **Yeniden aktar** + uyarı |
  | Aktarım sürüyor | kilitli + **Vazgeç** |
  | Hasta bağlı değil | pasif + "Hasta seçilmedi" uyarısı |

  Yanında **COMED'de aç** bağlantısı.
- **Sekmeler:** AI epikriz · **COMED taslağı** · Hasta özeti · Yönetim raporu
  · Görüşme metni
- **COMED taslağı sekmesi:** eksik zorunlu alanlar, form alanları, ICD
  önerileri, hizmet istemleri, ilaç istemleri; ve **aktarım debug paneli**
  (eklentinin doldurduğu / bulamadığı alanlar, "POST İLE GİDEN: Yok").
- **PDF indir** (epikriz, hasta, yönetim).

**Alt şerit:** COMED hastası sayısı, rapor sayısı, toplam token/maliyet, model.

### Ekranda neler YOK

- Analiz başlatma, ses kaydı veya yükleme **yok** (bunlar mobil uygulamada).
- Rapor / taslak / transkript **düzenleme yok** (salt okunur; düzeltme COMED'de yapılır).
- Kayıt silme yok.
- İş listesini panelden eşitleme yok (yalnız eklenti).
- Aktarım geçmişi yok (yalnız son aktarım görünür).
- Sayfalama yok (en fazla 200 kayıt).

### Doktor neyi görür

Yalnızca kendisine ait olanı: kendi iş listesi (`synced_by = doktor`), kendi
oluşturduğu veya kendisine atanmış kayıtlar. Başka doktorun hastası için
aktarım istenirse 403: *"Hasta bu doktorun COMED iş listesinde değil"*.

---

## 11. Admin paneli

**Adres:** https://doktor-hasta-gorusmesi.onrender.com/admin
**Giriş:** `/admin/login` — `ADMIN_USER` / `ADMIN_PASS` (varsayılan
`admin`/`admin`; Render'da değiştirilmeli). Çerez 12 saat.

### VAR

- Özet: toplam kayıt, toplam token, toplam maliyet, model
- **Tüm kayıtlar** (tüm doktorlar + web'den gelenler), en fazla 200, arama
  (özet / no)
- Her satırda: COMED durum rozeti, **Dinle** (ses), **Raporlar** (doktor
  panelindeki 5 sekmenin aynısı, debug paneli dahil), **PDF**, **Sil**
  (onaylı, kalıcı)
- Debug uçları (arayüzde linki yok, adres çubuğuna yazılır):
  `/admin/comed-view` (COMED iz kayıtları), `/admin/comed/request-log`,
  `/admin/kayit/{id}` (ham JSON)

### YOK

- Kullanıcı yönetimi (doktor/hasta ekleme, şifre değiştirme) — hesaplar
  yalnızca Render ortam değişkeni `DOCTOR_ACCOUNTS_JSON` ile yönetilir
- İş listesi görünümü, aktarım listesi/iptali
- Doktora / tarihe göre süzme, sayfalama
- Rapor düzenleme, dışa aktarma (PDF dışında), ayar ekranı
- Kayıt listesinde sahip/doktor/hasta adı sütunu

---

## 12. Chrome eklentisi

> Kod: `comed_bridge_extension/` · Mağaza paketi: `store_assets/chrome_magaza_paketi/` (birebir aynı)

### Dosyalar

| Dosya | Görevi |
|---|---|
| `manifest.json` | MV3, ad "Klinot", sürüm 3.0.0; izinler `storage`, `tabs`; host: `goztepetest.comed…`, `goztepetestapi.comed…`, `doktor-hasta-gorusmesi.onrender.com` |
| `background.js` | Service worker. COMED sekmesini bulur/açar/öne getirir; COMED girişinden sonra hedef karta geri götürür; **Klinot API'sine Bearer token ile istek atan tek yer** (`klinotFetch`); 401 gelirse token'ı siler |
| `doctor_bridge.js` | Yalnız Klinot doktor panelinde çalışır. Paneldeki `window.postMessage`'ı eklentiye (`chrome.runtime.sendMessage`) iletir, cevabı geri yollar |
| `content.js` (~3450 satır) | COMED sayfalarında çalışır: iş listesi eşitleme, hasta kimliği okuma, aktarım sorgulama, **form doldurma**, istemler, taslak geri alma, işlem günlüğü balonu |
| `page_trace.js` | COMED sayfasının kendi JS ortamında (`world: MAIN`) çalışır; COMED API trafiğini izler (debug), "Sayfadan ayrıl?" uyarısını gerektiğinde bastırır |
| `popup.html/js/css` | Eklenti penceresi: giriş, hız ayarı, iz kaydı düğmesi, taslağı temizle |

İçerik betikleri yalnız şu adreslerde çalışır:
`doctor_bridge.js` → `https://doktor-hasta-gorusmesi.onrender.com/*` ·
`content.js` + `page_trace.js` → `https://goztepetest.comed.mlpcare.com/tr-tr/medical/*`.
COMED adresleri koda **test ortamı (goztepetest)** olarak gömülüdür; canlı
COMED'e geçişte manifest + `background.js`, `content.js`, `page_trace.js`,
`popup.js` güncellenmeli ve mağazaya yeni sürüm gönderilmelidir.

### Eklenti penceresi (popup)

- Sürüm rozeti (manifest'ten).
- **Giriş:** Klinot doktor kullanıcı adı + şifre → `POST /api/v1/mobile/auth/login`
  (`client_type: "extension"`). Doktor olmayan rol reddedilir. Sunucu adresi
  kutusu varsayılan olarak Render adresidir.
- `chrome.storage.local`'a yazılanlar: `apiBase`, `username`, `displayName`,
  `token`, `fillSpeed`, `traceEnabled`. **Şifre saklanmaz.**
- **Form doldurma hızı:** 0.5× · 0.75× · **1×** · 1.5× · 2.5×; aktarım
  sürerken bile anında etkiler (bekleme süreleri ölçeklenir, zaman aşımları
  ölçeklenmez).
- **İz kaydı** (COMED API trafiği): varsayılan **açık**.
- **Bu karttaki Klinot taslağını temizle:** son aktarımın eklediği ICD,
  Özgeçmiş, Soygeçmiş kayıtlarını siler, Sistem Sorgulama'yı önceki haline
  döndürür, kartı yeniler. **İstemleri (hizmet/ilaç/tetkik) geri almaz.**
- "Başka hesapla bağlan" / "Vazgeç". Ayrı bir çıkış düğmesi yok.

### Eklenti neleri sürekli yapar (COMED açıkken)

`content.js` her **5 saniyede** bir sayfayı kontrol eder:

| Sayfa | Ne yapar | Sıklık |
|---|---|---|
| COMED iş listesi | Tarih aralığını "3 Ay"a genişletir, satırları okur (ad, hasta no, visit_id, bölüm, doktor, doğum tarihi) → `POST /comed/worklist/sync` | açılışta + 60 sn'de bir |
| COMED iş listesi | Kimliği eksik hastaları sunucudan alır (`/worklist/missing-identity`), her birinin kartını **görünmez bir iframe**'de açıp T.C. + doğum tarihini okur, gönderir (hasta başına en çok 3 deneme) | sırayla |
| COMED iş listesi | Bekleyen aktarımı olan hastanın satırındaki **"Göreve Git"**e basar (kartı açar) | iş varsa |
| Hasta kartı | Kart üst bilgisinden + "Hasta Bilgileri" panelinden kimliği okuyup eşitler | değişince + 15 sn'de bir |
| Hasta kartı | `GET /comed/bridge/transfers?visit_id=…` → bu karta ait bekleyen iş varsa **doldurmaya başlar** | 5 sn'de bir |

- Kart ile iş eşleştirmesi **yalnızca URL'deki `visit_id`** ile yapılır.
- T.C. ve doğum tarihi tarayıcıdan sunucuya HTTPS ile **ham** gider; sunucu
  HMAC özetini alıp ham değeri **kaydetmeden atar**.

### İz kaydı (page_trace.js) — neye dikkat

- Yalnız `goztepetestapi.comed.mlpcare.com` isteklerini yakalar; başlıklar
  (header) hiç alınmaz; `authorization|cookie|password|secret|token|session`
  adlı alanlar `[REDACTED]` yapılır.
- Ama istek/yanıt **gövdeleri** (hasta adı, klinik veri vb.) sunucuya gider ve
  `comed_trace_events`'e yazılır (kullanıcı başına son 2000). Bu bir debug
  özelliğidir ve **varsayılan açıktır**; canlıya geçişte kapatılması veya
  sınırlanması önerilir.

### İşlem günlüğü balonu

COMED sayfasının sağ kenarında "K" yuvarlağı. Üzerine gelince/tıklayınca
"İşlem günlüğü" açılır: hasta adı · hasta no · protokol, adım adım ne
doldurulduğu, renk (mavi: çalışıyor, yeşil: tamam, kırmızı: kontrol gerekli).
Son mesaj: *"Aktarım bitti · Genel doktor kontrolü gerekli · N sn · 1× hız"*.
Balon dikey olarak sürüklenebilir.

### Kırılganlık

Eklenti COMED alanlarını **görünen Türkçe metinle ve CSS sınıflarıyla**
bulur: kart başlıkları ("Yakınması", "Özgeçmiş", "Düşme Riski", "Tanılar
(ICD - 10)" …), placeholder'lar ("Şikayeti", "Öykü", "Meslek" …), düğmeler
("Ekle", "Görüldü", "Özellik Yok", "Göreve Git" …), `data-test`
öznitelikleri ve iş listesinde sütun sırası. COMED arayüzü değişirse ilgili
alan **sessizce** doldurulamaz (debug panelinde "bulunamadı" görünür).
Tetkik istemleri test doktorunun **favori paket adlarına** (`STUDY_PACKAGES`)
bağlıdır.

---

## 13. "COMED'e aktar" adım adım

### A. Doktor panelinde düğmeye basılır

1. Doktor `/doctor`'da kaydı açar, **"COMED'e aktar ve kartı aç"** (veya
   **"Tekrar aktar"**) der. Kayıtta hasta bağlı değilse panel uyarır.
2. Panel → `POST /doctor/api/comed/transfers {record_id, patient}`.
3. Sunucu (`main.py:828-864`):
   - kayıt bu doktorun mu? değilse 404
   - hastanın `visit_id`'si bu doktorun **COMED iş listesinde** mi? değilse 403
   - `comed_integration.build_transfer_bundle` ile **aktarım paketi** üretir:
     taslağı normalize eder, düşme riskini transkriptten düzeltir, COMED
     seçenek adlarına çevirir; `auto_sign: false`,
     `doctor_review_required: true`, `execution_mode: "extension_form_fill"`;
     bölümler: muayene formu, özgeçmiş, tanılar, hizmet istemleri, ilaç istemleri
   - `comed_transfers` tablosuna **`queued`** olarak yazar, `id` döner.

### B. COMED kartı açılır

4. Panel, sayfadaki `doctor_bridge.js`'e `postMessage`
   (`klinot-doctor-comed-open-v1`, kart adresi) gönderir; 7 sn cevap bekler.
5. `doctor_bridge.js` → `background.js`: `{type: "klinot-open-comed", url}`.
6. `background.js` açık COMED sekmesi arar (aynı pencere öncelikli; tam aynı
   kart > başka COMED sayfası > giriş sayfası):
   - **Varsa** o sekmeyi öne getirir ve karta yönlendirir (COMED'in
     "kaydedilmemiş değişiklik" uyarısını bir kerelik bastırarak).
   - **Yoksa** yeni sekmede kartı açar.
   - **COMED oturumu kapalıysa** sekme giriş sayfasında kalır; doktor
     **kendisi** giriş yapar; giriş bitince eklenti otomatik olarak hedef
     karta döner (30 dk içinde).
7. Eklenti 7 sn'de cevap vermezse panel kartı `window.open` ile açar; aktarım
   iptal edilmez, kuyrukta bekler.

### C. Eklenti işi alır

8. Kart sayfasındaki `content.js` 5 sn'de bir
   `GET /api/v1/mobile/comed/bridge/transfers?visit_id=<URL'deki visit_id>`
   sorar. Sunucu yalnız **bu doktorun** `queued`/`filling` aktarımlarını, son
   1 saat içindekileri, en yenisi başta verir.
9. Eklenti `POST …/status {status: "filling"}` bildirir.
10. Formun hazır olmasını bekler (Yakınması, Sistem Sorgusu, Fizik Muayene
    kartları; en çok 45 sn). Geri alma için mevcut ICD / Özgeçmiş /
    Soygeçmiş durumunun fotoğrafını çeker.

### D. Form doldurma sırası

| # | COMED bölümü | Ne yapılır | Kaynak alan |
|---|---|---|---|
| 1 | **Sistem Sorgulama** dokümanı | Açar, 9 grubu işaretler (söylenmeyen gruplar "Özellik Yok" / "Komplikasyon Yok"), **dokümanın kendi Kaydet'ine basar**. Kaydedilemezse aktarım `failed` | `review_of_system` |
| 2 | Yakınması | Şikayeti, Öykü, şikâyet başlangıcı (sayı + saat/gün/hafta/ay/yıl) | `patient_complaint`, `patient_story`, `complaint_start_date` |
| 3 | Sistem Sorgusu metni | Serbest metin | `review_of_system_simple` |
| 4 | Fizik Muayene | Muayene notu, Kilo, Boy, Ateş, Nabız, KB-S, KB-D, SPO2 | `exam_simple_textarea`, `vitals` |
| 5 | İzlem ve Plan → Tedavi Notu | Not + "Verilen ilaçlar: …" + "Kontrol notu: …" (üzerine yazar) | `treatment_note_v2`, `requested_drugs` |
| 6 | **Özgeçmiş** | Alışkanlıklar (Sigara/Alkol/Madde + açıklama + ➕); Kronik hastalık, İlaç, Alerji, Ameliyat, Özel durum, Aşı, Cihaz, Engellilik, Kan transfüzyonu, Terapi — her biri otomatik tamamlamadan seçilip **eklenir**; Medeni hal, Meslek, Eğitim; sonunda **"Görüldü"** | `profile.*` |
| 6b | Öykü'ye ek | COMED listesinde bulunamayan özgeçmiş öğeleri Öykü'nün sonuna "Özgeçmiş (HBYS listesinde yok): …" diye yazılır (bir kez) | |
| 7 | **Soygeçmiş** | Akrabalık satırı × hastalık hücresi tıklanır, açıklama yazılır; yoksa "Özellik Yok"; "Görüldü" | `profile.family_history` |
| 8 | Psikolojik Durum | Durum toggle'ları + açıklama | `psychological_status` |
| 9 | **Düşme Riski** | Zorunlu alan: söylenmediyse **"Yok"**; varsa "Var" + 8 soru (yaş 65 üstü/altı, düşme hikâyesi, ilaç, bağımlılık, yürüyüş/denge, görme, oryante, genel sağlık) | `fall_risk` |
| 10 | Ağrı | Yok/Var, NRS skoru (kaydırıcı), bölge, açıklama, nitelik (Bastırıcı vb.), ritim, başlangıç | `pain` |
| 11 | **Tanılar (ICD-10)** | En çok 3 tanı: kod yazılır, `KOD \|` ile başlayan seçilir; Ön/Kesin/Ayırıcı tanı, taraf, birincil, açıklama → **Ekle** | `diagnoses` |
| 12 | İzlem ve Plan seçenekleri | Tedavi planı, "Ameliyat Planlanacak mı?" Evet/Hayır, Kontrol önerisi anahtarı | `treatment_plan_label`, `is_surgery_will_planned` |
| 13 | **Hizmet istemleri** (`?app-action=action-order-procedure`) | Hizmet aranır (yoksa "Genel" sekmesi), satır seçilir, uygulayan doktor = isteyen doktor, **Ekle** | `requested_services` (screen ≠ tetkik) |
| 14 | **İlaç istemleri** (`action-order-drug`) | En çok 10 ilaç: marka adı aranır, doz/form puanlamasıyla en uygun seçilir (eşik altıysa doktora bırakılır), "Günlük N Kez", endikasyon notu, **Ekle** | `requested_drugs` |
| 15 | **Tetkik istemleri** (`action-order-study`) | Doktorun favori paketleri içinde istenen tetkikler işaretlenir, radyoloji notu "Acil bir durum yoktur", **Ekle**; klinik seçim isteyen satırlar doktora bırakılır | `requested_services` (screen = tetkik) |
| 16 | Son | Ağrı toggle'ları tekrar doğrulanır, tanı listesi "Protokol" görünümüne alınır | |

**Eşleştirme kuralları:**
- Otomatik tamamlama: tam eşleşme > baştan eşleşme > kelime başında
  eşleşme. **Kelime ortası eşleşme asla seçilmez** ("Penisilin" →
  "Benzilpenisilin" seçilmez; "Aspirin" sunucuda "Asetilsalisilik asit"e çevrilir).
- Zaten ekli olan öğe (özgeçmiş, ICD, aktif toggle, mevcut istem) tekrar
  eklenmez → "Tekrar aktar" çoğu alanda güvenlidir. Metin alanlarının
  **üzerine yazılır**. İlaç istemlerinde mükerrer kontrolü **yoktur**.
- Bulunamayan / emin olunamayan her şey atlanır ve debug'a "bulunamadı"
  olarak yazılır; uydurma seçim yapılmaz.

### E. Bitiş ve durumlar

17. Başarılıysa → `POST …/status {status: "ready_for_review", debug: {doldurulan alan sayısı, alan alan sonuç, bulunamayanlar, auto_sign: false}}`.
    Hata olursa → `failed` + hata mesajı (ör. kart 45 sn'de hazır olmadı,
    Sistem Sorgulama kaydedilemedi, hiç alan doldurulamadı).
18. Doktor paneli 3 sn'de bir durumu sorar; bitince bildirim gösterir ve
    düğme "Tekrar aktar" olur. Debug paneli hangi alanın dolduğunu gösterir.
19. Doktor COMED'de kontrol eder, düzeltir ve **ana formun "Kaydet" / "Kaydet
    ve İmzala"sına kendisi basar**. Eklenti bu tıklamayı görür, ekranda
    "Kayıt başarılı" çıkarsa aktarımı **`completed`** yapar.

```
queued ──► filling ──► ready_for_review ──► completed
   │           │                 (doktor kaydedince)
   │           └──► failed
   └── 75 sn ilerlemezse panelde "takıldı" → "Yeniden aktar"
       1 saatten eski bekleyenler eklentiye artık verilmez
```

### ⚠ Önemli ayrım: ne "taslak", ne "kayıt"?

- **Ana muayene formu** (şikâyet, öykü, muayene, vital, plan, düşme riski,
  ağrı …) eklenti tarafından yalnızca **ekranda doldurulur**; doktor
  kaydetmezse kaybolur. Ana formun Kaydet/İmzala düğmesine eklenti
  **basmaz**.
- Ancak COMED'in bazı bölümleri kendi **"Ekle" / "Kaydet"** düğmesiyle
  **anında kayıt oluşturur** ve eklenti bunlara basar: **Sistem Sorgulama
  dokümanı, ICD tanıları, Özgeçmiş/Soygeçmiş öğeleri, hizmet / ilaç / tetkik
  istemleri.** Bunlar doktor ana formu kaydetmese de COMED'de durur.
  ICD/Özgeçmiş/Soygeçmiş/Sistem Sorgulama eklentideki **"taslağı temizle"**
  ile geri alınabilir; **istemler geri alınamaz**, doktor COMED'den siler.

---

## 14. Chrome Web Store yayını

| Bilgi | Değer |
|---|---|
| Ad | **Klinot** |
| Eklenti kimliği | `dcpmeafiggekpdjhebknjpdgkjgdlnjo` |
| Yayıncı hesabı | Developer Dashboard'daki şirket hesabı |
| Yayındaki sürüm | **3.0.0** (2.39.0'ın yerine geçti) |
| Görünürlük | **Gizli** — mağazada aranınca çıkmaz; yalnız izin verilen / linki bilen hesaplar kurabilir |
| Ücret | Eklenti ücretsiz |
| Gizlilik politikası | https://doktor-hasta-gorusmesi.onrender.com/gizlilik |
| Mağaza metinleri | `store_assets/MAGAZA_METINLERI.md` |
| Mağaza görselleri | `store_assets/` (ikon 128, ekran görüntüsü 1280×800, promo 440×280) |
| Yüklenen paket | `store_assets/klinot-magaza-v3.0.0.zip` |
| Panel | https://chrome.google.com/webstore/devconsole |

### Kendi geliştirici hesabını açmak istersen

Chrome Web Store'a eklenti yayınlamak için bir Google hesabıyla **geliştirici
kaydı** gerekir; Google **tek seferlik 5 ABD doları** kayıt ücreti alır
(kart ile, devconsole'a ilk girişte istenir). Bu ücret bir kez ödenir, o
hesaptan istenen sayıda eklenti yayınlanabilir. Mevcut "Klinot" eklentisi
şirket hesabındadır; kendi hesabından yüklersen **yeni bir eklenti kimliği**
oluşur (aynı eklentinin güncellemesi olmaz). Mevcut eklentiyi güncellemek için
yayıncı hesabına erişim (veya hesaba "grup yayıncısı" olarak eklenmek) gerekir.

### Mağaza paketinin kuralları

- Mağaza paketi ile günlük kullanılan eklenti **birebir aynıdır**
  (`comed_bridge_extension/` = `store_assets/chrome_magaza_paketi/`;
  `tests/test_store_release.py` bayt bayt karşılaştırır).
- Manifest'te `localhost` izni yoktur; yalnızca COMED test alanları ve
  Klinot sunucusu.
- Mağaza metinlerinde ve gizlilik sayfasında **"COMED" adı geçmez**
  ("hastane bilgi sistemi" denir).
- İzinler: `storage`, `tabs` + 3 host. İzin listesi değişirse kullanıcılar
  güncellemede yeniden onay görür ve eklenti onaylanana kadar kapanır —
  **izin eklemekten kaçının.**

### Güncelleme nasıl atılır

1. Kodu değiştir, `python scripts/bump_version.py 3.0.1` ile sürümü yükselt
   (mağaza aynı numarayı kabul etmez).
2. `comed_bridge_extension/` içeriğini `store_assets/chrome_magaza_paketi/`'ne
   kopyala ve **manifest.json kök dizinde olacak şekilde** zip'le
   (`store_assets/klinot-magaza-vX.Y.Z.zip`, aynı zip `build_artifacts/`'a).
3. devconsole → Klinot → **Paket** → **Yeni paket yükle** → zip'i seç.
4. **İncelemeye gönder**. İnceleme genelde 1–3 gün; sonuç mail ile gelir.
5. Onaydan sonra kuran herkes birkaç saat içinde otomatik güncellenir.
6. İnceleme sürerken yeni paket yüklenemez; "Önceki sürüme döndür" yalnız acil
   geri alma içindir.

### Günlük geliştirme kurulumu

Geliştirici bilgisayarında eklenti, `chrome://extensions` → Geliştirici modu →
**Paketlenmemiş öğe yükle** → `comed_bridge_extension` klasörü ile kurulur;
kod değişince ↻ ile yenilenir. **Mağaza sürümü ile yerel sürüm aynı anda
açık olmamalı** (ikisi de aynı işi alıp formu iki kez doldurmaya çalışır) —
birini kapat.

---

## 15. Sürümleme, dallar, paketler

- **Sürüm: v3.0.0.** Sürüm 9 ayrı dosyada yazılıdır; **elle değiştirme**:

  ```bash
  python scripts/bump_version.py 3.0.1   # hepsini yükseltir
  python scripts/bump_version.py --check # tutarlılık kontrolü
  ```

  (config.py, manifest.json, render.yaml, pubspec.yaml, api_client.dart,
  login_screen.dart, widget_test.dart …). `tests/test_version_consistency.py`
  `build_artifacts/` dosya adlarını da kontrol eder.
- **Dallar:**
  - `main` — geliştirme; Render buradan deploy eder.
  - `mvp` — gösterim/kararlı sürüm. Şu an `main` ile aynı (`2ce0e1f`, v3.0.0).
    **İstenmedikçe `mvp`'ye dokunulmaz.**
  - `test`, `codex/*` — eski çalışma dalları.
- **Paketler (`build_artifacts/`):** yalnız güncel sürüm tutulur —
  `Klinot-v3.0.0.apk`, `klinot-comed-bridge-v3.0.0.zip`.
- Değişiklik günlüğü: `CHANGELOG.md`.

---

## 16. Çalıştırma, test, deploy

### Yerel

```bash
python -m venv venv
venv\Scripts\activate            # macOS/Linux: source venv/bin/activate
pip install -r requirements.txt
# .env oluştur: GEMINI_API_KEY, OPENAI_API_KEY, SESSION_SECRET ...
uvicorn main:app --reload
```

- `http://127.0.0.1:8000/doctor/login`, `/admin/login`, `/legacy`
- `.env` değişince sunucuyu tamamen kapatıp aç (`--reload` .env'i izlemez).

### Ortam değişkenleri (Render → Environment)

| Değişken | Not |
|---|---|
| `GEMINI_API_KEY` | gizli |
| `GEMINI_MODEL` | `gemini-2.5-flash` |
| `OPENAI_API_KEY` | gizli |
| `OPENAI_STT_MODEL` / `OPENAI_STT_FALLBACK_MODEL` | `gpt-4o-transcribe-diarize` / `gpt-transcribe` |
| `APP_VERSION` | `v3.0.0` |
| `COMED_WEB_BASE_URL`, `COMED_API_BASE_URL` | Göztepe test |
| `DOCTOR_ACCOUNTS_JSON` | gizli; doktor hesapları |
| `ADMIN_USER`, `ADMIN_PASS` | admin girişi (varsayılan admin/admin) |
| `SESSION_SECRET` | gizli; **mutlaka dolu** |
| `MOBILE_SESSION_DAYS` | 30 |
| `PATIENT_SMS_WEBHOOK_URL` | SMS sağlayıcısı (henüz yok) |
| `PATIENT_TEST_OTP_ENABLED` | `false` (true ise 000000 geçer) |
| `SEED_MANAGER_DEMO` | `true` → demo kayıtlar her açılışta yüklenir |

### Test

```bash
python -m pytest -q
```

Şu an: **319 geçti, 2 skip, 2 bilinen hata** (`test_admin_regressions`,
yerel `kayitlar.db` ile ilgili; canlıyı etkilemiyor).

### Deploy

`main`'e push → Render otomatik deploy eder (~2-3 dk). **Her deploy
veritabanını sıfırlar** (demo kayıtlar geri gelir, diğerleri gider). Doktorun
COMED iş listesi de sıfırlanır; eklenti COMED iş listesi açılınca yeniden
eşitler.

### Canlı test kuralı

Eklenti veya taslak değişikliği **canlı COMED test ortamında gerçek bir
"Tekrar aktar" ile denenmeden** yayınlanmaz.

---

## 17. Güvenlik kuralları

Bunlar tasarım gereğidir, değiştirilmemeli:

1. **Otomatik imza yok.** Pakette `auto_sign: false`,
   `doctor_review_required: true`. Eklenti **ana muayene formunun Kaydet /
   Kaydet ve İmzala düğmelerine asla basmaz** (bölümlerin kendi "Ekle"
   düğmeleri için bkz. §13 sonu).
2. **COMED'e API ile yazılmaz.** Yalnız ekrandaki form doldurulur.
3. **COMED şifresi / oturum başlıkları Klinot sunucusuna gitmez.** İz
   kayıtlarında `authorization|cookie|password|secret|token|session` anahtarları
   `[REDACTED]` yapılır ve yalnız COMED test API alanından gelen izler kabul
   edilir (`main.py:241-271, 922-948`).
4. **Ham T.C. kimlik saklanmaz**, yalnız HMAC özeti.
5. Doktor yalnız **kendi iş listesindeki** hastaya aktarım yapabilir.
6. API anahtarları yalnız sunucuda; GitHub'a `.env` konmaz (`.gitignore`).
7. KVKK: gerçek hasta verisi için kurum politikası, açık rıza ve sağlayıcı
   sözleşmeleri ayrıca değerlendirilmeli. Şu an **test COMED ortamı** kullanılıyor.

---

## 18. Bilinen eksikler / teknik borç

1. **Korumasız uçlar:** `/analyze`, `/analyze/stream`, `/transcribe`, `/pdf`,
   `/legacy` oturum istemiyor → linki bilen ücretli API kotasını harcayabilir.
   CORS / CSRF / hız sınırı yok.
2. **Kalıcı veritabanı yok** (Render ücretsiz disk). Postgres'e geçiş:
   `docs/TASIMA.md`.
3. **Hesap yönetimi yok:** doktorlar ortam değişkeninde, düz metin şifre.
4. **SMS sağlayıcısı bağlı değil** → hasta girişi canlıda çalışmaz.
5. `main.py` tek dosya; `APIRouter`'lara bölünmeli.
6. Eklenti COMED alanlarını **görünen Türkçe metinle** buluyor
   ("Şikayeti", "Özgeçmiş" …). COMED arayüz metni değişirse sessizce kırılır.
7. COMED test kataloğunda düz "Ekokardiyografi" yok; bilerek
   "Transözofageal ekokardiografi" seçiliyor (`COMED_EKO_NAME`).
8. Görüşmede geçmese de LLM bazen psikolojik durum "Sakin" yazıyor.
9. Admin panelindeki "COMED'e aktar", `requested_by="admin"` yazdığı için
   hiçbir doktorun eklentisine ulaşmaz (kod okumasından çıkarım).
10. Admin "Sil" kaydı siler ama ilgili `comed_transfers` satırları kalır.
11. Doktor panelinde hasta seçimi kayda kalıcı yazılmaz.
12. `mock_data.py`, ElevenLabs kodu, `transcript_screen.dart` ölü kod.
13. `.git` geçmişi eski APK'lar yüzünden şişkin (~500 MB).
14. Analiz sırasında telefonun bağlantısı koparsa (`/analyze/stream`) kayıt
    **kaydedilmez** (ses→metin işi ise bağlantıdan bağımsız tamamlanır).
15. Hasta, `GET /api/v1/mobile/records/{id}` ile kendi kaydının **tamamını**
    (doktor epikrizi, yönetim raporu dahil) çekebilir; yalnız analiz cevabı
    kırpılıyor.
16. OTP kodları sunucu belleğinde; yeniden başlatmada kaybolur, hız sınırı yok.
17. Bekleyen ses sınırı (20) tüm kullanıcılar için ortak.
18. Eklentinin iz kaydı (COMED API gövdeleri, hasta verisi dahil) varsayılan
    açık ve sunucuda saklanıyor.
19. APK debug anahtarıyla imzalı; Play Store için gerçek imza gerekir.
20. Eski belgeler kısmen bayat: `MOBILE_APP.md`, `build_artifacts/README.md`,
    `comed_bridge_extension/README.md` (kaldırılan POST yolunu anlatıyor),
    `docs/MIMARI.md` (v2.13.2). **Güncel referans bu belgedir.**

---

## 19. Linkler ve hesaplar özeti

| Ne | Nerede |
|---|---|
| Kaynak kod | https://github.com/Enesaydnn7/Doktor-hasta-Gorusmesi |
| Canlı sunucu | https://doktor-hasta-gorusmesi.onrender.com |
| Doktor paneli | `/doctor` (giriş `/doctor/login`) |
| Admin paneli | `/admin` (giriş `/admin/login`) |
| Eski analiz sayfası | `/legacy` |
| Gizlilik | `/gizlilik` |
| COMED (test) | https://goztepetest.comed.mlpcare.com/tr-tr/medical |
| Chrome Web Store paneli | https://chrome.google.com/webstore/devconsole |
| Eklenti kimliği | `dcpmeafiggekpdjhebknjpdgkjgdlnjo` |
| Test doktor hesabı | `Kullanici.kayadr;Kullanici.aydin1|tracer` / `1` |
| Admin (varsayılan) | `admin` / `admin` |
| Mobil APK | `build_artifacts/Klinot-v3.0.0.apk` |
| Diğer belgeler | `README.md`, `MOBILE_APP.md`, `docs/COMED_FORM_MAP.md`, `docs/TASIMA.md`, `CHANGELOG.md` |
