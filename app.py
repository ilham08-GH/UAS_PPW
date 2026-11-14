import streamlit as st
import requests
from requests.adapters import HTTPAdapter
from urllib3.util.retry import Retry
import urllib3
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

# Nonaktifkan peringatan SSL tidak aman untuk server kampus dengan cert chain khusus
urllib3.disable_warnings(urllib3.exceptions.InsecureRequestWarning)

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
# FUNGSI HELPER: NAMA HALAMAN DESKRIPTIF & BERSIH
# ==============================================================================
def get_page_name(url, page_titles=None, max_len=30):
    """Menghasilkan nama halaman manusiawi dari <title>, subdomain, atau slug path yang bersih."""
    parsed = urlparse(url)
    if page_titles and url in page_titles:
        title = str(page_titles[url]).strip()
        for sep in [' - ', ' | ', ' — ', ' :: ']:
            if sep in title:
                parts = title.split(sep)
                if len(parts[0]) > 3:
                    title = parts[0].strip()
        if title and title != '-' and title != url and not title.startswith('http'):
            if not any(err in title.lower() for err in ['not found', 'error 404', 'tidak ditemukan', '404 error']):
                return title[:max_len]
            
    netloc = parsed.netloc.replace('www.', '')
    path = parsed.path.strip('/')
    
    netloc_parts = netloc.split('.')
    subdomain = netloc_parts[0] if len(netloc_parts) > 2 else ""
    
    if path:
        last_slug = path.split('/')[-1]
        last_slug = last_slug.replace('.html', '').replace('.htm', '').replace('.php', '')
        clean_slug = last_slug.replace('-', ' ').title()
        if len(clean_slug) > max_len:
            clean_slug = clean_slug[:max_len-3] + '...'
        if subdomain:
            return f"[{subdomain}] {clean_slug}"[:max_len]
        return clean_slug[:max_len]
    else:
        if subdomain:
            return f"[{subdomain}] Beranda"[:max_len]
        return f"Beranda ({netloc})"[:max_len]


