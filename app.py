import streamlit as st
import requests
from bs4 import BeautifulSoup
from urllib.parse import urljoin, urlparse
from collections import deque
import time
import json
import os
import networkx as nx
import numpy as np
import pandas as pd
import matplotlib.pyplot as plt
import matplotlib.cm as cm
import streamlit.components.v1 as components
from pyvis.network import Network

# ==============================================================================
# KONFIGURASI HALAMAN STREAMLIT (TANPA SIDEBAR, FULL-WIDTH)
# ==============================================================================
st.set_page_config(
    page_title="Citation Graph & Small-World Web Explorer",
    page_icon="🕸️",
    layout="wide",
    initial_sidebar_state="collapsed"
)

# Custom Styling (CSS) - Hapus sidebar sepenuhnya & beri gaya modern
st.markdown("""
<style>
    /* Sembunyikan sidebar dan tombol panah toggle */
    [data-testid="stSidebar"], 
    [data-testid="stSidebarNav"], 
    [data-testid="collapsedControl"] {
        display: none !important;
    }
    
    .block-container {
        padding-top: 1.6rem;
        padding-bottom: 2.5rem;
    }
    .main-title {
        font-size: 2.2rem;
        font-weight: 800;
        color: #0f172a;
        margin-bottom: 0.1rem;
    }
    .sub-title {
        font-size: 1.05rem;
        color: #475569;
        margin-bottom: 0.6rem;
    }
    .author-badge {
        display: inline-block;
        background-color: #f1f5f9;
        border: 1px solid #cbd5e1;
        color: #1e293b;
        padding: 4px 14px;
        border-radius: 9999px;
        font-size: 0.85rem;
        font-weight: 600;
        margin-bottom: 1.0rem;
    }
    .metric-card {
        background-color: #ffffff;
        border: 1px solid #e2e8f0;
        border-radius: 12px;
        padding: 14px;
        text-align: center;
        box-shadow: 0 1px 3px rgba(0,0,0,0.04);
    }
    .metric-val {
        font-size: 1.7rem;
        font-weight: 800;
        color: #2563eb;
    }
    .metric-lbl {
        font-size: 0.85rem;
        color: #64748b;
        font-weight: 600;
    }
    .graph-container {
        border: 1px solid #e2e8f0;
        border-radius: 12px;
        background-color: #ffffff;
        padding: 4px;
        box-shadow: 0 2px 6px rgba(0,0,0,0.03);
    }
</style>
""", unsafe_allow_html=True)


# ==============================================================================
# FUNGSI PAGERANK ROBUST (BEBAS ERROR SCIPY)
# ==============================================================================
def compute_pagerank(G, alpha=0.85, max_iter=100, tol=1e-6):
    """Menghitung PageRank dengan NetworkX, fallback otomatis ke Power Iteration murni jika SciPy absen."""
    try:
        return nx.pagerank(G, alpha=alpha, max_iter=max_iter, tol=tol)
    except Exception:
        nodes = list(G.nodes())
        N = len(nodes)
        if N == 0:
            return {}
        pr = {n: 1.0 / N for n in nodes}
        for _ in range(max_iter):
            pr_new = {}
            dangling_sum = sum(pr[n] for n in nodes if G.out_degree(n) == 0)
            dangling_contrib = alpha * dangling_sum / N
            for v in nodes:
                in_sum = sum(pr[u] / G.out_degree(u) for u in G.predecessors(v) if G.out_degree(u) > 0)
                pr_new[v] = (1.0 - alpha) / N + alpha * in_sum + dangling_contrib
            diff = sum(abs(pr_new[n] - pr[n]) for n in nodes)
            pr = pr_new
            if diff < tol:
                break
        return pr


# ==============================================================================
# DETEKSI KOMUNITAS (CLUSTERING KELOMPOK ALA CONNECTED PAPERS)
# ==============================================================================
# Palet warna komunitas khas Connected Papers
COMMUNITY_PALETTE = [
    '#3b82f6',  # Biru
    '#10b981',  # Hijau Emerald
    '#f97316',  # Oranye
    '#ef4444',  # Merah Coral
    '#8b5cf6',  # Ungu Violet
    '#eab308',  # Kuning Emas
    '#06b6d4',  # Cyan
    '#ec4899',  # Pink
    '#84cc16',  # Lime
    '#a855f7',  # Lavender
    '#b45309',  # Coklat Amber
    '#0284c7'   # Biru Langit
]

def detect_communities(G):
    """Deteksi komunitas/klaster simpul menggunakan algoritma Louvain atau Modularity."""
    G_undir = G.to_undirected()
    if G_undir.number_of_nodes() == 0:
        return {}
    try:
        # Louvain Community Detection
        comm_list = list(nx.community.louvain_communities(G_undir, seed=42))
    except Exception:
        try:
            comm_list = list(nx.community.greedy_modularity_communities(G_undir))
        except Exception:
            comm_list = [set(G.nodes())]
            
    node_to_community = {}
    for comm_idx, members in enumerate(comm_list):
        for node in members:
            node_to_community[node] = comm_idx
    return node_to_community


