## v2.19.0 — 13 Ekim 2026

- Doktor panelindeki ses oynatıcı artık takılmıyor. `/doctor/audio/{kid}` ucu
  yönetici ucuyla aynı HTTP byte-range (206) desteğini kullanıyor ve 15 saniyelik
  arka plan yenilemesi çalan kaydı artık yeniden çizmiyor.
- COMED iş listesi kart tasarımı yenilendi: her kart sırayla farklı renk alır,
  hastaya bağlı rapor/aktarım durumu kartta görünür, karta tıklayınca kayıt
  listesi o hastaya göre süzülür.
- Eklentiye form doldurma hız ayarı eklendi (0.5× – 2.5×). Hız, aktarım
  sürerken COMED sayfasındaki Klinot balonundan da değiştirilebilir.
- Soygeçmiş ve düşme riski artık hiçbir koşulda boş bırakılmıyor; kart önce
  açılır, etiket büyük/küçük harf farkı gözetmeden aranır ve gerekirse
  "Özellik Yok" / "Görüldü" işaretlenir.
- Hasta girişinde doğum tarihi elle de yazılabiliyor; noktalar otomatik eklenir,
  takvim zorunlu değil.
- KVKK aydınlatma metni bağlantısının altı çizildi.
- Epikriz raporunun adı her yerde "AI epikriz" oldu.

# Sürüm Geçmişi

## v2.18.0 — 8 Ekim 2026

- **Hasta ekranında kayıt bölümü yukarı alındı.** Randevu seçme kartı ekranın en değerli yerini kaplıyor, "Kaydı başlat" düğmesini aşağı itiyor ve kullanıcının kaydırması gerekiyordu. Hastanın randevusu zaten belli olduğu için seçim sunmak gereksizdi.
- Tek randevulu hastada artık seçme kartı yerine kayıt kartının **altında** kısa bir bilgi şeridi var: "Bu görüşme randevunuza işlenecek" + bölüm, doktor ve hasta numarası tek satırda, yanında yenileme düğmesi. Uygulama açılınca ilk görülen şey kayıt ekranı oluyor.
- Birden fazla randevu varsa, yükleme sürerken veya hata durumunda tam seçici korunuyor; doktor ekranı hiç değişmedi.

## v2.17.1 — 8 Ekim 2026

- **Hasta girişindeki "T.C. kimlik numarası geçersiz" hatası düzeltildi.** Giriş, resmi T.C. kimlik kontrol basamağı algoritmasını uyguluyordu. COMED test ortamındaki hastalar ise uydurma numaralar taşıyor (ör. `12345678912`) ve bu algoritmayı geçmiyor; giriş daha ilk adımda kapanıyordu. Önceki test hastasının numarası (`28411425816`) tesadüfen geçerli bir numara olduğu için sorun fark edilmemişti.
- Kontrol basamağı doğrulaması artık `PATIENT_TCKN_CHECKSUM` ile yönetiliyor ve **varsayılan olarak kapalı**. Biçim kontrolü (11 hane, sıfırla başlamaz) her durumda sürüyor. Girişin asıl güvenliği zaten numaranın kendisi değil; TCKN + doğum tarihi özetinin COMED'den eşitlenmiş gerçek bir randevuyla eşleşmesi ve ardından gelen SMS doğrulaması. Uydurma bir numara hiçbir randevuyla eşleşemez. Gerçek hasta verisine geçerken `PATIENT_TCKN_CHECKSUM=true` yapılmalı.

## v2.17.0 — 8 Ekim 2026

- **Tek balon.** Ayrı durum şeridi kaldırıldı. Artık tek bir balon var: fare üzerine gelince de işlem sırasında da aynı balon yana açılıyor ve o anki adımı kendi içinde gösteriyor. İki kutunun yan yana durması ve üst üste binmesi sorunu kökten bitti. Balon içeriği kadar genişliyor (ölçüldü: 304 px / 257 px / boşta 56 px).
- **POST şablonu sistemi tamamen kaldırıldı.** Her protokol için doğrulanmış şablon bulunmadığından davranış öngörülemez oluyor ve doktora "POST şablonu yok", "POST tamamlanamadı" gibi anlamsız mesajlar gidiyordu. Artık bütün alanlar yalnızca eklenti tarafından form doldurularak hazırlanıyor.
  - `content.js`: `executeNativePosts` ve POST dalları kaldırıldı.
  - `page_trace.js`: POST çalıştırıcı kaldırıldı, dosya 333 → 220 satıra indi; yalnızca gözlemci olarak kaldı, COMED'e hiçbir istek göndermiyor.
  - `comed_integration.py`: `build_native_requests` ve yardımcıları kaldırıldı (186 satır), paket `schema_version: 6` ve `execution_mode: "extension_form_fill"` döndürüyor.
  - Köprü hiçbir koşulda Kaydet/Kaydet ve İmzala düğmesine basmıyor; son kontrol, kayıt ve imza doktorda.

