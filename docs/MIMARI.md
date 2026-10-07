# Klinot — Mimari Haritası (v2.13.2)

> Bu belge **koddan doğrulanarak** yazıldı, README iddialarından değil.
> Satır numaraları yazıldığı andaki dosyalara göredir.

## 1. Sistem neyden oluşuyor

| Parça | Teknoloji | Görevi |
|---|---|---|
| Backend | FastAPI + SQLite | STT, analiz, kayıt, COMED paketi |
| Mobil | Flutter (Android/iOS) | Kayıt → transkript → rapor → PDF |
| Eklenti | Chrome MV3 | COMED oturumuna form aktarımı |
| Web panel | Jinja2 + vanilla JS | `/admin`, `/doctor`, `/legacy` |

## 2. Roller ve kimlik doğrulama

Üç rol var: **admin**, **doctor**, **patient**.

| Rol | Nasıl girer | Oturum |
|---|---|---|
| admin | kullanıcı/şifre → imzalı çerez | `SESSION_HOURS` (vars. 12s) |
| doctor | kullanıcı/şifre → çerez **veya** Bearer token | 12s / `MOBILE_SESSION_DAYS` (30g) |
| patient | **TCKN + doğum tarihi + SMS kodu** → Bearer token | 30 gün |

### Hasta girişi (3 adım)

1. `POST /api/v1/mobile/auth/patient/otp/start` — TCKN doğrulanır (`auth.valid_tckn`,
   resmî kontrol basamağı dahil), doğum tarihi ISO'ya çevrilir, ikisinden
   `HMAC-SHA256(TCKN|YYYY-AA-GG)` üretilir.
2. Bu özet `comed_worklist.patient_identity_hash` ile eşleşmeli. Eşleşme yoksa
   *"Kimlik bilgileriyle eşleşen aktif COMED randevusu bulunamadı"*.
3. `POST .../otp/verify` — kod doğrulanır, Bearer token döner.

**Önemli:** Ham TCKN veritabanında saklanmaz, yalnızca HMAC özeti tutulur.

**Kimlik özeti nereden geliyor?** Chrome eklentisi, doktor COMED hasta kartını
açtığında TCKN ve doğum tarihini sayfadan okuyup `worklist/sync` ile gönderir.
Bu alanlar COMED'de yalnız "Hasta Bilgileri" açılır panelinde bulunduğu için
tarama `textContent` üzerinden yapılır (gizli düğümler dahil).

### Bağımlılık fonksiyonları (`main.py`)

`admin_auth` · `doctor_auth` · `mobile_auth` · `mobile_doctor` · `mobile_patient`
· `mobile_clinical_user` (doctor **veya** patient) · `mobile_admin`

## 3. ⚠️ Korumasız uçlar

Bunlarda **hiçbir kimlik doğrulaması yok**:

| Uç | Risk |
|---|---|
| `POST /analyze` | Linki bilen herkes Gemini kotasını harcar |
| `POST /analyze/stream` | aynı |
| `POST /transcribe` | Ses yükleyip OpenAI kotasını harcar |
| `POST /pdf` | PDF üretir |
| `GET /legacy` | Eski panel arayüzü |
| `GET /health` | Model/yapılandırma bilgisi sızdırır |

Mobil karşılıkları (`/api/v1/mobile/...`) doğru şekilde korunuyor; korumasız
olanlar yalnız web sürümleri. `main.py` içinde middleware, CORS ayarı veya
hız sınırı **yok**.

## 4. Veri akışı

```
Ses (m4a/webm, ≤48 MB)
  │  POST /api/v1/mobile/transcriptions  → job_id (202)
  │  Aynı ses tekrar gönderilirse SHA256 ile aynı işe bağlanır
  ▼
stt.py → SADECE OpenAI
  │  birincil : gpt-4o-transcribe-diarize (konuşmacı ayrımlı)
  │  yedek    : gpt-transcribe (yalnız ana model boş dönerse)
  ▼
role_classifier.py → Gemini (1 çağrı)
  │  Konuşmacı A/B → "Doktor"/"Hasta". Sözcükler DEĞİŞTİRİLMEZ.
  │  Başarısız olursa konuşma sırası/cümle sırası ile devam eder.
  ▼
llm.py → Gemini (4 PARALEL çağrı, asyncio.gather)
  │  hasta · doktor · yonetim · comed
  │  TEMPERATURE=0, top_p=0.1, top_k=1 → tekrarlanabilir çıktı
  │  Sonra _reconcile_comed_with_epicrisis(): deterministik düzeltme
  ▼
db.py → SQLite (kayitlar tablosu, ses BLOB olarak içeride)
  ▼
comed_integration.py → transfer paketi → Chrome eklentisi → COMED formu
```