# ==============================================================================
# FUNGSI HELPER: NAMA HALAMAN DESKRIPTIF
# ==============================================================================
def get_page_name(url, page_titles=None, max_len=30):
    """Menghasilkan nama halaman manusiawi dari <title>, subdomain, atau slug path."""
    parsed = urlparse(url)
    if page_titles and url in page_titles:
        title = str(page_titles[url]).strip()
        for suffix in ['- Universitas Trunojoyo Madura', '| Universitas Trunojoyo Madura', '- UTM', '| UTM']:
            if suffix in title:
                title = title.replace(suffix, '').strip()
        if title and title != '-' and title != url and not title.startswith('http'):
            return title[:max_len]
            
    netloc = parsed.netloc.replace('www.', '')
    subdomain = netloc.replace('.trunojoyo.ac.id', '').replace('trunojoyo.ac.id', '')
    path = parsed.path.strip('/')
    
    if path:
        last_slug = path.split('/')[-1]
        if subdomain:
            return f"[{subdomain}] /{last_slug}"[:max_len]
        return f"/{last_slug}"[:max_len]
    else:
        if subdomain:
            return f"[{subdomain}] Beranda"[:max_len]
        return "Beranda Utama (UTM)"


# ==============================================================================
# KELAS WEB CRAWLER (BFS)
# ==============================================================================
class WebCrawler:
    def __init__(self, seed_url, max_pages=35, delay=0.7, allowed_domains=None):
        self.seed_url = seed_url
        self.max_pages = max_pages
        self.delay = delay
        parsed = urlparse(seed_url)
        self.seed_domain = parsed.netloc
        self.allowed_domains = allowed_domains or [self.seed_domain]
        self.visited = set()
        self.edges = []
        self.page_titles = {}
        self.failed_urls = []
        self.headers = {'User-Agent': 'Mozilla/5.0 (Educational WebMining-Bot/UTM)'}
        
    def _normalize_url(self, url):
        parsed = urlparse(url)
        normalized = f"{parsed.scheme}://{parsed.netloc}{parsed.path}".rstrip('/')
        return normalized

    def _is_valid_url(self, url):
        try:
            parsed = urlparse(url)
            if parsed.scheme not in ('http', 'https'):
                return False
            if not any(d in parsed.netloc for d in self.allowed_domains):
                return False
            skip_ext = ('.pdf', '.jpg', '.png', '.gif', '.zip', '.docx', '.xlsx', '.css', '.js')
            if parsed.path.lower().endswith(skip_ext):
                return False
            return True
        except:
            return False

    def crawl(self, progress_callback=None):
        queue = deque([self._normalize_url(self.seed_url)])
        while queue and len(self.visited) < self.max_pages:
            current_url = queue.popleft()
            if current_url in self.visited:
                continue
            try:
                response = requests.get(current_url, headers=self.headers, timeout=8)
                if 'text/html' not in response.headers.get('Content-Type', ''):
                    continue
                self.visited.add(current_url)
                
                soup = BeautifulSoup(response.text, 'html.parser')
                title_tag = soup.find('title')
                title = title_tag.get_text(strip=True) if title_tag else current_url
                self.page_titles[current_url] = title
                
                found_links = set()
                for a_tag in soup.find_all('a', href=True):
                    full_url = urljoin(current_url, a_tag['href'].strip())
                    norm = self._normalize_url(full_url)
                    if self._is_valid_url(norm) and norm != current_url:
                        found_links.add(norm)
                        
                for target in found_links:
                    self.edges.append((current_url, target))
                    if target not in self.visited:
                        queue.append(target)
                        
                if progress_callback:
                    progress_callback(len(self.visited), self.max_pages, current_url, title)
                time.sleep(self.delay)
            except Exception as e:
                self.failed_urls.append((current_url, str(e)))
        return self.visited, self.edges, self.page_titles


