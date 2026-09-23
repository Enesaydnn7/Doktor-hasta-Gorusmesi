# Klinot COMED Köprüsü

Bu Manifest V3 Chrome eklentisi, Göztepe COMED test ekranı ile Klinot arasındaki
kurumsal-ağ köprüsüdür.

## Kurulum

1. Bu `comed_bridge_extension` klasörünü bilgisayara indirin. GitHub ZIP'i
   kullanıyorsanız önce ZIP'i klasöre çıkarın.
2. Chrome adres çubuğuna `chrome://extensions` yazın.
3. Sağ üstten **Geliştirici modu** seçeneğini açın.
4. **Paketlenmemiş öğe yükle** düğmesine basın.
5. İçinde `manifest.json` bulunan `comed_bridge_extension` klasörünü seçin.
6. Chrome araç çubuğundaki yapboz simgesinden **Klinot COMED Köprüsü** eklentisini
   sabitleyin ve açın.
7. Eklentide API adresini değiştirmeden, mobil Klinot'a girdiğiniz **Klinot kullanıcı
   adı ve şifresiyle** “Köprüyü bağla” deyin. Buraya COMED parolası yazılmaz.
8. Kurumsal Wi-Fi'da `http://goztepe.comedtest.mlpcare.com/tr-tr/medical/hasta-tibbi-karti`
   iş listesini açın ve COMED'e kendi hesabınızla giriş yapın.
9. İş listesi sayfasını bir kez yenileyin. Sağ altta “Klinot · 1 hasta iş listesine
   eşitlendi” bildirimi görünmelidir.
10. Telefonda Klinot iş listesindeki yenile simgesine basın.

## Test isteği izleme

Eklenti açılır penceresindeki **COMED test isteği izleme** seçeneği, yalnız
`goztepe.comedtestapi.mlpcare.com` alan adına giden GET/POST isteklerinin URL,
JSON gövdesi, yanıt durumu ve JSON yanıtını Klinot tanı kaydına gönderir. İstek
başlıkları, çerezler, COMED parolası ve oturum/token alanları okunmaz veya
saklanmaz. Bu seçenek gerçek COMED payload haritası çıkarılırken açık tutulur;
test tamamlandıktan sonra kapatılabilir.

COMED'deki **Göreve Git** düğmesi normal bir bağlantı olmadığı için köprü tablo
satırını doğrudan okur. Göreve ilk kez girildiğinde hasta kartı kimliği de otomatik
tamamlanır. Liste ve kart bilgileri yalnız aynı Klinot kullanıcısına gösterilir.

Köprü iş listesini mobil uygulamaya eşitler. Mobilde **COMED'e aktar** denince
bekleyen taslak için doğru protokolün **Göreve Git** düğmesini açar. v2.8.1 hibrit
çalışır: aynı protokol için başarılı olduğu doğrulanan `saveDocumentProcesses`
gövdesi varsa seçili protokol kimliği tekrar doğrulanarak COMED test API'sine POST
edilir. Böyle bir öğrenilmiş şablon yoksa aktarım durmaz; açık hasta kartındaki
muayene, profil, soygeçmiş, düşme riski, ağrı, tanı ve izlem-plan alanları eklenti
tarafından taslak olarak doldurulur. Ayrı Sistem Sorgulama belgesi de kendi içinde
doldurulup sağ alttaki kendi `Kaydet` düğmesiyle kapatılır; dokuz zorunlu gruptan biri
işaretlenemezse ana muayeneye geçilmez ve hata admin debug kaydına yazılır. Ana muayene
kaydı ve imza doktora bırakılır.

POST yürütücüsü yalnız izin listesindeki kayıt uçlarını kabul eder; imza, silme ve
başka hasta/protokol gövdelerini reddeder. COMED'in uygulama/oturum başlıkları yalnız
sayfa belleğindeki kapalı yürütücüde kullanılır; değerleri DOM'a, eklenti deposuna veya
Klinot sunucusuna çıkarılmaz. Otomatik imza yoktur.

Lookup/ICD seçimi yalnız COMED'in ekranda sunduğu gerçek sonuç eşleşirse yapılır;
eşleşme yoksa veri uydurulmaz. Görüşmede bulunmayan kırmızı noktalı alanlar doktor
kontrolünde tamamlanır. Admin panelindeki debug kartı POST, eklenti, operasyonel
varsayılan ve eksik alanları ayrı listeler. Durum mobil uygulama ve admin panelinde
`sırada → POST/form hazırlanıyor → kontrol bekliyor → tamamlandı` şeklinde izlenir.
