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
    page_icon="📦",
    layout="wide",
    initial_sidebar_state="collapsed"
)

# ==============================================================================
# CUSTOM STYLING: CARDBOARD / KRAFT BOX NEOBRUTALISM (ANTI AI-SLOP)
# ==============================================================================
st.markdown("""
<style>
    @import url('https://fonts.googleapis.com/css2?family=Space+Mono:ital,wght@0,400;0,700;1,400&family=Work+Sans:wght@500;700;800&display=swap');

    /* Sembunyikan sidebar dan elemen bawaan Streamlit */
    [data-testid="stSidebar"], 
    [data-testid="stSidebarNav"], 
    [data-testid="collapsedControl"],
    header[data-testid="stHeader"] {
        display: none !important;
    }

    /* Latar Belakang Kertas Kraft / Gudang Kardus */
    .stApp {
        background-color: #e6dac8;
        background-image: radial-gradient(#bfae96 1px, transparent 1px);
        background-size: 20px 20px;
        color: #1f1a16;
        font-family: 'Work Sans', sans-serif;
    }

    .block-container {
        padding-top: 2rem;
        padding-bottom: 3rem;
        max-width: 1380px;
    }

    /* Kotak Header Kardus Utama */
    .cardboard-header {
        background-color: #d6bc97;
        border: 3px solid #1f1a16;
        box-shadow: 7px 7px 0px #1f1a16;
        padding: 24px 28px;
        margin-bottom: 24px;
        position: relative;
    }

    /* Efek Lakban Coklat di Atas Kardus */
    .cardboard-header::before {
        content: "UAS PPW";
        position: absolute;
        top: -14px;
        right: 28px;
        background-color: #b85d38;
        color: #f7f1e5;
        font-family: 'Space Mono', monospace;
        font-size: 0.72rem;
        font-weight: 700;
        letter-spacing: 1.5px;
        padding: 4px 12px;
        border: 2px solid #1f1a16;
        transform: rotate(1.5deg);
    }

    .main-title {
        font-family: 'Space Mono', monospace;
        font-size: 2.1rem;
        font-weight: 700;
        color: #1f1a16;
        text-transform: uppercase;
        letter-spacing: -1px;
        margin-bottom: 6px;
        line-height: 1.2;
    }

    .sub-title {
        font-size: 1rem;
        color: #3d332a;
        font-weight: 500;
        margin-bottom: 14px;
    }

    .author-stamp {
        display: inline-block;
        background-color: #f4ece1;
        border: 2px solid #1f1a16;
        box-shadow: 3px 3px 0px #1f1a16;
        color: #1f1a16;
        font-family: 'Space Mono', monospace;
        padding: 5px 14px;
        font-size: 0.8rem;
        font-weight: 700;
    }

    /* Kartu Metrik Potongan Kardus */
    .metric-card {
        background-color: #f4ece1;
        border: 3px solid #1f1a16;
        box-shadow: 5px 5px 0px #1f1a16;
        padding: 16px 12px;
        text-align: left;
        position: relative;
        transition: transform 0.1s ease;
    }
    .metric-card:hover {
        transform: translate(-2px, -2px);
        box-shadow: 7px 7px 0px #1f1a16;
    }
    .metric-card::after {
        content: "";
        position: absolute;
        top: 6px;
        right: 6px;
        width: 8px;
        height: 8px;
        background-color: #1f1a16;
    }
    .metric-val {
        font-family: 'Space Mono', monospace;
        font-size: 1.65rem;
        font-weight: 700;
        color: #b85d38;
        line-height: 1.2;
    }
    .metric-lbl {
        font-family: 'Space Mono', monospace;
        font-size: 0.76rem;
        color: #1f1a16;
        font-weight: 700;
        text-transform: uppercase;
        margin-top: 4px;
        white-space: nowrap;
        overflow: hidden;
        text-overflow: ellipsis;
    }

    /* Kontainer Graf Kardus */
    .graph-container {
        border: 3px solid #1f1a16;
        background-color: #f4ece1;
        padding: 6px;
        box-shadow: 7px 7px 0px #1f1a16;
        margin-bottom: 16px;
    }

    /* Kotak Empty State Gudang Kardus */
    .empty-box {
        background-color: #d6bc97;
        border: 3px dashed #1f1a16;
        box-shadow: 6px 6px 0px #1f1a16;
        padding: 45px 25px;
        text-align: center;
        margin-top: 25px;
    }

    /* Override Input, Tombol */
    div[data-testid="stTextInput"] input {
        background-color: #f4ece1 !important;
        border: 2px solid #1f1a16 !important;
        border-radius: 0px !important;
        color: #1f1a16 !important;
        font-family: 'Space Mono', monospace !important;
        font-size: 0.9rem !important;
        box-shadow: 3px 3px 0px #1f1a16 !important;
    }

    div[data-baseweb="select"] > div {
        background-color: #f4ece1 !important;
        border: 2px solid #1f1a16 !important;
        border-radius: 0px !important;
        color: #1f1a16 !important;
        font-family: 'Space Mono', monospace !important;
        box-shadow: 3px 3px 0px #1f1a16 !important;
    }

    .stButton > button, .stDownloadButton > button {
        background-color: #b85d38 !important;
        color: #f4ece1 !important;
        border: 3px solid #1f1a16 !important;
        border-radius: 0px !important;
        box-shadow: 5px 5px 0px #1f1a16 !important;
        font-family: 'Space Mono', monospace !important;
        font-weight: 700 !important;
        text-transform: uppercase !important;
        padding: 0.55rem 1.2rem !important;
        transition: all 0.1s ease !important;
    }
    .stButton > button:hover, .stDownloadButton > button:hover {
        transform: translate(2px, 2px) !important;
        box-shadow: 3px 3px 0px #1f1a16 !important;
        background-color: #9e4b2a !important;
    }

    /* ==========================================================
       PENGATURAN TAB KARTON TEGAS (NEOBRUTALISM STYLE)
       ========================================================== */
    div[data-baseweb="tab-list"] {
        gap: 8px;
        background-color: transparent !important;
        border-bottom: none !important;
    }

    button[data-baseweb="tab"] {
        background-color: #d6bc97 !important;
        border: 2.5px solid #1f1a16 !important;
        border-radius: 0px !important;
        box-shadow: 3px 3px 0px #1f1a16 !important;
        padding: 10px 16px !important;
        font-family: 'Space Mono', monospace !important;
        font-weight: 700 !important;
        color: #1f1a16 !important;
        transition: all 0.1s ease !important;
    }

    button[data-baseweb="tab"]:hover {
        background-color: #c4a982 !important;
        transform: translate(-1px, -1px);
        box-shadow: 4px 4px 0px #1f1a16 !important;
    }

    button[data-baseweb="tab"][aria-selected="true"] {
        background-color: #f4ece1 !important;
        color: #b85d38 !important;
        border-bottom: 2.5px solid #f4ece1 !important;
        box-shadow: 4px 4px 0px #1f1a16 !important;
        transform: translate(-2px, -2px);
    }

    div[data-testid="stTabs"] > div[role="tabpanel"] {
        background-color: #f4ece1;
        border: 3px solid #1f1a16;
        box-shadow: 7px 7px 0px #1f1a16;
        padding: 24px;
        margin-top: -2px;
    }

    label, .stMarkdown p, .stMarkdown li {
        color: #1f1a16 !important;
    }
    label p {
        font-family: 'Space Mono', monospace !important;
        font-weight: 700 !important;
        font-size: 0.85rem !important;
        text-transform: uppercase;
    }
</style>
""", unsafe_allow_html=True)