# ==============================================================================
# FUNGSI MEMBANGUN CITATION GRAPH BERGAYA CONNECTED PAPERS (HTML)
# ==============================================================================
def generate_connected_papers_graph(G, pr_scores, ranking, page_titles, seed_url,
                                    color_mode="Klaster Komunitas (Connected Papers)",
                                    size_multiplier=1.0, spring_spacing=100,
                                    show_all_labels=False):
    """
    Menghasilkan graf interaktif bergaya Connected Papers:
    - Background putih bersih (#ffffff)
    - Node dikelompokkan ke dalam klaster warna komunitas
    - Node pusat (seed/Top-1) berwarna Charcoal gelap (#1e293b) seperti di Connected Papers
    - Garis edges abu-abu lembut (#cbd5e1)
    - Tata letak ForceAtlas2 untuk spatial clustering alami
    """
    net = Network(height='720px', width='100%', directed=True,
                  bgcolor='#ffffff', font_color='#1e293b', cdn_resources='remote')
    
    # Gunakan ForceAtlas2Based physics: algoritma pemetaan klaster ilmiah (Gephi / Connected Papers)
    net.force_atlas_2based(
        gravity=-50,
        central_gravity=0.015,
        spring_length=spring_spacing,
        spring_strength=0.07,
        damping=0.45,
        overlap=0.15
    )

    max_pr = max(pr_scores.values()) if pr_scores else 1
    min_pr = min(pr_scores.values()) if pr_scores else 0
    denom = (max_pr - min_pr) if (max_pr - min_pr) > 0 else 1
    
    # Deteksi komunitas untuk pewarnaan klaster
    node_communities = detect_communities(G)
    top_nodes = [u for u, _ in ranking[:8]]
    top1_node = ranking[0][0] if ranking else seed_url

    for node in G.nodes():
        pr_val = pr_scores.get(node, 0)
        norm_val = (pr_val - min_pr) / denom
        
        # Ukuran node proporsional dengan skala ukuran (importance)
        node_size = (14 + (norm_val ** 0.8) * 45) * size_multiplier
        
        title_full = page_titles.get(node, node)
        name_short = get_page_name(node, page_titles, max_len=26)
        
        rank_pos = [i + 1 for i, (u, _) in enumerate(ranking) if u == node]
        rank_str = f"Rank #{rank_pos[0]}" if rank_pos else ""
        comm_id = node_communities.get(node, 0)

        # 1. PEWARNAAN ALA CONNECTED PAPERS:
        if node == top1_node or node == seed_url:
            # Simpul Seed / Top-1 berwarna Dark Charcoal (#1e293b) dengan font kontras
            node_color = '#1e293b'
            border_color = '#0f172a'
            font_color = '#ffffff' if node_size > 28 else '#1e293b'
        elif color_mode == "Klaster Komunitas (Connected Papers)":
            node_color = COMMUNITY_PALETTE[comm_id % len(COMMUNITY_PALETTE)]
            border_color = node_color
            font_color = '#0f172a'
        else:
            # Gradasi PageRank (Merah = Tinggi, Biru = Rendah)
            r = int(59 + norm_val * 180)
            g = int(130 - norm_val * 80)
            b = int(246 - norm_val * 180)
            node_color = f'rgb({r}, {g}, {b})'
            border_color = '#334155'
            font_color = '#0f172a'

        # Tampilkan label hanya pada node penting atau jika opsi 'show_all_labels' aktif
        if show_all_labels or node in top_nodes or node == top1_node:
            node_label = name_short
        else:
            node_label = ""

        # Tooltip Hover yang Informatif & Elegan
        hover_html = (
            f"<div style='font-family: Inter, system-ui, sans-serif; padding: 6px; font-size: 12px; line-height: 1.4;'>"
            f"<b style='color: #0f172a; font-size: 13px;'>{title_full}</b><br>"
            f"<span style='color: #64748b; font-size: 11px;'>{node}</span><br>"
            f"<hr style='border: 0; border-top: 1px solid #e2e8f0; margin: 6px 0;'>"
            f"<b>🏆 PageRank:</b> <span style='color: #2563eb; font-weight: bold;'>{pr_val:.6f}</span> ({rank_str})<br>"
            f"<b>🎨 Klaster Komunitas:</b> #{comm_id + 1}<br>"
            f"<b>📥 Tautan Masuk (In-Degree):</b> {G.in_degree(node)}<br>"
            f"<b>📤 Tautan Keluar (Out-Degree):</b> {G.out_degree(node)}"
            f"</div>"
        )

        net.add_node(
            node,
            label=node_label,
            title=hover_html,
            size=node_size,
            color=node_color,
            borderWidth=2,
            borderWidthSelected=4,
            font={'size': 11, 'color': font_color, 'face': 'Inter, sans-serif', 'strokeWidth': 2, 'strokeColor': '#ffffff'}
        )

    # Tambahkan Edges (Garis Halus Abu-abu Muda ala Connected Papers)
    for source, target in G.edges():
        is_highlight = target in top_nodes[:3]
        edge_color = '#94a3b8' if is_highlight else '#cbd5e1'
        edge_width = 1.4 if is_highlight else 0.9

        net.add_edge(
            source, target,
            color={'color': edge_color, 'highlight': '#2563eb', 'hover': '#3b82f6'},
            arrows={'to': {'enabled': True, 'scaleFactor': 0.6}},
            width=edge_width,
            smooth={'type': 'continuous', 'roundness': 0.15}
        )

    return net.generate_html()