# ==============================================================================
# KELAS WEB CRAWLER ROBUST (SESSION, RETRY, TIMEOUT PANJANG & FILTER 404)
# ==============================================================================
class WebCrawler:
    def __init__(self, seed_url, max_pages=30, delay=0.4, timeout=16, allowed_domains=None):
        self.seed_url = seed_url
        self.max_pages = max_pages
        self.delay = delay
        self.timeout = timeout
        parsed = urlparse(seed_url)
        self.seed_domain = parsed.netloc.replace('www.', '')
        self.allowed_domains = allowed_domains or [self.seed_domain]
        self.visited = set()
        self.edges = []
        self.page_titles = {}
        self.failed_urls = []
        
        # Inisialisasi Session HTTP dengan Connection Pooling & Auto-Retry
        self.session = requests.Session()
        retries = Retry(total=2, backoff_factor=0.3, status_forcelist=[500, 502, 503, 504])
        self.session.mount('https://', HTTPAdapter(max_retries=retries))
        self.session.mount('http://', HTTPAdapter(max_retries=retries))
        
        # Headers lengkap menyerupai peramban desktop asli (anti blokir WAF / ModSecurity)
        self.headers = {
            'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/124.0.0.0 Safari/537.36',
            'Accept': 'text/html,application/xhtml+xml,application/xml;q=0.9,image/avif,image/webp,*/*;q=0.8',
            'Accept-Language': 'id,en-US;q=0.9,en;q=0.8',
        }
        
    def _normalize_url(self, url):
        parsed = urlparse(url)
        path = parsed.path.rstrip('/')
        return f"{parsed.scheme}://{parsed.netloc}{path}"

    def _is_valid_url(self, url):
        try:
            parsed = urlparse(url)
            if parsed.scheme not in ('http', 'https'):
                return False
            if not any(d in parsed.netloc for d in self.allowed_domains):
                return False
            skip_ext = (
                '.pdf', '.jpg', '.jpeg', '.png', '.gif', '.zip', '.rar', 
                '.docx', '.xlsx', '.pptx', '.css', '.js', '.svg', '.mp4', 
                '.mp3', '.ico', '.xml', '.rss', '.json', '.webp', '.woff', '.woff2',
                '.exe', '.dmg', '.tar', '.gz'
            )
            if parsed.path.lower().endswith(skip_ext):
                return False
            path_lower = parsed.path.lower()
            if any(bad in path_lower for bad in ['/wp-includes/', '/feed/', '/feed', '/trackback/']):
                return False
            return True
        except:
            return False

    def _fetch(self, url):
        """Mengambil halaman dengan toleransi SSL dan fallback HTTP jika HTTPS bermasalah."""
        try:
            return self.session.get(url, headers=self.headers, timeout=self.timeout, allow_redirects=True, verify=True)
        except requests.exceptions.SSLError:
            # Fallback jika cert chain kampus bermasalah
            return self.session.get(url, headers=self.headers, timeout=self.timeout, allow_redirects=True, verify=False)
        except (requests.exceptions.ConnectionError, requests.exceptions.Timeout) as e:
            # Coba fallback ke http jika https gagal/timeout
            if url.startswith('https://'):
                http_url = 'http://' + url[8:]
                try:
                    return self.session.get(http_url, headers=self.headers, timeout=self.timeout, allow_redirects=True)
                except:
                    pass
            raise e

    def crawl(self, progress_callback=None):
        queue = deque([self._normalize_url(self.seed_url)])
        while queue and len(self.visited) < self.max_pages:
            current_url = queue.popleft()
            if current_url in self.visited:
                continue
            try:
                response = self._fetch(current_url)
                
                # 1. CEK STATUS CODE HTTP (Hanya proses HTTP 200 OK)
                if response.status_code != 200:
                    self.failed_urls.append((current_url, f"HTTP {response.status_code}"))
                    continue
                    
                if 'text/html' not in response.headers.get('Content-Type', ''):
                    continue
                
                soup = BeautifulSoup(response.text, 'html.parser')
                title_tag = soup.find('title')
                title = title_tag.get_text(strip=True) if title_tag else current_url
                
                # 2. FILTER SOFT-404 & ERROR PAGE
                title_lower = title.lower()
                error_signatures = [
                    'page not found', '404 not found', 'halaman tidak ditemukan', 
                    'error 404', 'not found', '404 error', 'laman tidak ditemukan', 
                    'tidak ditemukan', 'access denied', '403 forbidden'
                ]
                if any(sig in title_lower for sig in error_signatures):
                    self.failed_urls.append((current_url, f"Soft-404: {title}"))
                    continue

                self.visited.add(current_url)
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
                err_msg = str(e)
                if "Read timed out" in err_msg or "ConnectTimeout" in err_msg:
                    err_clean = "Waktu koneksi habis (Timeout)"
                elif "SSLError" in err_msg:
                    err_clean = "Masalah Sertifikat SSL"
                else:
                    err_clean = err_msg[:60]
                self.failed_urls.append((current_url, err_clean))
        return self.visited, self.edges, self.page_titles


