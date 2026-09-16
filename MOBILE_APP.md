# Klinot mobil MVP mimarisi

Klinot, yüz yüze doktor–hasta görüşmesinde telefonun masanın ortasında bulunduğu kayıt senaryosudur. `mobile_app/` tek Flutter kod tabanından Android ve iOS doktor istemcileri üretir. Mobil uygulamada yönetim ekranı bulunmaz. Bütün görüşmeler mevcut web `/admin` panelinde toplanır; ileride hazırlanacak ayrı yönetim uygulaması da aynı yönetici API'lerini kullanabilir.

## Akış

1. Doktor mobil uygulamada oturum açar ve COMED iş listesinden görüşeceği hasta/protokolü seçer.
2. Hasta bilgilendirme onayı işaretlenir ve kayıt başlatılır.
3. Uygulama mono AAC/M4A kaydeder, ekranı açık tutar ve gerçek mikrofon seviyesini gösterir.
4. Kayıt `/api/v1/mobile/transcribe` ile mevcut Scribe/OpenAI zincirine gönderilir.
5. Doktor transkripti kontrol edip gerekiyorsa düzeltir.
6. `/api/v1/mobile/analyze/stream` üç raporu ve COMED alan taslağını paralel üretir. Doktor uygulaması yapılandırılmış epikrizi ve iletişim önerilerini gösterir.
7. Doktor epikrizi PDF olarak indirebilir veya taslağı “COMED'e aktar” ile açık kurumsal COMED oturumuna gönderebilir.
8. Chrome köprüsü güvenli metin alanlarını doldurur; doktor COMED'de kontrol eder ve COMED'in kendi Kaydet/İmzala işlemini kullanır.
9. Ses, transkript, bütün raporlar, COMED taslağı, kullanım ve istemci bilgisi mevcut veritabanına kaydedilir; ayrı web `/admin` panelinde de izlenir.

## Mobil API v1

| Yöntem | Uç | Yetki | İş |
|---|---|---|---|
| `POST` | `/api/v1/mobile/auth/login` | Açık | Doktor/yönetici girişi, Bearer token |
| `GET` | `/api/v1/mobile/health` | Açık | API ve model sağlık bilgisi |
| `POST` | `/api/v1/mobile/transcribe` | Doktor/Yönetici | Multipart ses yükleme ve STT |
| `POST` | `/api/v1/mobile/analyze/stream` | Doktor/Yönetici | NDJSON gerçek ilerleme ve raporlar |
| `POST` | `/api/v1/mobile/pdf/epikriz` | Doktor/Yönetici | Doktor epikrizini PDF olarak üretme |
| `GET` | `/api/v1/mobile/comed/worklist` | Doktor/Yönetici | COMED'den eşitlenmiş iş listesini getirir |
| `POST` | `/api/v1/mobile/comed/worklist/sync` | Doktor/Yönetici | Chrome köprüsünün iş listesini eşitlemesi |
| `POST` | `/api/v1/mobile/comed/transfers` | Doktor/Yönetici | Kayıt için doktor kontrollü aktarım oluşturur |
| `GET` | `/api/v1/mobile/comed/transfers/{id}` | Doktor/Yönetici | Aktarım durumunu getirir |
| `GET` | `/api/v1/mobile/comed/bridge/transfers` | Doktor/Yönetici | Köprü için bekleyen aktarımı getirir |
| `POST` | `/api/v1/mobile/comed/bridge/transfers/{id}/status` | Doktor/Yönetici | Köprünün aktarım durumunu güncellemesi |
| `GET` | `/api/v1/mobile/records` | Yönetici | Kayıtlar ve toplam istatistik |
| `GET` | `/api/v1/mobile/records/{id}` | Yönetici | Rapor ve transkript ayrıntısı |
| `DELETE` | `/api/v1/mobile/records/{id}` | Yönetici | Kayıt silme |

Mobil doktor hesabı için Render Environment bölümüne `MOBILE_DOCTOR_USER` ve `MOBILE_DOCTOR_PASS` eklenir. Yönetici mevcut `ADMIN_USER` ve `ADMIN_PASS` ile web `/admin` paneline girer. Mobil yönetici API'leri gelecekteki ayrı yönetim uygulaması için korunur; Klinot doktor uygulaması bu uçları çağırmaz. Canlıda ayrıca uzun ve rastgele bir `SESSION_SECRET` kullanılmalıdır.

## Veri ve dayanıklılık

`kayitlar` tablosunda `source`, `client_version`, `metadata` ve `comed` alanları bulunur. `comed_worklist` hastaları/protokolleri, `comed_transfers` ise aktarım kuyruğu ve denetim durumunu tutar. STT tamamlandıktan sonra analiz bekleyen sesler süreç belleği yerine `bekleyen_sesler` tablosunda tutulur; böylece iki HTTP isteği farklı çalışanlara düşse bile ses kaybolmaz. Analiz kaydı başarısız olursa bekleyen ses silinmez.

## COMED köprüsü

`comed_bridge_extension/` klasörü Chrome geliştirici modunda “Paketlenmemiş öğe yükle” ile kurulur. Eklentide Klinot API adresi ve doktor Bearer oturumu tanımlanır. Kurumsal Wi-Fi üzerinde açık Göztepe COMED test oturumu iş listesini eşitler, ilgili hasta ekranındaki taslak alanları doldurur ve durumu “Doktor kontrolüne hazır” olarak işaretler. COMED oturum anahtarı telefona veya Klinot sunucusuna kopyalanmaz; otomatik imza yapılmaz.

Bu sürüm mevcut MVP ile uyum için SQLite kullanır. Render'ın geçici diskli kurulumunda gerçek hasta kayıtlarının kalıcı olacağı varsayılmamalıdır. Kurumsal pilot öncesi yönetilen PostgreSQL ve şifreli nesne depolama, kurum kimlik yönetimi, denetim kaydı, saklama/silme politikaları ve anahtar yönetimi eklenmelidir.

## Dağıtım

- Android: Windows üzerinden Android Studio + Emulator ile geliştirilir; hızlı demo için Google Play Internal Testing veya imzalı APK kullanılabilir.
- iOS: Aynı Flutter kaynak kodu kullanılır; ancak TestFlight yüklemesi için macOS, Xcode ve Apple Developer hesabı gerekir.
- API adresi derleme sırasında `--dart-define=API_BASE_URL=...` ile değiştirilebilir.