## v2.16.2 — 8 Ekim 2026

- **Fare balonun üzerine gelince şerit artık ezilmiyor.** Balon 56 px'den 196 px'e açılırken şeridin üstüne biniyordu. Şerit de aynı anda sola kayıyor; aralarında boşluk kalıyor.
- **Alt satırdaki bağlam metni düzeltildi.** İş listesi sayfasında hasta adı okunamadığı için sayfa gövdesinin başı — yani araç çubuğu metni ("İş Listesi Havuz İş Listesi Randevular Tıbbi İkinci Görüş…") — hasta adı sanılıp şeride basılıyor ve kutuya sığmıyordu. Hasta adı artık yalnızca hasta kartında okunuyor, ad temizleyiciden geçiyor ve bağlam metni tek satırda kalacak şekilde kırpılıyor.

## v2.16.1 — 8 Ekim 2026

- **Durum şeridi yana doğru açılıyor.** Şerit mutlak konumlu ve kapsayıcısı yalnızca balon kadar (56 px) geniş olduğu için tarayıcı "shrink-to-fit" uygulayıp her kelimeyi alt satıra atıyordu; mesaj dar ve uzun bir sütun gibi görünüyordu. `width:max-content` ile şerit artık içeriği kadar yana genişliyor (ölçüldü: 211×52 px).
- **Tanı "Taraf Tipi" listesi açık bırakılmıyor.** Önceki kod listeyi açıp 60 ms bekliyor ve `clickText` ile seçeneği arıyordu; `clickText` yalnızca `button/label/span` tarıyor, oysa seçenekler `li`/`div` olabiliyor. Seçenek bulunamayınca liste açık kalıyor ve doktorun karşısına yarım kalmış bir alan çıkıyordu. Yeni `selectDropdownOption()` seçeneği geniş bir kümede arıyor, seçimden sonra listenin gerçekten kapandığını doğruluyor, kapanmadıysa Escape ile kapatıyor.

## v2.16.0 — 8 Ekim 2026

- **Aktarım sırasında canlı durum şeridi.** Eskiden alanlar doldurulurken ekranda yalnızca balon görünüyordu; ne olduğunu anlamak için günlüğü açmak gerekiyordu. Artık balonun yanında kısa bir şerit beliriyor ve "Şikayet dolduruldu", "Özgeçmiş ve soygeçmiş hazırlanıyor" gibi anlık adımları gösteriyor. Altında hasta/protokol bilgisi var. Şerit 6 saniye sonra sönüyor, günlük açılınca gizleniyor; detaylı günlük eskisi gibi balona tıklanınca açılıyor.
- **Son adım kalıcı.** Aktarım bittiğinde şerit sönmüyor ve "Aktarım bitti · Lütfen kontrol edip Kaydet ve İmzala" olarak ekranda kalıyor.
- **Düşme riski ve soygeçmiş artık eklentide de garanti.** Düşme riski `exists` değeri `true` değilse (null dâhil) "Yok" işaretleniyor. Soygeçmişte hiçbir satır eşleşmezse "Özellik Yok" basılıyor. Daha önce bu durumlarda alanlar boş kalabiliyor ve COMED formu kaydedilemiyordu; sunucu tarafındaki zorunluluk artık eklenti tarafında da aynen uygulanıyor.

## v2.15.1 — 7 Ekim 2026

