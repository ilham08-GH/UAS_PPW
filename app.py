import streamlit as st
import requests
from requests.adapters import HTTPAdapter
from urllib3.util.retry import Retry
import urllib3
from bs4 import BeautifulSoup
from urllib.parse import urljoin, urlparse
from collections import deque
import time
import html as html_lib
import networkx as nx
import pandas as pd
import matplotlib.pyplot as plt
import streamlit.components.v1 as components
from pyvis.network import Network

urllib3.disable_warnings(urllib3.exceptions.InsecureRequestWarning)

# ==============================================================================
# KONFIGURASI HALAMAN STREAMLIT
# ==============================================================================
st.set_page_config(page_title="NODECRAFT", page_icon="📦", layout="wide", initial_sidebar_state="collapsed")

# ==============================================================================
# CUSTOM STYLING: CARDBOARD / KRAFT BOX NEOBRUTALISM
# ==============================================================================
st.markdown("""
<style>
    @import url('https://fonts.googleapis.com/css2?family=Space+Mono:ital,wght@0,400;0,700;1,400&family=Work+Sans:wght@500;700;800&display=swap');
    [data-testid="stSidebar"], [data-testid="stSidebarNav"], [data-testid="collapsedControl"], header[data-testid="stHeader"] { display: none !important; }
    .stApp { background-color: #e6dac8; background-image: radial-gradient(#bfae96 1px, transparent 1px); background-size: 20px 20px; color: #1f1a16; font-family: 'Work Sans', sans-serif; }
    .block-container { padding-top: 2rem; padding-bottom: 3rem; max-width: 1380px; }
    .cardboard-header { background-color: #d6bc97; border: 3px solid #1f1a16; box-shadow: 7px 7px 0px #1f1a16; padding: 24px 28px; margin-bottom: 24px; position: relative; }
    .cardboard-header::before { content: "UAS PPW"; position: absolute; top: -14px; right: 28px; background-color: #b85d38; color: #f7f1e5; font-family: 'Space Mono', monospace; font-size: 0.72rem; font-weight: 700; letter-spacing: 1.5px; padding: 4px 12px; border: 2px solid #1f1a16; transform: rotate(1.5deg); }
    .main-title { font-family: 'Space Mono', monospace; font-size: 2.1rem; font-weight: 700; color: #1f1a16; text-transform: uppercase; letter-spacing: -1px; margin-bottom: 6px; line-height: 1.2; }
    .metric-card { background-color: #f4ece1; border: 3px solid #1f1a16; box-shadow: 5px 5px 0px #1f1a16; padding: 16px 12px; text-align: left; position: relative; transition: transform 0.1s ease; }
    .metric-card:hover { transform: translate(-2px, -2px); box-shadow: 7px 7px 0px #1f1a16; }
    .metric-card::after { content: ""; position: absolute; top: 6px; right: 6px; width: 8px; height: 8px; background-color: #1f1a16; }
    .metric-val { font-family: 'Space Mono', monospace; font-size: 1.65rem; font-weight: 700; color: #b85d38; line-height: 1.2; }
    .metric-lbl { font-family: 'Space Mono', monospace; font-size: 0.76rem; color: #1f1a16; font-weight: 700; text-transform: uppercase; margin-top: 4px; white-space: nowrap; overflow: hidden; text-overflow: ellipsis; }
    .graph-container { border: 3px solid #1f1a16; background-color: #f4ece1; padding: 6px; box-shadow: 7px 7px 0px #1f1a16; margin-bottom: 16px; }
    .empty-box { background-color: #d6bc97; border: 3px dashed #1f1a16; box-shadow: 6px 6px 0px #1f1a16; padding: 45px 25px; text-align: center; margin-top: 25px; }
    div[data-testid="stTextInput"] input { background-color: #f4ece1 !important; border: 2px solid #1f1a16 !important; border-radius: 0px !important; color: #1f1a16 !important; font-family: 'Space Mono', monospace !important; box-shadow: 3px 3px 0px #1f1a16 !important; }
    div[data-baseweb="select"] > div { background-color: #f4ece1 !important; border: 2px solid #1f1a16 !important; border-radius: 0px !important; color: #1f1a16 !important; font-family: 'Space Mono', monospace !important; box-shadow: 3px 3px 0px #1f1a16 !important; }
    .stButton > button { background-color: #b85d38 !important; color: #f4ece1 !important; border: 3px solid #1f1a16 !important; border-radius: 0px !important; box-shadow: 5px 5px 0px #1f1a16 !important; font-family: 'Space Mono', monospace !important; font-weight: 700 !important; text-transform: uppercase !important; padding: 0.55rem 1.2rem !important; transition: all 0.1s ease !important; }
    .stButton > button:hover { transform: translate(2px, 2px) !important; box-shadow: 3px 3px 0px #1f1a16 !important; background-color: #9e4b2a !important; }
    div[data-testid="stTabs"] { background-color: transparent !important; margin-top: 10px !important; }
    div[data-baseweb="tab-list"] { gap: 8px !important; background-color: transparent !important; border-bottom: none !important; padding-bottom: 0px !important; margin-bottom: -3px !important; }
    div[data-baseweb="tab-highlight"], div[data-baseweb="tab-border"] { display: none !important; }
    div[data-baseweb="tab-list"] button[data-baseweb="tab"], button[role="tab"] { background-color: #d6bc97 !important; border: 3px solid #1f1a16 !important; border-bottom: 3px solid #1f1a16 !important; border-radius: 0px !important; box-shadow: 4px 4px 0px #1f1a16 !important; padding: 10px 18px !important; font-family: 'Space Mono', monospace !important; font-weight: 700 !important; color: #1f1a16 !important; margin-right: 6px !important; margin-bottom: 0px !important; transition: all 0.1s ease !important; }
    div[data-baseweb="tab-list"] button[data-baseweb="tab"] p, button[role="tab"] p { font-family: 'Space Mono', monospace !important; font-weight: 700 !important; color: #1f1a16 !important; font-size: 0.88rem !important; margin: 0 !important; }
    div[data-baseweb="tab-list"] button[data-baseweb="tab"]:hover, button[role="tab"]:hover { background-color: #cbb08a !important; transform: translate(-1px, -1px) !important; box-shadow: 5px 5px 0px #1f1a16 !important; }
    div[data-baseweb="tab-list"] button[data-baseweb="tab"][aria-selected="true"], button[role="tab"][aria-selected="true"] { background-color: #f4ece1 !important; border: 3px solid #1f1a16 !important; border-bottom: 3px solid #f4ece1 !important; box-shadow: 4px -2px 0px #1f1a16 !important; transform: translateY(3px) !important; z-index: 10 !important; }
    div[data-baseweb="tab-list"] button[data-baseweb="tab"][aria-selected="true"] p, button[role="tab"][aria-selected="true"] p { color: #b85d38 !important; font-weight: 800 !important; }
    div[data-testid="stTabs"] div[role="tabpanel"], div[data-testid="stTabs"] div[data-baseweb="tab-panel"] { background-color: #f4ece1 !important; border: 3px solid #1f1a16 !important; box-shadow: 7px 7px 0px #1f1a16 !important; padding: 24px 22px !important; margin-top: 0px !important; }
    .cardboard-table-wrap { border: 3px solid #1f1a16; box-shadow: 6px 6px 0px #1f1a16; background-color: #f4ece1; overflow-x: auto; margin-top: 14px; margin-bottom: 24px; }
    table.cardboard-table { width: 100%; border-collapse: collapse; font-family: 'Space Mono', monospace; font-size: 0.85rem; background-color: #f4ece1; color: #1f1a16; }
    table.cardboard-table th { background-color: #d6bc97; color: #1f1a16; font-weight: 700; border-bottom: 3px solid #1f1a16; border-right: 1.5px solid #1f1a16; padding: 12px 14px; white-space: nowrap; }
    table.cardboard-table td { padding: 10px 14px; border-bottom: 1.5px solid #1f1a16; border-right: 1.5px solid #1f1a16; font-weight: 700; }
    table.cardboard-table tbody tr:nth-child(even) { background-color: #ede2d3; }
    table.cardboard-table tbody tr:hover { background-color: #e3d0b8 !important; }
</style>
""", unsafe_allow_html=True)


