# Taşıma kılavuzu — Render → Ubuntu sunucu + Supabase

Bu belge, Klinot'u Render'dan kendi Ubuntu sunucumuza ve veritabanını
SQLite'tan Supabase'e (Postgres) taşımak için gereken her şeyi içerir.
Taşıma gününde tek başına yeterli olacak şekilde yazıldı.

**Son güncelleme:** v2.23.0 · 13 Ekim 2026

---

## 0. Önce bilinmesi gerekenler

| Konu | Durum |
|---|---|
| SQLite kullanımı | **Yalnızca `db.py` içinde.** Başka hiçbir `.py` dosyası `sqlite3` import etmiyor. Postgres'e geçerken tek dosya değişir. |
| Uygulama sunucusu | FastAPI + Uvicorn. Render'a özgü hiçbir kod yok, sadece `render.yaml` ve `Procfile` var. |
| Python | Dockerfile'da 3.11. `requirements.txt` sürüm kısıtı koymuyor; **3.11 kullanın**. |
| Ses kayıtları | Veritabanında `BLOB` olarak duruyor. **Supabase'e taşırken en kritik konu bu** — bkz. §4.3. |
| Hazır dağıtım dosyası | `Dockerfile` ve `Procfile` var. **systemd/nginx dosyası yok**, §3'te verildi. |

---

## 1. Ortam değişkenleri — tam liste

`README.md` yalnızca 11 tanesini sayıyor; kodda **30** tane okunuyor.
Aşağıdaki liste koddan doğrulandı. Taşırken bunların hepsini gözden geçirin.

### 1.1 Zorunlu — bunlar olmadan çalışmaz

| Değişken | Nerede okunuyor | Açıklama |
|---|---|---|
| `GEMINI_API_KEY` | `config.py:8` | Google Gemini anahtarı |
| `OPENAI_API_KEY` | `config.py:38` | Ses dökümü (STT) anahtarı |
| `SESSION_SECRET` | `auth.py:110` | Oturum imzalama. **Boş bırakılırsa her yeniden başlatmada rastgele üretilir ve tüm oturumlar düşer.** Uzun rastgele bir değer verin. |

### 1.2 Üretime geçmeden MUTLAKA değiştirilecekler

| Değişken | Kodda varsayılan | Üretimde olması gereken | Neden |
|---|---|---|---|
| `ADMIN_USER` | `admin` | kendi değeriniz | Yönetim paneli |
| `ADMIN_PASS` | `admin` | güçlü parola | **Varsayılan `admin`/`admin`** |
| `PATIENT_TEST_OTP_ENABLED` | `true` | `false` | Açıkken SMS kodu **`000000`** kabul ediliyor |
| `PATIENT_TCKN_CHECKSUM` | `false` | `true` | Kapalıyken uydurma T.C. kimlik numarası kabul ediliyor |
| `SEED_MANAGER_DEMO` | `true` | `false` | Açıkken demo kayıtları otomatik ekleniyor |
| `DOCTOR_ACCOUNTS_JSON` | test hesabı, parola `1` | gerçek hesaplar | Varsayılan parola `1` |
| `PATIENT_ACCOUNTS_JSON` | test hastası, parola `1` | gerçek hesaplar | Varsayılan parola `1` |

### 1.3 Yapılandırma

| Değişken | Varsayılan | Açıklama |
|---|---|---|
| `APP_VERSION` | `v2.23.0` | Arayüzde gösterilen sürüm |
| `GEMINI_MODEL` | `gemini-2.5-flash` | |
| `TEMPERATURE` | `0` | Gemini çıktı kararlılığı |
| `OPENAI_STT_MODEL` | `gpt-4o-transcribe-diarize` | |
| `OPENAI_STT_FALLBACK_MODEL` | `gpt-transcribe` | Birincisi başarısızsa |
| `OPENAI_STT_LANGUAGE` | `tr` | |
| `OPENAI_STT_TIMEOUT` | `900` | Saniye |
| `COMED_WEB_BASE_URL` | `https://goztepetest.comed.mlpcare.com/tr-tr/medical` | **Canlıya geçerken test adresinden değiştirin** |
| `COMED_API_BASE_URL` | `https://goztepetestapi.comed.mlpcare.com/tr-tr/api/json` | Aynı şekilde |
| `SESSION_HOURS` | `12` | Web oturumu ömrü |
| `MOBILE_SESSION_DAYS` | `30` | Mobil token ömrü |
| `PATIENT_OTP_TTL_SECONDS` | `300` | OTP geçerlilik süresi |
| `PATIENT_OTP_MAX_ATTEMPTS` | `5` | Yanlış deneme sınırı |
| `PATIENT_LEGACY_LOGIN_ENABLED` | `false` | Eski hasta girişi; kapalı kalsın |
| `PATIENT_SMS_WEBHOOK_URL` | boş | Gerçek SMS için gerekli |
| `DB_PATH` | `kayitlar.db` | **Postgres'e geçince yerini `DATABASE_URL` alacak** |

