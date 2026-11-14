# 🌐 UAS Penambangan & Pencarian Web (PPW)
### Web Structure Mining: Crawling, Link Graph, PageRank, dan Citation Graph Explorer

Dokumentasi dan repositori proyek **Ujian Akhir Semester (UAS)** mata kuliah **Penambangan & Pencarian Web (PPW)**, Program Studi Teknik Informatika, Fakultas Teknik, Universitas Trunojoyo Madura.

---

## 👤 Biodata Mahasiswa
- **Nama**: Muhammad Ilham Adila Almafaz
- **NIM**: 230411100113 (23-113)
- **Program Studi**: Teknik Informatika
- **Fakultas**: Fakultas Teknik
- **Universitas**: Universitas Trunojoyo Madura

---

## 📌 Deskripsi Proyek
Proyek ini mengimplementasikan sistem **Web Structure Mining** secara menyeluruh (*end-to-end*):
1. **Web Crawler Rekursif (BFS)**: Menjelajahi halaman web dari *seed URL* (domain `trunojoyo.ac.id`), mengekstraksi metadata judul `<title>` dan seluruh hyperlink `<a href="...">`.
2. **Pemodelan Graf Berarah (*Directed Graph / DiGraph*)**: Memodelkan halaman sebagai simpul (*nodes*) dan tautan hyperlink sebagai busur berarah (*edges* $A \to B$) menggunakan pustaka **NetworkX**.
3. **Analisis Algoritma PageRank**: Menghitung skor probabilitas prestise/kualitas setiap halaman web melalui metode iteratif dengan *damping factor* ($d = 0{,}85$), serta mendeteksi titik konvergensi.
4. **Analisis Sentralitas Jaringan**: Menghitung perbandingan metrik *In-Degree Centrality*, *Out-Degree Centrality*, dan *Betweenness Centrality*.
5. **Interactive Citation Graph UI**: Membangun visualisasi interaktif topologi jaringan web ala *ScienceDirect* / *Connected Papers* berbasis **PyVis (Vis.js)** dan dashboard **Streamlit**.
6. **Perankingan Top-10**: Menemukan dan menampilkan 10 halaman web paling penting (*most authoritative pages*) berdasarkan skor PageRank tertinggi.

---

## 🚀 Alur Kerja Sistem (*Pipeline Architecture*)

```
[Seed URL: trunojoyo.ac.id]
           │
           ▼
[BFS Web Crawler & Link Extractor]
           │
           ▼
[Directed Graph (NetworkX DiGraph)] ──> [Adjacency Matrix & Network Density]
           │
           ▼
[PageRank Calculation (d = 0.85)] ───> [Centrality Measures (Degree, Betweenness)]
           │
           ▼
[Top-10 Leaderboard & Visualization]
           │
           ▼
[Interactive Citation Graph UI (Streamlit & PyVis)] ──> [Export JSON/CSV for Lab Server]
```

---

## 📁 Struktur Direktori Repositori

```text
UAS_PPW/
├── app.py                     # Aplikasi Dashboard Streamlit Interaktif
├── UAS1.ipynb                 # Notebook Eksperimen & Analisis Lengkap
├── requirements.txt           # Dependensi pustaka Python
├── run_app.bat                # Shortcut menjalankan Streamlit di Windows
├── update.ps1                 # Skrip otomatisasi Git Add, Commit & Push
├── .gitignore                 # File pengabaian Git
├── README.md                  # Dokumentasi proyek
└── Output/
    ├── graph_pagerank.json    # Data graf & skor PageRank terstruktur
    ├── top10_pagerank.csv     # Data Top-10 halaman terbaik
    └── citation_graph.html    # Standalone HTML graf interaktif
```

---

## 💻 Panduan Menjalankan Secara Lokal

### 1. Clone Repositori
```bash
git clone https://github.com/ilham08-GH/UAS_PPW.git
cd UAS_PPW
```

### 2. Install Dependensi
Pastikan Python 3.10+ sudah terpasang, lalu jalankan:
```bash
pip install -r requirements.txt
```

### 3. Menjalankan Dashboard Streamlit
Jalankan perintah berikut pada terminal:
```bash
streamlit run app.py
```
*(Atau cukup klik dua kali file `run_app.bat` pada Windows)*.

Buka browser di alamat: `http://localhost:8501`

---

## 📊 Fitur Aplikasi Streamlit (`app.py`)
- **Pilihan Sumber Data**:
  - 🧪 *Data Demo (UTM Sample)*: Eksplorasi langsung tanpa menunggu crawling.
  - 🕷️ *Crawl Langsung (Live)*: Crawling dinamis dari seed URL dengan konfigurasi batas halaman dan jeda request.
  - 📂 *Load File Tersimpan*: Membaca data hasil analisis dari folder `Output/`.
- **Interactivity Citation Graph**: Node dapat digeser (*drag*), diperbesar (*zoom*), dan di-*hover* untuk membaca metadata detail halaman.
- **Top-10 Leaderboard**: Menampilkan peringkat halaman terpenting lengkap dengan nama deskriptif dan grafik batang.
- **Ekspor Data Lab**: Download file `graph_pagerank.json`, `top10_pagerank.csv`, dan `citation_graph.html` siap saji untuk integrasi backend server lab.