# ==============================================================================
# FUNGSI RENDER TABEL CARDBOARD
# ==============================================================================
def render_cardboard_table(df, align_right_cols=None, badge_col=None):
    align_right_cols = align_right_cols or []
    headers = df.columns.tolist()
    html = ["<div class='cardboard-table-wrap'><table class='cardboard-table'><thead><tr>"]
    for col in headers:
        align = "right" if col in align_right_cols else "left"
        html.append(f"<th style='text-align: {align};'>{html_lib.escape(str(col))}</th>")
    html.append("</tr></thead><tbody>")
    for idx, row in df.iterrows():
        html.append("<tr>")
        for col in headers:
            val = row[col]
            align = "right" if col in align_right_cols else "left"
            if col == badge_col:
                val_str = html_lib.escape(str(val))
                badge_style = "background: #1f1a16; color: #f4ece1; border: 2px solid #b85d38;" if idx == 0 else "background: #b85d38; color: #f7f1e5; border: 1.5px solid #1f1a16;" if idx in (1, 2) else "background: #d6bc97; color: #1f1a16; border: 1.5px solid #1f1a16;"
                cell_html = f"<span style='{badge_style} padding: 2px 7px; display: inline-block;'>{val_str}</span>"
            elif col == 'URL ASLI':
                url_text = str(val)
                short_url = url_text[:46] + '...' if len(url_text) > 46 else url_text
                cell_html = f"<a href='{html_lib.escape(url_text)}' target='_blank' style='color: #2f5266; text-decoration: underline;'>{html_lib.escape(short_url)}</a>"
            elif col in ('SKOR PAGERANK', 'PAGERANK'): cell_html = f"<span style='color: #b85d38;'>{val}</span>"
            else: cell_html = html_lib.escape(str(val))
            html.append(f"<td style='text-align: {align};'>{cell_html}</td>")
        html.append("</tr>")
    html.append("</tbody></table></div>")
    return "".join(html)