- **İş listesi otomatik son 3 aya açılıyor (düzeltildi).** v2.15.0'daki deneme çalışmıyordu. İki nedeni vardı: (1) bayrak denemeden *önce* set edildiği için sayfa yüklenmeden yapılan ilk deneme başarısız olunca özellik kalıcı olarak devre dışı kalıyordu; (2) COMED'in tarih kutusu `disabled` bir `input` — ona tıklamak hiçbir olay tetiklemiyor, takvimi yalnızca yanındaki `[data-test="co-button-icon-calendar"]` düğmesi açıyor. Artık gerçek seçiciler kullanılıyor, aralığın genişlediği doğrulanıyor ve bayrak yalnızca başarıdan sonra set ediliyor. Canlı COMED test ortamında ölçüldü: aralık `07.10.2026 - 07.10.2026` → `09.07.2026 - 07.10.2026`, liste 0 → 2 hasta.

## v2.15.0 — 7 Ekim 2026

- **Eklentide tekrar giriş sorulmuyor.** Bir kez bağlandıktan sonra kullanıcı adı/şifre alanları gizleniyor, yerine bağlı hesap görünüyor. Oturum düşerse (401) kayıtlı oturum silinip giriş ekranı kendiliğinden geri geliyor. "Başka hesapla bağlan" ile elle değiştirilebiliyor.
- **Düşme riski ve soygeçmiş artık zorunlu.** Görüşmede konuyla ilgili bir şey geçmiyorsa alanlar boş bırakılmıyor: düşme riski "yok", soygeçmiş "özellik yok" olarak işaretleniyor. Model boş bıraksa bile sunucu tarafında deterministik olarak dolduruluyor.
- **Doktor paneli yönetici paneliyle birebir aynı düzene geçti.** Aynı istatistik şeridi, arama kutusu, kayıt satırları ve açılır detay; detayda ses kaydı, beş rapor sekmesi, PDF indirme ve COMED aktarım çubuğu.
- `popup.js` içinde gözden kaçan eski COMED adresi düzeltildi (ters bölü ile yazıldığı için toplu değiştirmede yakalanmamıştı).

## v2.14.0 — 7 Ekim 2026

- **COMED adresleri değişti.** Web `https://goztepetest.comed.mlpcare.com`, API `https://goztepetestapi.comed.mlpcare.com` oldu. Protokol `http` → **`https`**; iz kaydı ve eklenti POST izin listesindeki şema kontrolleri de güncellendi, aksi halde sessizce çalışmayı bırakacaklardı.
- **Tek doktor hesabı.** `Kullanici.kayadr;Kullanici.aydin1|tracer` (şifre `1`). Eski iki test hesabı kaldırıldı.
- **Eklenti kapat düğmesi aşağı ok oldu.** Panel aşağı indiği için `×` yerine aşağı bakan ok simgesi kullanılıyor.
- **Doktor paneli yönetici paneliyle aynı derinliğe geldi.** Ses kaydı oynatıcısı, sekmeli rapor görünümü (doktor epikrizi, hasta özeti, yönetim raporu, COMED taslağı, görüşme metni), iletişim önerileri ve üç rapor için ayrı PDF indirme eklendi.
- Rapor render katmanı `static/report_view.js` dosyasına çıkarıldı; `/admin` ve `/doctor` panelleri artık aynı kodu paylaşıyor, kopya kod kalmadı.

## v2.13.2 — 6 Ekim 2026

- **Hasta adı düzeltildi.** Köprü, COMED kart sayfasında ismi sayfa gövdesinin ilk 80 karakterinden alıyordu; COMED başlığı isme cinsiyet, yaş, doğum tarihi ve hasta numarasını boşluksuz eklediği için uygulamaya `Sena Nur Deneme Hastasıdır K28yıl22.10.1997 Hasta No:1300013` gibi bir metin düşüyordu. Ad artık ilk meta işaretinden kesiliyor.
- **Üst şerit taşması giderildi.** Uygulama başlığındaki kullanıcı adının genişlik sınırı yoktu; uzun bir ad logoyu dışarı itip ekrandan taşıyordu. Ad artık ekranın en fazla %38'ini kaplıyor ve taşan kısım üç nokta ile kısaltılıyor.

## v2.13.1 — 6 Ekim 2026

- SMS sağlayıcısı henüz bağlanmadığı için hasta girişindeki sabit test kodu (`000000`) geçici olarak varsayılan açık hâle getirildi; kimlik eşleşen hasta artık SMS beklemeden giriş yapabiliyor.
- Gerçek SMS servisi devreye girince `PATIENT_TEST_OTP_ENABLED=false` yapılması yeterli. Açıkken TCKN ve doğum tarihini bilen herkes o hastanın kaydına girebileceği için yalnızca test ortamında açık bırakılmalıdır.

