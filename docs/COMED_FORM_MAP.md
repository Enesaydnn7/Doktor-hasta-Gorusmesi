# COMED Muayene Formu Alan Haritası

Bu harita Göztepe COMED test ortamındaki `patient-clinical-card` ekranında
20 Eylül 2026 tarihinde gerçek DOM, lookup ve seçenek etkileşimleriyle doğrulandı.
Klinot yalnız taslağı doldurur; **Kaydet** ve **Kaydet ve İmzala** doktor kontrolündedir.

## Doldurulan ana form

| Bölüm | COMED alanları | Zorunluluk | Klinot davranışı |
|---|---|---:|---|
| Yakınması | Şikâyet | Evet | Metin varsa doldurur |
| Yakınması | Başlangıç sayısı; saat/gün/hafta/ay/yıl | Evet | Sayı ve birim açıkça söylenmişse doldurur |
| Yakınması | Öykü | Evet | Görüşme öyküsünü doldurur |
| Özgeçmiş | Özellik Yok | Evet | Yalnız açıkça “yok” denmişse işaretler |
| Özgeçmiş | Alışkanlık: Sigara/Alkol/Madde + açıklama | Hayır | Seçenek ve açıklamayı doldurur |
| Özgeçmiş | Kronik Hastalık | Koşullu | COMED lookup sonucunu seçer, açıklamayı ve sarı ekle düğmesini işler |
| Özgeçmiş | İlaç | Koşullu | COMED ilaç lookup sonucunu seçer ve ekler |
| Özgeçmiş | Alerji | Koşullu | COMED alerji lookup sonucunu seçer ve ekler |
| Özgeçmiş | Ameliyat | Koşullu | COMED ameliyat lookup sonucunu seçer ve ekler |
| Özgeçmiş | Özel Durumlar, Aşı, Cihaz, Kan Transfüzyon, Terapi | Koşullu | Her listeyi kendi lookup alanında ayrı ayrı işler |
| Özgeçmiş | Meslek | Hayır | COMED meslek lookup sonucunu seçer |
| Özgeçmiş | Eğitim | Hayır | Eğitim/Yok/Önlisans/İlköğretim/Lise/Lisans/Lisans Üstü seçeneklerinden seçer |
| Özgeçmiş | Medeni Durumu | Hayır | Belirtilmedi/Bekar/Evli seçeneklerinden seçer |
| Soygeçmiş | Özellik Yok | Evet | Yalnız açıkça “yok” denmişse işaretler |
| Soygeçmiş | Akraba | Koşullu | Erkek Kardeşi/Babası/Annesi/Kız Kardeşi/Diğer satırını seçer |
| Soygeçmiş | Hastalık | Koşullu | Diyabet/Guatr/Hipertansiyon/Kan Hastalığı/KAH/Malignite/Diğer sütununu seçer |
| Soygeçmiş | Açıklama, anne-baba akrabalığı | Koşullu | Popup açıklamasını kaydeder; akrabalık kutusunu eşler |
| Sistem Sorgusu | Serbest metin | Hayır | Metin varsa doldurur |
| Psikolojik Durum | Sakin/Üzgün/Ajite/Kaygılı/Agresif + açıklama | Hayır | Seçenekleri ve açıklamayı doldurur |
| Düşme Riski | Var/Yok | Evet | Yok’u doğrudan; Var’ı yalnız bütün zorunlu alt cevaplar varsa doldurur |
| Düşme Riski | Yaş grubu, hikâye, ilaç, bağımlılık, denge, görme, oryantasyon, genel sağlık | Var ise zorunlu | Açılan risk kartındaki sekiz cevabı eşler |
| Ağrı | Var/Yok | Evet | Var/Yok seçer |
| Ağrı | Bölge, açıklama, nitelik, ritim, başlangıç | Koşullu | Mevcut bilgileri ayrı alanlara doldurur |
| Ağrı | Skor | Koşullu | Doğrudan alan kilitli; COMED’in ayrı Ağrı Değerlendirme formu doktor kontrolündedir |
| Fizik Muayene | Kilo, Boy, Ateş, Nabız, KB-S, KB-D, SPO2 | Kilo/Boy/Nabız zorunlu işaretli | Görüşmede/veride varsa doldurur; VKİ ve VYA COMED tarafından hesaplanır |
| Fizik Muayene | Muayene Notu | Evet | Metin varsa doldurur |
| Tanılar | ICD lookup | Evet | Kodu yazar, gerçek COMED sonucunu seçmeden eklemez |
| Tanılar | Ayırıcı/Kesin/Ön Tanı | Evet | `differential/definitive/preliminary` değerini eşler |
| Tanılar | Taraf: Ayrım Yok/Sol/Sağ | Hayır | `none/left/right` değerini eşler |
| Tanılar | Ana Tanı, İlk Tanı Tarihi, Açıklama | Hayır | Ana tanı kutusunu, etkinse tarihi ve açıklamayı doldurur |
| İzlem ve Plan | Tedavi Notu | Evet | Tedavi ve kontrol notunu aynı klinik notta birleştirir |
| İzlem ve Plan | Dokuz tedavi planı seçeneği | Evet | Şemadaki geçerli seçeneği işaretler |
| İzlem ve Plan | Ameliyat planlanacak mı? | Evet | Evet/Hayır değerini işaretler |
| İzlem ve Plan | Kontrol Önerilme Durumu | Hayır | “Önerilmedi” anahtarını ters anlamıyla doğru eşler |
| Kontrol Notları | Geçmiş kartı | Salt okunur | Yeni giriş alanı değildir; kontrol notu Tedavi Notuna eklenir |
| Hasta Özel Notları | Yeni Ekle | Hayır | Muayene taslağı değildir; otomatik yazılmaz |