def compute_pagerank(G, alpha=0.85, max_iter=100, tol=1e-6):
    try: return nx.pagerank(G, alpha=alpha, max_iter=max_iter, tol=tol)
    except Exception:
        nodes = list(G.nodes())
        N = len(nodes)
        if N == 0: return {}
        pr = {n: 1.0 / N for n in nodes}
        for _ in range(max_iter):
            pr_new = {}
            dangling_sum = sum(pr[n] for n in nodes if G.out_degree(n) == 0)
            dangling_contrib = alpha * dangling_sum / N
            for v in nodes:
                in_sum = sum(pr[u] / G.out_degree(u) for u in G.predecessors(v) if G.out_degree(u) > 0)
                pr_new[v] = (1.0 - alpha) / N + alpha * in_sum + dangling_contrib
            if sum(abs(pr_new[n] - pr[n]) for n in nodes) < tol: break
            pr = pr_new
        return pr

COMMUNITY_PALETTE = ['#b85d38', '#3b6e5c', '#d48c29', '#2f5266', '#8c3f4d', '#6b5b3e', '#4a6b82', '#a35c37', '#526b44', '#7a496b', '#9c6b30', '#3d5a58']

def detect_communities(G):
    G_undir = G.to_undirected()
    if G_undir.number_of_nodes() == 0: return {}
    try: comm_list = list(nx.community.louvain_communities(G_undir, seed=42))
    except: comm_list = [set(G.nodes())]
    node_to_community = {}
    for comm_idx, members in enumerate(comm_list):
        for node in members: node_to_community[node] = comm_idx
    return node_to_community