# ==============================================================================
# FUNGSI PAGERANK ROBUST (BEBAS ERROR SCIPY)
# ==============================================================================
def compute_pagerank(G, alpha=0.85, max_iter=100, tol=1e-6):
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
# DETEKSI KOMUNITAS
# ==============================================================================
COMMUNITY_PALETTE = [
    '#b85d38', '#3b6e5c', '#d48c29', '#2f5266',
    '#8c3f4d', '#6b5b3e', '#4a6b82', '#a35c37',
    '#526b44', '#7a496b', '#9c6b30', '#3d5a58'
]

def detect_communities(G):
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
# KELAS WEB CRAWLER ROBUST
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
        
        self.session = requests.Session()
        retries = Retry(total=2, backoff_factor=0.3, status_forcelist=[500, 502, 503, 504])
        self.session.mount('https://', HTTPAdapter(max_retries=retries))
        self.session.mount('http://', HTTPAdapter(max_retries=retries))
        
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
        try:
            return self.session.get(url, headers=self.headers, timeout=self.timeout, allow_redirects=True, verify=True)
        except requests.exceptions.SSLError:
            return self.session.get(url, headers=self.headers, timeout=self.timeout, allow_redirects=True, verify=False)
        except (requests.exceptions.ConnectionError, requests.exceptions.Timeout) as e:
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
                if response.status_code != 200:
                    self.failed_urls.append((current_url, f"HTTP {response.status_code}"))
                    continue
                if 'text/html' not in response.headers.get('Content-Type', ''):
                    continue
                
                soup = BeautifulSoup(response.text, 'html.parser')
                title_tag = soup.find('title')
                title = title_tag.get_text(strip=True) if title_tag else current_url
                
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
# FUNGSI MEMBANGUN CITATION GRAPH
# ==============================================================================
def generate_connected_papers_graph(G, pr_scores, ranking, page_titles, seed_url,
                                    color_mode="Klaster Komunitas (Connected Papers)",
                                    size_multiplier=1.0, spring_spacing=100,
                                    show_all_labels=False, freeze_physics=True):
    net = Network(height='720px', width='100%', directed=True,
                  bgcolor='#f4ece1', font_color='#1f1a16', cdn_resources='remote')
    
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
        rank_str = f"RANK #{rank_pos[0]}" if rank_pos else ""
        comm_id = node_communities.get(node, 0)

        if node == top1_node or node == seed_url:
            node_color = '#1f1a16'
            border_color = '#b85d38'
        elif color_mode == "Klaster Komunitas (Connected Papers)":
            node_color = COMMUNITY_PALETTE[comm_id % len(COMMUNITY_PALETTE)]
            border_color = '#1f1a16'
        else:
            r = int(214 - norm_val * 120)
            g = int(188 - norm_val * 115)
            b = int(151 - norm_val * 110)
            node_color = f'rgb({r}, {g}, {b})'
            border_color = '#1f1a16'

        if show_all_labels or node in top_nodes or node == top1_node:
            node_label = name_short
        else:
            node_label = ""

        hover_html = (
            f"<div style='font-family: Space Mono, monospace; background: #f4ece1; border: 2px solid #1f1a16; padding: 8px; font-size: 12px; color: #1f1a16;'>"
            f"<b style='font-size: 13px;'>{title_full}</b><br>"
            f"<span style='color: #5c4e43; font-size: 11px;'>{node}</span><br>"
            f"<hr style='border: 0; border-top: 2px dashed #1f1a16; margin: 6px 0;'>"
            f"<b>PAGERANK:</b> <span style='color: #b85d38; font-weight: bold;'>{pr_val:.6f}</span> ({rank_str})<br>"
            f"<b>KLASTER:</b> #{comm_id + 1}<br>"
            f"<b>IN-DEGREE:</b> {G.in_degree(node)} | <b>OUT-DEGREE:</b> {G.out_degree(node)}"
            f"</div>"
        )

        net.add_node(
            node,
            label=node_label,
            title=hover_html,
            size=node_size,
            color={'background': node_color, 'border': border_color, 'highlight': {'background': '#b85d38', 'border': '#1f1a16'}},
            borderWidth=2.5,
            borderWidthSelected=4,
            font={'size': 11, 'color': '#1f1a16', 'face': 'Space Mono, monospace', 'strokeWidth': 3, 'strokeColor': '#f4ece1'}
        )

    for source, target in G.edges():
        is_highlight = target in top_nodes[:3]
        edge_color = '#6e5d4f' if is_highlight else '#b5a492'
        edge_width = 1.6 if is_highlight else 1.0

        net.add_edge(
            source, target,
            color={'color': edge_color, 'highlight': '#b85d38', 'hover': '#1f1a16'},
            arrows={'to': {'enabled': True, 'scaleFactor': 0.55}},
            width=edge_width,
            smooth={'type': 'continuous', 'roundness': 0.12}
        )

    html_out = net.generate_html()

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
st.markdown("""
<div class='cardboard-header' style='text-align: center;'><div class='main-title'>[ NodeCraft ]</div></div>
""", unsafe_allow_html=True)


