"""Yerel gelistirme icin doktor paneline ornek COMED is listesi ve kayit ekler.

Yalnizca 127.0.0.1 uzerinde calisan gelistirme sunucusunu denemek icindir;
uretim verisine dokunmaz. Calistirmak icin:

    python scripts/seed_demo_worklist.py
"""

import math
import struct
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

import auth  # noqa: E402
import db  # noqa: E402


def wav_tone(seconds: int = 20, rate: int = 8000, freq: float = 220.0) -> bytes:
    """Tarayicinin gercekten calabilecegi kucuk bir WAV uret.

    Ses oynaticinin ileri/geri atlamasini denemek icin gecerli bir dosya
    gerekiyor; rastgele baytlar cozulemiyor.
    """
    frames = bytearray()
    for index in range(rate * seconds):
        value = int(12000 * math.sin(2 * math.pi * freq * index / rate))
        frames += struct.pack("<h", value)
    data_size = len(frames)
    header = b"RIFF" + struct.pack("<I", 36 + data_size) + b"WAVEfmt "
    header += struct.pack("<IHHIIHH", 16, 1, 1, rate, rate * 2, 2, 16)
    header += b"data" + struct.pack("<I", data_size)
    return bytes(header + frames)


PATIENTS = [
    ("22207357", "Enes Aydın", "1300013", "Kardiyoloji", "12.04.1991"),
    ("22207358", "Dursun Kılıçarslan", "476644", "Dahiliye", "03.11.1958"),
    ("22207359", "Sena Nur Yıldız", "1300027", "Göğüs Hastalıkları", "22.10.1997"),
    ("22207360", "Mehmet Can Öztürk", "1300041", "Ortopedi", "07.02.1983"),
    ("22207361", "Ayşe Demirtaş", "1300055", "Nöroloji", "18.06.2002"),
]

AUDIO = wav_tone()  # ~320 KB, 20 saniyelik gercek ses


def main() -> None:
    doctor = next(iter(auth._doctor_accounts()))

    items = [
        {
            "visit_id": visit,
            "clinical_card_id": visit,
            "patient_id": patient_no,
            "patient_name": name,
            "patient_no": patient_no,
            "protocol_no": f"V-{visit}",
            "department": department,
            "doctor_name": "Prof. Dr. Personel Kaya",
            "task": f"{department} muayenesi",
            "status": "Bekliyor",
            "birth_date": birth,
            "clinical_card_url": (
                "https://goztepetest.comed.mlpcare.com/tr-tr/medical/"
                f"hasta-tibbi-karti/{visit}/patient-clinical-card/"
            ),
        }
        for visit, name, patient_no, department, birth in PATIENTS
    ]
    count = db.comed_worklist_sync(items, synced_by=doctor)

    # Ilk iki hastaya birer gorusme kaydi bagla; biri sesli olsun.
    for visit, name, *_ in PATIENTS[:2]:
        db.kaydet(
            f"Doktor: Merhaba {name}, şikayetiniz nedir? Hasta: Göğsümde ağrı var.",
            {"ozet": f"{name} için hasta özeti"},
            {"ozet": f"{name} için AI epikriz"},
            {"ozet": f"{name} için yönetim raporu"},
            ses=AUDIO,
            ses_mime="audio/wav",
            ses_ad=f"{visit}.wav",
            owner_user=doctor,
            assigned_doctor_user=doctor,
            metadata={
                "comed_patient": {
                    "visit_id": visit,
                    "patient_name": name,
                    "clinical_card_url": items[0]["clinical_card_url"],
                }
            },
        )

    print(f"{count} hasta ve 2 kayıt eklendi · doktor: {doctor}")


if __name__ == "__main__":
    main()