def get_page_name(url, page_titles=None, max_len=30):
    parsed = urlparse(url)
    if page_titles and url in page_titles:
        title = str(page_titles[url]).strip()
        for sep in [' - ', ' | ', ' — ', ' :: ']:
            if sep in title:
                parts = title.split(sep)
                if len(parts[0]) > 3: title = parts[0].strip()
        if title and title != '-' and title != url and not title.startswith('http'):
            return title[:max_len]
    netloc = parsed.netloc.replace('www.', '')
    path = parsed.path.strip('/')
    subdomain = netloc.split('.')[0] if len(netloc.split('.')) > 2 else ""
    if path:
        clean_slug = path.split('/')[-1].replace('.html', '').replace('.php', '').replace('-', ' ').title()
        if len(clean_slug) > max_len: clean_slug = clean_slug[:max_len-3] + '...'
        return f"[{subdomain}] {clean_slug}"[:max_len] if subdomain else clean_slug[:max_len]
    return f"[{subdomain}] Beranda"[:max_len] if subdomain else f"Beranda ({netloc})"[:max_len]


# ==============================================================================
# KELAS WEB CRAWLER (TANPA MAX PER DOMAIN)
# ==============================================================================
class WebCrawler:
    def __init__(self, seed_url, max_depth=3, max_pages=50, delay=0.4, timeout=16):
        self.seed_url = seed_url
        self.max_depth = max_depth
        self.max_pages = max_pages
        self.delay = delay
        self.timeout = timeout
        self.visited = set()
        self.all_nodes = set()
        self.edges = []
        self.page_titles = {}
        self.depth_counts = {}
        self.failed_urls = []
        ...

    def crawl(self, progress_callback=None):
        start_url = self._normalize_url(self.seed_url)
        queue = deque([(start_url, 0)])
        self.all_nodes.add(start_url)

        while queue:
            current_url, current_depth = queue.popleft()
            if current_depth > self.max_depth:
                continue
            if current_url in self.visited:
                continue

            # Batas kuota berlaku per level kedalaman (bukan total global)
            used_in_depth = self.depth_counts.get(current_depth, 0)
            if used_in_depth >= self.max_pages:
                continue

            try:
                response = self._fetch(current_url)
                if response.status_code != 200 or 'text/html' not in response.headers.get('Content-Type', ''):
                    continue

                soup = BeautifulSoup(response.text, 'html.parser')
                title_tag = soup.find('title')
                title = title_tag.get_text(strip=True) if title_tag else current_url
                if any(sig in title.lower() for sig in ['page not found', '404', 'error']):
                    continue

                self.visited.add(current_url)
                self.all_nodes.add(current_url)
                self.depth_counts[current_depth] = used_in_depth + 1
                self.page_titles[current_url] = title

                if current_depth < self.max_depth:
                    found_links = set()
                    for a_tag in soup.find_all('a', href=True):
                        full_url = urljoin(current_url, a_tag['href'].strip())
                        norm = self._normalize_url(full_url)
                        if self._is_valid_url(norm) and norm != current_url:
                            found_links.add(norm)

                    for target in found_links:
                        self.all_nodes.add(target)
                        self.edges.append((current_url, target))
                        if target not in self.visited:
                            queue.append((target, current_depth + 1))

                if progress_callback:
                    progress_callback(len(self.visited), current_depth, current_url, title)
                time.sleep(self.delay)
            except Exception as e:
                self.failed_urls.append((current_url, str(e)[:40]))

        return self.all_nodes, self.edges, self.page_titles
        
