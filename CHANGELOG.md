## Doktor paneli ses kaydı — 10 Kasım 2026 (v3.0.0 üstü, eklenti/APK değişmedi)

- Doktor paneline mobil uygulamadaki akışın aynısı eklendi: iş listesinden
  hasta seç → **Kaydı başlat** → **Durdur ve analiz et**. Ses aynı arka plan
  STT işine (`/doctor/api/transcriptions`), analiz aynı akışa
  (`/doctor/api/analyze/stream`) gider; kayıt doktora ve seçili COMED
  hastasına bağlanır, rapor açılır, "COMED'e aktar" aynı düğmedir.
- Mobil ve panel aynı `_start_transcription` / `_transcription_status`
  çekirdeğini kullanıyor. Kayıt kaynağı `doctor_web`.
- Çubuk kendi dosyalarında (`doctor_recorder.js/.css`), önbellekteki eski
  `doctor.css` ile stilsiz kalmasın diye.

## v3.0.0 — 5 Kasım 2026

### Mağazaya çıkacak sürüm; main ve mvp aynı

- Günlük eklenti ile Chrome Web Store paketi birleşti: ad **Klinot**, simgeler,
  açılır pencerede "HBYS" dili, manifestte localhost yok.
- `store_assets/chrome_magaza_paketi` ve `store_assets/klinot-magaza-v3.0.0.zip`
  bugünkü kodla (v2.38.5–v2.38.6 COMED düzeltmeleri) yeniden üretildi.