**Gemini toplam 5 kez çağrılır:** 1 rol tespiti + 4 rapor.

## 5. Veritabanı (SQLite, `db.py`)

| Tablo | İşi |
|---|---|
| `kayitlar` | Analiz kaydı: transkript, 3 rapor, COMED taslağı, ses BLOB, usage |
| `bekleyen_sesler` | STT ile analiz arasındaki geçici ses |
| `transcription_jobs` | Asenkron STT işi (queued→processing→completed/failed) |
| `comed_worklist` | Doktor başına COMED iş listesi + `patient_identity_hash` |
| `comed_transfers` | Aktarım paketi ve durumu |
| `comed_trace_events` | Temizlenmiş COMED API izleri (hata ayıklama) |

`comed_worklist` birincil anahtarı `(visit_id, synced_by)` — her doktorun kendi
listesi ayrı.

Aktarım durumları: `queued → filling → ready_for_review → completed | failed`

## 6. Chrome eklentisi

| Dosya | İşi |
|---|---|
| `content.js` (~1700 satır) | Form doldurma, iş listesi eşitleme, işlem günlüğü balonu |
| `page_trace.js` | MAIN world'de fetch/XHR yakalama, COMED oturum başlıkları |
| `background.js` | Klinot API köprüsü (Bearer token) |
| `doctor_bridge.js` | Doktor panelinden sekme yeniden kullanımı |
| `popup.*` | Klinot hesabı bağlama |

**Güvenlik notu:** COMED parolası ve oturum başlıkları Klinot sunucusuna
**gönderilmez**; yalnız sayfanın kapalı belleğinde kullanılır.

**Kırılganlık:** Alanlar görünen Türkçe metinle bulunuyor (`"Şikayeti"`,
`"Kaydet ve İmzala"`). COMED arayüz metnini değiştirirse sessizce kırılır.

## 7. Mobil ekranlar

| Dosya | Durum |
|---|---|
| `login_screen.dart` | Doktor/hasta sekmeli giriş, OTP |
| `recorder_screen.dart` (~1000+ satır) | Kayıt, hasta seçimi, analiz |
| `reports_screen.dart` (~900+ satır) | Raporlar, PDF |
| `transcript_screen.dart` | **Erişilemez — ölü kod** |

## 8. Bilinen borçlar

1. **Korumasız uçlar** (bkz. §3) — en acil.
2. **`SESSION_SECRET` boşsa** imza anahtarı `ADMIN_USER`/`ADMIN_PASS`'ten
   türüyor; varsayılan `admin/admin` ise admin çerezi taklit edilebilir.
3. **`PATIENT_TEST_OTP_ENABLED` varsayılan `true`** — `000000` kodu geçerli.
   SMS sağlayıcısı bağlanınca **mutlaka** `false` yapılmalı.
4. **ElevenLabs ölü kodu** — `_elevenlabs_transcribe()` ve
   `_elevenlabs_segments()` (`stt.py:216`, `stt.py:255`, ~120 satır) artık
   hiç çağrılmıyor; `config.py`'de 6 kullanılmayan ayar duruyor.
5. **`mock_data.py`** hiçbir yerden import edilmiyor.
6. **`main.py` 1000+ satır** — admin/doctor/patient/mobil/COMED tek dosyada,
   `APIRouter`'a bölünmeli.
7. **Versiyon 8 yerde elle yazılı** (config.py, manifest.json, pubspec.yaml,
   api_client.dart, login_screen.dart, widget_test.dart, render.yaml, README).
8. **Render ücretsiz planda disk kalıcı değil** — yeniden başlatmada kayıtlar
   silinir. Kalıcılık için Postgres gerekir.
9. **`.git` ~521 MB** — geçmişteki eski APK'lar yüzünden. Güncel ağaç temiz
   (yalnız mvp + güncel sürüm paketi tutuluyor) ama geçmiş şişkin.

## 9. Testler

`python -m pytest` → **115 test** (+15 subtest), hepsi geçiyor.

Kapsanmayanlar: hasta OTP uçtan uca akışı, aktarım durum döngüsü
(queued→completed), byte-range ses akışı, eklenti popup'ı.
