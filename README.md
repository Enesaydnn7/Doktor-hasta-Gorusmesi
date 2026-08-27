# Klinik Görüşme Analiz Paneli — OpenAI ses dökümü + Gemini analiz

Doktor–hasta görüşmesinin metnini alır, **Gemini** ile aynı görüşmeden **üç rapor** üretir.
Epikriz şeması, gerçek hastane epikrizlerinin yapısına göre kurulmuştur (sigorta/kayıt uyumlu).

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
OPENAI_API_KEY=...
OPENAI_STT_MODEL=gpt-4o-transcribe-diarize
```

## Dosyalar

| Dosya | İş |
|---|---|
| `main.py` | FastAPI; `/analyze` |
| `llm.py` | Gemini çağrısı; görüşme tarihini ekler; 3 raporu sırayla üretir |
| `stt.py` | OpenAI Transcription API çağrısı ve konuşmacı etiketleme |
| `prompts.py` | 3 system prompt (detaylı epikriz şeması burada) |
| `pdf_report.py` | Rapor PDF üretimi (epikriz formatı) |
| `config.py` | `.env` ayarları |
| `templates/`, `static/` | panel arayüzü |

## Notlar

- Giriş metin veya sestir; ses OpenAI API ile konuşmacı ayrımlı metne çevrilir.
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
   - `OPENAI_API_KEY` = (OpenAI Platform anahtarın)
   - `OPENAI_STT_MODEL` = `gpt-4o-transcribe-diarize`
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
1. Görüşme sesini mikrofonla kaydet ya da hazır ses dosyası (mp3/wav/m4a/ogg...) yükle.
2. Sistem sesi OpenAI `gpt-4o-transcribe-diarize` ile Türkçe metne döker ve konuşmacıları ayırır.
3. Metin, düzenlenebilir kutuya düşer — kontrol edip düzeltirsin.
4. "Analiz et" ile 3 rapor + epikriz üretilir.

- Ses motoru ayrı bir dosyadadır: `stt.py`. Yerel model indirilmez; kayıt OpenAI Transcription API'ye gönderilir.
- Tarayıcının ürettiği `.webm` dosyası dönüştürülmeden doğrudan API'ye gönderilir.
- API'nin konuşmacı segmentlerindeki sözcükler yeniden yazılmaz; yalnızca `Doktor:` / `Hasta:` etiketi eklenir.
- Not: 20 MB üstü ses için daha kısa kayıt kullanın (uzun görüşmeler için ileride parçalama eklenebilir).
- KVKK: ses metinden daha hassastır. Gerçek hasta kayıtlarında kendi sunucunuzda Whisper'a geçmeyi planlayın.

---

## Yenilik: Maliyet / token izleme (monitoring)

Her analizden sonra sonuçların üstünde küçük bir çubuk çıkar:
- **Süre** (analiz kaç saniye sürdü)
- **Token** (toplam = giriş + çıkış)
- **Tahmini maliyet** (USD) + "≈ .../1000 analiz" projeksiyonu

Ses yüklendiğinde de o dökümün token/maliyeti "metne döküldü" satırında gösterilir.

Fiyatlar `pricing.py` içindedir. Üç rapor için Gemini 2.5 Flash; ses dökümü için OpenAI
`gpt-4o-transcribe-diarize` standart token fiyatları kullanılır. API kullanım bilgisini token olarak
döndürmezse arayüz ses maliyetini `—` gösterir; sıfır dolar gibi yanıltıcı bir değer yazmaz.

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
