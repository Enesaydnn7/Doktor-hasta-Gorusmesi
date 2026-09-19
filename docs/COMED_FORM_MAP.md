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

## Doldurulmayan ayrı iş akışları

Tetkik/ilaç/hizmet/konsültasyon/diyet/bakım/kan ürünü/kök hücre istemleri,
reçeteler, yatış-taburculuk, ameliyat raporu, epikriz çıktıları, onamlar,
E-Rapor, EKG, TAVI, anjiyografi ve diğer kurumsal formlar ana muayene
formundan ayrı yetki ve iş akışlarıdır. Ses kaydından otomatik tetiklenmezler.

## POST davranışı

Klinot uzantısı açık ve yetkili COMED sekmesinde alanları doldurur. Doktor COMED’in
**Kaydet** düğmesine bastığında COMED kendi `saveDocumentProcesses`, profil ve tanı
kayıt isteklerini üretir. Uzantı COMED parolasını veya oturum anahtarını okumaz,
saklamaz ve otomatik imza atmaz.

## Veri bütünlüğü

“Boş alan kalmasın” hedefi, görüşmede bulunan bütün verinin doğru yere taşınmasıdır.
Görüşmede bulunmayan vital bulgu, muayene, düşme riski veya özgeçmiş bilgisi uydurulmaz;
bu alanlar `missing_required` listesinde doktorun tamamlaması için açıkça gösterilir.
