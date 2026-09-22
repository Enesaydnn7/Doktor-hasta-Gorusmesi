# Sürüm Geçmişi

## v2.8.0 — 22 Eylül 2026

- COMED'in genişletilemeyen `window` nesnesinde izleyiciyi durduran hata giderildi; gerçek GET/POST şablonları yeniden yakalanabilir hale geldi.
- Ayrı Sistem Sorgulama belgesindeki sekiz sistem grubu ve komplikasyon alanı doldurulup kendi kaydı tamamlanıyor; ana muayene kaydı ve imza hâlâ doktora bırakılıyor.
- Eksik zorunlu MVP kontrolleri doktor tarafından görülebilen operasyonel varsayılanlarla hazırlanıyor; nabız 100, düşme/ağrı yok, ayaktan takip ve ameliyat hayır seçimleri debug kaydında açıkça işaretleniyor.
- Admin paneline POST ile giden, eklentiyle doldurulan, operasyonel varsayılan ve bulunamayan alanları ayrı gösteren aktarım debug görünümü eklendi.
- Aktarım debug verisi kullanıcı kapsamlı olarak veritabanında saklanıyor ve mobil/administrator kayıt yanıtlarında gösteriliyor.

## v2.7.1 — 22 Eylül 2026

- Aynı protokole ait doğrulanmış ana POST şablonu bulunmadığında aktarımı durduran regresyon giderildi.
- Köprü hibrit hale getirildi: doğrulanmış POST varsa onu kullanır, yoksa seçili açık hasta kartını eklenti üzerinden doldurur.
- Hibrit akış ana muayene, yaşamsal bulgular, profil/soygeçmiş, psikolojik durum, düşme riski, ağrı, ICD ve izlem-plan alanlarını hazırlar; otomatik kaydetme veya imza atma yapmaz.
- Aktarım durumunda kullanılan yöntem ve hazırlanan alan sayısı gösterilir.

## v2.7.0 — 21 Eylül 2026

- Muayene aktarımında DOM alanı doldurma kaldırıldı; köprü artık yalnız doğrulanmış, aynı protokole ait ve izin listesindeki COMED kayıt POST gövdelerini kullanıyor.
- COMED oturum başlıkları sadece sayfa belleğindeki kapalı yürütücüde tutuluyor; parola, çerez ve token Klinot sunucusuna gönderilmiyor veya kaydedilmiyor.
- İmza/silme uçları açıkça engellendi, POST zaman aşımı eklendi ve sonsuz yüklenme yerine anlaşılır hata durumu getirildi.
- Kullanıcıya ait sterilize COMED izleri mobil API üzerinden yalnız aynı oturuma kapsamlı biçimde okunabilir hale getirildi.

## v2.6.2 — 20 Eylül 2026

- Yakalanan COMED test isteklerini mevcut yönetici oturumuyla görüntüleyen, normal admin tasarımını değiştirmeyen korumalı HTML doğrulama görünümü eklendi.

## v2.6.1 — 20 Eylül 2026

- COMED tanı kayıt uçları, istemci filtrelerinin `traces` yolunu engellemesini önlemek için `request-log` olarak adlandırıldı.

## v2.6.0 — 20 Eylül 2026

- Göztepe COMED test API'sinin gerçek GET/POST URL, JSON gövde ve yanıt durumlarını yakalayan tanı katmanı eklendi.
- İzleme yalnız test API alan adına sınırlandı; parola, çerez, yetkilendirme başlığı ve oturum/token alanları kaydedilmez.
- Yakalanan istekler kullanıcı bazında ve sınırlı saklama politikasıyla yönetici inceleme ucuna aktarılıyor.
- Bu tanı sürümü, DOM doldurma akışını gerçek COMED payload haritasına dönüştürmek için temel oluşturur; otomatik imza hâlâ kapalıdır.

## v2.5.0 — 20 Eylül 2026

- COMED Özgeçmiş aktarımı kronik hastalık, ilaç, alerji, ameliyat, özel durum, aşı, cihaz, kan transfüzyonu ve terapi lookup alanlarının gerçek sonuç seçimi ve alt kayıt ekleme akışıyla genişletildi.
- Soygeçmiş akraba–hastalık matrisi, anne-baba akrabalığı, psikolojik durum ve düşme riski yaş grubu şemaya ve tarayıcı köprüsüne eklendi.
- Ağrı bölgesi ile açıklaması ayrıldı; tanılarda ayırıcı/kesin/ön tanı, taraf, ana tanı ve ilk tanı tarihi desteklendi.
- Göztepe COMED test panelinin ana muayene alanları yeniden doğrulandı; eksiksiz v3 örnek JSON ve güncel alan haritası eklendi.
- Test ortamında COMED lookup seçimi ve profil alt kaydı gerçek “Kayıt başarılı” yanıtıyla doğrulandı; otomatik imza kapalı kalmaya devam ediyor.