# ==============================================================================
# SAMPLE DATA DEMO: SMALL-WORLD NETWORK (UTM CLUSTERS)
# ==============================================================================
def get_sample_utm_graph():
    """Menyediakan graf sampel 24 simpul yang merefleksikan sifat Small-World Network kampus UTM."""
    nodes = [
        # Pusat Utama
        'https://www.trunojoyo.ac.id',
        'https://www.trunojoyo.ac.id/visimisi',
        'https://www.trunojoyo.ac.id/sejarah-singkat-utm',
        'https://www.trunojoyo.ac.id/profil-pimpinan',
        
        # Klaster 1: Fakultas Teknik (FT)
        'https://ft.trunojoyo.ac.id',
        'https://ft.trunojoyo.ac.id/informatika',
        'https://ft.trunojoyo.ac.id/sistem-informasi',
        'https://ft.trunojoyo.ac.id/teknik-elektro',
        'https://ft.trunojoyo.ac.id/laboratorium-komputasi',
        
        # Klaster 2: Penelitian & Pengabdian (LPPM)
        'https://lppm.trunojoyo.ac.id',
        'https://lppm.trunojoyo.ac.id/jurnal-ilmiah',
        'https://lppm.trunojoyo.ac.id/penelitian-dan-pengabdian',
        'https://lppm.trunojoyo.ac.id/haki-dan-paten',
        
        # Klaster 3: Layanan Akademik & Mahasiswa (BAA & SIAKAD)
        'https://siakad.trunojoyo.ac.id',
        'https://baa.trunojoyo.ac.id',
        'https://baa.trunojoyo.ac.id/kalender-akademik',
        'https://baa.trunojoyo.ac.id/registrasi-mahasiswa',
        'https://library.trunojoyo.ac.id',
        
        # Klaster 4: Fakultas Ekonomi & Bisnis (FEB)
        'https://feb.trunojoyo.ac.id',
        'https://feb.trunojoyo.ac.id/akuntansi',
        'https://feb.trunojoyo.ac.id/manajemen',
        'https://feb.trunojoyo.ac.id/ekonomi-pembangunan',
        
        # Klaster 5: Berita & Prestasi Kampus
        'https://www.trunojoyo.ac.id/berita-prestasi-mahasiswa-nasional',
        'https://www.trunojoyo.ac.id/pendidikan-berdampak-kampus'
    ]
    
    titles = {
        'https://www.trunojoyo.ac.id': 'Beranda - Universitas Trunojoyo Madura',
        'https://www.trunojoyo.ac.id/visimisi': 'Visi & Misi Universitas Trunojoyo Madura',
        'https://www.trunojoyo.ac.id/sejarah-singkat-utm': 'Sejarah Singkat Pendirian UTM',
        'https://www.trunojoyo.ac.id/profil-pimpinan': 'Profil Rektorat & Pimpinan Universitas',
        'https://ft.trunojoyo.ac.id': 'Fakultas Teknik UTM',
        'https://ft.trunojoyo.ac.id/informatika': 'Program Studi Teknik Informatika',
        'https://ft.trunojoyo.ac.id/sistem-informasi': 'Program Studi Sistem Informasi',
        'https://ft.trunojoyo.ac.id/teknik-elektro': 'Program Studi Teknik Elektro',
        'https://ft.trunojoyo.ac.id/laboratorium-komputasi': 'Laboratorium Rekayasa Perangkat Lunak',
        'https://lppm.trunojoyo.ac.id': 'Lembaga Penelitian & Pengabdian (LPPM)',
        'https://lppm.trunojoyo.ac.id/jurnal-ilmiah': 'Portal Jurnal & Publikasi Ilmiah',
        'https://lppm.trunojoyo.ac.id/penelitian-dan-pengabdian': 'Pusat Riset Unggulan Madura',
        'https://lppm.trunojoyo.ac.id/haki-dan-paten': 'Sentra KI & Inovasi Teknologi',
        'https://siakad.trunojoyo.ac.id': 'Sistem Informasi Akademik (SIAKAD)',
        'https://baa.trunojoyo.ac.id': 'Biro Akademik & Kemahasiswaan (BAA)',
        'https://baa.trunojoyo.ac.id/kalender-akademik': 'Jadwal & Kalender Akademik',
        'https://baa.trunojoyo.ac.id/registrasi-mahasiswa': 'Panduan Registrasi Mahasiswa Baru',
        'https://library.trunojoyo.ac.id': 'Perpustakaan Digital Universitas',
        'https://feb.trunojoyo.ac.id': 'Fakultas Ekonomi & Bisnis UTM',
        'https://feb.trunojoyo.ac.id/akuntansi': 'Program Studi Akuntansi',
        'https://feb.trunojoyo.ac.id/manajemen': 'Program Studi Manajemen',
        'https://feb.trunojoyo.ac.id/ekonomi-pembangunan': 'Program Studi Ekonomi Pembangunan',
        'https://www.trunojoyo.ac.id/berita-prestasi-mahasiswa-nasional': 'Prestasi Mahasiswa UTM Tingkat Nasional',
        'https://www.trunojoyo.ac.id/pendidikan-berdampak-kampus': 'Pendidikan Berdampak Pengabdian'
    }
    
    # Hubungan edges membentuk dense internal clusters + bridge shortcuts (Small-World Network)
    edges = [
        # Koneksi Pusat
        ('https://www.trunojoyo.ac.id', 'https://www.trunojoyo.ac.id/visimisi'),
        ('https://www.trunojoyo.ac.id', 'https://www.trunojoyo.ac.id/sejarah-singkat-utm'),
        ('https://www.trunojoyo.ac.id', 'https://www.trunojoyo.ac.id/profil-pimpinan'),
        ('https://www.trunojoyo.ac.id', 'https://ft.trunojoyo.ac.id'),
        ('https://www.trunojoyo.ac.id', 'https://lppm.trunojoyo.ac.id'),
        ('https://www.trunojoyo.ac.id', 'https://siakad.trunojoyo.ac.id'),
        ('https://www.trunojoyo.ac.id', 'https://feb.trunojoyo.ac.id'),
        ('https://www.trunojoyo.ac.id', 'https://library.trunojoyo.ac.id'),
        ('https://www.trunojoyo.ac.id', 'https://baa.trunojoyo.ac.id'),
        ('https://www.trunojoyo.ac.id', 'https://www.trunojoyo.ac.id/berita-prestasi-mahasiswa-nasional'),
        
        # Dense Cluster: Fakultas Teknik
        ('https://ft.trunojoyo.ac.id', 'https://ft.trunojoyo.ac.id/informatika'),
        ('https://ft.trunojoyo.ac.id', 'https://ft.trunojoyo.ac.id/sistem-informasi'),
        ('https://ft.trunojoyo.ac.id', 'https://ft.trunojoyo.ac.id/teknik-elektro'),
        ('https://ft.trunojoyo.ac.id/informatika', 'https://ft.trunojoyo.ac.id/laboratorium-komputasi'),
        ('https://ft.trunojoyo.ac.id/sistem-informasi', 'https://ft.trunojoyo.ac.id/laboratorium-komputasi'),
        ('https://ft.trunojoyo.ac.id/laboratorium-komputasi', 'https://ft.trunojoyo.ac.id'),
        ('https://ft.trunojoyo.ac.id', 'https://siakad.trunojoyo.ac.id'),  # Shortcut
        ('https://ft.trunojoyo.ac.id', 'https://www.trunojoyo.ac.id'),
        
        # Dense Cluster: LPPM
        ('https://lppm.trunojoyo.ac.id', 'https://lppm.trunojoyo.ac.id/jurnal-ilmiah'),
        ('https://lppm.trunojoyo.ac.id', 'https://lppm.trunojoyo.ac.id/penelitian-dan-pengabdian'),
        ('https://lppm.trunojoyo.ac.id', 'https://lppm.trunojoyo.ac.id/haki-dan-paten'),
        ('https://lppm.trunojoyo.ac.id/penelitian-dan-pengabdian', 'https://lppm.trunojoyo.ac.id/jurnal-ilmiah'),
        ('https://lppm.trunojoyo.ac.id/haki-dan-paten', 'https://lppm.trunojoyo.ac.id'),
        ('https://lppm.trunojoyo.ac.id', 'https://www.trunojoyo.ac.id'),
        ('https://lppm.trunojoyo.ac.id/jurnal-ilmiah', 'https://library.trunojoyo.ac.id'),  # Shortcut
        
        # Dense Cluster: BAA, SIAKAD & Library
        ('https://baa.trunojoyo.ac.id', 'https://baa.trunojoyo.ac.id/kalender-akademik'),
        ('https://baa.trunojoyo.ac.id', 'https://baa.trunojoyo.ac.id/registrasi-mahasiswa'),
        ('https://baa.trunojoyo.ac.id', 'https://siakad.trunojoyo.ac.id'),
        ('https://siakad.trunojoyo.ac.id', 'https://baa.trunojoyo.ac.id/kalender-akademik'),
        ('https://library.trunojoyo.ac.id', 'https://siakad.trunojoyo.ac.id'),
        ('https://siakad.trunojoyo.ac.id', 'https://www.trunojoyo.ac.id'),
        
        # Dense Cluster: FEB
        ('https://feb.trunojoyo.ac.id', 'https://feb.trunojoyo.ac.id/akuntansi'),
        ('https://feb.trunojoyo.ac.id', 'https://feb.trunojoyo.ac.id/manajemen'),
        ('https://feb.trunojoyo.ac.id', 'https://feb.trunojoyo.ac.id/ekonomi-pembangunan'),
        ('https://feb.trunojoyo.ac.id/akuntansi', 'https://feb.trunojoyo.ac.id/manajemen'),
        ('https://feb.trunojoyo.ac.id', 'https://siakad.trunojoyo.ac.id'),  # Shortcut
        ('https://feb.trunojoyo.ac.id', 'https://www.trunojoyo.ac.id'),
        
        # Berita
        ('https://www.trunojoyo.ac.id/berita-prestasi-mahasiswa-nasional', 'https://www.trunojoyo.ac.id'),
        ('https://www.trunojoyo.ac.id/pendidikan-berdampak-kampus', 'https://www.trunojoyo.ac.id')
    ]
    
    G = nx.DiGraph()
    G.add_nodes_from(nodes)
    G.add_edges_from(edges)
    return G, titles


