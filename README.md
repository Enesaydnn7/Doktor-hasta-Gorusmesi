# Klinik Görüşme Analiz Paneli — Scribe/OpenAI ses dökümü + Gemini analiz

Doktor–hasta görüşmesinin metnini alır, **Gemini** ile aynı görüşmeden üç rapor ve COMED alan taslağını paralel üretir.
Epikriz şeması, gerçek hastane epikrizlerinin yapısına göre kurulmuştur (sigorta/kayıt uyumlu).

`mobile_app/` altında yüz yüze görüşmeler için Android/iOS **Klinot Doktor** Flutter MVP'si bulunur. Mobil uygulama yalnızca kayıt, transkript kontrolü, doktor epikrizi ve epikriz PDF indirme akışını içerir; yönetim ekranları ayrı web `/admin` panelindedir. Mobil mimari ve kurulum: [MOBILE_APP.md](MOBILE_APP.md).

| Kime | Ne alır |
|---|---|
| **Hasta** | Sade dille özet: değerlendirme, yapılacaklar, ilaçlar, kontrol |
| **Doktor** | **Detaylı epikriz** + iletişim koçluğu |
| **Yönetim** | Güvenlik/üslup + doktor skoru (**verimlilik dahil**) + risk |

## Detaylı epikrizde neler var?

- **Görüşme tarihi ve doktor bilgisi** (görüşmede geçiyorsa)
- **Şikayet + başlangıç**: göreli süre kesin tarihe çevrilir — "3 hafta önce (yaklaşık 15.07.2026)"
  (sigorta için kritik; sistem görüşme tarihini modele otomatik verir)
- **Ağrı skoru** (X/10)
- **Öykü**, **fizik muayene bulguları**
- **Özgeçmiş**: kronik hastalıklar, ameliyatlar, kullandığı ilaçlar, alerjiler, alışkanlıklar
- **Soygeçmiş**: ailesel/genetik hastalıklar
- **Laboratuvar/tetkik** sonuçları (veya "istendi" notu)
- **Ön tanı + kesin tanı** (kesin tanı ancak doktor net söylediyse) + **ICD kodları**
- **Tedavi/ilaç uygulamaları**, **izlem & plan**
- **Kontrol**: önerildi mi, ne zaman, hangi durumda erken başvurmalı

**Altın kural:** Sistem yalnızca görüşmede geçeni yazar; olmayan alana **"belirtilmedi"** der,
asla uydurmaz (halüsinasyon koruması).

Yönetim skorlarına **verimlilik** eklendi: gereksiz uzatma olmaması, doğru soruların sorulması,
anamnezin (başlangıç tarihi, ağrı skoru, özgeçmiş, kırmızı bayraklar) eksiksiz toplanması,
tetkik/tedavinin isabeti. Ayrıca 1-2 cümlelik **verimlilik notu** verilir.

---

## Kurulum & çalıştırma

```bash
python -m venv venv
source venv/bin/activate          # Windows: venv\Scripts\activate
pip install -r requirements.txt
cp .env.example .env
uvicorn main:app --reload
```

Tarayıcı: **http://127.0.0.1:8000** → "Örnek yükle" → "Analiz et".

`.env` içine anahtarını yaz:

```env

GEMINI_API_KEY=...
GEMINI_MODEL=gemini-2.5-flash
APP_VERSION=v2.6.1
COMED_WEB_BASE_URL=http://goztepe.comedtest.mlpcare.com/tr-tr/medical
COMED_API_BASE_URL=http://goztepe.comedtestapi.mlpcare.com/tr-tr/api/json
MOBILE_SESSION_DAYS=30
ELEVENLABS_API_KEY=...
ELEVENLABS_STT_MODEL=scribe_v2
ELEVENLABS_STT_LANGUAGE=tr
OPENAI_API_KEY=...
OPENAI_STT_MODEL=gpt-4o-transcribe-diarize
OPENAI_STT_FALLBACK_MODEL=gpt-transcribe
```

## Dosyalar

| Dosya | İş |
|---|---|
| `main.py` | FastAPI; `/analyze` |
| `llm.py` | Gemini çağrısı; görüşme tarihini ekler; 3 rapor ile COMED taslağını paralel üretir |
| `stt.py` | ElevenLabs Scribe v2, OpenAI yedeği ve konuşmacı etiketleme |
| `role_classifier.py` | Konuşmacı metinlerinden Gemini ile yalnızca doktor/hasta rol eşlemesi |
| `prompts.py` | Hasta, doktor, yönetim ve COMED system promptları |
| `comed_integration.py` | COMED taslağı normalizasyonu, zorunlu alan kontrolü ve aktarım paketi |
| `comed_bridge_extension/` | Kurumsal ağdaki açık COMED oturumuna taslakları taşıyan Chrome köprüsü |
| `pdf_report.py` | Rapor PDF üretimi (epikriz formatı) |
| `config.py` | `.env` ayarları |
| `templates/`, `static/` | panel arayüzü |
| `mobile_app/` | Android/iOS Klinot Flutter uygulaması |
| `MOBILE_APP.md` | Mobil mimari, API ve dağıtım notları |