## v2.4.3 — 16 Eylül 2026

- COMED alanları artık ilgili muayene kartı içinde, alan etiketiyle eşleştiriliyor; Boy değerinin Kilo alanına yazılmasına yol açan genel seçici kaldırıldı.
- ICD-10 kodu COMED arama sonuçlarıyla doğrulanıp ön/kesin tanı ve ana tanı seçimiyle forma ekleniyor.
- Düşme riski alt skoru, ağrı ayrıntıları, özgeçmiş alışkanlıkları, medeni durum ve kontrol önerisi eşlemeleri genişletildi.
- Göztepe muayene formunun alan, seçenek, zorunluluk ve otomasyon kapsamı `docs/COMED_FORM_MAP.md` içinde belgelendi.
- Doktorun `Kaydet` / `Kaydet ve İmzala` kontrolü korunur; otomatik imza yoktur.

## v2.4.2 — 16 Eylül 2026

- COMED'in sayfa yenilemeden yaptığı iş listesi → hasta kartı geçişi artık algılanıyor; köprü kart açıldıktan sonra bekleyen aktarımı otomatik dolduruyor.
- Bekleyen aktarım bulunduğunda köprü doğru protokolün “Göreve Git” düğmesini otomatik çalıştırıyor; otomatik kaydetme ve imzalama hâlâ kapalı.
- Köprü yalnız giriş yapan Klinot kullanıcısının aktarım kuyruğunu görüyor ve hasta kartının gerçek URL'sini aktarım kaydına ekliyor.
- Mobil uygulama yanıt gelmezse sonsuz yükleme göstermek yerine açıklama ve aynı aktarımı tekrar kontrol etme seçeneği sunuyor; yeni mükerrer kuyruk kaydı oluşturmuyor.

## v2.4.1 — 16 Eylül 2026

- COMED iş listesi artık bağlantı olmayan “Göreve Git” düğmeli tablo satırlarını doğrudan okuyup mobil uygulamaya eşitliyor.
- Hasta kartı ilk kez açıldığında klinik kart kimliği ve gerçek URL aynı kayda ekleniyor; sonraki liste yenilemelerinde bu bilgi korunuyor.
- COMED iş listeleri Klinot kullanıcısına göre ayrıldı; farklı doktor oturumlarının listeleri birbirini silmiyor veya görmüyor.
- Mobil boş iş listesine eklenti kurulum adımları ve COMED/Klinot girişlerinin farkını açıklayan yardım eklendi.
- Yönetici kayıt listesi eski beş sütunlu düzenine döndürüldü. COMED durumu işlem alanında gösteriliyor; iletişim önerileri belirgin kartlarla sunuluyor.
- Yönetici CSS dosyasına sürüm parametresi eklendi; eski tarayıcı önbelleğinin yeni HTML düzenini bozması engellendi.

## v2.4.0 — 16 Eylül 2026

- Mobil görüşme akışına COMED iş listesinden hasta/protokol seçimi eklendi; hasta seçilmeden kayıt başlatılması engellendi.
- Hasta, doktor ve yönetim raporlarına ek olarak COMED alan taslağı dördüncü Gemini işi olarak aynı anda hazırlanıyor; mevcut üç raporun bekleme süresi uzatılmıyor.
- Doktor epikrizi ve iletişim önerileri mobilde daha okunur bölüm/kart yapısıyla, Türkçe alan adlarıyla ve belirgin durum göstergeleriyle yenilendi.
- Doktor kontrolündeki “COMED'e aktar” akışı, aktarım durumu ve “COMED'de aç” kısayolu mobil uygulamaya ve yönetici paneline eklendi.
- Göztepe COMED test oturumunda çalışan Chrome köprüsü eklendi. Köprü yalnızca taslak alanları doldurur; COMED'in kendi Kaydet/İmzala işlemi doktor tarafından yapılır.
- COMED iş listesi, aktarım kuyruğu ve köprü durumları için yeni FastAPI uçları ve SQLite tabloları eklendi.

## v2.3.0 — 15 Eylül 2026

- Mobil Bearer oturumu web panelinin 12 saatlik çerezinden ayrıldı ve 30 günlük güvenli mobil oturum süresi tanımlandı; 12 saatten eski fakat 30 günü doldurmamış mevcut APK tokenları yeniden çalışır.
- APK, güvenli depodan açılan oturumu sunucuda doğruluyor; gerçekten geçersiz tokenla kayıt alınmasına izin vermek yerine kullanıcıyı giriş ekranına yönlendiriyor.
- “Analiz et” sonrasında tamamlandı kartı kaldırıldı; tam dönen dairesel gösterge, “Epikriz hazırlanıyor” açıklaması ve gizli arka plan işleme ekranı eklendi.
- Analiz tamamlandığında doktor epikrizi otomatik açılmaya devam ediyor; görüşme metni, analiz adımları ve yüzdeler doktora gösterilmiyor.
- STT/LLM sağlayıcıları, analiz promptları, admin paneli ve kalıcı demo kayıtları değiştirilmedi.