### 1.4 Ölü değişkenler — kullanılmıyor, taşımayın

ElevenLabs desteği kaldırıldı ama `config.py:23-36` hâlâ bunları okuyor:
`ELEVENLABS_API_KEY`, `ELEVENLABS_STT_MODEL`, `ELEVENLABS_STT_LANGUAGE`,
`ELEVENLABS_STT_TIMEOUT`, `ELEVENLABS_STT_KEYTERMS`.

`KLINOT_API_BASE` yalnızca `scripts/live_comed_transfer.py` test betiğinde kullanılır.

---

## 2. Güvenlik — taşımadan önce kapatılması gerekenler

Mimari belgesinde (`docs/MIMARI.md`) de geçen, **hâlâ açık** olan konular.
Render'da iç ağda sorun olmayabilir ama kendi sunucunuzda internete açılınca önem kazanır.

1. **Kimlik doğrulaması olmayan uçlar var:** `POST /analyze`, `/analyze/stream`,
   `/transcribe`, `/pdf`, `GET /legacy`. Bunlar token istemiyor. Taşımadan önce
   ya kapatın ya kimlik doğrulaması ekleyin — aksi halde adresi bilen herkes
   LLM bütçenizi harcayabilir.
2. **Hız sınırı (rate limit) yok.** Nginx seviyesinde sınır koyun (§3.2).
3. **CORS yapılandırması yok.** Mobil uygulama ve eklenti doğrudan çağırdığı için
   şimdilik sorun çıkarmıyor; tarayıcıdan başka origin eklenirse gözden geçirin.
