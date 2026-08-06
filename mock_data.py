# -*- coding: utf-8 -*-
"""
DEMO modu verisi (API anahtarsız çalışma ve sunum için).
Genişletilmiş örnek diyalogla (gerilim tipi baş ağrısı) uyumludur.
Diyalogda GEÇMEYEN alanlar bilerek "belirtilmedi"/boş bırakılmıştır —
sistem uydurma yapmaz, gerçek davranışı budur.
"""


def results():
    return {
        "hasta": {
            "ozet": "Üç haftadır süren baş ağrınız için yapılan görüşmede, ağrınızın büyük "
                    "olasılıkla yoğun stres ve az uykuya bağlı kas gerginliğinden kaynaklandığı "
                    "değerlendirildi. Tansiyon ölçümü ve kısa bir sinir sistemi muayenesi planlandı.",
            "tani": "Gerilim tipi baş ağrısı (kas gerginliğine bağlı baş ağrısı) — tehlikeli bir durum düşünülmüyor.",
            "yapilacaklar": [
                "Uyku düzeninizi toparlayın; gecede 7-8 saat uyumayı hedefleyin.",
                "Gün içinde kısa molalar verip ekrandan ve masadan uzaklaşın.",
                "Boyun ve omuz bölgesi için basit gevşeme/germe hareketleri yapın.",
            ],
            "ilaclar": [
                "Parasetamol (Parol) — yalnızca ağrınız olduğunda, doktorunuzun önerdiği dozda.",
            ],
            "kontrol": "2 hafta sonra kontrole gelmeniz önerildi. Ağrı aniden çok şiddetlenirse, "
                       "ateş, bulanık görme veya kusma eklenirse beklemeden başvurun.",
            "kapanis": "Muayenede endişe verici bir bulgu tarif edilmedi. Uyku ve stres düzenlenince "
                       "şikayetlerinizin belirgin şekilde azalması bekleniyor.",
        },
        "doktor": {
            "epikriz": {
                "gorusmeTarihi": "05.08.2026",
                "doktor": "belirtilmedi",
                "sikayet": "Baş ağrısı (iki yanlı, sıkıştırıcı), konsantrasyon güçlüğü",
                "baslangic": "3 hafta önce (yaklaşık 15.07.2026)",
                "oyku": "Yaklaşık 3 haftadır süren, öğleden sonra başlayıp akşam artan, iki yanlı "
                        "sıkıştırıcı/baskı tarzında, enseye yayılan baş ağrısı. Bulantı, kusma, "
                        "fotofobi yok. Masa başı yoğun çalışma, belirgin iş stresi, gecede 4-5 saat "
                        "uyku. Parasetamole kısmi ve geçici yanıt.",
                "agriSkoru": "6/10",
                "ozgecmis": {
                    "kronik": [],
                    "ameliyatlar": ["Apandektomi (2015)"],
                    "ilaclar": [],
                    "alerji": [],
                    "aliskanlik": ["Sigara: kullanmıyor", "Alkol: sosyal, nadir"],
                },
                "soygecmis": ["Annede hipertansiyon"],
                "fizikMuayene": "Planlandı: tansiyon ölçümü ve kısa nörolojik muayene. Görüşmede "
                                "fokal nörolojik yakınma veya kırmızı bayrak tarif edilmedi.",
                "lab": ["istendi: tansiyon ölçümü (görüşme sırasında planlandı)"],
                "onTani": "Gerilim tipi baş ağrısı (uykusuzluk ve stresle tetiklenmiş)",
                "kesinTani": "belirtilmedi",
                "icd": [
                    {"kod": "G44.2", "aciklama": "Gerilim tipi baş ağrısı"},
                    {"kod": "R51", "aciklama": "Baş ağrısı"},
                ],
                "tedavi": [
                    "Parasetamol (Parol) — gerektiğinde, mevcut kullanım şemasıyla devam",
                    "Uyku hijyeni ve stres yönetimi önerileri",
                ],
                "plan": "Tansiyon ölçümü ve kısa nörolojik muayene; uyku düzeni ve stres yönetimi "
                        "önerileri; yanıt alınamazsa veya alarm bulgusu gelişirse ileri değerlendirme.",
                "kontrol": {
                    "onerildi": True,
                    "zaman": "2 hafta sonra (yaklaşık 19.08.2026)",
                    "not": "Ağrının aniden şiddetlenmesi, ateş, görme bozukluğu veya kusma "
                           "eklenmesi halinde erken başvuru.",
                },
            },
            "koclugu": {
                "guclu": [
                    "Açık uçlu sorularla sistematik ve yeterli bir öykü alındı (başlangıç, karakter, eşlik eden bulgular).",
                    "Hastanın 'tümör' endişesi fark edilip sakin ve anlaşılır biçimde giderildi.",
                    "Ağrı skoru ve özgeçmiş/soygeçmiş sorgulandı — kayıt kalitesi açısından güçlü.",
                ],
                "oneriler": [
                    {"an": "Hasta 'ciddi bir şey değil di mi, tümör mü?' diye endişelendiğinde",
                     "oneri": "Endişeyi normalize eden bir cümle ('bu çok yaygın bir korku, birlikte adım adım bakacağız') güveni daha da artırır."},
                    {"an": "Kırmızı bayrak taraması kısmen eksik kaldı",
                     "oneri": "'Ani ve şimşek gibi mi başladı, hayatınızın en şiddetli ağrısı mı, ateş/görme değişikliği/güçsüzlük var mı' soruları eklenmeli."},
                ],
            },
        },
        "yonetim": {
            "guvenlik": {
                "durum": "temiz",
                "hasta": "Hasta dilinde uygunsuz, argo veya saygısız ifade saptanmadı.",
                "doktor": "Doktorun dili saygılı, sakin ve profesyonel.",
                "tespitler": [],
            },
            "skor": {"genel": 87, "empati": 92, "netlik": 86, "dinleme": 82, "verimlilik": 84},
            "verimlilikNotu": "Görüşme hedefe yönelik ilerledi; başlangıç tarihi, ağrı skoru, özgeçmiş "
                              "ve soygeçmiş eksiksiz sorgulandı. Kırmızı bayrak taramasının tam "
                              "yapılmaması ve kontrol tarihinin netleştirilme biçimi küçük puan kaybettirdi.",
            "degerlendirme": "Görüşme sıcak ve yapıcı geçti. Doktor hastanın endişesini fark edip "
                             "giderdi, anamnez büyük ölçüde eksiksizdi ve plan anlaşılır aktarıldı. "
                             "Geliştirilecek tek alan tam kırmızı bayrak taraması.",
            "risk": "yok",
        },
    }