# ==============================================================================
# FUNGSI MEMBANGUN CITATION GRAPH
# ==============================================================================
def generate_connected_papers_graph(G, pr_scores, ranking, page_titles, seed_url, color_mode="Klaster Komunitas (Connected Papers)", show_all_labels=False):
    net = Network(height='720px', width='100%', directed=True, bgcolor='#f4ece1', font_color='#1f1a16', cdn_resources='remote')
    net.force_atlas_2based(gravity=-180, central_gravity=0.01, spring_length=150, spring_strength=0.05, damping=0.8, overlap=0.4)

    max_pr = max(pr_scores.values()) if pr_scores else 1
    min_pr = min(pr_scores.values()) if pr_scores else 0
    denom = (max_pr - min_pr) if (max_pr - min_pr) > 0 else 1
    
    node_communities = detect_communities(G)
    top_nodes = [u for u, _ in ranking[:5]]
    top1_node = ranking[0][0] if ranking else seed_url

    for node in G.nodes():
        pr_val = pr_scores.get(node, 0)
        norm_val = (pr_val - min_pr) / denom
        node_size = 12 + (norm_val ** 0.8) * 45
        name_short = get_page_name(node, page_titles, max_len=28)
        title_full = page_titles.get(node, name_short)
        rank_pos = [i + 1 for i, (u, _) in enumerate(ranking) if u == node]
        comm_id = node_communities.get(node, 0)

        if node == top1_node or node == seed_url: node_color, border_color = '#1f1a16', '#b85d38'
        elif color_mode == "Klaster Komunitas (Connected Papers)": node_color, border_color = COMMUNITY_PALETTE[comm_id % len(COMMUNITY_PALETTE)], '#1f1a16'
        else: node_color, border_color = f'rgb({int(214 - norm_val * 120)}, {int(188 - norm_val * 115)}, {int(151 - norm_val * 110)})', '#1f1a16'

        node_label = name_short if show_all_labels or node in top_nodes or node == top1_node else " "
        hover_text = f"JUDUL: {title_full}\nURL: {node}\n------------------------\nPAGERANK: {pr_val:.5f}\nKLASTER: #{comm_id + 1}\nIN: {G.in_degree(node)} | OUT: {G.out_degree(node)}"

        net.add_node(
            node, label=node_label, title=hover_text, size=node_size,
            color={'background': node_color, 'border': border_color, 'highlight': {'background': '#b85d38', 'border': '#1f1a16'}},
            borderWidth=2.5, borderWidthSelected=4,
            font={'size': 12, 'color': '#1f1a16', 'face': 'Space Mono, monospace', 'strokeWidth': 4, 'strokeColor': '#f4ece1'}
        )

    for source, target in G.edges():
        is_highlight = target in top_nodes[:2]
        net.add_edge(source, target, color={'color': '#6e5d4f' if is_highlight else '#b5a492', 'highlight': '#b85d38'}, arrows={'to': {'enabled': True, 'scaleFactor': 0.50}}, width=1.6 if is_highlight else 1.0, smooth={'type': 'continuous', 'roundness': 0.12})

    html_out = net.generate_html()
    return html_out.replace("return network;", "network.once('stabilized', function() { network.setOptions({ physics: false }); }); return network;")


# ==============================================================================
# HEADER UTAMA & PANEL FORM
# ==============================================================================
st.markdown("<div class='cardboard-header' style='text-align: center;'><div class='main-title'>[ NodeCraft ]</div></div>", unsafe_allow_html=True)

with st.container():
    seed_url_input = st.text_input("SEED URL TARGET (HALAMAN AWAL):", value="", placeholder="Contoh: https://trunojoyo.ac.id")
    
    # Kembali ke 4 kolom (slider domain dihapus)
    col_p1, col_p2, col_p3, col_p4 = st.columns(4)
    with col_p1: max_depth_input = st.slider("KEDALAMAN:", 1, 4, 2)
    with col_p2: max_pages_input = st.slider("MAKS NODE:", 10, 200, 60, 10)
    with col_p3: delay_input = st.slider("JEDA (DETIK):", 0.1, 2.0, 0.4)
    with col_p4: damping_factor = st.slider("DAMPING (d):", 0.10, 0.99, 0.85)

    crawl_btn = st.button("MULAI CRAWLING & BANGUN GRAF", type="primary", use_container_width=True)

# ==============================================================================
# LOGIKA CRAWLING
# ==============================================================================
if 'graph_data' not in st.session_state:
    st.session_state.graph_data = None