## Ayrı istem ekranları (doldurulur)

Bunlar ana muayene formunda değil, kartın alt araç çubuğundan açılan ayrı
ekranlardadır. Köprü ikisini de dolduruyor; son kontrol ve imza doktordadır.

| Ekran | Adres | Alan | Davranış |
| --- | --- | --- | --- |
| Hizmet İstem | `?app-action=action-order-procedure` | Hizmet adı, Uygulayan, Açıklama | Favoriler'de yoksa Genel sekmesinden arar; Uygulayan isteyen doktorla aynı seçilir. Radyolojide ek zorunlu alan çıkarsa istem doktora bırakılır |
| İlaç İstem | `?app-action=action-order-drug` | Ana İlaç, Günlük sıklık, İstem Notu | Arama kutusundan seçer; doz/veriliş yolu/uygulama COMED varsayılanında kalır. Sıklık yalnız söylendiyse ve 1-12 arasındaysa işaretlenir |

### Tetkik İstem ekranı — canlı ölçüm (22 Ekim 2026)

COMED'de istemler ÜÇ ayrı ekrana dağılmış:

| Ekran | Adres | Ne var |
| --- | --- | --- |
| Hizmet İstem | `?app-action=action-order-procedure` | EKG gibi işlemler |
| İlaç İstem | `?app-action=action-order-drug` | ilaçlar |
| **Tetkik İstem** | `?app-action=action-order-study` | **laboratuvar + radyoloji** |

"Tam Kan Sayımı katalogda yok" sonucunun sebebi buydu: yanlış ekranda aranıyordu.

Sol ağaç: Favoriler (paketler) · Laboratuvar · Radyoloji · Patoloji · Kardiyoloji.
Soldaki "Ara" kutusu GLOBAL DEĞİL, yalnız seçili paketin içinde arar.

Favori paketleri ve içerikleri:

| Paket | Tetkik | Tip |
| --- | --- | --- |
| adnan kaya kardiyoloji paketi | 21 | Laboratuvar |
| ANJİYO RUTİN | 19 | Laboratuvar |
| kısa biyo | 8 | Laboratuvar |
| Enzim | 2 | Laboratuvar |
| alt ekstremite doppler | 4 | Radyoloji |
| akciğer grafisi | 2 | Radyoloji |
| karotis | 1 | Radyoloji |
| Bt koroner / ekooo / karotis mrlar | 0 (boş) | — |

