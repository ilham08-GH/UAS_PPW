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
# KONFIGURASI HALAMAN STREAMLIT (TANPA SIDEBAR)
# ==============================================================================
st.set_page_config(
    page_title="Web Structure Mining - Citation Graph & PageRank",
    page_icon="🌐",
    layout="wide",
    initial_sidebar_state="collapsed"
)

# Custom Styling (CSS) - Hapus & sembunyikan sidebar sepenuhnya
st.markdown("""
<style>
    /* Sembunyikan sidebar dan tombol panah toggle */
    [data-testid="stSidebar"], 
    [data-testid="stSidebarNav"], 
    [data-testid="collapsedControl"] {
        display: none !important;
    }
    
    .block-container {
        padding-top: 1.8rem;
        padding-bottom: 2.5rem;
    }
    .main-title {
        font-size: 2.2rem;
        font-weight: 800;
        color: #1e3a8a;
        margin-bottom: 0.2rem;
    }
    .sub-title {
        font-size: 1.05rem;
        color: #4b5563;
        margin-bottom: 0.8rem;
    }
    .author-badge {
        display: inline-block;
        background-color: #eff6ff;
        border: 1px solid #bfdbfe;
        color: #1d4ed8;
        padding: 4px 12px;
        border-radius: 9999px;
        font-size: 0.85rem;
        font-weight: 600;
        margin-bottom: 1.2rem;
    }
    .metric-card {
        background-color: #f8fafc;
        border: 1px solid #e2e8f0;
        border-radius: 10px;
        padding: 16px;
        text-align: center;
        box-shadow: 0 1px 3px rgba(0,0,0,0.05);
    }
    .metric-val {
        font-size: 1.8rem;
        font-weight: 700;
        color: #2563eb;
    }
    .metric-lbl {
        font-size: 0.9rem;
        color: #64748b;
        font-weight: 600;
    }
</style>
""", unsafe_allow_html=True)


# ==============================================================================
# FUNGSI PAGERANK ROBUST (BEBAS ERROR SCIPY)
# ==============================================================================
def compute_pagerank(G, alpha=0.85, max_iter=100, tol=1e-6):
    """
    Menghitung PageRank dengan NetworkX.
    Jika SciPy tidak terpasang di server, otomatis fallback ke algoritma
    Power Iteration murni berbasis Python/NumPy agar aplikasi tidak pernah crash.
    """
    try:
        return nx.pagerank(G, alpha=alpha, max_iter=max_iter, tol=tol)
    except Exception:
        # Fallback manual iteratif (100% bebas SciPy)
        nodes = list(G.nodes())
        N = len(nodes)
        if N == 0:
            return {}
            
        pr = {n: 1.0 / N for n in nodes}
        for _ in range(max_iter):
            pr_new = {}
            # Hitung dangling nodes (simpul tanpa link keluar)
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
# FUNGSI HELPER: NAMA HALAMAN DESKRIPTIF
# ==============================================================================
def get_page_name(url, page_titles=None, max_len=32):
    """Menghasilkan nama halaman manusiawi dari <title>, subdomain, atau path slug."""
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
    def __init__(self, seed_url, max_pages=30, delay=0.8, allowed_domains=None):
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
        self.headers = {'User-Agent': 'Mozilla/5.0 (Educational WebMining-Bot)'}
        
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
# FUNGSI MEMBANGUN PYVIS CITATION GRAPH (HTML)
# ==============================================================================
def generate_pyvis_html(G, pr_scores, ranking, page_titles):
    net = Network(height='680px', width='100%', directed=True,
                  bgcolor='#111827', font_color='#f3f4f6', cdn_resources='remote')
    
    net.barnes_hut(gravity=-3500, central_gravity=0.25,
                   spring_length=160, spring_strength=0.04, damping=0.09)

    max_pr = max(pr_scores.values()) if pr_scores else 1
    min_pr = min(pr_scores.values()) if pr_scores else 0
    denom = (max_pr - min_pr) if (max_pr - min_pr) > 0 else 1
    top5_set = set([u for u, _ in ranking[:5]])

    for node in G.nodes():
        pr_val = pr_scores.get(node, 0)
        title = page_titles.get(node, node)
        label = get_page_name(node, page_titles, max_len=20)
        norm_size = (pr_val - min_pr) / denom
        size = 16 + norm_size * 50

        # Skema Warna: Cyan -> Kuning -> Oranye -> Merah (Top Rank)
        r = int(50 + norm_size * 205)
        g = int(180 - norm_size * 120)
        b = int(240 - norm_size * 200)
        color = f'rgb({r}, {g}, {b})'

        rank_pos = [i + 1 for i, (u, _) in enumerate(ranking) if u == node]
        rank_str = f"Rank #{rank_pos[0]}" if rank_pos else ""

        hover_html = (
            f"<div style='font-family: Arial, sans-serif; padding: 6px; font-size: 12px;'>"
            f"<b style='color: #fde047; font-size: 13px;'>{title}</b><br>"
            f"<span style='color: #94a3b8; font-size: 11px;'>{node}</span><br>"
            f"<hr style='border: 0; border-top: 1px solid #374151; margin: 6px 0;'>"
            f"<b>🏆 PageRank:</b> <span style='color: #4ade80;'>{pr_val:.6f}</span> ({rank_str})<br>"
            f"<b>📥 In-Degree:</b> {G.in_degree(node)} | <b>📤 Out-Degree:</b> {G.out_degree(node)}"
            f"</div>"
        )
        net.add_node(node, label=label, title=hover_html, size=size, color=color,
                     borderWidth=2, borderWidthSelected=4)

    for source, target in G.edges():
        is_top = target in top5_set
        edge_color = 'rgba(239, 68, 68, 0.85)' if is_top else 'rgba(156, 163, 175, 0.55)'
        edge_width = 2.2 if is_top else 1.2
        net.add_edge(source, target,
                     color={'color': edge_color, 'highlight': '#f87171', 'hover': '#38bdf8'},
                     arrows={'to': {'enabled': True, 'scaleFactor': 0.8}},
                     width=edge_width,
                     smooth={'type': 'curvedCW', 'roundness': 0.12})

    return net.generate_html()


