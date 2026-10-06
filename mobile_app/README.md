# Klinot mobil

Doktor ile hastanın yüz yüze görüşmesinde telefonun masanın ortasında durduğu senaryo için Flutter MVP.

## Özellikler

- Doktor/yönetici girişi ve cihazda güvenli oturum saklama
- Görünür kayıt durumu, canlı mikrofon seviyesi, süre, duraklat/devam ve iptal
- AAC/M4A mono kayıt, otomatik kazanç ve gürültü azaltma
- Yalnızca OpenAI STT ile arka planda metne dönüştürme
- Görüşme metnini ve analiz ilerlemesini doktora göstermeden arka planda işleme
- İşlem tamamlandığında doktor epikrizi ve önerileri
- Ses, transkript ve üç raporu mevcut web yönetim paneline kaydetme

## Çalıştırma

Flutter SDK kurulduktan sonra:

```powershell
cd mobile_app
flutter pub get
flutter run --dart-define=API_BASE_URL=https://doktor-hasta-gorusmesi.onrender.com
```

Yerel backend için Android Emulator adresi `http://10.0.2.2:8000`, fiziksel cihaz için bilgisayarın yerel ağ IP adresidir. HTTP kullanılırsa Android/iOS geliştirme güvenlik ayarları ayrıca yapılmalıdır; canlı HTTPS adresinde gerekmez.

## Kalite kontrol

```powershell
flutter analyze
flutter test
```

Android imzalı AAB ve iOS TestFlight dağıtımı için kuruma ait paket kimliği, mağaza hesapları, ikonlar, gizlilik metni ve release imzası ayrıca tanımlanmalıdır.