# ==============================================================================
# HEADER UTAMA
# ==============================================================================
st.markdown("<div class='main-title'>🕸️ Citation Graph & Small-World Web Explorer</div>", unsafe_allow_html=True)
st.markdown("<div class='sub-title'>Visualisasi Jaringan Hyperlink Web Bergaya <i>Connected Papers</i> dengan Analisis Small-World & PageRank</div>", unsafe_allow_html=True)
st.markdown("<div class='author-badge'>👤 Muhammad Ilham Adila Almafaz (NIM: 230411100113) — Teknik Informatika UTM</div>", unsafe_allow_html=True)


# ==============================================================================
# PANEL PENGATURAN & SUMBER DATA (COLLAPSIBLE)
# ==============================================================================
with st.expander("⚙️ Panel Pengaturan & Sumber Data", expanded=True):
    col_set1, col_set2 = st.columns([2, 1])
    with col_set1:
        source_mode = st.radio(
            "Pilih Sumber Data:",
            ["🧪 Data Demo (UTM Small-World Network)", "🕷️ Crawl Langsung (Live)", "📂 Load File Tersimpan"],
            horizontal=True
        )
    with col_set2:
        damping_factor = st.slider("Damping Factor (d):", 0.10, 0.99, 0.85, 0.05)

    if source_mode == "🕷️ Crawl Langsung (Live)":
        st.markdown("---")
        col_c1, col_c2, col_c3, col_c4 = st.columns([3, 2, 2, 2])
        with col_c1:
            seed_url_input = st.text_input("Seed URL Target:", "https://www.trunojoyo.ac.id")
        with col_c2:
            domain_filter = st.text_input("Filter Domain:", "trunojoyo.ac.id")
        with col_c3:
            max_pages_input = st.slider("Maks Halaman:", 10, 80, 30, 5)
        with col_c4:
            delay_input = st.slider("Jeda Request (s):", 0.2, 2.0, 0.7, 0.1)
            
        crawl_btn = st.button("🚀 Mulai Crawling & Bangun Graf", type="primary", use_container_width=True)
    else:
        crawl_btn = False