## v2.2.1 — 14 Eylül 2026

- 9 Eylül tarihli bacak ağrısı deneme kaydı, sesi ve üç raporuyla birlikte sürümlü demo arşivine eklendi.
- Render yeniden başlatma veya deploy sırasında geçici SQLite silinse bile hem gastrit hem bacak ağrısı demosu admin paneline otomatik ve tek kopya olarak geri ekleniyor.
- Analiz promptları, STT zinciri, mobil ekranlar ve normal yeni kayıt akışı değiştirilmedi.

## v2.0.1 — 8 Eylül 2026

- Flutter mobil uygulamasının Android derleme hedefi, `flutter_secure_storage` uyumluluğu için API 37'ye yükseltildi.
- Android Gradle Plugin 9.1.1'e geçirildi; uygulamanın minimum/target Android sürümü ve çalışma davranışı değiştirilmedi.
- Mobil istemci sürümü `2.0.1+2` olarak kaydedildi.

## v2.0.0 — 8 Eylül 2026

- `mobile_app/` altında Android ve iOS hedefli “Klinot” Flutter MVP'si eklendi.
- Yüz yüze görüşme için açık kayıt durumu, canlı ses seviyesi, süre, duraklat/devam, iptal ve metne dönüştürme akışı eklendi.
- Metin kontrolünden sonra üç rapor mevcut sırayla hazırlanıyor; mobil yüzde göstergesi sunucunun gerçek `0 → 33 → 67 → 100` olaylarını kullanıyor.
- Doktor ve yönetici rolleri için imzalı, süreli Bearer oturumuna sahip `/api/v1/mobile/*` API uçları eklendi.
- Mobil kayıtlar mevcut SQLite kayıtları ve web admin paneliyle birleştirildi; kaynak ve mobil sürüm bilgisi saklanıyor.
- Sesin STT ile analiz istekleri arasında işlem belleğinde kaybolmaması için geçici ses aktarımı SQLite tablosuna taşındı.
- Mevcut web paneli, rapor promptları, Scribe/OpenAI STT zinciri ve üçlü Gemini analiz davranışı değiştirilmedi.

## v1.8.0 — 2 Eylül 2026

- Eski veya tarayıcı önbelleğinde kalmış epikriz rapor adı güvenli biçimde `doktor` raporuna çevriliyor; eski kayıt PDF isteği artık “Geçersiz rapor tipi” hatasıyla durmuyor.
- Analiz ekranına yüzde ve aşama göstergeli ilerleme çubuğu eklendi.
- İlerleme yüzdesi zaman tahminiyle değil; hasta özeti, detaylı epikriz ve yönetim raporu Gemini çağrılarının gerçekten başlaması/tamamlanmasıyla `0 → 33 → 67 → 100` olarak güncelleniyor.
- Eski `/analyze` API davranışı, mevcut kayıtlar, ses kaydı ve analiz promptları değiştirilmedi.

## v1.7.3 — 1 Eylül 2026

- Ses analizinden sonra kullanılan geçici ses kimliği ve STT kullanım durumu tarayıcıda açıkça tanımlandı; `lastAudioId is not defined` hatası giderildi.
- Admin oturumu Render yeniden başlatmaları arasında kararlı hale getirildi; PDF isteğinin yeniden başlatma sonrasında yetkisiz kalması önlendi.
- Hasta, doktor ve yönetim PDF'leri özel karakterli rapor metinleriyle güvenli üretiliyor; indirme hataları artık gerçek sunucu mesajını gösteriyor.
- Admin ses kaydına HTTP Range/206 desteği eklendi; tarayıcı süreyi ve oynatma imlecini doğru hesaplayıp ileri-geri sarabiliyor.
- Statik JavaScript dosyaları sürüm parametresiyle çağrılarak eski tarayıcı önbelleğinin hatalı kodu çalıştırması engellendi.
- Korunan gastrit demo kaydı ve analiz promptları değiştirilmedi.

## v1.7.2 — 27 Ağustos 2026

- Private repoda korunan yönetici demo kaydı yeni/geçici SQLite veritabanına uygulama açılışında otomatik ekleniyor.
- Render Free uyku, yeniden başlatma veya deploy nedeniyle SQLite'ı sıfırlasa bile demo kayıt admin panelinde tekrar oluşuyor.
- Aynı demo kaydının birden fazla eklenmesini önleyen kalıcı `demo_key` alanı ve benzersiz indeks eklendi.
- SQLite işlemlerinden sonra bağlantıların açık kalmasına neden olan bağlantı yaşam döngüsü düzeltildi.

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