## Notlar

- Giriş metin veya sestir; ses öncelikle Scribe v2, servis kullanılamazsa OpenAI API ile konuşmacı ayrımlı metne çevrilir.
- KVKK: gerçek hasta verisinde kurum politikanıza göre ilerleyin; gerekirse `llm.py`'deki
  bağlantıyı kendi sunucunuzdaki bir modele çevirin.


## Yenilikler (bu sürüm)

- **Model:** `gemini-2.5-flash` (config'de).
- **Tutarlılık:** `TEMPERATURE=0` + deterministik ayarlar → aynı görüşme, mümkün olduğunca aynı çıktı.
- **ICD zorunlu:** Her epikrizde 1-3 ICD-10 kodu (en olası ilk sırada), asla boş bırakılmaz.
- **Verimlilik skoru:** Yönetim raporunda 0-100 ölçekli ayrı metrik + kısa not.
- **PDF indir:** Her rapor panelinde, hastane epikrizi görünümünde PDF indirme butonu
  (Türkçe karakter destekli). Sunucuda `/pdf` uç noktası üretir.

> `.env` düzenledikten sonra sunucuyu **tam kapatıp** yeniden başlat (`uvicorn --reload` yalnızca
> `.py` dosyalarını izler, `.env`'i görmez). Terminalde açılışta `[klinik-analiz] model=... | anahtar=...`
> satırı çıkar.

---

## Ücretsiz canlıya alma (domain almadan, link ile paylaşma)

> Not: GitHub Pages bunu ÇALIŞTIRAMAZ (o sadece statik site içindir). FastAPI arkada
> Python çalıştırdığı için Python destekleyen ücretsiz bir servise ihtiyaç var.

### Ön adım — kodu GitHub'a koy
1. github.com'da yeni bir depo (repo) aç.
2. Bu klasördeki dosyaları oraya yükle. **`.env` dosyasını YÜKLEME** (`.gitignore` bunu
   zaten engelliyor; anahtarın herkese açık olmasın).

### Seçenek A — Render.com (en kolay, GitHub'a bağlanır) — ÖNERİLEN
1. render.com'a GitHub ile giriş yap (kart bilgisi istemez).
2. **New +  →  Web Service  →** repoyu seç.
3. Ayarlar otomatik gelmezse:
   - Build Command: `pip install -r requirements.txt`
   - Start Command: `uvicorn main:app --host 0.0.0.0 --port $PORT`
   - Instance Type: **Free**
4. **Environment** sekmesinden değişkenleri gir:
   - `GEMINI_API_KEY` = (anahtarın)
   - `GEMINI_MODEL` = `gemini-2.5-flash`
   - `APP_VERSION` = `v2.6.1`
   - `MOBILE_SESSION_DAYS` = `30`
   - `ELEVENLABS_API_KEY` = (ElevenLabs API anahtarın)
   - `ELEVENLABS_STT_MODEL` = `scribe_v2`
   - `ELEVENLABS_STT_LANGUAGE` = `tr`
   - `OPENAI_API_KEY` = (OpenAI Platform anahtarın)
   - `OPENAI_STT_MODEL` = `gpt-4o-transcribe-diarize`
   - `OPENAI_STT_FALLBACK_MODEL` = `gpt-transcribe`
5. Deploy bitince sana `https://klinik-analiz-xxxx.onrender.com` gibi bir link verir.
   İşte paylaşacağın link bu.

> Ücretsiz planda uygulama 15 dk kullanılmazsa "uykuya" geçer; ilk açılış ~30-50 sn sürebilir,
> sonra normal hızlanır. Göstermelik demo için sorun değil. (`render.yaml` dosyası kuruluma yardımcı olur.)

### Seçenek B — Hugging Face Spaces (yapay zeka ekipleri için ideal, kartsız)
1. huggingface.co'da hesap aç  →  **New Space**.
2. **SDK: Docker** seç (repoda `Dockerfile` hazır).
3. Space'in dosyalarına bu projeyi yükle (yine `.env` hariç).
4. Space **Settings  →  Secrets** kısmına ekle:
   - `GEMINI_API_KEY`, `GEMINI_MODEL=gemini-2.5-flash`
   - `ELEVENLABS_API_KEY`, `ELEVENLABS_STT_MODEL=scribe_v2`, `ELEVENLABS_STT_LANGUAGE=tr`
   - `OPENAI_API_KEY`, `OPENAI_STT_MODEL=gpt-4o-transcribe-diarize`
5. Space otomatik derlenir; `https://kullanici-adi-space-adi.hf.space` linkini paylaşırsın.

### ÖNEMLİ — anahtar ve maliyet
- API anahtarını **asla** GitHub'a koyma; her zaman platformun "Environment/Secrets"
  bölümüne gir (`.env` yüklenmez).
- Linki paylaştığın herkes senin OpenAI ve Gemini API kotanı kullanır (masraf sana yazar). Yöneticine/güvendiğin
  birkaç kişiye göstermek için uygundur; herkese açık yayacaksan kota/masrafı göz önünde bulundur.
- KVKK: canlı demoda gerçek hasta verisi girme; örnek/senaryo metinleriyle göster.

---

## Yenilik: Sesten analiz (ses → metin → rapor)

Panelde metin kutusunun üstünde **Kaydet** ve **Ses dosyası yükle** var:
1. Önce listeden mikrofonu seçip **Mikrofonu test et** düğmesine bas. Konuşurken canlı seviye çubuğu hareket etmeli.
2. Görüşme sesini mikrofonla kaydet ya da hazır ses dosyası (mp3/wav/m4a/ogg...) yükle.
3. Sistem sesi öncelikle ElevenLabs `scribe_v2` ile Türkçe metne döker; görüşmenin iki konuşmacılı olduğunu bildirir
   ve tıbbi anahtar terimlerle kelime tanımayı güçlendirir.
4. Scribe kullanılamazsa OpenAI `gpt-4o-transcribe-diarize` otomatik yedektir. Onun segment ve birleşik metni de
   boşsa son kez OpenAI `gpt-transcribe` denenir. Bilgisayara veya Render'a model indirilmez.
5. Gemini yalnızca A/B konuşmacılarından hangisinin doktor, hangisinin hasta olduğunu cümlelerin anlamından seçer.
6. Metin, düzenlenebilir kutuya düşer — kontrol edip düzeltirsin.
7. "Analiz et" ile üç rapor ve COMED alan taslağı aynı anda üretilir.

### COMED Chrome köprüsü

Hazır eklenti paketi: [`build_artifacts/klinot-comed-bridge-v2.6.1.zip`](build_artifacts/klinot-comed-bridge-v2.6.1.zip).
ZIP'i klasöre çıkardıktan sonra [`build_artifacts/README.md`](build_artifacts/README.md) içindeki adımları izleyin.
COMED oturumu Chrome'da normal şekilde açılır; eklentiye COMED parolası değil, mobil Klinot hesabı girilir.

### STT model seçimi ve ücret

- OpenAI, `gpt-transcribe` modelini yüksek doğruluklu STT modeli; `gpt-4o-transcribe-diarize` modelini ise
  konuşmacıyı belirleyen model olarak belgeliyor.
- ElevenLabs, Scribe v2 için Türkçeyi kendi ölçümünde **Excellent (≤%5 WER)** sınıfında gösteriyor ve modelde
  32 konuşmacıya kadar diarization ile anahtar terim desteği bulunuyor. Bu oran üreticinin kendi ölçümüdür;
  bağımsız klinik doğrulama değildir.
- Bu projenin Türkçe + iki konuşmacı + tıbbi terim ihtiyacı nedeniyle Scribe v2 birincil seçildi.
- Scribe v2 liste fiyatı `$0.22/saat`; etkin tıbbi anahtar terimler `$0.05/saat` ekler. Toplam yaklaşık
  `$0.27/saat` (`$0.0045/dakika`). OpenAI yedeği yalnızca gerektiğinde ayrıca ücretlenir.

Kaynaklar: [Scribe v2 özellikleri](https://elevenlabs.io/docs/overview/capabilities/speech-to-text/),
[Scribe API parametreleri](https://elevenlabs.io/docs/api-reference/speech-to-text/convert),
[ElevenLabs API fiyatları](https://elevenlabs.io/pricing/api?price.section=speech_to_text),
[OpenAI GPT-Transcribe](https://developers.openai.com/api/docs/models/gpt-transcribe),
[OpenAI diarization modeli](https://developers.openai.com/api/docs/models/gpt-4o-transcribe-diarize).

- Ses motoru ayrı bir dosyadadır: `stt.py`. Yerel model indirilmez; kayıt öncelikle Scribe API'ye gönderilir.
- Tarayıcının ürettiği `.webm` dosyası dönüştürülmeden doğrudan API'ye gönderilir.
- Kulaklık takılıp çıkarıldığında mikrofon listesi yenilenir. Sessiz/boş kayıt API'ye gönderilmez; böylece hem
  anlaşılır bir uyarı gösterilir hem de gereksiz STT isteği engellenir.
- Yedek `gpt-transcribe` yalnızca ana model hem segment hem metin döndürmezse çağrılır; güncel liste fiyatı
  yaklaşık `$0.0045/dakika`dır ve bu ek maliyet arayüzde ayrı gösterilir.
- OpenAI segmentlerindeki sözcükler yeniden yazılmaz. Rol sınıflandırıcısı yalnızca A/B eşlemesi döndürür;
  hasta ilk konuşsa bile cümlelerin anlamına göre `Doktor:` / `Hasta:` etiketi eklenir.
- Demo sırasında tek kişi iki rolü aynı sesle okursa sözcükler numaralandırılır; Gemini yalnızca hangi
  sözcük aralığının doktor/hasta olduğunu seçer. Böylece aynı ses içinde de rol değişimi bulunabilir.
- Rol sınıflandırması başarısız olursa transkript kaybedilmez; çok sesli kayıtta konuşma sırası,
  tek sesli demoda cümle sırası kullanılır ve arayüz kontrol uyarısı gösterir.
- Not: 20 MB üstü ses için daha kısa kayıt kullanın (uzun görüşmeler için ileride parçalama eklenebilir).
- KVKK: ses metinden daha hassastır. Gerçek hasta kayıtlarında kurum politikasını, açık rızayı ve kullanılan
  sağlayıcılarla gerekli veri işleme/saklama sözleşmelerini ayrıca değerlendirin.

---

## Yenilik: Maliyet / token izleme (monitoring)

Her analizden sonra sonuçların üstünde küçük bir çubuk çıkar:
- **Süre** (analiz kaç saniye sürdü)
- **Token** (toplam = giriş + çıkış)
- **Tahmini maliyet** (USD) + "≈ .../1000 analiz" projeksiyonu

Ses yüklendiğinde de o dökümün token/maliyeti "metne döküldü" satırında gösterilir.
Doktor/hasta rol sınıflandırmasının Gemini token ve maliyeti ayrı satırda gösterilir. Sesli akışta
Sesli akışta Gemini toplam beş kez çağrılır: bir rol tespiti; "Analiz et" sonrasında üç rapor ve paralel COMED taslağı.

Fiyatlar `pricing.py` içindedir. Üç rapor ve COMED taslağı için Gemini 2.5 Flash; birincil ses dökümü için Scribe v2'nin
ses süresine dayalı liste fiyatı kullanılır. OpenAI yedeği devreye girerse kendi token/süre fiyatı ayrıca
hesaplanır. API yeterli süre veya kullanım bilgisi döndürmezse arayüz ses maliyetini `—` gösterir;
sıfır dolar gibi yanıltıcı bir değer yazmaz.

---

## Admin paneli (`/admin`)

Aynı adresin `/admin` yolunda açılır. Kendi **giriş sayfası** vardır (kullanıcı adı/şifre kutuları,
şifre göster düğmesi); tarayıcının açılır kutusu kullanılmaz. Varsayılan: **admin / admin**
(değiştirmek için `.env` veya Render Environment: `ADMIN_USER`, `ADMIN_PASS`).
Oturum imzalı çerezle tutulur (`SESSION_HOURS`, varsayılan 12 saat); sağ üstten **Çıkış** yapılır.

- Üstte özet: toplam kayıt, toplam token, toplam maliyet.
- Her analiz bir **satır**: kayıt no, tarih-saat, özet (tanı/şikayet), ses var mı.
- **Dinle**: görüşmenin ses kaydı panelden çalınır.
- **Raporlar**: satır açılır; doktor epikrizi / hasta özeti / yönetim raporu / görüşme metni
  sekmeleri ve her rapor için **PDF indir**.
- **Sil**: kaydı siler. Arama kutusundan tanı/şikayet/kayıt no ile filtrelenir.

Veriler `db.py` üzerinden **SQLite** (`kayitlar.db`) dosyasında tutulur; ses kaydı da
veritabanına yazılır. `DB_PATH` ile konum değiştirilebilir.

> **Önemli:** Render ücretsiz planda disk kalıcı değildir — servis yeniden başlarsa kayıtlar
> sıfırlanabilir. Kalıcı saklama için Render'ın ücretsiz **Postgres**'ine geçilmelidir;
> o durumda yalnızca `db.py` değişir.

Private repodaki yönetici demo kaydı istisnadır: `SEED_MANAGER_DEMO=true` olduğunda uygulama açılışında
`demo_records/` arşivinden SQLite'a yeniden eklenir. Yeni canlı hasta kayıtları için kalıcı veritabanı hâlâ gerekir.