- Canlı doğrulama (kayıt #4, uzun diyalog): düşme riski Var, Bastırıcı,
  Kaygılı, Penisilin, Apendektomi, meslek/eğitim, Öykü eki, tedavi notu;
  istemler EKG, EKO, akciğer grafisi, 7 tetkik, Parol, Allergodil — her biri
  bir kez. Soğuk algınlığı diyaloğu (#5): konuşulmayan alanlar boş kaldı,
  Aspirin → Asetilsalisilik asit.

## v2.38.6 — 5 Kasım 2026

### COMED aktarımı: yanlış katalog eşleşmesi

- Özgeçmiş aramalarında ilk "içeren" satır seçilmiyor; önce birebir, sonra
  başı eşleşen, sonra kelime başı eşleşen satır seçiliyor. Canlıda "Aspirin"
  → "Çapraz bağlı hemoglobin diaspirin", "Penisilin" → "Benzilpenisilin"
  seçiliyordu. Eşleşme yoksa kalem Öykü'ye yazılıyor.
- "Aspirin" alerjisi katalogdaki "Asetilsalisilik asit" adıyla aranıyor.
- Ağrı niteliği seçimleri aktarım sonunda yeniden kontrol ediliyor
  ("Bastırıcı" seçili kalmıyordu).
- Mağaza paketi (`store_assets/chrome_magaza_paketi`) değişmedi.

## v2.38.5 — 5 Kasım 2026

### COMED aktarımında eksik kalan alanlar

- Düşme riski: başlıktaki bitişik yaş ("29yıl22.10.1997") okunuyor; artık
  yanlışlıkla "Yok" seçilmiyor.
- Ağrı niteliği, ritim, psikolojik durum ve medeni hal: tekrar aktarımda
  seçim kalkmıyor (aç/kapa düğmesine ikinci kez basılmıyor).
- Eğitim seçeneği doğru listeden seçiliyor.
- Ameliyat adları COMED karşılığına çevriliyor (Apandisit → Apendektomi vb.).
- Özgeçmişte HBYS listesinde bulunmayan kalemler (ilaç, cihaz, terapi, diyet,
  kan nakli…) Öykü'nün sonuna "Özgeçmiş (HBYS listesinde yok)" diye yazılıyor;
  ilk kelimeyle yanlış kalem seçme kaldırıldı.
- Tedavi notuna verilen ilaçlar ve kontrol notu ekleniyor.
- Doktor panelinde kalıcı test kaydı: "COMED tam test · Göğüs ağrısı + rinit"
  (ses kaydıyla, `demo_records/`).

## v2.39.0 — 4 Kasım 2026

### Chrome Web Store'a hazırlık (liste dışı yayın)

- Eklentinin adı **Klinot**; açıklama ve açılır pencerede kurum/sistem adı
  geçmiyor (HBYS deniyor).
- Klinot logosundan simgeler (`icons/16-128`), açılır pencere başlığında logo.
- Paketten yerel geliştirme adresleri (localhost, 127.0.0.1) çıkarıldı.
- Sunucuda herkese açık **/gizlilik** sayfası (mağazanın istediği gizlilik
  politikası linki).
- `store_assets/`: mağaza simgesi, ekran görüntüsü (1280×800), küçük tanıtım
  görseli (440×280), mağaza ve izin metinleri (`MAGAZA_METINLERI.md`).

## v2.38.4 — 4 Kasım 2026

v2.38.3'teki "Protokol" sekmesi tıklaması tutmuyordu: sekme `.switch-toggle`
içinde gizli `<input>` + `<label class="switch-toggle-label">` çifti; ilk sürüm
`<span>`'a basıyordu. Artık LABEL'a basılıyor ve `input.checked` ile
doğrulanıyor. Adım aktarımın EN SONUNA ("Son alanlar doğrulanıyor"dan sonra,
"Aktarım bitti"den önce) taşındı. Canlı: Tümü 14 satır → Protokol 3 satır.

## v2.38.3 — 4 Kasım 2026

Aktarım bitince Tanılar (ICD-10) listesinde **Protokol** sekmesine basılıyor
(`showProtocolDiagnoses`). "Tümü"de hastanın eski protokollerinin onlarca
tanısı görünüyor, doktor "çok fazla ICD kodu yazılmış" sanıyordu. Sekme
bulunamazsa dokunulmaz. Canlı test bu sürümde yapılamadı.

## v2.38.2 — 4 Kasım 2026

Eklenti açılır penceresinin başlığına sürüm rozeti eklendi
(`chrome.runtime.getManifest().version`), hangi eklentinin yüklü olduğu
görülsün.

## v2.38.1 — 3 Kasım 2026

### Allergodil eklenmiyordu: Türkçe noktasız ı

Doktorun aktarımında "Allergodil burun spreyi: birden çok form var" diye
atlandı. Sebep: COMED ürünü "ALLERGODIL" yazıyor; `toLocaleLowerCase("tr-TR")`
bunu "allergodıl" (noktasız ı) yapıyor, "allergodil" ile hiç eşleşmiyordu.
İlaç puanlamasında iki taraf da ı → i ile katlanıyor.

Canlı test (hasta 22207362, 09:26): ALLERGODIL Burun Spreyi, Günde 2 kez —
COMED İlaç İstem listesine düştü.

## v2.38.0 — 3 Kasım 2026

- **EKO → Transözofageal ekokardiografi** (kesin kullanıcı kuralı; v2.37.1'deki
  3D geri alındı). Hizmet İstem penceresi EKG ile aynı akışla doluyor
  (v2.37.0'da canlı doğrulandı).
- **Allergodil.** Model/ses dökümü "Alergodil" yazıyordu, COMED'de arama sonuç
  vermiyordu. Sunucu adı "Allergodil burun spreyi"ne çeviriyor; prompt'a
  COMED yazımı eklendi.
- **İlaç araması:** aramaya yalnız marka yazılıyor ("Allergodil burun spreyi"
  aramasında COMED sonuç vermiyor), puanlama tam adla. Doktorun söylediği
  yerel form (sprey, damla, krem…) üründe varsa +20; virgülle biten ad
  ("…burun spreyi, çözelti") tam eşleşme sayılıyor. Allergodil böylece
  eşiği (120) geçiyor.
- Canlı COMED testi bu sürümde yapılamadı (oturum yok).

## v2.37.1 — 3 Kasım 2026

Doktorun isteği: düz "EKO" → COMED'deki **3D ekokardiyografi** (önceden
Transözofageal ekokardiografi). Yalnız sunucu değişti
(`comed_integration.COMED_EKO_NAME`); eklenti aynı.

## v2.37.0 — 26 Ekim 2026

### Hizmet İstem: EKG'den sonra EKO hep düşüyordu (canlıda bulundu)

Doktorun aktarımında EKO "Hizmet İstem'de ek zorunlu alan istiyor" diye
atlandı; tek başına denenince ekleniyordu. Canlı COMED'de adım adım ölçülen
sebepler:

1. **Aramasız tıklama.** Bir istem eklendikten sonra favori listesindeki
   satıra aramasız basınca pencere açılıp 0,5 sn içinde kapanıyor. Artık her
   hizmet ÖNCE aranıyor, sonra tıklanıyor.
2. **Eski pencere.** İkinci hizmette önceki pencerenin "Vazgeç"i ekranda
   kaldığı için "açıldı" kontrolü anında geçiyordu. Artık yeni pencerenin boş
   "Uygulayan" alanıyla gelmesi bekleniyor.
3. **"Ekle" geç etkinleşiyor.** Pasif görülürse 8 sn'ye kadar bekleniyor.
4. **Yanlış satır.** Tam ad eşleşmesi alttaki istem listesindeki eski
   "Hizmet Elektrokardiogram (EKG)" satırını yakalıyordu. Artık yalnız katalog
   satırları (ilk hücre kod) eşleşir.

### Hata: istem gerekçesi "Psikolojik Durum" açıklamasını eziyordu

İstem penceresinde "Açıklama" kutusu yok; `byPlaceholder("Açıklama")` arkadaki
kartın İLK Açıklama alanını — Psikolojik Durum açıklamasını — buluyordu. Her
hizmet isteminin gerekçesi oraya yazılıyordu. Gerekçe yazımı kaldırıldı
(zorunlu değil).

### Canlı test (hasta 22207363)

EKG + EKO (gerekçeli): iki kez arka arkaya, her seferinde Hizmet İstem
listesi tam +2. 11 istemli tam akış: Hizmet +2 (EKG, Transözofageal
ekokardiografi), Tetkik +8; atlanan yalnız Hemogram (COMED'de pasif).

## v2.36.1 — 26 Ekim 2026

### Doktor "EKO" derse COMED'deki EKO eklenir

Doktorun isteği: "eko derse hemen bunu yazsın, eklesin." CANLI ÖLÇÜM: Hizmet
İstem'de "eko" araması yalnız **Transözofageal ekokardiografi** (kod 10782,
SUT 700610) döndürüyor; düz "Ekokardiyografi" katalogda yok. Sunucu düz
EKO / Ekokardiyografi adını bu kaleme çeviriyor
(`comed_integration._comed_service_name`). Stres/3D/fetal gibi nitelikli
EKO'lar olduğu gibi kalır. Eklenti değişmedi.

Canlı test 16:32: istem Hizmet İstem listesine düştü.

## v2.36.0 — 26 Ekim 2026

### Her istem TEK ekrana gider

Doktorun isteği: "EKO ve EKG Hizmet İstem'de, akciğer grafisi Tetkik
İstem'de olacak; bir şey hem hizmette hem tetkikte alınmayacak."

- Model her istemin ekranını yazıyor: `screen: "hizmet" | "tetkik"`
  (laboratuvar + radyoloji → tetkik; EKG, EKO, efor, holter, endoskopi gibi
  işlemler → hizmet).
- Sunucu (`comed_integration._service_screen`) kullanıcı kuralını sabitliyor:
  EKG/EKO her zaman hizmet, grafi/röntgen her zaman tetkik — model yanlış
  etiketlese de.
- Köprü: `tetkik` istemleri Hizmet İstem'e hiç sokulmuyor; `hizmet` istemi
  bulunamazsa Tetkik'e devredilmiyor, "Hizmet İstem'de bulunamadı — doktor
  tamamlamalı" diye rapor ediliyor. Ekranı belirsiz eski kayıtlar eski yoldan.
- **Neden:** CANLI ÖLÇÜM — Hizmet İstem kataloğunda laboratuvar da var
  (CRP L101850). "Önce Hizmet'te dene" kuralı CRP'yi yanlış ekrandan ekliyordu.

### ALT, AST, AKŞ sessizce kayboluyordu

Köprü Hizmet İstem'de yalnız **ilk 8** istemi deniyordu (`slice(0, 8)`);
11 istemli görüşmede 9.–11. (ALT, AST, AKŞ) atlanan listesine bile
yazılmadan düşüyordu. Sınır kaldırıldı (üst sınır sunucuda 25).

### Prompt

Ses dökümü hataları için örnekler eklendi ("tromponin", "CK-MP", "alete",
"aset'e", "promoni").

### Canlı test (hasta 22207363, 16:20)

11 istem: EKG Hizmet'ten; CRP, Kreatinin, ALT, AST, AKŞ, Troponin I, CK-MB,
Akciğer Grafisi Tetkik'ten — COMED listesinden doğrulandı, her biri tek kez.
Atlanan: Hemogram (COMED'de pasif), Ekokardiyografi (katalogda düz hali yok).

Not: Hizmet İstem ekranının alt listesi Hizmet + Laboratuvar + Radyoloji
istemlerinin hepsini gösterir; Tetkik İstem ekranınınki yalnız Laboratuvar
+ Radyoloji. Aynı tetkiğin iki ekranda görünmesi çift istem DEĞİLDİR.

## v2.35.0 — 26 Ekim 2026

### İstemler sabit sırayla, her ekran kapanarak

Doktorun isteği: önce muayene formu, sonra **Hizmet İstem → İlaç İstem →
Tetkik İstem**. İstem bölümü `fillFormDraft`'ın ortasından alınıp ayrı bir
`fillOrders` fonksiyonuna taşındı ve formun **en sonuna** kondu. Her istem
türü bitince ekran kapatılıp karta dönülüyor; önceden ekranlar üst üste
biniyor, doktor sonrakini göremiyordu.

### Gerçek test: üretim kodu canlı COMED'de

`scripts/live_order_test.py` eklendi. content.js'ten `fillOrders`'ı ve
kullandığı 53 bildirimi **dosyadan birebir çıkarıp** canlı COMED sayfasında
çalıştırılabilir paket yapıyor. Elle kopyalama yok; üretim kodu değişirse
test de değişir. (v2.32.0'daki ilaç hatası kopyanın üretim koduyla
ayrışmasındandı.)

Test diyaloğu (EKG, EKO, akciğer grafisi, tam kan, CRP, troponin + 5 ilaç)
canlı backend'den geçirildi, çıkan veri bu paketle hasta 22207363'te
koşturuldu. İlk koşu **6 istemden 1**'ini ekledi; aşağıdaki hatalar o
koşulardan bulundu.

### Canlıda bulunan ve düzeltilen hatalar

1. **EKG "istem penceresi açılmadı".** Hizmet İstem ilk açıldığında liste
   yeniden çiziliyor; eşleştiricinin bulduğu satır DOM'dan kopuyor, kopuk
   satıra basmak hiçbir şey açmıyor. Tek başına denenince pencere 0,5 sn'de
   açılıyordu. Açılmazsa satır yeniden bulunup bir kez daha basılıyor.
2. **Akciğer Grafisi / Troponin Hizmet İstem'de takılıyordu.** İkisi de Hizmet
   kataloğunda da var ama orada radyoloji/laboratuvar ek alanı istiyor.
   Artık vazgeçilmiyor, **Tetkik İstem'e devrediliyor**; orada varsayılan
   açıklamayla ekleniyor.
3. **Tetkik ekranı liste görünümüne düşüyordu.** "Ekle"den sonra ekran
   favori ağacı olmayan istem LİSTESİ görünümüne dönebiliyor; sonraki 8 paket
   "menüde görünmüyor" diye **sessizce** atlanıyordu. Artık
   "Yeni Tetkik İstem" ile ekleme görünümüne dönülüyor ve atlanma loglanıyor.
4. **İkinci paketten itibaren tikler kaydedilmiyordu.** Bir paketin
   "Ekle"sinden sonra onay kutusu görünüşte tikleniyor ama alt istek paneli
   açılmıyor, "Ekle" pasif kalıyor. İstem gönderilen her paketten sonra
   Tetkik ekranı kapatılıp **taze açılıyor**.
5. ⚠️ **"Eklendi" yalan söylüyordu.** Hata çıkmaması kaydedildiği anlamına
   gelmiyordu: tam koşuda sayaç "3 tetkik eklendi" dedi, COMED'in istem
   listesine tek satır düşmedi. Başarı artık **COMED istem listesine yeni
   satır düşmesiyle** ölçülüyor; düşmezse "Ekle'ye basıldı ama listeye
   düşmedi — doktor kontrol etmeli" yazılıyor.

Ayrıca paket başlığı ("Favoriler : …") seçilen pakete geçene kadar
bekleniyor; başarısız paketin tikleri sonrakine karışmasın diye kaldırılıyor.

### Son koşu — COMED listelerinden bağımsız doğrulandı (14:42:53 → 14:44:03)

| Ekran | Kaydedilen |
| --- | --- |
| Hizmet İstem | Elektrokardiogram (EKG) |
| Tetkik İstem | CRP (kantitatif), Troponin I, Akciğer Grafisi (İki Yön) |
| İlaç İstem | PAROL Tablet 500 mg |

Eklenemeyenler katalog boşluğu: düz "Ekokardiyografi" yok (yalnız
3D/Fetal/Stres), "Tam Kan Sayımı"nın katalog adı "Hemogram" ve pasif;
Augmentin/Ventolin/Nexium/Aferin COMED ilaç kataloğunda yok.

### Analiz promptu

- COMED katalog adlandırması öğretildi (kısaltma başta): hemogram, ALT (SGPT),
  AST (SGOT), CRP (Kantitatif), Troponin I, CK-MB, Demir (Fe), TIBC, HbA1c,
  Kreatinin (Serum), HDL/LDL-Kolesterol, karotis doppler.
- Toplu istekler tek tek açılıyor ("kardiyak enzimler" → Troponin I + CK-MB);
  ne kastedildiği belli değilse yazılmıyor.
- Model ekran seçmiyor: hangi istemin hangi ekranda olduğunu köprü kataloğa
  bakarak buluyor.

### Kimlik okuma (bu sürüme dahil)

Görünmez çerçeve hasta kimliğini "ilk 11 haneli sayı / ilk tarih" ile
okuyordu; panel açılmadan kartta telefon, protokol no, geliş tarihi
bulunduğu için yanlış kimlik dönüyor ve bir daha denenmiyordu. Artık panel
okumasıyla aynı **etiketli** ayrıştırıcı kullanılıyor ve başarısız deneme
sınırlı sayıda tekrar ediliyor. Testi content.js'teki gerçek düzenli
ifadeleri çalıştırıyor.

Testler: 277 → 288.


## v2.34.1 — 22 Ekim 2026

### Tetkik İstem: zorunlu alanlar ancak "Ekle"den SONRA ortaya çıkıyor

v2.34.0'da zorunlu alanlar işaretleme anında aranıyordu ve hiçbiri
görünmüyordu. Canlı ölçümde gerçek davranış bulundu: COMED doğrulamayı
**"Ekle"ye basıldıktan sonra** yapıyor ve o anda şunu gösteriyor:

```
Form Alanları Hatası / Zorunlu alanları doldurunuz
  → "Girilen açıklama hasta tetkik raporunda yer alacaktır alanı zorunludur,
     uzunluğu 3 degerinden büyük olmalı."   (her radyoloji satırı için)
  → "Endikasyon seçiniz alanı zorunludur."  (örn. Vitamin D3)
```

Düzeltmeler:

- Zorunlu açıklama kutusu **placeholder ile** bulunuyor. Sınıf/kırmızı-nokta
  tespiti canlıda hiç tutmadı; placeholder ile **7/7** alan dolduruldu.
- Varsayılan metin **"Acil bir durum yoktur"** (COMED en az 4 karakter
  istiyor).
- "Ekle"den sonra hâlâ hata varsa alanlar doldurulup **bir kez daha**
  deneniyor — zorunluluk o ana kadar görünmediği için tek deneme yetmiyordu.
- İkinci denemeden sonra da hata kalıyorsa (örn. **Endikasyon** gibi klinik
  seçim isteyen alan) istem gönderilmiyor, sebebiyle birlikte doktora
  bırakılıyor. Endikasyonu otomatik seçmek tıbbi karar vermek olurdu.

### Ölçülen zorunluluklar

| Tetkik | Zorunlu alan | Davranış |
| --- | --- | --- |
| RDUS / radyoloji satırları | "Girilen açıklama..." metni | varsayılan yazılır |
| Vitamin D3 (25-OH-Kolekalsiferol) | **Endikasyon seçiniz** | doktora bırakılır |
| Hemogram (796) | — | onay kutusu pasif, atlanır |

Laboratuvar tetkiklerinin geri kalanında zorunlu alan yok.

## v2.34.0 — 22 Ekim 2026

### Tetkik İstem ekranı eklendi (üçüncü istem ekranı)

COMED'de istemler **üç ayrı ekrana** dağılmış. İkisini yapmıştık, üçüncüsü
hiç yoktu:

| Ekran | Adres | Durum |
| --- | --- | --- |
| Hizmet İstem | `action-order-procedure` | vardı |
| İlaç İstem | `action-order-drug` | vardı |
| **Tetkik İstem** | **`action-order-study`** | **yeni** |

Bu, v2.33.0'daki "Tam Kan Sayımı katalogda hiç yok" sonucunun gerçek
sebebiydi: laboratuvar tetkikleri Hizmet İstem'de değil, bu ekranda. Yanlış
yerde aranıyordu.

### Hangi ekranda olduğunu katalog söylüyor, model değil

Analiz çıktısı tek alanda (`requested_services`) kalıyor. Köprü önce Tetkik
İstem'i deniyor, bulamadıklarını Hizmet İstem'e devrediyor (EKG gibi işlemler
orada). Modele "bu lab mı işlem mi" diye sordurmak hataya açıktı.

### Ad eşleştirme: model bilimsel ad yazıyor, COMED kısaltma kullanıyor

Canlı doğrulanan eşleşmeler:

| Gemini çıktısı | COMED kataloğu |
| --- | --- |
| Alanin Aminotransferaz (ALT) | ALT (SGPT) |
| C-Reaktif Protein (CRP) | CRP (Kantitatif) |
| Total Demir Bağlama Kapasitesi (TDBK) | Total Demir Bağlama Kapasitesi (TIBC) |
| HDL Kolesterol | HDL-Kolesterol |
| Kreatinin | Kreatinin (Serum) |
| Demir | Demir (Fe) |

Düz "includes" eşleşmesi bunların çoğunu kaçırırdı. Artık aday olarak tam ad,
parantezsiz çekirdek **ve parantez içindeki kısaltma** deneniyor; tire/boşluk
sadeleştiriliyor. 3D/Fetal/Stres vetosu burada da geçerli.

### Ölçülen davranışlar

- **Hemogram (796) onay kutusu pasif** geliyor — işaretlenemiyor, atlanıyor ve
  raporda sebebi yazıyor.
- **"Dokümanları Doldurunuz"** uyarısı çıkan tetkik **hiç gönderilmiyor**;
  yarım bırakılmış istem doktoru yanıltır.
- Radyolojide "Acil" yanındaki açıklama zorunlu olabiliyor → doktor aciliyet
  belirtmediyse **"Aciliyeti yok"** yazılıyor.
- Birden çok tetkik aynı anda işaretlenip **tek "Ekle"** ile ekleniyor.
- Favori paketleri ve içerikleri ölçülüp belgelendi (21/19/8/2/4/2/1; üç paket
  boş). Soldaki "Ara" kutusu global değil, seçili paketin içinde arıyor.

### İstem sınırı 8 → 25

Tek görüşmede 16 tetkik istenebildiği ölçüldü (kardiyoloji paneli + grafi +
doppler + EKG). 8'lik sınır istemleri sessizce kesiyordu.

### Test

Kendi oluşturduğum diyalog canlı backend'e gönderildi, çıkan 16 tetkik canlı
COMED kataloğunda eşleştirildi. `docs/COMED_FORM_MAP.md`'de ölçüm tabloları
var. 254 → 269 test.

## v2.33.1 — 22 Ekim 2026 (ACİL DÜZELTME)

### v2.33.0 dökümü tamamen bozdu

v2.33.0'da OpenAI dökümüne eklenen `prompt` parametresi canlıda **her isteği
503'e düşürdü**. Mobil uygulamada "Analiz servisi isteği tamamlayamadı"
hatası çıkıyor, görüşme kaybediliyordu. Canlı `/transcribe` ucuna küçük bir
ses dosyası gönderilerek yeniden üretildi.

Sebep: **her STT modeli `prompt` parametresini kabul etmiyor.** v2.33.0
öncesindeki `assertNotIn("prompt", kwargs)` testi muhtemelen tam da bunun
için konmuştu; test güncellendi ama altındaki gerçek doğrulanmadı.

### Kural: döküm, prompt uğruna asla başarısız olmamalı

`prompt` bir **iyileştirmedir, zorunluluk değildir**:

- Model reddederse aynı çağrı **promptsuz tekrarlanır**, görüşme kurtarılır.
- Yalnız "parametre kabul edilmiyor" hataları yutulur. Kota (429), anahtar
  (401), sunucu (500) ve ağ hataları **eskisi gibi yukarı taşınır** — gerçek
  arızayı gizlemiyoruz.
- Ne olduğu `usage.stt_prompt_sent` / `usage.stt_prompt_rejected` alanlarına
  yazılıyor; promptun gidip gitmediğini tahmin etmek yerine veriden görüyoruz.
- Hem ana diarize modeli hem yedek model için geçerli.

Böylece prompt destekleniyorsa Türkçe yanlılığı korunur, desteklenmiyorsa
sistem hiç bozulmadan çalışır.

### Ders

Bir satırlık "iyileştirme" bile canlıda doğrulanmadan gönderilmemeli.
v2.33.0'ın hizmet/katalog değişiklikleri canlı COMED'de ölçülmüştü; STT
promptu ölçülmedi ve kıran o oldu.

Testler: 249 → 254. Yeni `test_stt_prompt_fallback.py` hem kurtarma yolunu
hem de gerçek hataların yutulmadığını doğruluyor.

## v2.33.0 — 22 Ekim 2026

### Hizmet istemlerinde de yanlış tetkik seçimi düzeltildi

İlaç tarafında bulunan PAROL COLD hatasının aynısı hizmet isteminde de vardı.
Canlı COMED'de ölçüldü (hasta 22207363):

| Doktor ne dedi | Katalogda ne var |
| --- | --- |
| EKG | `Elektrokardiogram (EKG)` + 12 derivasyonlu, evde çekim, trase, Fetal |
| **EKO** | **düz "Ekokardiyografi" YOK** — yalnız 3D / Fetal / Stres |
| **Tam Kan Sayımı** | **katalogda hiç yok** (hemogram da 0 sonuç) |
| Akciğer Grafisi | `Akciğer Grafisi (İki Yön)` var |

Eski kural ilk `includes` eşleşmesini alıyordu: doktor "EKO yapalım"
dediğinde **3D ekokardiyografi** sipariş ediliyordu.

Artık ilaçtakiyle aynı disiplin:

- Tam hücre eşleşmesi her zaman kazanır.
- Doktorun söylemediği niteleyici (**3D, Fetal, Stres, evde çekim, trase,
  holter, efor, pediatrik, ambulatuar, yorumlama, monitorizasyon**) taşıyan
  satır **veto** edilir.
- Katalog satırı olmayanlar (zaten eklenmiş istemler) elenir — ilk hücresi
  kod olmayan satır aday sayılmaz, böylece aynı istem iki kez girilmez.
- Emin olunamazsa **tetkik istenmez**, doktora bırakılır ve sebebi yazılır.

Canlı doğrulandı: EKG ve Akciğer Grafisi doğru satırı buluyor; EKO ve Tam Kan
Sayımı doktora bırakılıyor.

### Hizmet isteminde sessiz atlama bitti

İlaç tarafında yapıldığı gibi, hangi tetkikin hangi satırla eklendiği ve
neyin neden atlandığı aktarım kaydına yazılıyor; bitiş balonu eksik varsa
uyarıyor.

### STT artık Türkçeye yaslanıyor ("I am, I am" sorunu)

Kayıtlarda sessiz saniyelerde İngilizce parçalar çıkıyordu. `language="tr"`
zaten ayarlıydı ama tek başına yetmiyor; modele bağlam vermek gerekiyordu.

- OpenAI dökümüne **kısa Türkçe tıbbi bağlam** promptu eklendi.
- **RİSK VE SAVUNMA:** Whisper ailesi prompt metnini bazen transkriptin
  başına kopyalıyor. Bu yüzden prompt kasıtlı olarak kısa tutuldu (uzun terim
  listesi sızsa tıbbi kayıtta çok kötü görünürdü) ve `_strip_prompt_echo`
  ile çıktıdan temizleniyor. Gerçek konuşmaya dokunulmuyor — bunun için
  ayrı testler var.
- `OPENAI_STT_PROMPT=` boş bırakılırsa prompt hiç gönderilmez.

Not: eski `test_..._without_generation_prompt` testi bilinçli olarak
güncellendi; promptsuz çalışma kararı OpenAI diarize API'sine geçişte
alınmıştı, belgelenmiş bir sızma olayı yoktu.

### Analiz promptu güçlendirildi

Doktorun istediği tetkik/ilaç kaçmasın diye:

- **İstem sayılan kalıplar** sayıldı: "çekelim / yapalım / isteyelim /
  bakalım / alalım / planlayalım / takalım / ekleyelim".
- **İstem sayılmayanlar** netleştirildi: "faydalı olurdu", "gerekirse",
  hastanın geçmişte yaptırdıkları, doktorun **"vermiyorum / yazmıyorum"**
  dedikleri.
- Kısaltma sözlüğü: EKG, EKO/ECHO, PA akciğer, hemogram, BT, USG, TİT.
- **Söylenmeyen niteleyici eklenmesi yasaklandı**: "EKO" → "Ekokardiyografi",
  asla "3D/Stres/Fetal"; "Parol" → "Parol", asla "Parol Cold".
- Sıklık dönüşümleri: "sabah akşam" → 2, "8 saatte bir" → 3,
  "6 saatte bir" → 4; haftalık/"gerektiğinde" ise null.

### Testler

240 → 249. Yeni: `test_stt_prompt_echo.py` (saf fonksiyon, gerçek birim
testi). Eklenti betiklerinin tamamı gerçek V8'de `new Function` ile
ayrıştırılarak doğrulandı.

## v2.32.1 — 22 Ekim 2026

### İlaç istemi gerçekten çalışıyor (v2.32.0 hiç çalışmıyordu)

v2.32.0 ilaç ekranını açıyor ama **hiçbir ilacı eklemeden** "Aktarım bitti ·
20 sn" diyordu. Canlı COMED'de ölçülerek üç kök sebep bulundu:

1. **Arama kutusu bizzat eleniyordu.** Kod, alt araç çubuğundaki "Ara" ve
   "İsteyen ara..." kutularını elemek için placeholder'ında "ara" geçenleri
   atıyordu. Hedef kutunun placeholder'ı da **"Temel ilaçlar kategorisinde
   ara"** — yani doğru kutu da eleniyordu. Artık placeholder'da "ilaç"
   geçmesine bakılıyor.
2. **Olmayan bir sekme düğmesi 12 saniye bekleniyordu.** Hizmet isteminden
   farklı olarak ilaç ekranında `co-button-İlaç İstem` diye bir düğme **yok**;
   adres parametresi tek başına ekranı açıyor. 12 sn + 6 sn bekleme, doktorun
   gördüğü "20 sn"nin kaynağıydı.
3. **"Ana İlaç" etiketiyle arama tutmuyordu.** `.co-input__label` içinde böyle
   bir etiket yok.

### ⚠️ Hasta güvenliği: yanlış ilaç seçimi düzeltildi

v2.32.0 öneri listesinden **ilk başlayan eşleşmeyi** alıyordu. "parol"
araması COMED'de 10 sonuç veriyor ve ilki **PAROL COLD** — bir grip ilacı,
içinde fenilpropanolamin (sempatomimetik) var, yaşlı/hipertansif hastada
kontrendike. Yani köprü doktorun önüne yanlış ilacı koyuyordu.

Artık puanlama + veto var:

- Doktorun söylemediği marka eki (**COLD, HOT, PLUS, FORTE, PEDİATRİK**)
  taşıyan ürün **doğrudan elenir**; puanla telafi edilemez.
- Söylenen doz eşleşmeli: 500 mg istenip 325 mg seçilemez.
- Ayaktan muayenede ağızdan form varsayılan; IV flakon/ampul doktor açıkça
  söylemeden seçilmez.
- Marka adı kelime sınırıyla eşleşmeli: "Parol" ararken "PAROLOX" tam
  eşleşme sayılmaz.
- **Emin olunamazsa ilaç HİÇ EKLENMEZ**, doktora bırakılır.

Canlı katalogda doğrulanan kararlar (`docs/COMED_FORM_MAP.md`'de tablo var):

| Doktor ne dedi | Karar |
| --- | --- |
| Parol, 500 mg | PAROL Tablet 500 mg seçilir |
| Parol (doz yok) | PAROL Tablet 500 mg seçilir |
| Parol Cold | PAROL COLD seçilir (açıkça istendi) |
| Parol, 325 mg | doktora bırakılır |
| Parol süspansiyon | doktora bırakılır |
| Bilinmeyen ad | doktora bırakılır |

### Sessiz başarısızlık bitti

Aktarım bitiş balonu artık eksik alan varsa **"· N alan eksik"** yazıyor ve
kırmızıya dönüyor. Ayrıca hangi ilacın hangi formla eklendiği ve neyin neden
atlandığı aktarım kaydına yazılıyor; doktor imzalamadan önce "ben Parol
dedim, COLD mu Tablet mi eklenmiş" diye bakabiliyor.

### Diğer

- "Temel İlaç" kategorisinde bulunamayan ilaç için **"Tümü"** sekmesi yedeği
  (hizmet istemindeki Favoriler→Genel yedeğinin karşılığı).
- Testler: v2.32.0'ın `startsWith(wanted)` iddiası **hatayı şart koşuyordu**,
  kaldırıldı. Yerine canlı ölçümleri kayıt altına alan regresyon testleri
  geldi. Dürüst not: depoda JS/DOM test altyapısı olmadığı için bu testler
  kodun metnine bakar; asıl kanıt belgelenmiş canlı ölçümlerdir.

## v2.32.0 — 22 Ekim 2026

### İlaç istemleri otomatik

Hizmet isteminin (EKG/EKO) ilaç karşılığı. Doktor görüşmede "Parol yazıyorum,
günde 3 kez" dediğinde köprü bunu COMED'in **İlaç İstem** ekranına da giriyor.

COMED'de ilaç istemi ayrı bir ekranda açılıyor
(`?app-action=action-order-drug`). Hizmet isteminden farkı **zorunlu alanının
olmaması**: "Ana İlaç" arama kutusuna ad yazılıp öneri listesinden seçildiğinde
veriliş yolu, miktar, doz ve uygulama COMED'in varsayılanıyla geliyor; "Ekle"
demek yetiyor.

- `requested_drugs`: ad, doz, günlük sıklık ve gerekçe. En çok 10 ilaç,
  tekrarlar eleniyor.
- Doz veya sıklık görüşmede söylenmediyse **hiçbir alana dokunulmuyor** —
  COMED'in varsayılanı kalıyor ve doktor tamamlıyor. Model tahmin etmiyor.
- Günlük sıklık yalnız 1–12 arası kabul ediliyor, çünkü COMED'de sıklık
  "Günlük N Kez" düğmesine basılarak seçiliyor ve düğmeler bu aralıkta.
  Aralık dışı bir değer yanlış düğmeye basmaktansa boş bırakılıyor.
- Hastanın zaten kullandığı ilaçlar (öykü) istem sayılmıyor; yalnız görüşmede
  açıkça yazılan ilaçlar giriliyor.
- Narkotik gibi ek zorunlu alan isteyen ilaçlarda istem yarım bırakılmıyor,
  pencere kapatılıp doktora devrediliyor.
- Doktor paneli aktarımdan önce ilaç listesini mor rozetlerle gösteriyor.

İmza yine doktorda: `auto_sign` her durumda `false`.

### Doktor paneli COMED'e benzetildi

Doktor gün boyu COMED'de çalışıyor; panelin ona yabancı gelmemesi için sıra
COMED'in iş listesi ekranıyla aynı yapıldı.

- **Üstte arama kutusu ve tarih aralığı.** Tek arama kutusu hem COMED iş
  listesini hem görüşme kayıtlarını süzüyor.
- **Tarih aralığı** COMED'deki gibi: tek taraf doldurulursa yalnız o sınır
  uygulanıyor.
- **Sayım/maliyet şeridi sayfanın altına alındı.** Doktorun ilk gördüğü şey
  artık token sayısı değil, hasta listesi.
- Arama süzgeci 15 saniyelik arka plan yenilemesinden sonra da korunuyor
  (önceden siliniyordu).

## v2.31.0 — 15 Ekim 2026

### Hizmet istemleri artık gerçekten ekleniyor

v2.30.0'da köprü EKG penceresini açıyor ama ekleyemeden takılıyordu. Canlı
COMED'de üç ayrı sebep bulundu:

1. **Açılır alanların dinleyicisi ok ikonunda.** "Uygulayan" alanının
   kendisine, çocuklarına ve atalarına gönderilen tıklama paneli açmıyor;
   yalnızca içindeki ok ikonu açıyor. Ölçülerek bulundu.
2. **Aynı isimli iki düğme.** Tanı kartındaki "Ekle" ile istem
   penceresindeki "Ekle" aynı `data-test` değerini taşıyor. `querySelector`
   ilkini (tanı kartındakini) alıyordu; o hep pasif olduğu için istem hiç
   eklenemiyordu. Artık "Vazgeç" ile aynı hizadaki düğme seçiliyor.
3. **Arama kutusu kirli kalıyordu.** Önceki hizmetin araması süzgeç olarak
   duruyor, sonraki hizmet "listede yok" sanılıp atlanıyordu.

Ayrıca liste varsayılan olarak "Favoriler" sekmesinde açılıyor; orada olmayan
hizmet (örneğin Ekokardiyografi) bulunamıyordu. Artık bulunamazsa "Genel"
sekmesine geçip tüm katalogda aranıyor.

Eksik olay dizisi de tamamlandı: bazı COMED bileşenleri tıklamadan önce hover
olaylarını bekliyor, eksik dizi sessizce yutuluyordu.

Doldurulamayan istem yarım bırakılmıyor: pencere kapatılıp "doktor tarafından
tamamlanmalı" olarak işaretleniyor.

## v2.30.0 — 15 Ekim 2026

### Hizmet istemleri (EKG, EKO) otomatik giriliyor

Doktor görüşmede "EKG çekelim, EKO isteyelim" dediğinde bunlar eskiden yalnız
izlem-plan metnine yazılıyordu; doktor sonra COMED'de tek tek elle giriyordu.
Artık köprü bu istemleri de dolduruyor.

COMED'de hizmet istemleri muayene formunda **değil**, ayrı bir ekranda
giriliyor: `<kart adresi>?app-action=action-order-procedure`. Akış canlı
COMED'de adım adım doğrulandı ve gerçek bir EKG istemi oluşturuldu:

1. Ekranı aç, "Hizmet İstem" sekmesine geç
2. Hizmeti listede bul (favorilerde yoksa arama kutusuyla)
3. Satıra tıkla, detay penceresi açılır
4. "Uygulayan" doktoru seç (isteyen doktorun aynısı)
5. "Ekle" → kayıt listeye düşer

Doktor sonra ekranı kapatıp kontrol eder ve imzalar. İmza her zaman doktorda.

**Hizmet türüne göre pencere değişiyor:** "Hizmet" tipinde (EKG) Uygulayan
alanı zorunlu, "Radyoloji" tipinde (grafi) bu alan hiç yok; onun yerine çekim
yöntemi, vücut bölgesi gibi alanlar çıkıyor ve açıklama zorunlu oluyor.
Köprü dolduramadığı istemi yarım bırakmaz: pencereyi kapatıp doktora bırakır.

LLM artık yalnız doktorun **açıkça istediği** tetkikleri çıkarıyor; "faydalı
olurdu" gibi öneri cümlelerinden istem üretmiyor. Doktor paneline "Hizmet
istemleri" bölümü eklendi — aktarımdan önce ne girileceği görülüyor.

### Doktor girişinde "Beni hatırla"

Oturum 12 saatte düştüğü için doktor her gün yeniden giriş yapıyordu.
İşaretlenirse 30 gün açık kalıyor. İşaretlenmezse eski davranış aynen sürüyor.
Uzun ömürlü çerez de `httponly` ve `samesite=lax` kalıyor.

## v2.28.0 — 15 Ekim 2026

### "Siteden çıkılsın mı?" kutusu kalktı

"COMED'e aktar" doktorun açık sekmesini hasta kartına yönlendiriyor. COMED'de
yarım kalmış bir form varsa tarayıcı bu uyarıyı çıkarıyor ve doktor her
aktarımda kutuyla uğraşıyordu.

Projede bu uyarıyı bastıran bir mekanizma zaten vardı (taslak temizlemede
kullanılıyordu) ama aktarım sırasında devreye girmiyordu. Artık köprü,
sekmeyi yönlendirmeden önce bayrağı kuruyor; `page_trace.js` document_start'ta
kurduğu dinleyiciyle o tek çıkışı sessizce geçiriyor.

Bayrak artık zaman damgası taşıyor: geçiş bir şekilde olmazsa asılı kalan
eski bir bayrak, doktorun **gerçek** çıkışını sessizce yutmasın diye 15
saniye sonra geçersiz sayılıyor. Gerçek COMED sayfasında doğrulandı.

## v2.27.0 — 15 Ekim 2026

### Kimlik artık görünmez çerçevede okunuyor

v2.26.0'da kart **arka planda sekme** açılarak okunuyordu. Yanlıştı: sekme
görünüyordu ve COMED o sekmede yeniden giriş isteyebiliyordu.

Doğrusu, iş listesi sayfasının **içinde** ekrandan tamamen gizli bir
`<iframe>`: oturum aynı sekmede olduğu için giriş istemiyor, doktorun
ekranında hiçbir şey değişmiyor, iş bitince çerçeve siliniyor.

Canlı COMED'de doğrulandı: iki hastanın kimliği görünmez çerçevede okundu.

**Kritik ayrıntı:** "Hasta Bilgileri" paneli yalnızca **hasta adına
tıklayınca** açılıyor. On iki ikon düğmesi denendi, hiçbiri açmıyor.

### Yedek eşleşme: hasta numarası

Kimlik hiç okunamazsa hasta, hasta numarası + doğum tarihiyle de giriş
yapabilir. Doğum tarihi ham saklanmaz, HMAC özetiyle eşleşilir.

## v2.26.0 — 14 Ekim 2026

### Hasta randevusu artık doktoru beklemiyor

COMED iş listesi satırında T.C. kimlik numarası yok; kimlik yalnızca hasta
kartındaki "Hasta Bilgileri" panelinde yazıyor. Bu yüzden hasta, doktor o
kartı **elle açana kadar** randevusuna bağlanamıyordu: doktorda "3 hasta
eşitlendi" yazarken hasta telefonda "randevu bulunamadı" alıyordu.

Köprü artık kimliği eksik kartları **arka planda** açıp kimliği okuyor ve
sekmeyi kapatıyor. Doktorun ekranında hiçbir şey değişmiyor, açık sekmesi
bozulmuyor:

- Sekme `active: false` ile açılır, iş bitince kendini kapattırır.
- Aynı anda yalnızca bir kart açılır.
- Sekme bir şekilde kapanmazsa 60 saniyede güvenlik ağı kapatır.
- Arka plan kartında normal aktarım akışı çalışmaz; yalnız kimlik okunur.

Yeni uç: `GET /api/v1/mobile/comed/worklist/missing-identity`.

### Yedek eşleşme: hasta numarası

Kimlik hiç okunamazsa (kurulum kimliği göstermiyorsa) hasta **hasta
numarasıyla** da giriş yapabilir. Hasta numarası iş listesinde hazır olduğu
için bu yol kart açılmadan çalışır. Doğum tarihi yine ham saklanmıyor, HMAC
özetiyle eşleşiliyor.

### Not

`SESSION_SECRET` boş bırakılsa bile özet anahtarı yönetici bilgilerinden
türetildiği için kararlıdır; sunucu yeniden başladığında eşleşmeler bozulmaz.
Bu araştırma sırasında doğrulandı.

## v2.23.0 — 14 Ekim 2026

COMED aktarımı yeniden eski sağlamlığında. v2.22.0'da iki şey bozulmuştu,
bir de uzun süredir sessizce duran gerçek bir hata vardı.

### Geri alınan hata: aktarım iptal ediliyordu

v2.22.0'da köprü yanıt vermeyince aktarım iptal ediliyordu. Oysa sekme açmak
yalnızca bir kolaylık; asıl doldurmayı COMED sayfasındaki eklenti yapıyor ve
aktarım `queued` kaldığı sürece doktor COMED kartına kendi geçince iş yürüyor.
İptal edilince bu çalışan tek yol da kapanmıştı. Artık **hiçbir durumda iptal
edilmiyor**.

### Kuyruk tıkanması (asıl sebep)

Köprüye verilen bekleyen aktarım listesi 20 ile sınırlıydı ve **en eskiden**
başlıyordu. Alınamayan aktarımlar `queued` durumunda biriktikçe kuyruk doluyor,
doktorun **yeni** isteği listeye hiç giremiyor ve eklenti onu hiç görmüyordu.
Her yeniden denemede durum biraz daha kötüleşiyordu. Artık en yeniden
başlanıyor ve bir saatten eski istekler kuyruktan kendiliğinden düşüyor.

### Doktoru uğraştırmamak

- Köprü yanıt vermezse kart yine de yeni sekmede açılıyor (v2.21.0'daki
  davranış geri geldi).
- Eklenti güncellendiğinde açık doktor paneli ve COMED sekmeleri
  **kendiliğinden yenileniyor**. Önceden bu sekmelerdeki köprü sahipsiz kalıp
  sessizce çalışmıyordu; artık "sayfayı yenileyin" demeye gerek yok.
- Köprü artık sessizce ölmüyor: hata olursa panele hemen haber veriyor,
  panel yedi saniye boşuna beklemiyor. Arka plan betiği uykudaysa mesaj bir
  kez yineleniyor.

## v2.22.0 — 14 Ekim 2026

### COMED aktarımı artık takılı kalmıyor

- **Kök sebep:** aktarım `queued` durumunda asılı kalırsa "COMED'e aktar"
  düğmesi sonsuza kadar pasif kalıyordu; iptal ya da yeniden deneme yolu hiç
  yoktu. Eklenti kapalıysa veya köprü yanıt vermediyse doktor o görüşmeyi bir
  daha hiç aktaramıyordu.
- Sunucu artık ilerlemeyen aktarımı `stale` işaretliyor (kendi saatiyle, 75 sn).
  Takılan aktarımda düğme **"Yeniden aktar"** olarak açılıyor ve ne olduğunu
  anlatan bir uyarı çıkıyor.
- Yeni uç: `POST /doctor/api/comed/transfers/{id}/cancel`. Süren aktarımın
  yanında **"Vazgeç"** düğmesi var. COMED'e işlenmiş aktarım bırakılamıyor (409).
- Köprü yanıt vermezse aktarım kendiliğinden bırakılıyor; düğme hemen yeniden
  kullanılabilir oluyor.

### Boş sekme sorunu

- Köprü zaman aşımı 1,8 sn → **7 sn**. Chrome MV3 arka plan betiği uykuya
  daldığı için ilk mesajda uyanması birkaç saniye sürebiliyor; eski sınır sık
  sık doluyordu.
- Yanıt gelmediğinde `window.open` ile yedek sekme **açılmıyor** artık — o sekme
  çoğu zaman boş kalıyordu.
- Eklenti yeni sekmeyi doğrudan hedef adresle açıyor; önce `about:blank` açıp
  sonra yönlendirmiyor.

### Hasta randevusunun geç bağlanması

- Hastanın randevusu COMED'de ancak doktor hasta kartını açtığında eşleşebiliyor
  (T.C. kimlik numarası yalnızca o panelde yazıyor — COMED kısıtı). Hasta bunu
  bilmeden elle yenilemek zorunda kalıyordu.
- Uygulama artık **kendiliğinden tekrar deniyor** (6 saniyede bir, ~2,5 dakika)
  ve ekranda "Randevunuz aranıyor… Doktorunuz sizi sistemde açtığında randevunuz
  buraya otomatik gelecek" yazıyor.
- Eklenti iş listesi satırından doğum tarihini de topluyor.

## v2.21.0 — 14 Ekim 2026

- Doktor panelindeki kayıt listesi COMED iş listesine benzetildi: satırlar bir
  beyaz bir grimsi (zebra) oldu ve **hasta bilgileri sütunu** eklendi — ad
  soyad, baş harf rozeti, protokol ve hasta numarası. Önceden iki kayıt
  birbirinden ayırt edilemiyordu. Arama artık hasta adıyla da çalışıyor.
- **Hız ayarı doldurma sürerken değiştirilebiliyor.** Beklemeler tek parça
  `setTimeout` yerine dilim dilim yapılıyor ve her dilimde hız yeniden
  okunuyor; `waitForDomQuiet` de sabit zamanlayıcı yerine periyodik kontrol
  kullanıyor. Önceden o an süren 3,5 saniyelik bekleme eski hızla bittiği
  için ayar tutmuyor gibi görünüyordu. Ölçüldü: 4 sn'lik işin 1. saniyesinde
  2.5× yapılınca toplam 4000 ms yerine 2202 ms.
- Dilimlemenin getirdiği ~%25 zamanlayıcı sapması, planlanan değil gerçekte
  geçen süre düşülerek giderildi (sapma %0,6).
- Hız değiştiğinde COMED sayfasındaki Klinot balonu "Doldurma hızı 2.5×"
  bildirimi gösteriyor; ayarın ulaştığı görülüyor.

## v2.20.0 — 14 Ekim 2026

- **Eklenti hız ayarı artık gerçekten çalışıyor.** Önceki sürümde yalnızca
  `sleep()` beklemeleri ölçekleniyordu; ölçüldüğünde bunların toplamı ~2,7 sn,
  buna karşılık "DOM sakinleşene kadar bekle" beklemeleri 1,5–12,7 sn
  tutuyordu. Yani sürenin ancak ~%15'i ölçekleniyor, 2.5× bile fark
  yaratmıyordu. Artık her iki bekleme türü de ölçekleniyor: 2.5× ayarı
  doldurmayı ~%58 kısaltıyor, 0.5× ise iki katına çıkarıyor. Yalnızca
  `waitFor` zaman aşımı sabit kaldı — o bir güvenlik sınırı.
- Hız ayarı kaydıraç (slider) oldu ve yalnızca eklenti penceresinde duruyor;
  COMED sayfasındaki balondan kaldırıldı.
- Doktor panelindeki COMED iş listesi kart düzeninden çıkıp COMED'in kendi iş
  listesi gibi satır satır tabloya döndü: hasta, hasta no, protokol,
  işlem/bölüm, doktor, durum sütunları.
- Doktor panelinde kullanılan model artık yönetici panelindeki gibi görünüyor.
- Hasta artık randevusunu listeden seçmiyor. T.C. kimlik numarası ve doğum
  tarihiyle doğrulandığı için randevusu otomatik bağlanıyor; ekranda yalnızca
  hangi muayene ve hangi doktor olduğu yazıyor.

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