# ==============================================================================
# LOGIKA PENGUMPULAN & PEMROSESAN GRAF
# ==============================================================================
if 'graph_data' not in st.session_state:
    st.session_state.graph_data = None

if source_mode == "🧪 Data Demo (UTM Small-World Network)":
    G_demo, titles_demo = get_sample_utm_graph()
    st.session_state.graph_data = {
        'G': G_demo,
        'titles': titles_demo,
        'seed': 'https://www.trunojoyo.ac.id'
    }

elif source_mode == "📂 Load File Tersimpan":
    json_path = 'Output/graph_pagerank.json'
    if os.path.exists(json_path):
        with open(json_path, 'r', encoding='utf-8') as f:
            saved = json.load(f)
        G_saved = nx.DiGraph()
        titles_saved = {}
        for n in saved.get('nodes', []):
            G_saved.add_node(n['id'])
            titles_saved[n['id']] = n.get('title', n['id'])
        for e in saved.get('edges', []):
            G_saved.add_edge(e['source'], e['target'])
        st.session_state.graph_data = {
            'G': G_saved,
            'titles': titles_saved,
            'seed': saved.get('metadata', {}).get('seed_url', '-')
        }
        st.success(f"Berhasil memuat {G_saved.number_of_nodes()} simpul dari {json_path}")
    else:
        st.warning(f"File {json_path} belum ditemukan. Silakan lakukan crawl terlebih dahulu.")

elif source_mode == "🕷️ Crawl Langsung (Live)" and crawl_btn:
    crawler = WebCrawler(
        seed_url=seed_url_input,
        max_pages=max_pages_input,
        delay=delay_input,
        allowed_domains=[d.strip() for d in domain_filter.split(',') if d.strip()]
    )
    
    progress_bar = st.progress(0)
    status_text = st.empty()
    
    def on_progress(current, total, url, title):
        progress_bar.progress(current / total)
        status_text.caption(f"[{current}/{total}] Mengunjungi: {title[:40]} ({url[:45]}...)")
        
    visited, edges, titles = crawler.crawl(progress_callback=on_progress)
    progress_bar.empty()
    status_text.empty()
    
    G_crawled = nx.DiGraph()
    G_crawled.add_nodes_from(visited)
    filtered = [(u, v) for u, v in edges if u in visited and v in visited]
    G_crawled.add_edges_from(filtered)
    G_crawled.remove_edges_from(nx.selfloop_edges(G_crawled))
    
    st.session_state.graph_data = {
        'G': G_crawled,
        'titles': titles,
        'seed': seed_url_input
    }
    st.success(f"Crawling selesai! {G_crawled.number_of_nodes()} halaman berhasil dikelompokkan ke dalam graf.")


# ==============================================================================
# ANALISIS METRIK & PROFIL SMALL-WORLD
# ==============================================================================
if st.session_state.graph_data is None:
    st.info("Silakan pilih sumber data di atas untuk memulai eksplorasi.")
    st.stop()

G = st.session_state.graph_data['G']
titles = st.session_state.graph_data['titles']
seed_url = st.session_state.graph_data['seed']

# Hitung PageRank
pr_scores = compute_pagerank(G, alpha=damping_factor)
ranking = sorted(pr_scores.items(), key=lambda x: x[1], reverse=True)

# Hitung Metrik Small-World
G_undir = G.to_undirected()
clustering_coeff = nx.average_clustering(G_undir) if G_undir.number_of_nodes() > 1 else 0

# Random graph benchmark
N_nodes = G.number_of_nodes()
E_edges = G.number_of_edges()
avg_k = (2 * E_edges / N_nodes) if N_nodes > 0 else 0
c_random = (avg_k / N_nodes) if N_nodes > 0 else 0.001
clustering_ratio = (clustering_coeff / c_random) if c_random > 0 else 1.0

# Jarak terpendek rata-rata pada komponen terbesar
if nx.is_connected(G_undir):
    avg_path_len = nx.average_shortest_path_length(G_undir)
else:
    largest_cc = max(nx.connected_components(G_undir), key=len)
    avg_path_len = nx.average_shortest_path_length(G_undir.subgraph(largest_cc))

in_degs = dict(G.in_degree())
out_degs = dict(G.out_degree())
density_val = nx.density(G)
best_node = ranking[0][0]
best_title = get_page_name(best_node, titles, max_len=26)
best_pr = ranking[0][1]


# ==============================================================================
# DASHBOARD METRIC CARDS
# ==============================================================================
col1, col2, col3, col4, col5 = st.columns(5)
with col1:
    st.markdown(f"""
    <div class='metric-card'>
        <div class='metric-val'>{N_nodes}</div>
        <div class='metric-lbl'>Total Simpul (Nodes)</div>
    </div>
    """, unsafe_allow_html=True)
with col2:
    st.markdown(f"""
    <div class='metric-card'>
        <div class='metric-val'>{E_edges}</div>
        <div class='metric-lbl'>Total Busur (Edges)</div>
    </div>
    """, unsafe_allow_html=True)