# ==============================================================================
# PANEL PENGATURAN & FORM CRAWLING
# ==============================================================================
with st.container():
    col_c1, col_c2 = st.columns([3, 2])
    with col_c1:
        seed_url_input = st.text_input(
            "SEED URL TARGET (HALAMAN AWAL):",
            value="",
            placeholder="Masukkan URL"
        )
    with col_c2:
        domain_filter_input = st.text_input(
            "BATASAN DOMAIN (OPSIONAL):",
            value="",
            placeholder="Kosongkan untuk otomatis mengikuti domain Seed URL"
        )

    col_p1, col_p2, col_p3 = st.columns([1, 1, 1])
    with col_p1:
        max_pages_input = st.slider("MAKS HALAMAN:", min_value=5, max_value=80, value=25, step=5)
    with col_p2:
        delay_input = st.slider("JEDA REQUEST (DETIK):", min_value=0.1, max_value=2.0, value=0.4, step=0.1)
    with col_p3:
        damping_factor = st.slider("DAMPING FACTOR (d):", min_value=0.10, max_value=0.99, value=0.85, step=0.05)

    crawl_btn = st.button("MULAI CRAWLING & BANGUN GRAF", type="primary", use_container_width=True)


# ==============================================================================
# LOGIKA PENGUMPULAN & PEMROSESAN GRAF
# ==============================================================================
if 'graph_data' not in st.session_state:
    st.session_state.graph_data = None

