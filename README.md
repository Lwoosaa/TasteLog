# TasteLog 🎵🎬

Spotify dinleme geçmişin ile Letterboxd film günlüğünü birleştiren kişisel analiz aracı.

## Özellikler

**Müzik analizi**
- Haftalık / aylık / yıllık / özel tarih aralığı seçimi
- Seçilen dönemin en çok dinlenen sanatçıları ve şarkıları (top 10, grafikli)
- Günün saatine göre dinleme dağılımı
- Tüm dönem için aylık dinleme trendi
- Sanatçı, albüm ve şarkı tam sıralamaları (sınırsız, kaydırılabilir tablo)

**Film analizi**
- Letterboxd Diary — tarih, puan, tekrar izleme bilgisi
- Tüm İzlenenler — diary'de olmayan filmleri de gösterir
- TMDB entegrasyonu: kullanıcı puanı, oy sayısı, yayın tarihi, tür, keywords

## Kurulum

```bash
git clone https://github.com/Lwoosaa/TasteLog.git
cd TasteLog
pip install -r requirements.txt
```

**TMDB API key** için [themoviedb.org](https://www.themoviedb.org/settings/api) adresinden ücretsiz key al,
`settings.json` dosyasına ekle:

```json
{
  "tmdb_api_key": "senin_key_buraya"
}
```

İsteğe bağlı olarak top 5000 filmi önceden cache'e almak için:

```bash
python scripts/fetch_popular.py
```

## Çalıştırma

```bash
streamlit run app/main.py
```

Tarayıcıda `http://localhost:8501` adresine git, sol menüden Spotify ve Letterboxd ZIP dosyalarını yükle.

## Veri kaynakları

**Spotify:** Hesap → Gizlilik → Verilerimi İndir → Genişletilmiş Akış Geçmişi  
**Letterboxd:** Profil → Ayarlar → Import & Export → Export Your Data

## Proje yapısı

```
TasteLog/
├── app/
│   └── main.py               # Streamlit uygulaması
├── src/
│   ├── spotify_parser.py     # Spotify JSON → DataFrame
│   ├── letterboxd_parser.py  # Letterboxd CSV → DataFrame
│   ├── database.py           # SQLite sorguları (range bazlı)
│   └── tmdb.py               # TMDB API + SQLite cache
├── scripts/
│   ├── fetch_popular.py      # Top 5000 filmi önceden cache'e al
│   └── fill_missing_keywords.py  # Eksik keyword'leri tamamla
├── data/raw/                 # Ham veriler (.gitignore'da)
├── db/                       # SQLite veritabanı (.gitignore'da)
├── settings.json             # API key (.gitignore'da)
└── requirements.txt
```

## Teknik notlar

- 30 saniyeden kısa dinlemeler skip sayılıp filtrelenir
- Timezone: Europe/Istanbul
- TMDB verileri SQLite'a cache'lenir — her film için API tek sefer çağrılır
- `add_vline` Plotly'de string eksende çalışmaz, yerine `add_scatter` kullanılır

## Planlanan özellikler

- Film izlediğin gün müzik korelasyonu (film × müzik zaman çizelgesi)
- Müzik türü × film türü / keyword korelasyonu
- Spotify API ile gerçek zamanlı veri ve tür bilgisi
- FastAPI + React web uygulaması
