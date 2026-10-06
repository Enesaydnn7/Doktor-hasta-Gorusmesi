# Klinot COMED Köprüsü kurulumu

Kurulacak dosya: `klinot-comed-bridge-v2.11.0.zip`

Android uygulaması: `Klinot-v2.11.0.apk`

1. ZIP dosyasını bilgisayarda bir klasöre çıkarın.
2. Chrome adres çubuğunda `chrome://extensions` sayfasını açın.
3. Sağ üstten **Geliştirici modu** seçeneğini etkinleştirin.
4. **Paketlenmemiş öğe yükle** düğmesine basın.
5. ZIP'ten çıkan, içinde `manifest.json` bulunan klasörü seçin.
6. Eklentiyi yapboz menüsünden sabitleyin.
7. COMED'e Chrome'da normal COMED hesabınızla giriş yapın. Oturum kapanmışsa doktor panelindeki aktarım sizi girişe götürür ve girişten sonra hedef karta otomatik devam eder.
8. Eklentiyi açıp mobil Klinot'ta kullandığınız **Klinot kullanıcı adı ve şifresiyle** bağlayın. COMED parolasını eklentiye yazmayın.
9. Göztepe COMED iş listesini yenileyin. Sağ altta yeşil Klinot eşitleme mesajı görünmelidir.
10. Telefonda Klinot uygulamasındaki COMED iş listesinin yenile düğmesine basın.

Testten sonra son kaydedilmemiş Klinot taslağını geri almak için ilgili COMED hasta kartındayken eklentiyi açıp **Bu karttaki Klinot taslağını temizle** düğmesine basın. Sistem Sorgulama önceki seçimine döndürülür, ardından kart yenilenerek diğer kaydedilmemiş alanlar temizlenir.

Mobil uygulama, doktor web paneli ve eklentide aynı doktor hesabını kullanın. Her doktor yalnızca kendi COMED iş listesini ve raporlarını görür. Yönetici hesabı mobil uygulama ve eklentiye kabul edilmez; yalnızca `/admin` paneli içindir.

Test doktor hesapları:

- `adnan.kaya;enes.aydin1|tracer` / `1`
- `sami.sokucu;enes.aydin1|tracer` / `1`

Yönetim hesabı: `admin` / `admin`.

Chrome ZIP dosyasını doğrudan yüklemez; önce klasöre çıkarmak zorunludur.