with col3:
    st.markdown(f"""
    <div class='metric-card'>
        <div class='metric-val'>{clustering_coeff:.3f}</div>
        <div class='metric-lbl'>Koef. Klasterisasi (C̄)</div>
    </div>
    """, unsafe_allow_html=True)
with col4:
    st.markdown(f"""
    <div class='metric-card'>
        <div class='metric-val'>{avg_path_len:.2f}</div>
        <div class='metric-lbl'>Rata-rata Jarak (L)</div>
    </div>
    """, unsafe_allow_html=True)
with col5:
    st.markdown(f"""
    <div class='metric-card'>
        <div class='metric-val'>{best_pr:.3f}</div>
        <div class='metric-lbl'>🏆 Top-1: {best_title}</div>
    </div>
    """, unsafe_allow_html=True)

st.markdown("<br>", unsafe_allow_html=True)


# ==============================================================================
# TABS NAVIGASI
# ==============================================================================
tab1, tab2, tab3, tab4 = st.tabs([
    "🕸️ Citation Graph (Connected Papers Style)",
    "🏆 Top-10 Ranking & Grafik",
    "🔬 Analisis Sifat Small-World",
    "💾 Ekspor Data (Server Lab Ready)"
])


# ==============================================================================
# TAB 1: CITATION GRAPH BERGAYA CONNECTED PAPERS
# ==============================================================================
with tab1:
    # Toolbar Kontrol di Atas Graf (Mirip Tombol Connected Papers di Gambar Pengguna)
    col_t1, col_t2, col_t3, col_t4 = st.columns([3, 2, 2, 2])
    with col_t1:
        color_choice = st.selectbox(
            "🎨 Skema Warna Simpul:",
            ["Klaster Komunitas (Connected Papers)", "Gradasi Skor PageRank"]
        )
    with col_t2:
        size_scale = st.slider("Ukuran Simpul (Importance):", 0.5, 2.0, 1.0, 0.1)
    with col_t3:
        spacing_scale = st.slider("Jarak Klaster (Spacing):", 60, 200, 110, 10)
    with col_t4:
        st.markdown("<div style='height: 24px;'></div>", unsafe_allow_html=True)
        show_all_lbl = st.checkbox("Tampilkan Semua Judul", value=False)

    # Render Visualisasi Interaktif PyVis
    html_graph = generate_connected_papers_graph(
        G, pr_scores, ranking, titles, seed_url,
        color_mode=color_choice,
        size_multiplier=size_scale,
        spring_spacing=spacing_scale,
        show_all_labels=show_all_lbl
    )
    
    st.markdown("<div class='graph-container'>", unsafe_allow_html=True)
    components.html(html_graph, height=720, scrolling=False)
    st.markdown("</div>", unsafe_allow_html=True)
    
    # Legend Panduan Visual
    st.markdown(f"""
    **Keterangan Visual (Gaya Connected Papers):**
    - ⚫ **Simpul Hitam/Charcoal ({best_title}):** Simpul pusat / jangkar utama jaringan web (*Seed Paper/Top Node*).
    - 🔵 🟢 🟠 🔴 🟣 **Simpul Warna-Warni:** Menandakan **Klaster Komunitas Tematik** (misal: Fakultas Teknik, LPPM, SIAKAD, FEB) yang terkelompok secara otomatis menggunakan deteksi modularitas Louvain.
    - 🔘 **Ukuran Lingkaran:** Merefleksikan **bobot PageRank / Tingkat Pengaruh**. Semakin penting sebuah halaman, semakin besar lingkarannya.
    - 🔗 **Garis Abu-abu Halus:** Koneksi hyperlink antar halaman. Tautan padat di dalam satu kelompok membentuk **komunitas**, sedangkan tautan antar-kelompok membentuk **jembatan pintas (*small-world shortcut*)**.
    """)


# ==============================================================================
# TAB 2: TOP-10 RANKING & BAR CHART
# ==============================================================================
with tab2:
    st.markdown("### 🏆 Top-10 Halaman Web dengan PageRank Tertinggi")
    
    top10_rows = []
    medals = ["🥇", "🥈", "🥉", "4", "5", "6", "7", "8", "9", "10"]
    for i, (url, score) in enumerate(ranking[:10]):
        top10_rows.append({
            'Peringkat': medals[i],
            'Nama Halaman': get_page_name(url, titles, max_len=36),
            'URL Asli': url,
            'Skor PageRank': round(score, 6),
            'Tautan Masuk (In-Degree)': in_degs[url],
            'Tautan Keluar (Out-Degree)': out_degs[url]
        })
    df_top10 = pd.DataFrame(top10_rows)
    st.dataframe(df_top10, use_container_width=True, hide_index=True)
    
    # Horizontal Bar Chart
    st.markdown("#### Perbandingan Skor PageRank Top-10")
    fig, ax = plt.subplots(figsize=(10, 4.5))
    plot_labels = [get_page_name(u, titles, max_len=24) for u, _ in ranking[:10]][::-1]
    plot_scores = [s for _, s in ranking[:10]][::-1]
    colors = plt.cm.RdYlGn_r(np.linspace(0.15, 0.85, 10))
    
    bars = ax.barh(range(10), plot_scores, color=colors, edgecolor='#1e293b', height=0.65)
    ax.set_yticks(range(10))
    ax.set_yticklabels(plot_labels, fontsize=9.5, fontweight='bold', color='#1e293b')
    ax.set_xlabel('Skor PageRank', fontsize=10, fontweight='bold')
    ax.grid(axis='x', linestyle='--', alpha=0.5)
    
    for bar in bars:
        w = bar.get_width()
        ax.text(w + 0.002, bar.get_y() + bar.get_height() / 2, f"{w:.4f}",
                va='center', fontsize=9, fontweight='bold', color='#0f172a')
                
    plt.tight_layout()
    st.pyplot(fig)