## v2.13.0 — 6 Ekim 2026

- **Hasta girişi düzeltildi.** TCKN ve doğum tarihi COMED'de yalnızca "Hasta Bilgileri" açılır panelinde bulunuyor. Köprü bu alanları görünür metinden okuduğu için panel kapalıyken kimlik hiç yakalanmıyor, hasta uygulamasında "Kimlik bilgileriyle eşleşen aktif COMED randevusu bulunamadı" hatası çıkıyordu. Kimlik taraması artık gizli düğümleri de kapsıyor.
- **İş listesi artık yanlışlıkla silinmiyor.** Sayfa henüz yüklenmemişken yapılan boş ayrıştırma `replace` ile gönderiliyor ve doktorun kayıtlı iş listesiyle birlikte hastanın kimlik eşleşmesini de siliyordu. Boş sonuç artık mevcut listeyi koruyor.
- **COMED işlem günlüğü sohbet balonuna dönüştü.** Kenara yapışık dikdörtgen yerine ekrandan ayrık, yuvarlak ve sürüklenebilir bir balon; üzerine gelince yana doğru yumuşak açılıyor, tıklayınca günlük paneli ölçeklenerek beliriyor. İşlem sürerken balon nabız gibi atıyor, durum rengi gradyan olarak yansıyor.

## v2.10.3 — 1 Ekim 2026

- Taslak temizleme, aktarım öncesi kalıcı COMED kayıtlarını fotoğraflar ve yalnızca son Klinot aktarımının eklediği ICD, Özgeçmiş ve Soygeçmiş kayıtlarını çöp kutusu işlemleriyle geri alır.
- Doktorun aktarım öncesinde bulunan tanı ve geçmiş bilgileri güvenli karşılaştırmayla korunur.
- Sistem Sorgulama eski hâline getirildikten sonra COMED kartı otomatik yenilenir; bu tek yenilemede “kaydedilmemiş değişiklik” tarayıcı uyarısı gösterilmez.

## v2.10.2 — 1 Ekim 2026

- Doktor panelindeki COMED aktarımı yeni sekme açmak yerine aynı Chrome penceresindeki mevcut COMED sekmesini bulup yeniden kullanır.
- COMED oturumu kapalıysa giriş tamamlandıktan sonra bekleyen hasta kartı otomatik açılır ve aktarım ikinci kez düğmeye basmadan devam eder.
- Hasta kartının bileşenleri ve Sistem Sorgulama bağlantısı yüklenene kadar kontrollü bekleme eklendi; erken yükleme kaynaklı “Sistem Sorgulama düğmesi bulunamadı” hatası önlendi.
- Eklentiye, yalnızca son Klinot aktarımının kaydedilmemiş taslağını geri alan “Bu karttaki Klinot taslağını temizle” düğmesi eklendi.

## v2.10.1 — 1 Ekim 2026

- Hasta uygulamasında seçilen randevu için oluşturulan ses analizi artık hasta numarası ve ziyaret kimliğiyle randevudaki doktora otomatik atanır.
- Doktor panelinde hastadan gelen görüşmeler etiketlenir; doğru doktor raporu, sesi ve COMED aktarımını görebilir, diğer doktorlar erişemez.
- Hasta uygulamasının mevcut sağlık raporu deneyimi korunur ve hastaya COMED aktarım kontrolleri gösterilmez.

## v2.10.0 — 29 Eylül 2026

- Mobil girişe doktor/hasta rol seçimi ve hasta numarasıyla giriş eklendi.
- Hasta hesabı yalnızca kendi COMED randevularını görür; görüşme sonunda sade sağlık raporu açılır.
- Hasta sağlık raporu için ayrı PDF indirme akışı eklendi; COMED aktarımı doktor rolüyle sınırlandı.
- Kayıt bilgilendirme kutusu modern, iOS uyumlu anahtara dönüştürüldü.
- Doktorun mevcut kayıt, epikriz ve COMED aktarım akışı korunarak mobil sürüm `2.10.0+24` yapıldı.

## v2.9.2 — 29 Eylül 2026

