# musicboxd 🎵🎬

Spotify dinleme geçmişin ile Letterboxd film günlüğünü birleştiren kişisel analiz aracı.

## Özellikler

- Aylık en çok dinlenen sanatçılar ve şarkılar
- Günün saatine göre dinleme alışkanlıkları
- Aylık dinleme trendi
- Letterboxd film günlüğü entegrasyonu
- Film izlediğin gün ne dinlediğini görme

## Kurulum

```bash
git clone https://github.com/kullanici_adi/musicboxd
cd musicboxd
pip install -r requirements.txt
```

## Çalıştırma

```bash
streamlit run app/main.py
```

Tarayıcıda `http://localhost:8501` adresine git, sol menüden ZIP dosyalarını yükle.

## Veri kaynakları

**Spotify:** Hesap → Gizlilik → Verilerimi İndir → Genişletilmiş Akış Geçmişi  
**Letterboxd:** Profil → Ayarlar → Import & Export → Export Your Data

## Proje yapısı

```
musicboxd/
├── app/
│   └── main.py          # Streamlit uygulaması
├── src/
│   ├── spotify_parser.py    # Spotify JSON okuyucu
│   ├── letterboxd_parser.py # Letterboxd CSV okuyucu
│   └── database.py          # SQLite işlemleri
├── data/raw/            # Ham veriler (.gitignore'da)
├── db/                  # SQLite veritabanı (.gitignore'da)
└── requirements.txt
```

## İleride eklenecekler

- Film izlediğin gün müzik korelasyonu
- Tür bazlı analiz (müzik türü × film türü)
- Spotify API ile gerçek zamanlı veri
- FastAPI + React web uygulaması