# ==============================================================================
# FUNGSI MEMBANGUN CITATION GRAPH BERGAYA CONNECTED PAPERS (TENANG & STATIS)
# ==============================================================================
def generate_connected_papers_graph(G, pr_scores, ranking, page_titles, seed_url,
                                    color_mode="Klaster Komunitas (Connected Papers)",
                                    size_multiplier=1.0, spring_spacing=100,
                                    show_all_labels=False, freeze_physics=True):
    """
    Menghasilkan graf interaktif bergaya Connected Papers:
    - Background putih bersih (#ffffff)
    - Node dikelompokkan ke dalam klaster warna komunitas
    - Node pusat (seed/Top-1) berwarna Charcoal gelap (#1e293b)
    - Garis edges abu-abu lembut (#cbd5e1)
    - Tata letak ForceAtlas2 dengan opsi Kunci Posisi (Statis / Tidak Bergerak)
    """
    net = Network(height='720px', width='100%', directed=True,
                  bgcolor='#ffffff', font_color='#1e293b', cdn_resources='remote')
    
    # Gunakan ForceAtlas2Based physics: stabilisasi cepat & teratur
    net.force_atlas_2based(
        gravity=-50,
        central_gravity=0.015,
        spring_length=spring_spacing,
        spring_strength=0.08,
        damping=0.75,
        overlap=0.20
    )

    max_pr = max(pr_scores.values()) if pr_scores else 1
    min_pr = min(pr_scores.values()) if pr_scores else 0
    denom = (max_pr - min_pr) if (max_pr - min_pr) > 0 else 1
    
    node_communities = detect_communities(G)
    top_nodes = [u for u, _ in ranking[:8]]
    top1_node = ranking[0][0] if ranking else seed_url

    for node in G.nodes():
        pr_val = pr_scores.get(node, 0)
        norm_val = (pr_val - min_pr) / denom
        
        node_size = (14 + (norm_val ** 0.8) * 45) * size_multiplier
        
        title_full = page_titles.get(node, node)
        name_short = get_page_name(node, page_titles, max_len=26)
        
        rank_pos = [i + 1 for i, (u, _) in enumerate(ranking) if u == node]
        rank_str = f"Rank #{rank_pos[0]}" if rank_pos else ""
        comm_id = node_communities.get(node, 0)

        # Pewarnaan ala Connected Papers:
        if node == top1_node or node == seed_url:
            node_color = '#1e293b'
            border_color = '#0f172a'
            font_color = '#ffffff' if node_size > 28 else '#1e293b'
        elif color_mode == "Klaster Komunitas (Connected Papers)":
            node_color = COMMUNITY_PALETTE[comm_id % len(COMMUNITY_PALETTE)]
            border_color = node_color
            font_color = '#0f172a'
        else:
            r = int(59 + norm_val * 180)
            g = int(130 - norm_val * 80)
            b = int(246 - norm_val * 180)
            node_color = f'rgb({r}, {g}, {b})'
            border_color = '#334155'
            font_color = '#0f172a'

        if show_all_labels or node in top_nodes or node == top1_node:
            node_label = name_short
        else:
            node_label = ""

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

    html_out = net.generate_html()

    # Kunci posisi graf jika mode statis aktif (agar tidak bergoyang / bergerak-gerak)
    if freeze_physics:
        freeze_script = """
        network.once("stabilized", function() {
            network.setOptions({ physics: false });
        });
        network.once("stabilizationIterationsDone", function() {
            network.setOptions({ physics: false });
        });
        """
        html_out = html_out.replace("return network;", f"{freeze_script}\n        return network;")

    return html_out


# ==============================================================================
# HEADER UTAMA
# ==============================================================================
st.markdown("<div class='main-title'>🕸️ Citation Graph & Small-World Web Explorer</div>", unsafe_allow_html=True)
st.markdown("<div class='sub-title'>Visualisasi Jaringan Hyperlink Web Bergaya <i>Connected Papers</i> dengan Analisis Small-World & PageRank</div>", unsafe_allow_html=True)
st.markdown("<div class='author-badge'>👤 Muhammad Ilham Adila Almafaz (NIM: 230411100113) — Teknik Informatika UTM</div>", unsafe_allow_html=True)


# ==============================================================================
# PANEL PENGATURAN & FORM CRAWLING (DEFAULT KOSONG)
# ==============================================================================
with st.container():
    col_c1, col_c2 = st.columns([3, 2])
    with col_c1:
        seed_url_input = st.text_input(
            "🌐 Seed URL Target (Halaman Awal):",
            value="",
            placeholder="Masukkan URL, contoh: https://example.com, https://uinsa.ac.id, https://www.trunojoyo.ac.id"
        )
    with col_c2:
        domain_filter_input = st.text_input(
            "🔒 Batasan Domain (Opsional):",
            value="",
            placeholder="Kosongkan untuk otomatis menggunakan domain Seed URL"
        )

    col_p1, col_p2, col_p3 = st.columns([1, 1, 1])
    with col_p1:
        max_pages_input = st.slider("Maks Halaman:", min_value=5, max_value=80, value=25, step=5)
    with col_p2:
        delay_input = st.slider("Jeda Request (detik):", min_value=0.1, max_value=2.0, value=0.4, step=0.1)
    with col_p3:
        damping_factor = st.slider("Damping Factor (d):", min_value=0.10, max_value=0.99, value=0.85, step=0.05)

    crawl_btn = st.button("🚀 Mulai Crawling & Bangun Graf", type="primary", use_container_width=True)


# ==============================================================================
# LOGIKA PENGUMPULAN & PEMROSESAN GRAF
# ==============================================================================
if 'graph_data' not in st.session_state:
    st.session_state.graph_data = None