if crawl_btn:
    raw_seed = seed_url_input.strip()
    if not raw_seed: st.warning("Masukkan URL target!")
    else:
        if not raw_seed.startswith(('http://', 'https://')): raw_seed = 'https://' + raw_seed
        crawler = WebCrawler(seed_url=raw_seed, max_depth=max_depth_input, max_pages=max_pages_input, delay=delay_input)
        
        progress_bar = st.progress(0)
        status_text = st.empty()
        def on_progress(current, total, url, title):
            progress_bar.progress(min(1.0, current / total))
            status_text.caption(f"[{current}/{total}] MERAYAPI: {url[:60]}...")
            
        with st.spinner(f"Memetakan jaringan hyperlink..."):
            visited, edges, titles = crawler.crawl(progress_callback=on_progress)
            
        progress_bar.empty()
        status_text.empty()
        
        if len(visited) == 0: st.error("GAGAL MENGAMBIL DATA.")
        else:
            G_crawled = nx.DiGraph()
            G_crawled.add_nodes_from(all_nodes)
            G_crawled.add_edges_from(edges)
            G_crawled.remove_edges_from(nx.selfloop_edges(G_crawled))
            G_crawled.remove_edges_from(nx.selfloop_edges(G_crawled))
            st.session_state.graph_data = {'G': G_crawled, 'titles': titles, 'seed': raw_seed}

# KODE DI BAWAH INI HARUS RATA KIRI (TIDAK BOLEH MENJOROK / DI DALAM IF)
if st.session_state.graph_data is None:
    st.markdown("<div class='empty-box'><div style='font-size: 1.5rem; font-weight: 700; margin-bottom: 10px;'>[ DATA KOSONG ]</div><p>Masukkan Seed URL dan mulai Crawling.</p></div>", unsafe_allow_html=True)
    st.stop()

# ==============================================================================
# PEMROSESAN METRIK
# ==============================================================================
G = st.session_state.graph_data['G']
titles = st.session_state.graph_data['titles']
seed_url = st.session_state.graph_data['seed']

pr_scores = compute_pagerank(G, alpha=damping_factor)
ranking = sorted(pr_scores.items(), key=lambda x: x[1], reverse=True)
in_degs = dict(G.in_degree())
out_degs = dict(G.out_degree())

G_undir = G.to_undirected()
clustering_coeff = nx.average_clustering(G_undir) if G_undir.number_of_nodes() > 1 else 0
N_nodes, E_edges = G.number_of_nodes(), G.number_of_edges()
avg_path_len = nx.average_shortest_path_length(G_undir) if nx.is_connected(G_undir) else 0

best_node = ranking[0][0] if ranking else seed_url
best_title = get_page_name(best_node, titles, max_len=22)
best_pr = ranking[0][1] if ranking else 0.0

st.markdown("<br>", unsafe_allow_html=True)
col1, col2, col3, col4, col5 = st.columns(5)
with col1: st.markdown(f"<div class='metric-card'><div class='metric-val'>{N_nodes}</div><div class='metric-lbl'>SIMPUL (NODES)</div></div>", unsafe_allow_html=True)
with col2: st.markdown(f"<div class='metric-card'><div class='metric-val'>{E_edges}</div><div class='metric-lbl'>BUSUR (EDGES)</div></div>", unsafe_allow_html=True)
with col3: st.markdown(f"<div class='metric-card'><div class='metric-val'>{clustering_coeff:.3f}</div><div class='metric-lbl'>KOEF. KLASTER</div></div>", unsafe_allow_html=True)
with col4: st.markdown(f"<div class='metric-card'><div class='metric-val'>{avg_path_len:.2f}</div><div class='metric-lbl'>JARAK RATA-RATA</div></div>", unsafe_allow_html=True)
with col5: st.markdown(f"<div class='metric-card'><div class='metric-val'>{best_pr:.3f}</div><div class='metric-lbl'>TOP: {best_title}</div></div>", unsafe_allow_html=True)
st.markdown("<br>", unsafe_allow_html=True)


# ==============================================================================
# TABS NAVIGASI (DITAMBAH TAB 3 MATRIX)
# ==============================================================================
tab1, tab2, tab3 = st.tabs(["01 // CITATION GRAPH", "02 // TOP-10 PAGERANK", "03 // ADJACENCY MATRIX"])