# ==============================================================================
# SAMPLE DATA DEMO (UTM NETWORK)
# ==============================================================================
def get_sample_utm_graph():
    nodes = [
        'https://www.trunojoyo.ac.id',
        'https://www.trunojoyo.ac.id/visimisi',
        'https://www.trunojoyo.ac.id/dokumen-penelitian-pengabdian',
        'https://www.trunojoyo.ac.id/pendidikan-berdampak-utm',
        'https://www.trunojoyo.ac.id/pagar-nusa-utm-berjaya-raih-j',
        'https://baa.trunojoyo.ac.id',
        'https://lppm.trunojoyo.ac.id',
        'https://ft.trunojoyo.ac.id',
        'https://feb.trunojoyo.ac.id',
        'https://siakad.trunojoyo.ac.id'
    ]
    titles = {
        'https://www.trunojoyo.ac.id': 'Beranda - Universitas Trunojoyo Madura',
        'https://www.trunojoyo.ac.id/visimisi': 'Visi dan Misi Universitas Trunojoyo Madura',
        'https://www.trunojoyo.ac.id/dokumen-penelitian-pengabdian': 'Dokumen Penelitian & Pengabdian',
        'https://www.trunojoyo.ac.id/pendidikan-berdampak-utm': 'Pendidikan Berdampak UTM',
        'https://www.trunojoyo.ac.id/pagar-nusa-utm-berjaya-raih-j': 'Prestasi Mahasiswa UTM',
        'https://baa.trunojoyo.ac.id': 'Biro Akademik & Kemahasiswaan (BAA)',
        'https://lppm.trunojoyo.ac.id': 'Lembaga Penelitian & Pengabdian (LPPM)',
        'https://ft.trunojoyo.ac.id': 'Fakultas Teknik UTM',
        'https://feb.trunojoyo.ac.id': 'Fakultas Ekonomi & Bisnis UTM',
        'https://siakad.trunojoyo.ac.id': 'Sistem Informasi Akademik (SIAKAD)'
    }
    edges = [
        ('https://www.trunojoyo.ac.id', 'https://www.trunojoyo.ac.id/visimisi'),
        ('https://www.trunojoyo.ac.id', 'https://www.trunojoyo.ac.id/dokumen-penelitian-pengabdian'),
        ('https://www.trunojoyo.ac.id', 'https://www.trunojoyo.ac.id/pendidikan-berdampak-utm'),
        ('https://www.trunojoyo.ac.id', 'https://www.trunojoyo.ac.id/pagar-nusa-utm-berjaya-raih-j'),
        ('https://www.trunojoyo.ac.id', 'https://baa.trunojoyo.ac.id'),
        ('https://www.trunojoyo.ac.id', 'https://lppm.trunojoyo.ac.id'),
        ('https://www.trunojoyo.ac.id', 'https://ft.trunojoyo.ac.id'),
        ('https://www.trunojoyo.ac.id', 'https://feb.trunojoyo.ac.id'),
        ('https://www.trunojoyo.ac.id', 'https://siakad.trunojoyo.ac.id'),
        ('https://ft.trunojoyo.ac.id', 'https://www.trunojoyo.ac.id'),
        ('https://ft.trunojoyo.ac.id', 'https://siakad.trunojoyo.ac.id'),
        ('https://feb.trunojoyo.ac.id', 'https://www.trunojoyo.ac.id'),
        ('https://lppm.trunojoyo.ac.id', 'https://www.trunojoyo.ac.id/dokumen-penelitian-pengabdian'),
        ('https://baa.trunojoyo.ac.id', 'https://siakad.trunojoyo.ac.id'),
        ('https://www.trunojoyo.ac.id/visimisi', 'https://www.trunojoyo.ac.id'),
        ('https://www.trunojoyo.ac.id/dokumen-penelitian-pengabdian', 'https://lppm.trunojoyo.ac.id'),
        ('https://www.trunojoyo.ac.id/pendidikan-berdampak-utm', 'https://www.trunojoyo.ac.id'),
        ('https://www.trunojoyo.ac.id/pagar-nusa-utm-berjaya-raih-j', 'https://www.trunojoyo.ac.id')
    ]
    G = nx.DiGraph()
    G.add_nodes_from(nodes)
    G.add_edges_from(edges)
    return G, titles


