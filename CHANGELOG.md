# Sürüm Geçmişi

## v1.7.1 — 27 Ağustos 2026

- Yönetici sunumu için kullanılan gastrit demo sesinin orijinal WebM kopyası private repoda korumaya alındı.
- Dosyanın kayıt bilgileri ve SHA-256 doğrulama özeti `demo_records/README.md` içine eklendi.
- Panel sürüm rozeti `v1.7.1` olarak güncellendi.

## v1.7.0 — 27 Ağustos 2026

- `v1.6.0` çalışan MVP hâli `mvp-v1.6.0` etiketiyle ayrıca korumaya alındı.
- Türkçe ve iki konuşmacılı görüşmeler için ElevenLabs `scribe_v2` birincil STT modeli yapıldı.
- Diarization, sabit Türkçe dil kodu ve tıbbi anahtar terimlerle kelime doğruluğu güçlendirildi.
- Scribe hatası veya boş yanıtında mevcut OpenAI diarization + yüksek doğruluk STT zinciri otomatik yedek olarak korundu.
- Sağ üst köşeye küçük `v1.7.0` sürüm rozeti; sağlık yanıtına aktif STT sağlayıcısı ve yedek bilgisi eklendi.
- Scribe istek parametreleri, sözcük/konuşmacı koruması, maliyet ve OpenAI yedeği otomatik testlerle doğrulandı.
- Üç analiz promptu değiştirilmedi.

## v1.6.0 — 27 Ağustos 2026

- `v1.5.2` çalışan hâli ayrıca `mvp-v1.5.2` etiketiyle korumaya alındı.
- Panelde kullanılacak mikrofonu seçme ve aktif mikrofonun adını görme özelliği eklendi.
- API çağrısı yapmadan çalışan canlı mikrofon testi ve ses seviye çubuğu eklendi.
- Kulaklık çıkarılınca aygıt listesi yenileniyor; kaybolan giriş yerine varsayılan/laptop mikrofonuna geçiliyor.
- Sessiz veya çok kısa kayıtlar OpenAI API'ye gönderilmeden kullanıcı uyarılıyor.
- Mikrofon izni, aygıt bulunamaması ve başka uygulamanın mikrofonu kullanması için ayrı hata mesajları eklendi.

## v1.5.2 — 27 Ağustos 2026

- Diarization yanıtında konuşmacı segmentleri boşken mevcut birleşik metnin atılması düzeltildi.
- Hem segmentler hem birleşik metin boşsa yalnızca o kayıt için OpenAI `gpt-transcribe` API yedeği eklendi.
- Yedek STT kullanımı ve maliyeti kullanıcı/admin izleme toplamlarında ayrı gösteriliyor.
- Hasta verisini loglamadan segment sayısı, metin uzunluğu ve yedek kullanımını kaydeden tanı bilgileri eklendi.
- Birleşik metin ve boş ana yanıt senaryoları otomatik testlerle doğrulandı; analiz promptları değiştirilmedi.

## v1.5.1 — 27 Ağustos 2026

- Tek kişinin doktor ve hasta repliklerini aynı sesle okuduğu demo kayıtları desteklendi.
- OpenAI tek konuşmacı döndürdüğünde metin sözcükleri numaralandırılıyor; Gemini yalnızca Doktor/Hasta sözcük aralıklarını seçiyor.
- Aynı cümle içinde rol değişimi olsa bile hiçbir sözcük eklenmeden, silinmeden veya düzeltilmeden yeni satıra ayrılıyor.
- Tek sesli rol tespiti başarısız olduğunda `Konuşmacı:` yerine kontrol edilebilir Doktor/Hasta fallback'i kullanılıyor.
- Tek sesli replik ayrımı, tam sözcük koruması ve fallback için otomatik testler eklendi.

## v1.5.0 — 27 Ağustos 2026

- Konuşma sırasına bağlı doktor/hasta etiketlemesi yerine metnin anlamını kullanan Gemini rol sınıflandırıcısı eklendi.
- Hasta ilk konuşsa bile model yalnızca A/B → Doktor/Hasta eşlemesi yapıyor; OpenAI transkript sözcükleri değiştirilmiyor.
- Rol sınıflandırması başarısızsa transkript korunuyor ve arayüz kullanıcıya etiketleri kontrol etmesini söylüyor.
- Rol tespitinin Gemini tokenları ve maliyeti kullanıcı ve admin izleme toplamlarına eklendi.
- Rol eşlemesi, hasta-ilk senaryosu ve servis arızası fallback'i için otomatik testler eklendi.

## v1.4.0 — 27 Ağustos 2026

- Gemini'nin gerçek ses yerine ilgisiz konuşmalar üretmesine karşı ses dökümü OpenAI Transcription API'ye geçirildi.
- Yerel ASR modeli indirmeden `gpt-4o-transcribe-diarize` ile Türkçe konuşmacı ayrımı eklendi.
- Tarayıcıdaki WebM kayıtları dönüştürülmeden doğrudan API'ye gönderiliyor.
- Üretici prompt kaldırıldı; API segmentlerindeki sözler değiştirilmeden `Doktor:` / `Hasta:` etiketleniyor.
- OpenAI SDK çağrısı, konuşmacı biçimlendirmesi, boş yanıt ve API anahtarı için otomatik testler eklendi.

## v1.3.0 — 27 Ağustos 2026

- Tarayıcıdaki WebM ses kayıtları Gemini'ye gönderilmeden önce kesin olarak MP3'e dönüştürülüyor.
- Render Python ortamına taşınabilir FFmpeg paketi eklendi.
- Dönüşüm başarısızsa desteklenmeyen sesi Gemini'ye gönderme davranışı kaldırıldı.
- Sessiz veya anlaşılmayan kayıtlarda modelin konuşma uydurmaması için güvenlik talimatı eklendi.
- Kullanımdan kaldırılan `google-generativeai` yerine güncel `google-genai` SDK'sına geçildi.

## v1.2.0 — 27 Ağustos 2026

- Hasta, doktor ve yönetim analizleri aynı anda değil sırayla çalıştırılıyor.
- Her analiz çağrısının arasına 1 saniye bekleme eklendi.
- Analiz isteği zaman aşımı 45 saniyeye, ses dökümü zaman aşımı 60 saniyeye indirildi.
- Sıralı çalışma için otomatik test eklendi.

## v1.1.0 — 27 Ağustos 2026

- Geçici Gemini kota, yoğunluk ve bağlantı hataları için kontrollü yeniden deneme eklendi.
- Bozuk JSON ve düz metin sunucu hataları güvenli şekilde ele alındı.
- Kullanıcıya Türkçe hata mesajı ve takip kodu gösterilmesi eklendi.
- API bağımlılığı sabit sürüme bağlandı ve otomatik testler eklendi.

## v1.0.0 — 19 Ağustos 2026

- API dayanıklılık düzenlemelerinden önceki çalışan ana sürüm.
- Kullanıcı paneli, ses dökümü, üçlü analiz, PDF, yönetim paneli ve maliyet takibi mevcut.