if crawl_btn:
    raw_seed = seed_url_input.strip()
    if not raw_seed:
        st.warning("PERINGATAN: Masukkan Seed URL target terlebih dahulu sebelum memulai crawling.")
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
            status_text.caption(f"[{current}/{total}] LOG: {title[:40]} ({url[:45]}...)")
            
        with st.spinner(f"Memindai jaringan hyperlink pada {raw_seed}..."):
            visited, edges, titles = crawler.crawl(progress_callback=on_progress)
            
        progress_bar.empty()
        status_text.empty()
        
        if len(visited) == 0:
            err_reason = crawler.failed_urls[0][1] if crawler.failed_urls else "Server tidak merespons dalam batas waktu."
            st.error(f"GAGAL MENGAMBIL DATA DARI {raw_seed}.\n\nPENYEBAB: `{err_reason}`\n\nPastikan URL aktif atau coba tanpa awalan `www.`")
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


# ==============================================================================
# TAMPILAN AWAL JIKA BELUM ADA DATA (EMPTY STATE)
# ==============================================================================
if st.session_state.graph_data is None:
    st.markdown("""
    <div class='empty-box'>
        <div style='font-family: Space Mono, monospace; font-size: 1.5rem; font-weight: 700; color: #1f1a16; margin-bottom: 10px;'>
            [ DATA KOSONG ]
        </div>
        <p style='color: #3d332a; max-width: 640px; margin: 0 auto 18px auto; font-size: 0.95rem; line-height: 1.6;'>
            Masukkan <b>Seed URL</b> pada kolom di atas, lalu tekan tombol <b>MULAI CRAWLING & BANGUN GRAF</b>.
        </p>
    </div>
    """, unsafe_allow_html=True)
    st.stop()


# ==============================================================================
# ANALISIS METRIK & PROFIL SMALL-WORLD
# ==============================================================================
G = st.session_state.graph_data['G']
titles = st.session_state.graph_data['titles']
seed_url = st.session_state.graph_data['seed']

pr_scores = compute_pagerank(G, alpha=damping_factor)
ranking = sorted(pr_scores.items(), key=lambda x: x[1], reverse=True)

G_undir = G.to_undirected()
clustering_coeff = nx.average_clustering(G_undir) if G_undir.number_of_nodes() > 1 else 0

N_nodes = G.number_of_nodes()
E_edges = G.number_of_edges()
avg_k = (2 * E_edges / N_nodes) if N_nodes > 0 else 0
c_random = (avg_k / N_nodes) if N_nodes > 0 else 0.001
clustering_ratio = (clustering_coeff / c_random) if c_random > 0 else 1.0

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
best_title = get_page_name(best_node, titles, max_len=22)
best_pr = ranking[0][1] if ranking else 0.0


# ==============================================================================
# DASHBOARD METRIC CARDS
# ==============================================================================
st.markdown("<br>", unsafe_allow_html=True)
col1, col2, col3, col4, col5 = st.columns(5)
with col1:
    st.markdown(f"""
    <div class='metric-card'>
        <div class='metric-val'>{N_nodes}</div>
        <div class='metric-lbl'>TOTAL SIMPUL (NODES)</div>
    </div>
    """, unsafe_allow_html=True)
with col2:
    st.markdown(f"""
    <div class='metric-card'>
        <div class='metric-val'>{E_edges}</div>
        <div class='metric-lbl'>TOTAL BUSUR (EDGES)</div>
    </div>
    """, unsafe_allow_html=True)