# ==============================================================================
# HEADER UTAMA
# ==============================================================================
st.markdown("<div class='main-title'>🌐 Web Structure Mining — Citation Graph & PageRank</div>", unsafe_allow_html=True)
st.markdown("<div class='sub-title'>Visualisasi Topologi Hyperlink Web, Analisis Sentralitas, dan Identifikasi Halaman Web Terpenting</div>", unsafe_allow_html=True)
st.markdown("<div class='author-badge'>👤 Muhammad Ilham Adila Almafaz (NIM: 230411100113) — Teknik Informatika UTM</div>", unsafe_allow_html=True)


# ==============================================================================
# PANEL PENGATURAN DI DALAM HALAMAN UTAMA (EXPANDER)
# ==============================================================================
with st.expander("⚙️ Panel Pengaturan & Sumber Data", expanded=True):
    col_set1, col_set2 = st.columns([2, 1])
    with col_set1:
        source_mode = st.radio(
            "Pilih Sumber Data:",
            ["🧪 Data Demo (UTM Sample)", "🕷️ Crawl Langsung (Live)", "📂 Load File Tersimpan"],
            horizontal=True
        )
    with col_set2:
        damping_factor = st.slider("Damping Factor (d):", 0.10, 0.99, 0.85, 0.05)

    if source_mode == "🕷️ Crawl Langsung (Live)":
        st.markdown("---")
        col_c1, col_c2, col_c3, col_c4 = st.columns([3, 2, 2, 2])
        with col_c1:
            seed_url_input = st.text_input("Seed URL:", "https://www.trunojoyo.ac.id")
        with col_c2:
            domain_filter = st.text_input("Filter Domain:", "trunojoyo.ac.id")
        with col_c3:
            max_pages_input = st.slider("Maks Halaman:", 10, 80, 25, 5)
        with col_c4:
            delay_input = st.slider("Jeda Request (s):", 0.2, 2.0, 0.8, 0.1)
            
        crawl_btn = st.button("🚀 Mulai Crawling & Analisis", type="primary", use_container_width=True)
    else:
        crawl_btn = False


# ==============================================================================
# LOGIKA PENGUMPULAN & PEMROSESAN GRAF
# ==============================================================================
if 'graph_data' not in st.session_state:
    st.session_state.graph_data = None

if source_mode == "🧪 Data Demo (UTM Sample)":
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
    st.success(f"Crawling tuntas! {G_crawled.number_of_nodes()} halaman dan {G_crawled.number_of_edges()} hyperlink berhasil dianalisis.")


# ==============================================================================
# TAMPILAN DASHBOARD
# ==============================================================================
if st.session_state.graph_data is None:
    st.info("Silakan pilih sumber data di atas untuk memulai.")
    st.stop()

G = st.session_state.graph_data['G']
titles = st.session_state.graph_data['titles']
seed_url = st.session_state.graph_data['seed']

# Hitung PageRank menggunakan fungsi yang aman dari error SciPy
pr_scores = compute_pagerank(G, alpha=damping_factor)
ranking = sorted(pr_scores.items(), key=lambda x: x[1], reverse=True)

# Hitung Metrik Lainnya
in_degs = dict(G.in_degree())
out_degs = dict(G.out_degree())
density_val = nx.density(G)
best_node = ranking[0][0]
best_title = get_page_name(best_node, titles, max_len=30)
best_pr = ranking[0][1]

# --- METRIC CARDS ---
col1, col2, col3, col4 = st.columns(4)
with col1:
    st.markdown(f"""
    <div class='metric-card'>
        <div class='metric-val'>{G.number_of_nodes()}</div>
        <div class='metric-lbl'>Total Simpul (Halaman)</div>
    </div>
    """, unsafe_allow_html=True)
