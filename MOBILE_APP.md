# Klinot mobil MVP mimarisi

Klinot, yüz yüze doktor–hasta görüşmesinde telefonun masanın ortasında bulunduğu kayıt senaryosudur. `mobile_app/` tek Flutter kod tabanından Android ve iOS istemcileri üretir. Mevcut web paneli çalışmaya devam eder; mobil uygulama aynı FastAPI, STT, Gemini analiz ve yönetim kayıtlarını kullanır.

## Akış

1. Doktor veya yönetici mobil uygulamada oturum açar.
2. Hasta bilgilendirme onayı işaretlenir ve kayıt başlatılır.
3. Uygulama mono AAC/M4A kaydeder, ekranı açık tutar ve gerçek mikrofon seviyesini gösterir.
4. Kayıt `/api/v1/mobile/transcribe` ile mevcut Scribe/OpenAI zincirine gönderilir.
5. Doktor transkripti kontrol edip gerekiyorsa düzeltir.
6. `/api/v1/mobile/analyze/stream` üç Gemini raporunu sırayla üretir ve gerçek ilerleme olaylarını gönderir.
7. Ses, transkript, raporlar, kullanım ve istemci bilgisi mevcut veritabanına kaydedilir; web ve mobil admin tarafından görüntülenir.

## Mobil API v1

| Yöntem | Uç | Yetki | İş |
|---|---|---|---|
| `POST` | `/api/v1/mobile/auth/login` | Açık | Doktor/yönetici girişi, Bearer token |
| `GET` | `/api/v1/mobile/health` | Açık | API ve model sağlık bilgisi |
| `POST` | `/api/v1/mobile/transcribe` | Doktor/Yönetici | Multipart ses yükleme ve STT |
| `POST` | `/api/v1/mobile/analyze/stream` | Doktor/Yönetici | NDJSON gerçek ilerleme ve raporlar |
| `GET` | `/api/v1/mobile/records` | Yönetici | Kayıtlar ve toplam istatistik |
| `GET` | `/api/v1/mobile/records/{id}` | Yönetici | Rapor ve transkript ayrıntısı |
| `DELETE` | `/api/v1/mobile/records/{id}` | Yönetici | Kayıt silme |

Mobil doktor hesabı için Render Environment bölümüne `MOBILE_DOCTOR_USER` ve `MOBILE_DOCTOR_PASS` eklenir. Yönetici mevcut `ADMIN_USER` ve `ADMIN_PASS` ile hem web hem mobil panele girebilir. Canlıda ayrıca uzun ve rastgele bir `SESSION_SECRET` kullanılmalıdır.

## Veri ve dayanıklılık

`kayitlar` tablosuna `source`, `client_version` ve `metadata` alanları eklenmiştir. STT tamamlandıktan sonra analiz bekleyen sesler süreç belleği yerine `bekleyen_sesler` tablosunda tutulur; böylece iki HTTP isteği farklı çalışanlara düşse bile ses kaybolmaz. Analiz kaydı başarısız olursa bekleyen ses silinmez.

Bu sürüm mevcut MVP ile uyum için SQLite kullanır. Render'ın geçici diskli kurulumunda gerçek hasta kayıtlarının kalıcı olacağı varsayılmamalıdır. Kurumsal pilot öncesi yönetilen PostgreSQL ve şifreli nesne depolama, kurum kimlik yönetimi, denetim kaydı, saklama/silme politikaları ve anahtar yönetimi eklenmelidir.

## Dağıtım

- Android: Windows üzerinden Android Studio + Emulator ile geliştirilir; yöneticiye hızlı demo için Google Play Internal Testing veya imzalı APK kullanılabilir.
- iOS: Aynı Flutter kaynak kodu kullanılır; ancak TestFlight yüklemesi için macOS, Xcode ve Apple Developer hesabı gerekir.
- API adresi derleme sırasında `--dart-define=API_BASE_URL=...` ile değiştirilebilir.