# ==============================================================================
# TAB 3: ANALISIS SIFAT SMALL-WORLD
# ==============================================================================
with tab3:
    st.markdown("### 🔬 Analisis Karakteristik Small-World Network")
    st.markdown(r"""
    Menurut model teoretis **Watts & Strogatz (1998)**, sebuah jaringan dikategorikan sebagai **Small-World Network** jika memenuhi dua kriteria utama:
    1. **Koefisien Klasterisasi Tinggi ($C \gg C_{random}$):** Simpul-simpul membentuk kelompok komunitas padat (*high local clustering*).
    2. **Jarak Terpendek Pendek ($L \approx L_{random}$):** Hanya membutuhkan beberapa lompatan (*hops*) singkat untuk mencapai simpul mana pun di jaringan.
    """)
    
    col_sw1, col_sw2 = st.columns(2)
    with col_sw1:
        st.markdown("#### Verifikasi Empiris:")
        st.write(f"- **Koefisien Klasterisasi Nyata ($C$):** `{clustering_coeff:.4f}`")
        st.write(f"- **Koefisien Klasterisasi Graf Acak ($C_{{random}}$):** `{c_random:.4f}`")
        st.write(f"- **Rasio Klasterisasi ($C / C_{{random}}$):** `{clustering_ratio:.2f}x lipat lebih tinggi!`")
        st.write(f"- **Rata-rata Jarak Terpendek ($L$):** `{avg_path_len:.2f} lompatan`")
        
        if clustering_ratio > 1.5:
            st.success("✅ **Terbukti:** Graf memenuhi sifat **Small-World Network**, di mana website membentuk klaster fakultas/unit yang padat dan saling terhubung melalui halaman beranda/hub.")
        else:
            st.info("ℹ️ Struktur graf tersebar secara merata.")
            
    with col_sw2:
        st.markdown("#### Ukuran Sentralitas Tambahan:")
        in_deg_cent = nx.in_degree_centrality(G)
        betw_cent = nx.betweenness_centrality(G)
        cent_data = []
        for r_i, (u_i, p_i) in enumerate(ranking[:6], 1):
            cent_data.append({
                'Rank': r_i,
                'Halaman': get_page_name(u_i, titles, max_len=24),
                'PageRank': round(p_i, 4),
                'In-Degree C.': round(in_deg_cent[u_i], 4),
                'Betweenness C.': round(betw_cent[u_i], 4)
            })
        st.dataframe(pd.DataFrame(cent_data), hide_index=True)


# ==============================================================================
# TAB 4: EKSPOR DATA & INTEGRASI SERVER LAB
# ==============================================================================
with tab4:
    st.markdown("### 💾 Ekspor Hasil untuk Deployment Server Lab")
    st.info("File-file di bawah ini siap disetor atau diintegrasikan dengan backend server lab (Flask / FastAPI / D3.js).")
    
    nodes_export = []
    node_comms = detect_communities(G)
    for r, (u, score) in enumerate(ranking, 1):
        nodes_export.append({
            'id': u,
            'name': get_page_name(u, titles, max_len=40),
            'title': titles.get(u, u),
            'community_cluster': node_comms.get(u, 0) + 1,
            'pagerank': round(score, 6),
            'rank': r,
            'in_degree': in_degs[u],
            'out_degree': out_degs[u]
        })
    edges_export = [{'source': s, 'target': t} for s, t in G.edges()]
    full_export = {
        'metadata': {
            'seed_url': seed_url,
            'network_type': 'Small-World Citation Graph',
            'total_nodes': N_nodes,
            'total_edges': E_edges,
            'clustering_coefficient': round(clustering_coeff, 4),
            'average_shortest_path_length': round(avg_path_len, 4),
            'density': round(density_val, 6),
            'damping_factor': damping_factor
        },
        'nodes': nodes_export,
        'edges': edges_export
    }
    json_str = json.dumps(full_export, indent=2, ensure_ascii=False)
    csv_str = df_top10.to_csv(index=False)
    
    col_d1, col_d2, col_d3 = st.columns(3)
    with col_d1:
        st.download_button(
            label="📥 Download JSON Graf & PageRank",
            data=json_str,
            file_name="graph_pagerank.json",
            mime="application/json",
            use_container_width=True
        )
    with col_d2:
        st.download_button(
            label="📥 Download CSV Top-10 PageRank",
            data=csv_str,
            file_name="top10_pagerank.csv",
            mime="text/csv",
            use_container_width=True
        )
    with col_d3:
        st.download_button(
            label="📥 Download HTML Citation Graph",
            data=html_graph,
            file_name="citation_graph.html",
            mime="text/html",
            use_container_width=True
        )
        
    st.markdown("#### Preview Struktur JSON:")
    st.code(json.dumps(full_export['nodes'][:2], indent=2), language='json')