with col2:
    st.markdown(f"""
    <div class='metric-card'>
        <div class='metric-val'>{G.number_of_edges()}</div>
        <div class='metric-lbl'>Total Busur (Hyperlink)</div>
    </div>
    """, unsafe_allow_html=True)
with col3:
    st.markdown(f"""
    <div class='metric-card'>
        <div class='metric-val'>{density_val:.4f}</div>
        <div class='metric-lbl'>Kepadatan Graf (Density)</div>
    </div>
    """, unsafe_allow_html=True)
with col4:
    st.markdown(f"""
    <div class='metric-card'>
        <div class='metric-val'>{best_pr:.4f}</div>
        <div class='metric-lbl'>🏆 Top-1: {best_title}</div>
    </div>
    """, unsafe_allow_html=True)

st.markdown("<br>", unsafe_allow_html=True)

# --- TABS NAVIGASI ---
tab1, tab2, tab3, tab4 = st.tabs([
    "🕸️ Citation Graph (Interaktif)",
    "🏆 Top-10 Ranking & Grafik",
    "📊 Analisis Sentralitas",
    "💾 Ekspor Data (Server Lab Ready)"
])


# ==============================================================================
# TAB 1: INTERACTIVE CITATION GRAPH
# ==============================================================================
with tab1:
    st.markdown("### 🕸️ Visualisasi Interaktif Citation Graph (ScienceDirect Style)")
    st.caption("Pindahkan kursor pada simpul untuk melihat detail skor. Anda dapat melakukan drag, zoom, atau klik simpul untuk melihat tautannya.")
    
    html_graph = generate_pyvis_html(G, pr_scores, ranking, titles)
    components.html(html_graph, height=700, scrolling=False)
    
    st.markdown("""
    **Petunjuk Navigasi Graf:**
    - 🔴 **Simpul Merah / Oranye:** Halaman dengan skor PageRank tinggi (otoritas/prestise utama).
    - 🔵 **Simpul Biru:** Halaman perantara atau beranda subdomain dengan PageRank moderat.
    - ➡️ **Garis Panah Merah Tebal:** Tautan hyperlink yang mengarah langsung ke **Top-5 halaman terpenting**.
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
# TAB 3: ANALISIS SENTRALITAS LENGKAP
# ==============================================================================
with tab3:
    st.markdown("### 📊 Perbandingan Ukuran Sentralitas Jaringan")
    st.caption("Membandingkan posisi simpul berdasarkan berbagai dimensi keunggulan (*prominence*).")
    
    in_deg_cent = nx.in_degree_centrality(G)
    out_deg_cent = nx.out_degree_centrality(G)
    betw_cent = nx.betweenness_centrality(G)
    
    cent_rows = []
    for rank_idx, (url, pr_val) in enumerate(ranking[:10], 1):
        parsed = urlparse(url)
        cent_rows.append({
            'Rank': rank_idx,
            'Nama Halaman': get_page_name(url, titles, max_len=28),
            'Subdomain / Path': (parsed.netloc.replace('www.', '') + parsed.path)[:32],
            'PageRank': round(pr_val, 4),
            'In-Degree Cent.': round(in_deg_cent[url], 4),
            'Out-Degree Cent.': round(out_deg_cent[url], 4),
            'Betweenness Cent.': round(betw_cent[url], 4)
        })
    df_cent = pd.DataFrame(cent_rows)
    st.dataframe(df_cent, use_container_width=True, hide_index=True)
    
    with st.expander("🔍 Lihat Matriks Adjasensi Biner (10 Simpul Pertama)"):
        sub_nodes = [u for u, _ in ranking[:10]]
        sub_labels = [get_page_name(u, titles, max_len=18) for u in sub_nodes]
        adj = nx.to_pandas_adjacency(G, nodelist=sub_nodes, dtype=int)
        adj.index = sub_labels
        adj.columns = sub_labels
        st.dataframe(adj, use_container_width=True)


# ==============================================================================
# TAB 4: EKSPOR DATA & INTEGRASI SERVER LAB
# ==============================================================================
with tab4:
    st.markdown("### 💾 Ekspor Hasil untuk Deployment Server Lab")
    st.info("File-file di bawah ini siap disetor atau diintegrasikan dengan backend server lab (Flask / FastAPI / D3.js).")
    
    nodes_export = []
    for r, (u, score) in enumerate(ranking, 1):
        nodes_export.append({
            'id': u,
            'name': get_page_name(u, titles, max_len=40),
            'title': titles.get(u, u),
            'pagerank': round(score, 6),
            'rank': r,
            'in_degree': in_degs[u],
            'out_degree': out_degs[u]
        })
    edges_export = [{'source': s, 'target': t} for s, t in G.edges()]
    full_export = {
        'metadata': {
            'seed_url': seed_url,
            'total_nodes': G.number_of_nodes(),
            'total_edges': G.number_of_edges(),
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
