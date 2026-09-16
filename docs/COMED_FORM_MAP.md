# COMED Muayene Formu Alan Haritası

Bu harita Göztepe COMED test ortamındaki `patient-clinical-card` ekranı üzerinde
16 Eylül 2026 tarihinde yapılan DOM ve etkileşim incelemesine dayanır. Klinot
alanları doldurur; **Kaydet** ve **Kaydet ve İmzala** doktora bırakılır.

## Ana muayene alanları

| Bölüm | Alan/seçenek | COMED zorunlu işareti | Klinot aktarımı |
|---|---|---:|---|
| Yakınması | Şikâyet | Evet | Otomatik |
| Yakınması | Başlangıç değeri; saat/gün/hafta/ay/yıl veya tarih | Evet | Süre varsa otomatik |
| Yakınması | Öykü | Hayır | Otomatik |
| Özgeçmiş | Özellik Yok | Evet | Açıkça söylendiyse otomatik |
| Özgeçmiş | Alışkanlık: Sigara, Alkol, Madde + açıklama | Hayır | Kategori açıkça geçiyorsa otomatik |
| Özgeçmiş | Kronik Hastalık, İlaç, Alerji, Ameliyat | Hayır | COMED lookup doğrulaması gerektiği için doktor kontrolü |
| Özgeçmiş | Özel Durumlar, Aşı, Cihaz, Kan Transfüzyon, Terapi | Hayır | Doktor kontrolü |
| Özgeçmiş | Meslek, Eğitim, Medeni Durumu: Belirtilmedi/Bekar/Evli | Hayır | Metin/seçenek varsa otomatik |
| Soygeçmiş | Özellik Yok / Görüldü | Evet | Açıkça söylendiyse otomatik |
| Soygeçmiş | Erkek kardeş, baba, anne, kız kardeş, diğer | Hayır | Doktor kontrolü |
| Soygeçmiş | Diyabet, Guatr, Hipertansiyon, Kan Hastalığı, KAH, Malignite, Diğer | Hayır | Doktor kontrolü |
| Sistem Sorgusu | Serbest metin | Hayır | Otomatik |
| Psikolojik Durum | Sakin, Üzgün, Ajite, Kaygılı, Agresif + açıklama | Hayır | Şimdilik doktor kontrolü |
| Düşme Riski | Var/Yok | Evet | Yok ise otomatik; Var ise tüm alt maddeler biliniyorsa otomatik |
| Düşme Riski | Yaş (otomatik), düşme hikâyesi, ilaç, bağımlılık, yürüyüş/denge, görme, oryantasyon, genel sağlık | Var seçilince zorunlu | Tam veri varsa otomatik |
| Ağrı | Var/Yok, skor, açıklama | Evet | Otomatik |
| Ağrı | Nitelik: Keskin, Bastırıcı, Kolik, Ezici, Dolgunluk, Saplanıcı, Künt, Yanıcı, Stabilize | Hayır | Görüşmede geçiyorsa otomatik |
| Ağrı | Ritim: Sürekli/Aralıklı; başlangıç süresi | Hayır | Görüşmede geçiyorsa otomatik |
| Fizik Muayene | Kilo, Boy, Ateş, Nabız, KB-S, KB-D, SPO2 | Nabız zorunlu | Otomatik; VKİ ve VYA COMED tarafından hesaplanır |
| Fizik Muayene | Muayene Notu | Evet | Otomatik |
| Tanılar | ICD arama; Ayırıcı/Kesin/Ön Tanı; taraf: Ayrım Yok/Sol/Sağ; Ana Tanı; tarih; açıklama | Evet | ICD sonucu COMED listesinden doğrulanır ve forma eklenir |
| İzlem ve Plan | Tedavi Notu | Evet | Otomatik |
| İzlem ve Plan | Ayaktan/Yatarak takip, Ayaktan/Yatarak cerrahi, Rehabilitasyon, Palyatif, Günübirlik, Allojenik, Kemik İliği Nakli | Evet | Görüşmede açıkça seçilebiliyorsa otomatik |
| İzlem ve Plan | Ameliyat planlanacak mı: Evet/Hayır | Evet | Açıkça söylendiyse otomatik |
| İzlem ve Plan | Kontrol önerilmedi anahtarı, kontrol notları | Hayır | Önerilmedi anahtarı otomatik; not ekleme doktor kontrolü |
| Hasta Özel Notları | Yeni Ekle | Hayır | Hasta notu olduğu için otomatik aktarılmaz |

## Ana form dışındaki COMED özellik grupları

Sağdaki/alt araç menülerinde ayrıca şu modüller vardır: tetkik, ilaç, hizmet,
konsültasyon, diyet, bakım, kan ürünleri ve kök hücre istemleri; reçete türleri;
ameliyat/yatış/taburculuk; epikriz ve onam çıktıları; E-Rapor, EKG, TAVI,
anjiyografi, FIB-4, hasta profili ve diğer kurumsal formlar. Bunlar muayene
formunun parçası değildir ve ayrı iş akışları/izinler gerektirir; ses kaydından
otomatik tetiklenmez.

## Güvenlik sınırı

Klinot yalnız görüşmede açıkça bulunan veriyi forma taşır. COMED lookup seçimi
gerektiren öğeler listede doğrulanmadan eklenmez. Uzantı hiçbir zaman otomatik
imza atmaz; son **Kaydet** / **Kaydet ve İmzala** kararı doktordadır.