# --- TAB 1: GRAF ---
with tab1:
    col_t1, col_t2 = st.columns([3, 2])
    with col_t1: color_choice = st.selectbox("SKEMA WARNA SIMPUL:", ["Klaster Komunitas (Connected Papers)", "Gradasi Skor PageRank"])
    with col_t2: 
        st.markdown("<div style='height: 28px;'></div>", unsafe_allow_html=True)
        show_all_lbl = st.checkbox("TAMPILKAN SEMUA JUDUL", value=False)

    html_graph = generate_connected_papers_graph(G, pr_scores, ranking, titles, seed_url, color_mode=color_choice, show_all_labels=show_all_lbl)
    st.markdown("<div class='graph-container'>", unsafe_allow_html=True)
    components.html(html_graph, height=720, scrolling=False)
    st.markdown("</div>", unsafe_allow_html=True)

# --- TAB 2: PAGERANK ---
with tab2:
    st.markdown("#### PERINGKAT 10 HALAMAN (PETA AFILIASI)")
    top10_rows = [{'RANK': f"#{i+1:02d}", 'NAMA HALAMAN': get_page_name(url, titles, max_len=36), 'URL ASLI': url, 'SKOR PAGERANK': round(score, 6), 'IN-DEGREE': in_degs.get(url, 0), 'OUT-DEGREE': out_degs.get(url, 0)} for i, (url, score) in enumerate(ranking[:10])]
    df_top10 = pd.DataFrame(top10_rows)
    st.markdown(render_cardboard_table(df_top10, align_right_cols=['SKOR PAGERANK', 'IN-DEGREE', 'OUT-DEGREE'], badge_col='RANK'), unsafe_allow_html=True)
    
    if len(ranking) > 0:
        fig, ax = plt.subplots(figsize=(10, 4.5), facecolor='#f4ece1')
        ax.set_facecolor('#f4ece1')
        plot_items = ranking[:min(10, len(ranking))][::-1]
        bars = ax.barh(range(len(plot_items)), [s for _, s in plot_items], color='#b85d38', edgecolor='#1f1a16', linewidth=2, height=0.62)
        ax.set_yticks(range(len(plot_items)))
        ax.set_yticklabels([get_page_name(u, titles, max_len=24) for u, _ in plot_items], fontsize=9, fontweight='bold', family='monospace', color='#1f1a16')
        for spine in ax.spines.values(): spine.set_edgecolor('#1f1a16'); spine.set_linewidth(2)
        ax.grid(axis='x', linestyle='--', color='#8c7a66', alpha=0.6)
        plt.tight_layout()
        st.pyplot(fig)

# --- TAB 3: MATRIKS KETETANGGAAN ---
with tab3:
    st.markdown("#### TABEL MATRIKS ADJACENCY")
    adj_matrix = nx.to_pandas_adjacency(G, dtype=int)
    
    # Penanganan nama kolom ganda
    short_names, seen_names = {}, {}
    for node in G.nodes():
        name = get_page_name(node, titles, max_len=15)
        if name in seen_names:
            seen_names[name] += 1
            short_names[node] = f"{name} ({seen_names[name]})"
        else:
            seen_names[name] = 1
            short_names[node] = name
            
    adj_matrix.rename(index=short_names, columns=short_names, inplace=True)
    
    html_table = adj_matrix.to_html(classes="cardboard-table", border=0)
    html_table = html_table.replace('<td>1</td>', '<td style="color: #b85d38; font-weight: 900; font-size: 1.15rem;">1</td>').replace('<td>0</td>', '<td style="color: #8c7a66; opacity: 0.4;">0</td>')
    
    custom_html = f"""
<div class="cardboard-table-wrap">{html_table}</div>
<style>
.cardboard-table tbody th {{ background-color: #d6bc97; text-align: left; position: sticky; left: 0; z-index: 1; border-right: 2px solid #1f1a16; padding: 10px 14px;}}
.cardboard-table thead th:first-child {{ position: sticky; left: 0; z-index: 2; background-color: #d6bc97; }}
</style>
"""
    st.markdown(custom_html, unsafe_allow_html=True)