- Mobil epikriz hazırlama ekranı cihaz saatinden ölçülen gerçek geçen süreyi gösterir.
- Transkripsiyon aşamasında uydurma yüzde yerine belirsiz ilerleme, rapor üretiminde sunucunun tamamladığı gerçek adımlara göre yüzde gösterilir.
- COMED işlem günlüğü sağ alta taşındı; işlem sayısı, zaman, sonuç durumu ve okunabilir alan açıklamalarıyla yeniden tasarlandı.

## v2.9.1 — 29 Eylül 2026

- Doktor paneli COMED iş listesini açılış ekranı yaptı; hasta seçimi ayrı aktarım görünümünü açıyor ve token göstergesi kaldırıldı.
- Yeni analizler panel yenilenmeden otomatik görünür, hastaya bağlı rapor otomatik seçilir ve COMED aktarım düğmesi etkinleşir.
- Yönetici ve doktor giriş adresleri birbirinden bağımsız çalışır; açık doktor oturumu `/admin/login` sayfasını engellemez.
- COMED köprüsü kalıcı, tıklanabilir işlem günlüğü gösterir; doldurulan ve bulunamayan alanları adım adım listeler.
- Aktarım sonu metni uygulama, doktor paneli ve eklentide “Aktarım bitti · Genel doktor kontrolü gerekli” olarak birleştirildi.
- Mobil epikrizde uzun güçlü yön ve geçmiş metinleri yatay taşmadan aşağı doğru sarılır.
- Doktor skoru ve alt ölçütleri düşükte kırmızı, ortada turuncu, yüksekte yeşil gösterilir.

## v2.9.0 — 29 Eylül 2026

- İki ayrı doktor hesabı ve yalnız yönetim ekranına erişen admin rolü eklendi.
- Mobil uygulama, doktor web paneli ve COMED eklentisi aynı doktor hesabıyla çalışıyor.
- Kayıtlar, COMED iş listeleri, API izleri ve aktarım kuyrukları doktor bazında ayrıldı.
- Doktorun rapor seçip COMED hasta kartını açarak aktarım başlatabildiği web paneli eklendi.
- `|tracer` içeren COMED kullanıcı adları için token biçimi güvenli hale getirildi.

## v2.8.7 — 24 Eylül 2026

- Sistem Sorgulama gibi alt belgelerin `Kaydet` düğmeleri artık ana COMED muayenesinin tamamlandığı şeklinde yorumlanmıyor.
- Ana kayıt tamamlanma takibi yalnızca bütün form, Özgeçmiş, Soygeçmiş ve Sistem Sorgulama işlemleri ile son DOM doğrulaması bittikten sonra etkinleşiyor.
- Mobil uygulama ve yönetim paneli, gerçek aktarım sonuna kadar `dolduruluyor` durumunda kalıyor; `Aktarım bitti` mesajı yalnızca son kontrolden sonra gösteriliyor.

## v2.8.6 — 24 Eylül 2026

- 24 Eylül göğüs ağrısı denemesinin gerçek ses kaydı, transkripti, raporları ve COMED aktarım/debug verisi private repo içinde kalıcı demo kaydı olarak arşivlendi.
- Render'ın geçici SQLite diski sıfırlansa bile bu kayıt uygulama açılışında tekilleştirilmiş `demo_key` ile admin paneline yeniden ekleniyor.
- Aktarım sınırında yalnızca hasta cümleleri kullanılarak açık düşme/düşmeme beyanı yeniden doğrulanıyor; eski analiz taslakları yanlış düşme değeri taşıyorsa doktor incelemesinden önce düzeltiliyor.

## v2.8.5 — 24 Eylül 2026

- Bağlamlı Sistem Sorgusu bulguları COMED'in gerçek kısa seçeneklerine kanonik olarak eşleniyor; pozitif bulgu varken yanlış `Özellik Yok` seçilmiyor.
- Bozuk STT metninde açıkça bulunan ilaç, işitme kaybı, transfüzyon, fizik tedavi, özel diyet, sigara ve düşme riski paralel COMED çıktısında kaybolursa deterministik olarak geri kazanılıyor.
- Özgeçmiş tekrar-kayıt kontrolündeki gereksiz uzun beklemeler kısaltıldı ve aynı sigara kaydının tekrar eklenmesi engellendi.
- Aktarım başarı durumu, Özgeçmiş/Soygeçmiş dâhil DOM güncellemeleri sakinleşip son doğrulama tamamlandıktan sonra gösteriliyor; eksik bulunan alan sayısı ayrıca doktor kontrolüne bırakılıyor.

