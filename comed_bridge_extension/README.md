# Klinot COMED Köprüsü

Bu Manifest V3 Chrome eklentisi, Göztepe COMED test ekranı ile Klinot arasındaki
kurumsal-ağ köprüsüdür.

1. Chrome `chrome://extensions` ekranında geliştirici modunu açın.
2. **Paketlenmemiş öğe yükle** ile bu klasörü seçin.
3. Eklenti penceresinde Klinot kullanıcı adı/şifresiyle bağlanın.
4. `http://goztepe.comedtest.mlpcare.com/tr-tr/medical/` iş listesini açın.

Köprü iş listesini mobil uygulamaya eşitler. Mobilde **COMED'e aktar** denince
bekleyen taslağı yalnız aynı protokole ait açık tıbbi kartta doldurur. Doktorun
`Kaydet` düğmesine basması COMED'in kendi `forms/document/saveDocumentProcesses`
POST akışını çalıştırır. Köprü COMED oturum tokenını okumaz, saklamaz veya Klinot
sunucusuna göndermez; otomatik imza da atmaz.

ICD seçimi ve COMED'in kırmızı noktalı zorunlu alanlarından görüşmede bulunmayanlar
doktor kontrolünde tamamlanır. Durum mobil uygulama ve admin panelinde
`sırada → alanlar dolduruluyor → kontrol bekliyor → tamamlandı` şeklinde izlenir.