4. **HTTPS zorunlu olmalı.** Hasta verisi taşıyor; §3.3'teki Let's Encrypt adımı atlanmasın.
5. `.env` dosyası depoya **girmiyor** (`.gitignore`'da). Sunucuda `chmod 600` yapın.

---

## 3. Ubuntu sunucu kurulumu

Varsayım: Ubuntu 22.04/24.04, `klinot` adlı bir kullanıcı, uygulama `/opt/klinot` altında.

### 3.1 Temel kurulum

```bash
sudo apt update && sudo apt install -y python3.11 python3.11-venv nginx git
sudo useradd -r -m -d /opt/klinot -s /bin/bash klinot
sudo -u klinot git clone https://github.com/Enesaydnn7/Doktor-hasta-Gorusmesi.git /opt/klinot/app
cd /opt/klinot/app
sudo -u klinot python3.11 -m venv /opt/klinot/venv
sudo -u klinot /opt/klinot/venv/bin/pip install -r requirements.txt
# Postgres'e geçerken:
sudo -u klinot /opt/klinot/venv/bin/pip install "psycopg[binary,pool]"
```

Ortam dosyası — `/opt/klinot/app/.env` (§1'deki değişkenler):

```bash
sudo -u klinot cp .env.example /opt/klinot/app/.env
sudo -u klinot nano /opt/klinot/app/.env     # §1.1 ve §1.2'yi doldurun
sudo chmod 600 /opt/klinot/app/.env
```

### 3.2 systemd servisi

`/etc/systemd/system/klinot.service`:

```ini
[Unit]
Description=Klinot FastAPI
After=network.target

[Service]
Type=exec
User=klinot
Group=klinot
WorkingDirectory=/opt/klinot/app
EnvironmentFile=/opt/klinot/app/.env
ExecStart=/opt/klinot/venv/bin/uvicorn main:app \
    --host 127.0.0.1 --port 8000 --workers 2 --proxy-headers \
    --forwarded-allow-ips='127.0.0.1'
Restart=always
RestartSec=5
# Guvenlik siniri
NoNewPrivileges=true
PrivateTmp=true
ProtectSystem=strict
ProtectHome=true
ReadWritePaths=/opt/klinot/app

[Install]
WantedBy=multi-user.target
```

```bash
sudo systemctl daemon-reload
sudo systemctl enable --now klinot
sudo systemctl status klinot
journalctl -u klinot -f          # canli log
```

> **`--workers 2` uyarısı:** Birden fazla worker **ancak Postgres'e geçtikten sonra**
> güvenlidir. SQLite ile kalırsanız `--workers 1` kullanın; `db.py` içindeki
> `threading.Lock` yalnızca tek süreç içinde çalışır, süreçler arası korumaz.

### 3.3 Nginx + HTTPS

`/etc/nginx/sites-available/klinot`:

```nginx
# Ses yukleme ve hiz siniri
client_max_body_size 64M;          # kodda yukleme siniri 48 MB
limit_req_zone $binary_remote_addr zone=klinot:10m rate=30r/m;

server {
    listen 80;
    server_name klinot.ornek.com;

    location / {
        limit_req zone=klinot burst=20 nodelay;
        proxy_pass http://127.0.0.1:8000;
        proxy_set_header Host              $host;
        proxy_set_header X-Real-IP         $remote_addr;
        proxy_set_header X-Forwarded-For   $proxy_add_x_forwarded_for;
        proxy_set_header X-Forwarded-Proto $scheme;

        # Ses oynaticinin ileri/geri atlamasi icin sart:
        proxy_buffering off;

        # Analiz uzun surer
        proxy_read_timeout 900s;
        proxy_send_timeout 900s;
    }
}
```

```bash
sudo ln -s /etc/nginx/sites-available/klinot /etc/nginx/sites-enabled/
sudo nginx -t && sudo systemctl reload nginx
sudo apt install -y certbot python3-certbot-nginx
sudo certbot --nginx -d klinot.ornek.com      # HTTPS'i otomatik kurar
```

> **Not:** `proxy_buffering off;` satırını silmeyin. Ses kayıtlarında ileri/geri
> atlama HTTP byte-range (206) ile çalışıyor; nginx tamponlaması bunu bozabiliyor.

### 3.4 Taşıma sonrası güncellenecek yerler

- **Mobil uygulama:** `mobile_app/lib/api_client.dart` içindeki sunucu adresi.
  Yeni APK derlenip dağıtılmalı.
- **Chrome eklentisi:** Eklenti penceresindeki **API adresi** alanı
  (varsayılanı `comed_bridge_extension/popup.html` içinde). Doktorların
  eklentiyi yeniden bağlaması gerekir.
- `render.yaml` ve `Procfile` artık gereksiz; silinebilir.

---

## 4. Supabase (Postgres) geçişi

### 4.1 İşin büyüklüğü

Değişecek tek dosya `db.py`. Aşağıdaki SQLite'a özgü yerler düzeltilecek:

| Yer | Şu an | Postgres karşılığı |
|---|---|---|
| `db.py:39` | `sqlite3.connect(DB_PATH)` | `psycopg` bağlantı havuzu (`DATABASE_URL`) |
| `db.py:40` | `row_factory = sqlite3.Row` | `psycopg.rows.dict_row` |
| `db.py:34` | `threading.Lock()` | Gereksiz — havuz halleder, silinir |
| `db.py:55,241,267` | `INTEGER PRIMARY KEY AUTOINCREMENT` | `BIGSERIAL PRIMARY KEY` |
| `db.py:60,107` | `BLOB` | `BYTEA` (ama §4.3'ü okuyun) |
| `db.py:64,153,186,257` | `PRAGMA table_info(...)` | `information_schema.columns` sorgusu |
| `db.py:178,848,885` | `INSERT OR REPLACE INTO` | `INSERT ... ON CONFLICT (...) DO UPDATE` |
| tüm sorgular | `?` parametre | `%s` parametre |

`db.py:536` zaten `ON CONFLICT ... DO UPDATE` kullanıyor — o kısım hazır.

### 4.2 Tablolar

`kayitlar`, `bekleyen_sesler`, `transcription_jobs`, `comed_worklist`,
`comed_transfers`, `comed_trace_events`.

`comed_worklist` bileşik birincil anahtar kullanıyor: `(visit_id, synced_by)`.

### 4.3 ⚠ Ses kayıtları — en kritik karar

**Şu anda ses dosyaları veritabanının içinde `BLOB` olarak duruyor.**
Mevcut geliştirme veritabanından ölçüm:

```
veritabanı toplam : 6.6 MB
bunun sesi        : 5.6 MB   (yani %85'i ses)
12 kayıt, ortalama 0.5 MB — bunlar kısa test kayıtları
```

Gerçek bir 15–30 dakikalık görüşme **10–30 MB** olur. Buna göre:

| Plan | Alan | Yaklaşık kapasite |
|---|---|---|
| Supabase ücretsiz veritabanı | 500 MB | **~25–50 görüşme** |
| Supabase Pro veritabanı | 8 GB | ~400–800 görüşme |
| Supabase **Storage** (ücretsiz) | 1 GB | ~50–100 görüşme |
| Supabase **Storage** (Pro) | 100 GB | ~5.000–10.000 görüşme |

**Öneri:** Sesleri veritabanında değil **Supabase Storage**'da tutun.
Veritabanında yalnızca dosya yolu dursun. Bu değişiklik:

- `db.py`'de `ses` sütunu `BYTEA` yerine `TEXT` (storage yolu) olur,
- `main.py`'deki `_audio_response` yardımcısı dosyayı Storage'dan çeker,
  ya da doğrudan imzalı URL'ye yönlendirir,
- Postgres yedekleri küçük ve hızlı kalır.

Sesi veritabanında bırakmayı seçerseniz Postgres `BYTEA` bunu kaldırır,
ancak yedekler devasa olur ve Supabase ücretsiz plan çok çabuk dolar.

### 4.4 Veri taşıma

Mevcut `kayitlar.db` içindeki veriyi taşımak isterseniz:

```bash
# 1. Semayi Postgres'te olustur (db.py yeni haliyle uygulama bir kez acilir)
# 2. Veriyi aktar - pgloader en pratigi:
sudo apt install -y pgloader
pgloader kayitlar.db "postgresql://KULLANICI:PAROLA@db.xxxx.supabase.co:5432/postgres"
```

`pgloader` BLOB → BYTEA dönüşümünü kendi yapar. Aktarımdan sonra
`id` dizilerini (sequence) ileri sarmayı unutmayın:

```sql
SELECT setval('kayitlar_id_seq',        (SELECT COALESCE(MAX(id),1) FROM kayitlar));
SELECT setval('comed_transfers_id_seq', (SELECT COALESCE(MAX(id),1) FROM comed_transfers));
SELECT setval('comed_trace_events_id_seq', (SELECT COALESCE(MAX(id),1) FROM comed_trace_events));
```

### 4.5 Bağlantı adresi

Supabase panelinde **Project Settings → Database → Connection string**.
İki seçenek var:

- **Session pooler (port 5432):** uzun ömürlü bağlantılar, bizim için uygun.
- **Transaction pooler (port 6543):** sunucusuz ortamlar için; `PREPARE`
  desteklemez, kullanmayın.

```
DATABASE_URL=postgresql://postgres.xxxx:PAROLA@aws-0-eu-central-1.pooler.supabase.com:5432/postgres
```

> Supabase parolası gerçek bir sırdır — `.env` dışına yazmayın, depoya koymayın.

---

## 5. Taşıma günü kontrol listesi

**Hazırlık**
- [ ] Supabase projesi açıldı, `DATABASE_URL` alındı
- [ ] Sunucu kuruldu, domain DNS'i sunucuya yönlendirildi
- [ ] `.env` dolduruldu (§1.1 + §1.2 hepsi)

**Kod**
- [ ] `db.py` Postgres'e çevrildi (§4.1 tablosundaki 8 madde)
- [ ] `requirements.txt`'e `psycopg[binary,pool]` eklendi
- [ ] Ses saklama kararı verildi (§4.3) ve uygulandı
- [ ] `python -m pytest` geçiyor
- [ ] Korumasız uçlar kapatıldı (§2.1)

**Dağıtım**
- [ ] systemd servisi çalışıyor (`systemctl status klinot`)
- [ ] Nginx + HTTPS ayakta, `proxy_buffering off` duruyor
- [ ] Veri aktarıldı, sequence'ler ileri sarıldı

**Taşıma sonrası duman testi**
- [ ] `/health` 200 dönüyor
- [ ] Yönetici paneline giriş
- [ ] Doktor paneline giriş, kayıt listesi geliyor
- [ ] **Ses oynatılıyor ve ileri/geri atlanabiliyor** (byte-range + nginx testi)
- [ ] PDF indiriliyor
- [ ] Mobil uygulama yeni adresle bağlanıyor (yeni APK)
- [ ] Eklenti yeni API adresiyle bağlanıyor, COMED iş listesi eşitleniyor
- [ ] Yedekleme kuruldu (Supabase otomatik yedek + Storage)

---

## 6. Bu belgenin kapsamadıkları

- Google Play / App Store yayını (şu an APK elden dağıtılıyor)
- Chrome Web Store yayını (eklenti paketlenmemiş olarak kuruluyor)
- İzleme/alarm (uptime, hata takibi) kurulumu
- Yük testi