with col3:
    st.markdown(f"""
    <div class='metric-card'>
        <div class='metric-val'>{clustering_coeff:.3f}</div>
        <div class='metric-lbl'>KOEF. KLASTER (C)</div>
    </div>
    """, unsafe_allow_html=True)
with col4:
    st.markdown(f"""
    <div class='metric-card'>
        <div class='metric-val'>{avg_path_len:.2f}</div>
        <div class='metric-lbl'>JARAK RATA-RATA (L)</div>
    </div>
    """, unsafe_allow_html=True)
with col5:
    st.markdown(f"""
    <div class='metric-card'>
        <div class='metric-val'>{best_pr:.3f}</div>
        <div class='metric-lbl'>TOP-1: {best_title}</div>
    </div>
    """, unsafe_allow_html=True)

st.markdown("<br>", unsafe_allow_html=True)


# ==============================================================================
# TABS NAVIGASI
# ==============================================================================
tab1, tab2, tab3, tab4 = st.tabs([
    "01 // CITATION GRAPH",
    "02 // TOP-10 PAGERANK",
    "03 // SMALL-WORLD ANALYSIS",
    "04 // EKSPOR DATA LAB"
])


# ==============================================================================
# TAB 1: CITATION GRAPH
# ==============================================================================
with tab1:
    col_t1, col_t2, col_t3, col_t4 = st.columns([3, 2, 2, 3])
    with col_t1:
        color_choice = st.selectbox(
            "SKEMA WARNA SIMPUL:",
            ["Klaster Komunitas (Connected Papers)", "Gradasi Skor PageRank"]
        )
    with col_t2:
        size_scale = st.slider("SKALA SIMPUL:", 0.5, 2.0, 1.0, 0.1)
    with col_t3:
        spacing_scale = st.slider("JARAK KLASTER:", 60, 200, 100, 10)
    with col_t4:
        st.markdown("<div style='height: 4px;'></div>", unsafe_allow_html=True)
        freeze_toggle = st.checkbox("KUNCI POSISI GRAF (STATIS)", value=True)
        show_all_lbl = st.checkbox("TAMPILKAN SEMUA JUDUL", value=False)

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
    **LEGENDA PETA JARINGAN:**
    - **SIMPUL HITAM ARANG ({best_title}):** Simpul jangkar utama / skor PageRank tertinggi.
    - **SIMPUL WARNA CETAK INDUSTRIAL:** Klaster komunitas tematik hasil deteksi modularitas Louvain.
    - **DIAMETER LINGKARAN:** Proporsional terhadap bobot otoritas PageRank masing-masing halaman.
    """)


# ==============================================================================
# TAB 2: TOP-10 RANKING & BAR CHART KARDUS
# ==============================================================================
with tab2:
    st.markdown("#### PERINGKAT 10 HALAMAN DENGAN OTORITAS PAGERANK TERTINGGI")
    
    top10_rows = []
    for i, (url, score) in enumerate(ranking[:10]):
        top10_rows.append({
            'RANK': f"#{i+1:02d}",
            'NAMA HALAMAN': get_page_name(url, titles, max_len=36),
            'URL ASLI': url,
            'SKOR PAGERANK': round(score, 6),
            'IN-DEGREE': in_degs.get(url, 0),
            'OUT-DEGREE': out_degs.get(url, 0)
        })
    df_top10 = pd.DataFrame(top10_rows)
    st.dataframe(df_top10, use_container_width=True, hide_index=True)
    
    if len(ranking) > 0:
        st.markdown("#### GRAFIK DISTRIBUSI TOP-10 PAGERANK")
        fig, ax = plt.subplots(figsize=(10, 4.5), facecolor='#f4ece1')
        ax.set_facecolor('#f4ece1')
        
        plot_items = ranking[:min(10, len(ranking))][::-1]
        plot_labels = [get_page_name(u, titles, max_len=24) for u, _ in plot_items]
        plot_scores = [s for _, s in plot_items]
        
        bars = ax.barh(
            range(len(plot_items)),
            plot_scores,
            color='#b85d38',
            edgecolor='#1f1a16',
            linewidth=2,
            height=0.62
        )
        ax.set_yticks(range(len(plot_items)))
        ax.set_yticklabels(plot_labels, fontsize=9, fontweight='bold', family='monospace', color='#1f1a16')
        ax.set_xlabel('SKOR PAGERANK', fontsize=9.5, fontweight='bold', family='monospace', color='#1f1a16')
        
        for spine in ax.spines.values():
            spine.set_edgecolor('#1f1a16')
            spine.set_linewidth(2)
            
        ax.grid(axis='x', linestyle='--', color='#8c7a66', alpha=0.6)
        
        for bar in bars:
            w = bar.get_width()
            ax.text(w + (max(plot_scores) * 0.015), bar.get_y() + bar.get_height() / 2, f"{w:.4f}",
                    va='center', fontsize=8.5, fontweight='bold', family='monospace', color='#1f1a16')
                    
        ax.set_xlim(0, max(plot_scores) * 1.15)
        plt.tight_layout()
        st.pyplot(fig)


# ==============================================================================
# TAB 3: ANALISIS SIFAT SMALL-WORLD
# ==============================================================================
with tab3:
    st.markdown("#### PENGUJIAN TOPOLOGI SMALL-WORLD (WATTS & STROGATZ, 1998)")
    st.markdown(r"""
    Sebuah jaringan memenuhi kriteria **Small-World Network** apabila memenuhi dua syarat empiris:
    1. **Klasterisasi Lokal Tinggi ($C \gg C_{random}$):** Halaman-halaman membentuk kelompok subtopik yang rapat.
    2. **Rerata Lintasan Pendek ($L \approx L_{random}$):** Setiap halaman dapat dijangkau hanya dalam sedikit lompatan klik.
    """)
    
    col_sw1, col_sw2 = st.columns(2)
    with col_sw1:
        st.markdown("#### PARAMETER EMPIRIS:")
        st.write(f"- **Koefisien Klasterisasi Aktual ($C$):** `{clustering_coeff:.4f}`")
        st.write(f"- **Koefisien Klasterisasi Graf Acak ($C_{{random}}$):** `{c_random:.4f}`")
        st.write(f"- **Rasio Penguatan Klaster ($C / C_{{random}}$):** `{clustering_ratio:.2f}x`")
        st.write(f"- **Rata-rata Jarak Terpendek ($L$):** `{avg_path_len:.2f} hops`")
        
        if clustering_ratio > 1.5:
            st.success("STATUS: TERVERIFIKASI SMALL-WORLD NETWORK (Rasio klasterisasi jauh melampaui jaringan acak).")
        else:
            st.info("STATUS: DISTRIBUSI MERATA (Klasterisasi mendekati graf acak atau ukuran sampel terlalu kecil).")
            
    with col_sw2:
        st.markdown("#### TABEL SENTRALITAS JARINGAN:")
        in_deg_cent = nx.in_degree_centrality(G)
        betw_cent = nx.betweenness_centrality(G)
        cent_data = []
        for r_i, (u_i, p_i) in enumerate(ranking[:6], 1):
            cent_data.append({
                'RANK': f"#{r_i:02d}",
                'HALAMAN': get_page_name(u_i, titles, max_len=24),
                'PAGERANK': round(p_i, 4),
                'IN-DEGREE CENT.': round(in_deg_cent[u_i], 4),
                'BETWEENNESS CENT.': round(betw_cent[u_i], 4)
            })
        st.dataframe(pd.DataFrame(cent_data), hide_index=True, use_container_width=True)


# ==============================================================================
# TAB 4: EKSPOR DATA & INTEGRASI SERVER LAB
# ==============================================================================
with tab4:
    st.markdown("#### EKSPOR PAKET DATA UNTUK SERVER LAB")
    st.write("Unduh berkas keluaran di bawah ini untuk integrasi lebih lanjut pada sistem eksternal.")
    
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
            label="UNDUH JSON GRAF & PAGERANK",
            data=json_str,
            file_name="graph_pagerank.json",
            mime="application/json",
            use_container_width=True
        )
    with col_d2:
        st.download_button(
            label="UNDUH CSV TOP-10 PAGERANK",
            data=csv_str,
            file_name="top10_pagerank.csv",
            mime="text/csv",
            use_container_width=True
        )
    with col_d3:
        st.download_button(
            label="UNDUH HTML CITATION GRAPH",
            data=html_graph,
            file_name="citation_graph.html",
            mime="text/html",
            use_container_width=True
        )
        
    st.markdown("#### PREVIEW STRUKTUR JSON:")
    st.code(json.dumps(full_export['nodes'][:2], indent=2), language='json')
