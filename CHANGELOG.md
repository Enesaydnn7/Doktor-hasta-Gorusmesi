# Sürüm Geçmişi

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