Akış: satırdaki onay kutusu işaretlenir → altta "Laboratuvar İstekleri" /
"Radyoloji İstekleri" paneli açılır → sağ altta "Ekle". Birden çok tetkik
aynı anda işaretlenip tek "Ekle" ile eklenebiliyor.

**Hemogram (796)** onay kutusu PASİF geliyor; işaretlenemez, atlanır.

Radyoloji istemlerinde "Acil" yanındaki açıklama kutusu zorunlu olabiliyor
(kırmızı nokta); doktor aciliyet belirtmediyse "Aciliyeti yok" yazılır.
"Dokümanları Doldurunuz" uyarısı çıkan tetkik hiç gönderilmez, doktora bırakılır.

#### Ad eşleştirme: model bilimsel ad yazar, COMED kısaltma kullanır

Canlı doğrulanan eşleşmeler:

| Gemini çıktısı | COMED kataloğu |
| --- | --- |
| Açlık Kan Şekeri | Açlık Kan Şekeri (AKŞ) |
| Alanin Aminotransferaz (ALT) | ALT (SGPT) |
| Aspartat Aminotransferaz (AST) | AST (SGOT) |
| C-Reaktif Protein (CRP) | CRP (Kantitatif) |
| Demir | Demir (Fe) |
| Total Demir Bağlama Kapasitesi (TDBK) | Total Demir Bağlama Kapasitesi (TIBC) |
| HDL Kolesterol | HDL-Kolesterol |
| Kreatinin | Kreatinin (Serum) |

Bu yüzden aday olarak hem tam ad, hem parantezsiz çekirdek, hem de
parantez içindeki kısaltma denenir; tire/boşluk sadeleştirilir.

### Hizmet İstem kataloğu — canlı ölçüm (22 Ekim 2026)

Aynı tetkikin nitelikli türevleri var, düz hali olmayabiliyor:

| Arama | Katalogda çıkan |
| --- | --- |
| elektrokardiogram | Elektrokardiogram (EKG) · 12 derivasyonlu yorumlama · evde çekim · trase monitorizasyonu · Fetal |
| ekokardiyografi | 3D · Fetal (kadın hastalıkları) · Stres — **düz "Ekokardiyografi" YOK** |
| tam kan sayımı / hemogram | **hiç sonuç yok** |
| akciğer grafisi | Akciğer Grafisi (İki Yön) · (Lateral Tek Yön) |

"İlk includes eşleşmesi" kuralı "EKO" için 3D ekokardiyografi seçiyordu.
Kural: tam hücre eşleşmesi kazanır; doktorun söylemediği niteleyici
(3D/Fetal/Stres/evde/trase/holter/efor/pediatrik/ambulatuar/yorumlama/
monitorizasyon) VETO; ilk hücresi kod olmayan satır (zaten eklenmiş istem)
aday değil; emin olunamazsa doktora bırakılır.

Kategori sekmeleri: Tümü · Genel · Favoriler (varsayılan Favoriler).
Arama kutusu placeholder'ı: "Ara".

### İlaç İstem ekranı — canlı ölçüm (22 Ekim 2026)

Hasta 22207363, goztepetest. Ölçülen gerçekler:

- Adres parametresi tek başına ekranı açıyor; co-button-İlaç İstem diye bir
  sekme düğmesi YOK. Beklemek 12 saniye boşa gidiyor.
- Arama kutusunun placeholder'ı: "Temel ilaçlar kategorisinde ara". Aynı
  ekranda alt araç çubuğunda "Ara" ve "İsteyen ara..." kutuları var; "ara"
  geçenleri elemek hedef kutuyu da eliyor.