if crawl_btn:
    raw_seed = seed_url_input.strip()
    if not raw_seed:
        st.warning("⚠️ Silakan masukkan Seed URL target terlebih dahulu sebelum memulai crawling!")
    else:
        if not raw_seed.startswith(('http://', 'https://')):
            raw_seed = 'https://' + raw_seed
        
        parsed_seed = urlparse(raw_seed)
        seed_domain = parsed_seed.netloc.replace('www.', '')
        
        raw_filter = domain_filter_input.strip()
        if raw_filter:
            allowed_domains = [d.strip() for d in raw_filter.split(',') if d.strip()]
        else:
            allowed_domains = [seed_domain]
            
        crawler = WebCrawler(
            seed_url=raw_seed,
            max_pages=max_pages_input,
            delay=delay_input,
            timeout=16,
            allowed_domains=allowed_domains
        )
        
        progress_bar = st.progress(0)
        status_text = st.empty()
        
        def on_progress(current, total, url, title):
            pct = min(1.0, current / total)
            progress_bar.progress(pct)
            status_text.caption(f"[{current}/{total}] Mengunjungi: {title[:40]} ({url[:45]}...)")
            
        with st.spinner(f"🕷️ Sedang melakukan crawling hyperlink pada {raw_seed}..."):
            visited, edges, titles = crawler.crawl(progress_callback=on_progress)
            
        progress_bar.empty()
        status_text.empty()
        
        if len(visited) == 0:
            err_reason = crawler.failed_urls[0][1] if crawler.failed_urls else "Server tidak merespons dalam batas waktu."
            st.error(f"❌ Gagal mengambil halaman valid dari **{raw_seed}**.\n\n**Penyebab:** `{err_reason}`\n\n*Tips: Pastikan URL aktif, coba tanpa awalan `www.` (misal `https://uinsa.ac.id`), atau periksa koneksi internet server target.*")
        else:
            G_crawled = nx.DiGraph()
            G_crawled.add_nodes_from(visited)
            filtered = [(u, v) for u, v in edges if u in visited and v in visited]
            G_crawled.add_edges_from(filtered)
            G_crawled.remove_edges_from(nx.selfloop_edges(G_crawled))
            
            st.session_state.graph_data = {
                'G': G_crawled,
                'titles': titles,
                'seed': raw_seed,
                'failed_count': len(crawler.failed_urls)
            }
            msg = f"✅ Crawling berhasil! {G_crawled.number_of_nodes()} simpul dan {G_crawled.number_of_edges()} busur berhasil dihubungkan."
            if crawler.failed_urls:
                msg += f" (Sebanyak {len(crawler.failed_urls)} tautan rusak/404/timeout berhasil disaring bersih)."
            st.success(msg)


# ==============================================================================
# TAMPILAN AWAL JIKA BELUM ADA DATA (EMPTY STATE)
# ==============================================================================
if st.session_state.graph_data is None:
    st.markdown("""
    <div style='background: #f8fafc; border: 2px dashed #cbd5e1; border-radius: 14px; padding: 45px 25px; text-align: center; margin-top: 25px;'>
        <div style='font-size: 3.2rem; margin-bottom: 12px;'>🕸️</div>
        <h3 style='color: #1e293b; margin-bottom: 8px;'>Belum Ada Jaringan Web yang Dianalisis</h3>
        <p style='color: #64748b; max-width: 620px; margin: 0 auto 18px auto; font-size: 0.96rem; line-height: 1.6;'>
            Silakan masukkan <b>Seed URL Target</b> pada form di atas (contoh: website universitas seperti <code>https://uinsa.ac.id</code>, <code>https://www.its.ac.id</code>, atau <code>https://www.trunojoyo.ac.id</code>), 
            tentukan jumlah halaman maksimal, lalu klik tombol <b>🚀 Mulai Crawling & Bangun Graf</b>.
        </p>
        <span style='background: #e2e8f0; color: #334155; padding: 6px 16px; border-radius: 9999px; font-size: 0.85rem; font-weight: 600;'>
            💡 Dilengkapi Connection Pooling, toleransi latensi kampus lambat, filter anti-404 otomatis, dan visualisasi statis Connected Papers.
        </span>
    </div>
    """, unsafe_allow_html=True)
    st.stop()


