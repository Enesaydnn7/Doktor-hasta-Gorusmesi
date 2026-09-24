# Yönetici demosu ses kaydı

- Dosya: `gastrit_demo_kayit_2_2026-08-27.webm`
- Canlı kayıt numarası: `#2`
- Kayıt zamanı: `27 Ağustos 2026 12:53:10`
- Senaryo: Doktor–hasta gastrit görüşmesi demosu
- Boyut: `2.226.888` bayt
- SHA-256: `C0C115F894D68A7382CC7C000AF977E7C01C8380AD22A70080E7A9761550C540`
- Not: Bu kayıtta ElevenLabs anahtarı `401 Unauthorized` döndürdüğü için ses dökümü OpenAI yedeğiyle yapılmıştır.
- Arşiv verisi: `gastrit_demo_kayit_2_2026-08-27.json`

Dosya private repoda korunur. Uygulama her yeni/geçici SQLite veritabanında bu arşivi bir kez otomatik eklediği için demo admin panelinde yeniden görünür.

## Bacak ağrısı deneme kaydı

- Ses: `bacak_agrisi_demo_kayit_2_2026-09-09.m4a`
- Arşiv verisi: `bacak_agrisi_demo_kayit_2_2026-09-09.json`
- Kayıt zamanı: `9 Eylül 2026 16:55:15`
- Senaryo: Doktor–hasta bacak ağrısı görüşmesi
- Ses boyutu: `998.957` bayt
- SHA-256: `DB6FBD6D6B7C46124DC1FE4291816CED21FD5065D16317F1F43DAE81CE7CEC10`

Bu deneme de benzersiz `demo_key` ile her yeni/geçici SQLite veritabanına yalnızca bir kez eklenir; deploy sonrasında admin panelinde sesi ve raporlarıyla yeniden görünür.

## Göğüs ağrısı ve COMED aktarım denemesi

- Ses: `gogus_agrisi_demo_kayit_3_2026-09-24.m4a`
- Arşiv verisi: `gogus_agrisi_demo_kayit_3_2026-09-24.json`
- Kayıt zamanı: `24 Eylül 2026 06:44:49`
- Senaryo: Dursun Kılıçarslan test hastası; göğüs ağrısı ve tam COMED alan aktarımı
- Ses boyutu: `1.753.848` bayt
- SHA-256: `0CDC4D064251D38EADC70407328152BCD772D511E758932EA84C10991E85AF8A`

Bu kayıt da repo içinde ses, transkript, raporlar ve COMED taslağıyla korunur. Render'ın geçici diski sıfırlansa bile yeni veritabanına otomatik olarak yeniden eklenir.