- .co-input__label içinde "Ana İlaç" etiketi YOK; etiketle aramak tutmaz.
- Öneri listesi: .autocomplete__item (10 sonuç).
- Görünür co-button-Ekle sayısı 2, co-button-Vazgeç 1 → pencere içindeki
  düğme "Vazgeç" hizasından seçilmeli.

#### Aynı etken maddenin onlarca formu var

"parol" araması: PAROL COLD, PAROL HOT, PAROL HOT Pediatrik, PAROL IV Flakon
(iki ambalaj), PAROL Plus Süspansiyon, PAROL PLUS Tablet, PAROL Süspansiyon,
PAROL Tablet 500 mg (iki ambalaj).

"İlk başlayan eşleşme" kuralı PAROL COLD'u seçiyordu: grip ilacı,
fenilpropanolamin içerir, yaşlı hipertansifte kontrendike. Bu yüzden puanlama
ve veto kullanılıyor; emin olunamazsa ilaç HİÇ eklenmiyor.

| Doktor ne dedi | Karar (canlı doğrulandı) |
| --- | --- |
| Parol, 500 mg | secilir: PAROL Tablet 500 mg |
| Parol (doz yok) | secilir: PAROL Tablet 500 mg (ağızdan form varsayılan) |
| Parol Cold | secilir: PAROL COLD (doktor açıkça istedi) |
| Parol, 325 mg | doktora bırakılır (325 mg yalnız COLD'da var) |
| Parol süspansiyon | doktora bırakılır |
| Bilinmeyen ad | doktora bırakılır |

## Doldurulmayan ayrı iş akışları

Konsültasyon/diyet/bakım/kan ürünü/kök hücre istemleri,
reçeteler, yatış-taburculuk, ameliyat raporu, epikriz çıktıları, onamlar,
E-Rapor, EKG, TAVI, anjiyografi ve diğer kurumsal formlar ana muayene
formundan ayrı yetki ve iş akışlarıdır. Ses kaydından otomatik tetiklenmezler.

## POST davranışı

v2.8.2 hibrit çalışır. Klinot aynı protokol için daha önce başarıyla yakalanmış COMED
gövde şemasını güncel klinik taslakla eşleyebiliyorsa izin listesindeki
`saveDocumentProcesses` ve doğrulanabildiğinde `savevisitdiagnoses` uçlarına POST
eder. Ana POST şablonu yoksa seçili açık hasta kartını eklenti üzerinden doldurur;
böylece yeni protokoller öğrenme kaydı olmadan da MVP'de hazırlanabilir. Son kontrol,
kaydetme ve imza doktora aittir. Lookup kimliği doğrulanamayan kayıtlar uydurulmaz.

COMED parola, çerez ve oturum başlıkları Klinot sunucusuna gönderilmez. Başlıklar
yalnız açık COMED sayfasının kapalı belleğinde kullanılır; imza ve silme uçları
yürütücü izin listesinin dışındadır.

Sistem Sorgulama ayrı bir COMED belgesidir. Sekiz sistem grubu ile komplikasyon seçimi
tam yüklenmeden işlem yapılmaz. Görüşmede bulgu yoksa `Özellik Yok`/`Komplikasyon Yok`
seçilir; dokuz grubun her birinde gerçek checkbox işaretli olduğu doğrulanınca sağ-alt
`Kaydet` düğmesine basılır ve belge kapanmadan ana forma dönülmez. Ana muayene
`Kaydet ve İmzala` düğmesine otomatik basılmaz.

## Veri bütünlüğü

“Boş alan kalmasın” hedefi, görüşmede bulunan bütün verinin doğru yere taşınmasıdır.
Görüşmede bulunmayan klinik bilgiler uydurulmaz. MVP'nin zorunlu kontrol alanlarında
kullanılan operasyonel varsayılanlar `fallback_fields` ve aktarım debug kaydında açıkça
gösterilir; doktor imzadan önce bunları kontrol eder. Tanı, kilo ve boy gibi klinik olarak
uydurulamayacak değerler ancak görüşmeden ya da mevcut COMED kaydından gelebilir.