# ==============================================================================
# ANALISIS METRIK & PROFIL SMALL-WORLD
# ==============================================================================
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
    if G_undir.number_of_nodes() > 0:
        largest_cc = max(nx.connected_components(G_undir), key=len)
        avg_path_len = nx.average_shortest_path_length(G_undir.subgraph(largest_cc)) if len(largest_cc) > 1 else 0
    else:
        avg_path_len = 0

in_degs = dict(G.in_degree())
out_degs = dict(G.out_degree())
density_val = nx.density(G)
best_node = ranking[0][0] if ranking else seed_url
best_title = get_page_name(best_node, titles, max_len=26)
best_pr = ranking[0][1] if ranking else 0.0


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
# TAB 1: CITATION GRAPH BERGAYA CONNECTED PAPERS (TENANG & STATIS)
# ==============================================================================
with tab1:
    col_t1, col_t2, col_t3, col_t4 = st.columns([3, 2, 2, 3])
    with col_t1:
        color_choice = st.selectbox(
            "🎨 Skema Warna Simpul:",
            ["Klaster Komunitas (Connected Papers)", "Gradasi Skor PageRank"]
        )
    with col_t2:
        size_scale = st.slider("Ukuran Simpul (Importance):", 0.5, 2.0, 1.0, 0.1)
    with col_t3:
        spacing_scale = st.slider("Jarak Klaster (Spacing):", 60, 200, 100, 10)
    with col_t4:
        st.markdown("<div style='height: 8px;'></div>", unsafe_allow_html=True)
        freeze_toggle = st.checkbox("🔒 Kunci Posisi Graf (Tenang / Tidak Bergerak)", value=True,
                                    help="Jika aktif, posisi simpul langsung dikunci setelah susunan klaster terbentuk sehingga graf tidak bergoyang-goyang.")
        show_all_lbl = st.checkbox("Tampilkan Semua Judul", value=False)

    html_graph = generate_connected_papers_graph(
        G, pr_scores, ranking, titles, seed_url,
        color_mode=color_choice,
        size_multiplier=size_scale,
        spring_spacing=spacing_scale,
        show_all_labels=show_all_lbl,
        freeze_physics=freeze_toggle
    )
    
    st.markdown("<div class='graph-container'>", unsafe_allow_html=True)
    components.html(html_graph, height=720, scrolling=False)
    st.markdown("</div>", unsafe_allow_html=True)
    
    st.markdown(f"""
    **Keterangan Visual (Gaya Connected Papers):**
    - ⚫ **Simpul Hitam/Charcoal ({best_title}):** Simpul pusat / jangkar utama jaringan web (*Seed Paper/Top Node*).
    - 🔵 🟢 🟠 🔴 🟣 **Simpul Warna-Warni:** Menandakan **Klaster Komunitas Tematik** yang terkelompok secara otomatis menggunakan deteksi modularitas Louvain.
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
            'Tautan Masuk (In-Degree)': in_degs.get(url, 0),
            'Tautan Keluar (Out-Degree)': out_degs.get(url, 0)
        })
    df_top10 = pd.DataFrame(top10_rows)
    st.dataframe(df_top10, use_container_width=True, hide_index=True)
    
    if len(ranking) > 0:
        st.markdown("#### Perbandingan Skor PageRank Top-10")
        fig, ax = plt.subplots(figsize=(10, 4.5))
        plot_items = ranking[:min(10, len(ranking))][::-1]
        plot_labels = [get_page_name(u, titles, max_len=24) for u, _ in plot_items]
        plot_scores = [s for _, s in plot_items]
        colors = plt.cm.RdYlGn_r(np.linspace(0.15, 0.85, len(plot_items)))
        
        bars = ax.barh(range(len(plot_items)), plot_scores, color=colors, edgecolor='#1e293b', height=0.65)
        ax.set_yticks(range(len(plot_items)))
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
            st.success("✅ **Terbukti:** Graf memenuhi sifat **Small-World Network**, di mana website membentuk klaster halaman/subtopik yang padat dan saling terhubung melalui halaman beranda/hub.")
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
            'in_degree': in_degs.get(u, 0),
            'out_degree': out_degs.get(u, 0)
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