## v2.8.4 — 23 Eylül 2026

- Metre olarak gelen boy değeri COMED'in santimetre alanına çevriliyor; hatalı VKİ/VYA oluşması engellendi.
- Ağrı skoru COMED'in ayrı NRS kaydırıcısından dolduruluyor; saat cinsindeki ağrı başlangıcı yanlışlıkla gün olarak yazılmıyor.
- Düşme riski ayrıntı menüsü doğru COMED kapsayıcısından bulunuyor ve hasta yaşı kart başlığından türetiliyor.
- Özgeçmiş alışkanlıkları seçimden sonra `+` ile ekleniyor; gerçek bilgiler varken `Özellik Yok` seçimi uygulanmıyor.
- Soygeçmiş tablosu başlıksız COMED yapısına göre eşlenerek ilişki/hastalık hücreleri dolduruluyor.
- Sistem sorgusu özeti ayrıntılı bulgulardan üretiliyor; aynı bulgular zaten kayıtlıysa tekrar kaydetme yapılıp sunucu uyarısı açılmıyor.

## v2.8.3 — 23 Eylül 2026

- COMED özgeçmişinde aynı protokolde zaten bulunan hastalık yeniden eklenmiyor; yalnız bilinen tekrar-kayıt uyarısı güvenli biçimde kapatılıyor.
- Ağrı başlangıç süresi artık skor kutusunu ezmiyor; epikrizdeki `X/10` skoru COMED taslağıyla çapraz doğrulanıyor ve baskı tipi ağrı `Bastırıcı` olarak eşleniyor.
- Açık düşme öyküsü/risk beyanı COMED düşme riskine taşınıyor; hasta yaşı açık kart başlığından alınarak 65 yaş grubu doğru seçiliyor.
- Epikrizde yapılandırılmış kronik hastalık, ameliyat, ilaç, alerji, alışkanlık ve soygeçmiş bilgileri COMED paralel çıktısıyla uzlaştırılıyor; engellilik alanı da aktarım kapsamına eklendi.
- Mobil uygulama COMED aktarım durumunu eski 30 saniyelik pencere yerine arka planda 10 dakikaya kadar izliyor ve uygulamaya dönüldüğünde hemen yeniliyor.
- Başarılı analizden sonra yerel ses kaydı silinmiyor; doktor aynı kayıt için `Tekrar analiz et` seçeneğini kullanabiliyor.
- Ses ve transkript yönetim panelindeki analiz kaydında kalıcı olarak tutulmaya devam ediyor.

## v2.8.2 — 23 Eylül 2026

- Mobil transkripsiyon tek uzun bağlantı yerine kalıcı sunucu işi ve durum sorgulama akışına taşındı.
- 120 saniyelik kesilme kaldırıldı; 15–30 dakikalık kayıtlar için 45 dakikalık işleme penceresi eklendi.
- Aynı ses tekrar gönderildiğinde içerik kimliğiyle mevcut sonuç kullanılıyor; çift STT maliyeti önleniyor.
- Kayıt ve analiz sırasında ekran uyanık tutuluyor; bağlantı kesilse bile yerel ses silinmiyor.
- Yeni kayıtlar 64 kbps kalıcı uygulama klasörüne yazılıyor; eski geçici kayıtlar açılışta kurtarılıyor.

## v2.8.1 — 23 Eylül 2026

- Sistem Sorgulama belgesinin dokuz zorunlu grubunun tamamen yüklenmesi bekleniyor; görüşmede bulgu yoksa her grup için güvenli `Özellik Yok`/`Komplikasyon Yok` varsayılanı seçiliyor.
- COMED'in özel checkbox bileşeninde gerçek input hedefi kullanılıyor ve her grubun işaretlendiği doğrulanmadan alt belgenin sağ-alt `Kaydet` düğmesine basılmıyor.
- Alt belge kaydedilip kapanmadan ana muayene alanlarına geçilmiyor; başarısız kayıt artık hazır gibi gösterilmeyip admin debug kaydında `system_inquiry` aşamasıyla raporlanıyor.

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
