import streamlit as st
import requests
from requests.adapters import HTTPAdapter
from urllib3.util.retry import Retry
import urllib3
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
st.set_page_config(page_title="NODECRAFT // AURORA PASTEL", page_icon="✨", layout="wide", initial_sidebar_state="collapsed")

# ==============================================================================
# CUSTOM STYLING: SOFT AURORA GRADIENT & FROSTED GLASS
# ==============================================================================
st.markdown("""
<style>
    @import url('https://fonts.googleapis.com/css2?family=Plus+Jakarta+Sans:wght@400;500;600;700;800&family=JetBrains+Mono:wght@500;600;700;800&display=swap');

    [data-testid="stSidebar"], [data-testid="stSidebarNav"], [data-testid="collapsedControl"], header[data-testid="stHeader"] {
        display: none !important;
    }

    .stApp {
        background:
            radial-gradient(circle at 12% 14%, rgba(196, 181, 253, 0.54), transparent 44%),
            radial-gradient(circle at 86% 18%, rgba(165, 243, 252, 0.56), transparent 46%),
            radial-gradient(circle at 68% 82%, rgba(167, 243, 208, 0.50), transparent 48%),
            linear-gradient(145deg, #f4f1ff 0%, #eef6ff 48%, #ecfdf5 100%);
        color: #1e2235;
        font-family: 'Plus Jakarta Sans', sans-serif;
    }

    .block-container {
        padding-top: 2rem;
        padding-bottom: 3rem;
        max-width: 1380px;
    }

    .aurora-header {
        background: linear-gradient(125deg, rgba(255, 255, 255, 0.80), rgba(243, 238, 255, 0.72), rgba(236, 253, 245, 0.76));
        backdrop-filter: blur(20px);
        -webkit-backdrop-filter: blur(20px);
        border: 1.5px solid rgba(255, 255, 255, 0.92);
        border-radius: 24px;
        box-shadow: 0 16px 38px rgba(99, 102, 241, 0.12), inset 0 1px 0 rgba(255, 255, 255, 0.96);
        padding: 28px 32px;
        margin-bottom: 24px;
        position: relative;
        overflow: hidden;
    }

    .aurora-header::before {
        content: "UAS PPW // DOI CITATION";
        position: absolute;
        top: 18px;
        right: 24px;
        background: linear-gradient(90deg, rgba(124, 58, 237, 0.12), rgba(13, 148, 136, 0.14));
        color: #4f46e5;
        font-family: 'JetBrains Mono', monospace;
        font-size: 0.72rem;
        font-weight: 700;
        letter-spacing: 1px;
        padding: 5px 13px;
        border-radius: 999px;
        border: 1px solid rgba(129, 140, 248, 0.35);
    }

    .main-title {
        font-family: 'Plus Jakarta Sans', sans-serif;
        font-size: 2.2rem;
        font-weight: 800;
        background: linear-gradient(90deg, #4f46e5 0%, #0284c7 48%, #0d9488 100%);
        -webkit-background-clip: text;
        -webkit-text-fill-color: transparent;
        letter-spacing: -0.5px;
        margin-bottom: 6px;
        line-height: 1.2;
    }

    .sub-title {
        color: #525b75;
        font-size: 0.93rem;
        font-weight: 500;
    }

    .metric-card {
        background: rgba(255, 255, 255, 0.78);
        backdrop-filter: blur(16px);
        -webkit-backdrop-filter: blur(16px);
        border: 1.5px solid rgba(255, 255, 255, 0.92);
        border-radius: 20px;
        box-shadow: 0 10px 26px rgba(99, 102, 241, 0.09);
        padding: 18px 16px;
        text-align: left;
        position: relative;
        transition: transform 0.2s ease, box-shadow 0.2s ease;
    }

    .metric-card:hover {
        transform: translateY(-3px);
        box-shadow: 0 14px 32px rgba(14, 165, 233, 0.16);
    }

    .metric-val {
        font-family: 'JetBrains Mono', monospace;
        font-size: 1.7rem;
        font-weight: 800;
        background: linear-gradient(90deg, #4f46e5 0%, #0284c7 52%, #0d9488 100%);
        -webkit-background-clip: text;
        -webkit-text-fill-color: transparent;
        line-height: 1.2;
    }

    .metric-lbl {
        font-family: 'Plus Jakarta Sans', sans-serif;
        font-size: 0.75rem;
        color: #525b75;
        font-weight: 700;
        text-transform: uppercase;
        letter-spacing: 0.5px;
        margin-top: 6px;
        white-space: nowrap;
        overflow: hidden;
        text-overflow: ellipsis;
    }

    .graph-container {
        border: 1.5px solid rgba(255, 255, 255, 0.9);
        border-radius: 20px;
        background: rgba(255, 255, 255, 0.85);
        padding: 6px;
        box-shadow: 0 12px 30px rgba(99, 102, 241, 0.1);
        margin-bottom: 16px;
        overflow: hidden;
    }

    .empty-box {
        background: rgba(255, 255, 255, 0.72);
        backdrop-filter: blur(16px);
        border: 1.5px dashed rgba(99, 102, 241, 0.35);
        border-radius: 22px;
        box-shadow: 0 10px 28px rgba(99, 102, 241, 0.08);
        padding: 46px 25px;
        text-align: center;
        margin-top: 25px;
        color: #475569;
    }

    label, .stSlider label, .stTextInput label, .stSelectbox label, .stCheckbox label {
        color: #272c42 !important;
        font-weight: 700 !important;
        font-size: 0.84rem !important;
    }

    div[data-testid="stTextInput"] input {
        background-color: rgba(255, 255, 255, 0.84) !important;
        border: 1.5px solid rgba(148, 163, 184, 0.38) !important;
        border-radius: 14px !important;
        color: #1e2235 !important;
        font-family: 'JetBrains Mono', monospace !important;
        padding: 10px 14px !important;
        box-shadow: 0 4px 14px rgba(99, 102, 241, 0.06) !important;
    }

    div[data-testid="stTextInput"] input:focus {
        border-color: #0284c7 !important;
        box-shadow: 0 0 0 3px rgba(56, 189, 248, 0.25) !important;
    }

    div[data-baseweb="select"] > div {
        background-color: rgba(255, 255, 255, 0.84) !important;
        border: 1.5px solid rgba(148, 163, 184, 0.38) !important;
        border-radius: 14px !important;
        color: #1e2235 !important;
    }

    .stButton > button {
        background: linear-gradient(90deg, #4f46e5 0%, #0284c7 52%, #0d9488 100%) !important;
        color: #ffffff !important;
        border: none !important;
        border-radius: 14px !important;
        box-shadow: 0 8px 22px rgba(2, 132, 199, 0.28) !important;
        font-family: 'Plus Jakarta Sans', sans-serif !important;
        font-weight: 700 !important;
        letter-spacing: 0.4px !important;
        padding: 0.65rem 1.4rem !important;
        transition: all 0.2s ease !important;
    }

    .stButton > button:hover {
        transform: translateY(-2px) !important;
        box-shadow: 0 12px 26px rgba(13, 148, 136, 0.32) !important;
        filter: brightness(1.04) !important;
    }

    div[data-testid="stTabs"] {
        background-color: transparent !important;
        margin-top: 10px !important;
    }

    div[data-baseweb="tab-list"] {
        gap: 10px !important;
        background-color: transparent !important;
        border-bottom: none !important;
        margin-bottom: 12px !important;
    }

    div[data-baseweb="tab-highlight"], div[data-baseweb="tab-border"] {
        display: none !important;
    }

    div[data-baseweb="tab-list"] button[data-baseweb="tab"], button[role="tab"] {
        background: rgba(255, 255, 255, 0.65) !important;
        border: 1.5px solid rgba(255, 255, 255, 0.85) !important;
        border-radius: 14px !important;
        padding: 10px 18px !important;
        transition: all 0.2s ease !important;
    }

    div[data-baseweb="tab-list"] button[data-baseweb="tab"] p, button[role="tab"] p {
        font-family: 'JetBrains Mono', monospace !important;
        font-weight: 700 !important;
        color: #525b75 !important;
        font-size: 0.84rem !important;
        margin: 0 !important;
    }

    div[data-baseweb="tab-list"] button[data-baseweb="tab"][aria-selected="true"], button[role="tab"][aria-selected="true"] {
        background: linear-gradient(120deg, rgba(196, 181, 253, 0.48), rgba(165, 243, 252, 0.52), rgba(167, 243, 208, 0.48)) !important;
        border: 1.5px solid rgba(79, 70, 229, 0.45) !important;
        box-shadow: 0 6px 18px rgba(79, 70, 229, 0.14) !important;
    }

    div[data-baseweb="tab-list"] button[data-baseweb="tab"][aria-selected="true"] p, button[role="tab"][aria-selected="true"] p {
        color: #1e2235 !important;
        font-weight: 800 !important;
    }

    div[data-testid="stTabs"] div[role="tabpanel"], div[data-testid="stTabs"] div[data-baseweb="tab-panel"] {
        background: rgba(255, 255, 255, 0.74) !important;
        backdrop-filter: blur(18px) !important;
        border: 1.5px solid rgba(255, 255, 255, 0.9) !important;
        border-radius: 22px !important;
        box-shadow: 0 12px 32px rgba(99, 102, 241, 0.1) !important;
        padding: 24px 22px !important;
    }

    .aurora-table-wrap {
        border: 1.5px solid rgba(148, 163, 184, 0.28);
        border-radius: 16px;
        background: rgba(255, 255, 255, 0.82);
        overflow-x: auto;
        margin-top: 14px;
        margin-bottom: 24px;
    }

    table.aurora-table {
        width: 100%;
        border-collapse: collapse;
        font-family: 'JetBrains Mono', monospace;
        font-size: 0.83rem;
        color: #1e2235;
    }

    table.aurora-table th {
        background: linear-gradient(90deg, rgba(224, 231, 255, 0.92), rgba(204, 251, 241, 0.9));
        color: #1e2235;
        font-weight: 800;
        border-bottom: 1.5px solid rgba(148, 163, 184, 0.35);
        padding: 12px 14px;
        white-space: nowrap;
    }

    table.aurora-table td {
        padding: 10px 14px;
        border-bottom: 1px solid rgba(148, 163, 184, 0.18);
    }

    table.aurora-table tbody tr:nth-child(even) {
        background-color: rgba(241, 245, 249, 0.55);
    }

    table.aurora-table tbody tr:hover {
        background-color: rgba(165, 243, 252, 0.35) !important;
    }
</style>
""", unsafe_allow_html=True)


# ==============================================================================
# FUNGSI RENDER TABEL SOFT AURORA
# ==============================================================================
def render_aurora_table(df, align_right_cols=None, badge_col=None):
    align_right_cols = align_right_cols or []
    headers = df.columns.tolist()
    html = ["<div class='aurora-table-wrap'><table class='aurora-table'><thead><tr>"]
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
                if idx == 0:
                    badge_style = "background: linear-gradient(90deg, #4f46e5, #0d9488); color: #ffffff; font-weight: 800;"
                elif idx in (1, 2):
                    badge_style = "background: rgba(2, 132, 199, 0.14); color: #0369a1; border: 1px solid rgba(2, 132, 199, 0.32);"
                else:
                    badge_style = "background: rgba(100, 116, 139, 0.12); color: #334155; border: 1px solid rgba(148, 163, 184, 0.3);"
                cell_html = f"<span style='{badge_style} padding: 3px 9px; border-radius: 999px; display: inline-block;'>{val_str}</span>"
            elif col == 'DOI / URL':
                doi_text = str(val)
                href = doi_text if doi_text.startswith('http') else f"https://doi.org/{doi_text}"
                short_txt = doi_text[:44] + '...' if len(doi_text) > 44 else doi_text
                cell_html = f"<a href='{html_lib.escape(href)}' target='_blank' style='color: #0284c7; font-weight: 700; text-decoration: underline;'>{html_lib.escape(short_txt)}</a>"
            elif col in ('SKOR PAGERANK', 'PAGERANK'):
                cell_html = f"<span style='color: #0d9488; font-weight: 800;'>{val}</span>"
            else:
                cell_html = html_lib.escape(str(val))
            html.append(f"<td style='text-align: {align};'>{cell_html}</td>")
        html.append("</tr>")
    html.append("</tbody></table></div>")
    return "".join(html)


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
            if sum(abs(pr_new[n] - pr[n]) for n in nodes) < tol:
                break
            pr = pr_new
        return pr


PASTEL_AURORA_PALETTE = [
    '#7c6cf0', '#0ea5e9', '#10b981', '#a855f7', '#06b6d4', '#14b8a6',
    '#6366f1', '#ec4899', '#3b82f6', '#8b5cf6', '#22c55e', '#0284c7'
]


def detect_communities(G):
    G_undir = G.to_undirected()
    if G_undir.number_of_nodes() == 0:
        return {}
    try:
        comm_list = list(nx.community.louvain_communities(G_undir, seed=42))
    except Exception:
        comm_list = [set(G.nodes())]
    node_to_community = {}
    for comm_idx, members in enumerate(comm_list):
        for node in members:
            node_to_community[node] = comm_idx
    return node_to_community


def get_node_label(node_id, page_titles=None, max_len=32):
    if page_titles and node_id in page_titles:
        title = str(page_titles[node_id]).strip()
        if title and title != '-' and title != node_id:
            return (title[:max_len - 3] + '...') if len(title) > max_len else title
    return (node_id[:max_len - 3] + '...') if len(node_id) > max_len else node_id


# ==============================================================================
# KELAS DOI CITATION CRAWLER (OPENALEX + CROSSREF FALLBACK)
# ==============================================================================
class DOICitationCrawler:
    def __init__(self, seed_doi, max_depth=2, max_per_depth=25, delay=0.25, timeout=16):
        self.seed_doi = self._normalize_doi(seed_doi)
        self.max_depth = max_depth
        self.max_per_depth = max_per_depth
        self.delay = delay
        self.timeout = timeout

        self.visited = set()
        self.all_nodes = set()
        self.edges = []
        self.paper_titles = {}
        self.paper_years = {}
        self.depth_counts = {}
        self.failed_dois = []
        self._openalex_id_to_doi = {}

        self.session = requests.Session()
        retries = Retry(total=2, backoff_factor=0.3, status_forcelist=[429, 500, 502, 503, 504])
        self.session.mount('https://', HTTPAdapter(max_retries=retries))
        self.session.mount('http://', HTTPAdapter(max_retries=retries))
        self.headers = {
            'User-Agent': 'NodeCraft-DOI-Crawler/1.0 (mailto:student@trunojoyo.ac.id)',
            'Accept': 'application/json',
        }

    def _normalize_doi(self, raw):
        d = str(raw).strip().lower()
        for prefix in ('https://doi.org/', 'http://doi.org/', 'https://dx.doi.org/', 'http://dx.doi.org/', 'doi:'):
            if d.startswith(prefix):
                d = d[len(prefix):]
        return d.strip('/')

    def _resolve_openalex_refs(self, work_ids):
        resolved_dois = []
        uncached = []
        for wid in work_ids:
            short_id = wid.split('/')[-1]
            if short_id in self._openalex_id_to_doi:
                val = self._openalex_id_to_doi[short_id]
                if val:
                    resolved_dois.append(val)
            else:
                uncached.append(short_id)

        for i in range(0, len(uncached), 40):
            chunk = uncached[i:i + 40]
            filter_str = "|".join(chunk)
            url = f"https://api.openalex.org/works?filter=openalex:{filter_str}&select=id,doi,title,publication_year&per-page=50"
            try:
                res = self.session.get(url, headers=self.headers, timeout=self.timeout)
                if res.status_code == 200:
                    results = res.json().get('results', [])
                    seen_ids = set()
                    for item in results:
                        oid = item.get('id', '').split('/')[-1]
                        seen_ids.add(oid)
                        raw_doi = item.get('doi')
                        if raw_doi:
                            norm_doi = self._normalize_doi(raw_doi)
                            self._openalex_id_to_doi[oid] = norm_doi
                            if norm_doi not in self.paper_titles and item.get('title'):
                                yr = item.get('publication_year')
                                self.paper_titles[norm_doi] = f"{item['title']} ({yr})" if yr else item['title']
                                self.paper_years[norm_doi] = yr or '-'
                            resolved_dois.append(norm_doi)
                        else:
                            self._openalex_id_to_doi[oid] = None
                    for oid in chunk:
                        if oid not in seen_ids:
                            self._openalex_id_to_doi[oid] = None
            except Exception:
                pass
        return resolved_dois

    def _fetch_doi_metadata(self, doi):
        oa_url = f"https://api.openalex.org/works/https://doi.org/{doi}"
        try:
            res = self.session.get(oa_url, headers=self.headers, timeout=self.timeout)
            if res.status_code == 200:
                data = res.json()
                title = data.get('title') or doi
                yr = data.get('publication_year')
                label = f"{title} ({yr})" if yr else title
                ref_ids = data.get('referenced_works', [])[:60]
                ref_dois = self._resolve_openalex_refs(ref_ids)
                return label, yr or '-', ref_dois
        except Exception:
            pass

        cr_url = f"https://api.crossref.org/works/{doi}"
        try:
            res = self.session.get(cr_url, headers=self.headers, timeout=self.timeout)
            if res.status_code == 200:
                msg = res.json().get('message', {})
                titles = msg.get('title', [])
                title = titles[0] if titles else doi
                yr = '-'
                issued = msg.get('issued', {}).get('date-parts', [[]])
                if issued and issued[0]:
                    yr = issued[0][0]
                label = f"{title} ({yr})" if yr != '-' else title
                ref_dois = []
                for ref in msg.get('reference', []):
                    if 'DOI' in ref:
                        ref_dois.append(self._normalize_doi(ref['DOI']))
                return label, yr, ref_dois
        except Exception:
            pass

        return None, None, []

    def crawl(self, progress_callback=None):
        if not self.seed_doi:
            return self.visited, self.edges, self.paper_titles

        queue = deque([(self.seed_doi, 0)])
        self.all_nodes.add(self.seed_doi)

        while queue:
            current_doi, current_depth = queue.popleft()
            if current_depth > self.max_depth:
                continue
            if current_doi in self.visited:
                continue

            used_in_depth = self.depth_counts.get(current_depth, 0)
            if used_in_depth >= self.max_per_depth:
                continue

            title, yr, ref_dois = self._fetch_doi_metadata(current_doi)
            if title is None:
                self.failed_dois.append(current_doi)
                continue

            self.visited.add(current_doi)
            self.all_nodes.add(current_doi)
            self.depth_counts[current_depth] = used_in_depth + 1
            self.paper_titles[current_doi] = title
            self.paper_years[current_doi] = yr

            if current_depth < self.max_depth:
                unique_refs = []
                seen_refs = set()
                for r_doi in ref_dois:
                    if r_doi and r_doi != current_doi and r_doi not in seen_refs:
                        seen_refs.add(r_doi)
                        unique_refs.append(r_doi)

                for target_doi in unique_refs:
                    self.all_nodes.add(target_doi)
                    self.edges.append((current_doi, target_doi))
                    if target_doi not in self.visited:
                        queue.append((target_doi, current_depth + 1))

            if progress_callback:
                progress_callback(len(self.visited), current_depth, current_doi, title)
            time.sleep(self.delay)

        return self.visited, self.edges, self.paper_titles


# ==============================================================================
# FUNGSI MEMBANGUN CITATION GRAPH (SOFT AURORA LIGHT THEME)
# ==============================================================================
def generate_aurora_citation_graph(G, pr_scores, ranking, paper_titles, seed_doi,
                                   color_mode="Klaster Komunitas (Soft Aurora)",
                                   show_all_labels=False, max_vis_nodes=120):
    if G.number_of_nodes() > max_vis_nodes:
        top_ids = [u for u, _ in ranking[:max_vis_nodes]]
        G_vis = G.subgraph(top_ids).copy()
    else:
        G_vis = G

    net = Network(height='720px', width='100%', directed=True, bgcolor='#f7f9ff', font_color='#1e2235', cdn_resources='remote')
    net.force_atlas_2based(gravity=-180, central_gravity=0.01, spring_length=150, spring_strength=0.05, damping=0.82, overlap=0.4)

    max_pr = max(pr_scores.values()) if pr_scores else 1
    min_pr = min(pr_scores.values()) if pr_scores else 0
    denom = (max_pr - min_pr) if (max_pr - min_pr) > 0 else 1

    node_communities = detect_communities(G_vis)
    top_nodes = [u for u, _ in ranking[:5]]
    top1_node = ranking[0][0] if ranking else seed_doi

    for node in G_vis.nodes():
        pr_val = pr_scores.get(node, 0)
        norm_val = (pr_val - min_pr) / denom
        node_size = 13 + (norm_val ** 0.8) * 44
        name_short = get_node_label(node, paper_titles, max_len=30)
        title_full = paper_titles.get(node, name_short)
        comm_id = node_communities.get(node, 0)

        if node == top1_node or node == seed_doi:
            node_color, border_color = '#4f46e5', '#0d9488'
        elif color_mode == "Klaster Komunitas (Soft Aurora)":
            node_color, border_color = PASTEL_AURORA_PALETTE[comm_id % len(PASTEL_AURORA_PALETTE)], '#ffffff'
        else:
            node_color = f'rgb({int(129 - norm_val * 116)}, {int(140 + norm_val * 40)}, {int(248 - norm_val * 100)})'
            border_color = '#ffffff'

        node_label = name_short if show_all_labels or node in top_nodes or node == top1_node else " "
        hover_text = (
            f"JUDUL: {title_full}\nDOI: {node}\n"
            f"------------------------\n"
            f"PAGERANK: {pr_val:.5f}\nKLASTER: #{comm_id + 1}\n"
            f"DISITASI (IN): {G.in_degree(node)} | MENYITASI (OUT): {G.out_degree(node)}"
        )

        net.add_node(
            node, label=node_label, title=hover_text, size=node_size,
            color={'background': node_color, 'border': border_color, 'highlight': {'background': '#0d9488', 'border': '#1e2235'}},
            borderWidth=2.5, borderWidthSelected=4,
            font={'size': 12, 'color': '#1e2235', 'face': 'JetBrains Mono, monospace', 'strokeWidth': 4, 'strokeColor': '#f7f9ff'}
        )

    for source, target in G_vis.edges():
        is_highlight = target in top_nodes[:2]
        net.add_edge(
            source, target,
            color={'color': 'rgba(79, 70, 229, 0.45)' if is_highlight else 'rgba(148, 163, 184, 0.42)', 'highlight': '#0d9488'},
            arrows={'to': {'enabled': True, 'scaleFactor': 0.50}},
            width=1.6 if is_highlight else 1.0,
            smooth={'type': 'continuous', 'roundness': 0.12}
        )

    html_out = net.generate_html()
    return html_out.replace("return network;", "network.once('stabilized', function() { network.setOptions({ physics: false }); }); return network;")


# ==============================================================================
# HEADER UTAMA & PANEL FORM
# ==============================================================================
st.markdown("""
<div class='aurora-header'>
    <div class='main-title'>[ NodeCraft // Aurora ]</div>
    <div class='sub-title'>Pemetaan Jaringan Sitasi Jurnal Ilmiah (DOI-to-DOI) &amp; Analisis Otoritas PageRank</div>
</div>
""", unsafe_allow_html=True)

with st.container():
    seed_doi_input = st.text_input(
        "SEED DOI JURNAL AWAL:",
        value="",
        placeholder="Contoh: 10.1038/s41586-021-03819-2 atau https://doi.org/10.1109/5.771073"
    )

    col_p1, col_p2, col_p3, col_p4 = st.columns(4)
    with col_p1:
        max_depth_input = st.slider("KEDALAMAN SITASI:", 1, 3, 2)
    with col_p2:
        max_per_depth_input = st.slider("MAKS DOI / DEPTH:", 5, 60, 20, 5)
    with col_p3:
        delay_input = st.slider("JEDA API (DETIK):", 0.1, 1.5, 0.25)
    with col_p4:
        damping_factor = st.slider("DAMPING (d):", 0.10, 0.99, 0.85)

    crawl_btn = st.button("MULAI CRAWLING DOI & BANGUN GRAF SITASI", type="primary", use_container_width=True)

# ==============================================================================
# LOGIKA CRAWLING DOI
# ==============================================================================
if 'graph_data' not in st.session_state:
    st.session_state.graph_data = None

if crawl_btn:
    raw_seed = seed_doi_input.strip()
    if not raw_seed:
        st.warning("Masukkan DOI jurnal target terlebih dahulu!")
    else:
        crawler = DOICitationCrawler(
            seed_doi=raw_seed,
            max_depth=max_depth_input,
            max_per_depth=max_per_depth_input,
            delay=delay_input
        )

        progress_bar = st.progress(0)
        status_text = st.empty()
        max_expected = max(1, (max_depth_input + 1) * max_per_depth_input)

        def on_progress(current, depth, doi, title):
            progress_bar.progress(min(1.0, current / max_expected))
            status_text.caption(f"[{current}] DEPTH {depth} | MEMBACA DOI: {doi} — {title[:55]}...")

        with st.spinner("Menelusuri metadata dan referensi DOI melalui API..."):
            visited, edges, titles = crawler.crawl(progress_callback=on_progress)

        progress_bar.empty()
        status_text.empty()

        if len(visited) == 0:
            st.error("GAGAL MENGAMBIL METADATA DOI. Pastikan format DOI valid dan terdaftar di OpenAlex/Crossref.")
        else:
            G_crawled = nx.DiGraph()
            G_crawled.add_nodes_from(crawler.all_nodes)
            G_crawled.add_edges_from(edges)
            G_crawled.remove_edges_from(nx.selfloop_edges(G_crawled))
            st.session_state.graph_data = {
                'G': G_crawled,
                'titles': titles,
                'years': crawler.paper_years,
                'seed': crawler.seed_doi
            }

if st.session_state.graph_data is None:
    st.markdown("""
    <div class='empty-box'>
        <div style='font-size: 1.45rem; font-weight: 800; color: #4f46e5; margin-bottom: 8px;'>[ JARINGAN SITASI KOSONG ]</div>
        <p style='margin: 0; color: #525b75;'>Masukkan Seed DOI jurnal untuk menelusuri referensi dan membangun graf sitasi.</p>
    </div>
    """, unsafe_allow_html=True)
    st.stop()

# ==============================================================================
# PEMROSESAN METRIK
# ==============================================================================
G = st.session_state.graph_data['G']
titles = st.session_state.graph_data['titles']
years = st.session_state.graph_data.get('years', {})
seed_doi = st.session_state.graph_data['seed']

pr_scores = compute_pagerank(G, alpha=damping_factor)
ranking = sorted(pr_scores.items(), key=lambda x: x[1], reverse=True)
in_degs = dict(G.in_degree())
out_degs = dict(G.out_degree())

G_undir = G.to_undirected()
clustering_coeff = nx.average_clustering(G_undir) if G_undir.number_of_nodes() > 1 else 0
N_nodes, E_edges = G.number_of_nodes(), G.number_of_edges()
if nx.is_connected(G_undir) and N_nodes > 1:
    avg_path_len = nx.average_shortest_path_length(G_undir)
elif N_nodes > 1:
    largest_cc = max(nx.connected_components(G_undir), key=len)
    avg_path_len = nx.average_shortest_path_length(G_undir.subgraph(largest_cc)) if len(largest_cc) > 1 else 0
else:
    avg_path_len = 0

best_node = ranking[0][0] if ranking else seed_doi
best_title = get_node_label(best_node, titles, max_len=24)
best_pr = ranking[0][1] if ranking else 0.0

st.markdown("<br>", unsafe_allow_html=True)
col1, col2, col3, col4, col5 = st.columns(5)
with col1:
    st.markdown(f"<div class='metric-card'><div class='metric-val'>{N_nodes}</div><div class='metric-lbl'>ARTIKEL (NODES)</div></div>", unsafe_allow_html=True)
with col2:
    st.markdown(f"<div class='metric-card'><div class='metric-val'>{E_edges}</div><div class='metric-lbl'>SITASI (EDGES)</div></div>", unsafe_allow_html=True)
with col3:
    st.markdown(f"<div class='metric-card'><div class='metric-val'>{clustering_coeff:.3f}</div><div class='metric-lbl'>KOEF. KLASTER</div></div>", unsafe_allow_html=True)
with col4:
    st.markdown(f"<div class='metric-card'><div class='metric-val'>{avg_path_len:.2f}</div><div class='metric-lbl'>JARAK RATA-RATA</div></div>", unsafe_allow_html=True)
with col5:
    st.markdown(f"<div class='metric-card'><div class='metric-val'>{best_pr:.4f}</div><div class='metric-lbl'>TOP: {html_lib.escape(best_title)}</div></div>", unsafe_allow_html=True)
st.markdown("<br>", unsafe_allow_html=True)


# ==============================================================================
# TABS NAVIGASI
# ==============================================================================
tab1, tab2, tab3 = st.tabs(["01 // CITATION GRAPH", "02 // TOP-10 PAGERANK", "03 // ADJACENCY MATRIX"])

# --- TAB 1: GRAF ---
with tab1:
    col_t1, col_t2, col_t3 = st.columns([3, 2, 2])
    with col_t1:
        color_choice = st.selectbox("SKEMA WARNA SIMPUL:", ["Klaster Komunitas (Soft Aurora)", "Gradasi Skor PageRank"])
    with col_t2:
        max_vis_input = st.slider("MAKS NODE VISUAL:", 30, 250, 120, 10)
    with col_t3:
        st.markdown("<div style='height: 28px;'></div>", unsafe_allow_html=True)
        show_all_lbl = st.checkbox("TAMPILKAN SEMUA JUDUL", value=False)

    if N_nodes > max_vis_input:
        st.caption(f"Menampilkan Top-{max_vis_input} artikel berdasarkan PageRank dari total {N_nodes} simpul agar graf tetap ringan.")

    html_graph = generate_aurora_citation_graph(
        G, pr_scores, ranking, titles, seed_doi,
        color_mode=color_choice, show_all_labels=show_all_lbl, max_vis_nodes=max_vis_input
    )
    st.markdown("<div class='graph-container'>", unsafe_allow_html=True)
    components.html(html_graph, height=720, scrolling=False)
    st.markdown("</div>", unsafe_allow_html=True)

# --- TAB 2: PAGERANK ---
with tab2:
    st.markdown("#### PERINGKAT 10 ARTIKEL JURNAL PALING BERPENGARUH")
    top10_rows = [
        {
            'RANK': f"#{i+1:02d}",
            'JUDUL ARTIKEL': get_node_label(doi, titles, max_len=44),
            'TAHUN': years.get(doi, '-'),
            'DOI / URL': doi,
            'SKOR PAGERANK': round(score, 6),
            'IN-DEGREE': in_degs.get(doi, 0),
            'OUT-DEGREE': out_degs.get(doi, 0),
        }
        for i, (doi, score) in enumerate(ranking[:10])
    ]
    df_top10 = pd.DataFrame(top10_rows)
    st.markdown(render_aurora_table(df_top10, align_right_cols=['TAHUN', 'SKOR PAGERANK', 'IN-DEGREE', 'OUT-DEGREE'], badge_col='RANK'), unsafe_allow_html=True)

    if len(ranking) > 0:
        fig, ax = plt.subplots(figsize=(10, 4.5), facecolor='#f7f9ff')
        ax.set_facecolor('#ffffff')
        plot_items = ranking[:min(10, len(ranking))][::-1]
        ax.barh(range(len(plot_items)), [s for _, s in plot_items], color='#6366f1', edgecolor='#0d9488', linewidth=1.4, height=0.62)
        ax.set_yticks(range(len(plot_items)))
        ax.set_yticklabels([get_node_label(u, titles, max_len=28) for u, _ in plot_items], fontsize=9, fontweight='bold', family='monospace', color='#1e2235')
        ax.tick_params(axis='x', colors='#475569')
        for spine in ax.spines.values():
            spine.set_edgecolor('#cbd5e1')
            spine.set_linewidth(1.2)
        ax.grid(axis='x', linestyle='--', color='#cbd5e1', alpha=0.75)
        plt.tight_layout()
        st.pyplot(fig)

# --- TAB 3: MATRIKS KETETANGGAAN ---
with tab3:
    st.markdown("#### TABEL MATRIKS ADJACENCY SITASI (MAKS. TOP-40 ARTIKEL)")
    top_mat_nodes = [u for u, _ in ranking[:40]]
    G_mat = G.subgraph(top_mat_nodes)
    adj_matrix = nx.to_pandas_adjacency(G_mat, dtype=int)

    short_names, seen_names = {}, {}
    for node in G_mat.nodes():
        name = get_node_label(node, titles, max_len=18)
        if name in seen_names:
            seen_names[name] += 1
            short_names[node] = f"{name} ({seen_names[name]})"
        else:
            seen_names[name] = 1
            short_names[node] = name

    adj_matrix.rename(index=short_names, columns=short_names, inplace=True)

    html_table = adj_matrix.to_html(classes="aurora-table", border=0)
    html_table = (
        html_table
        .replace('<td>1</td>', '<td style="color: #0f766e; font-weight: 800; font-size: 1.05rem; background: rgba(153, 246, 228, 0.55);">1</td>')
        .replace('<td>0</td>', '<td style="color: #94a3b8; opacity: 0.55;">0</td>')
    )

    custom_html = f"""
<div class="aurora-table-wrap">{html_table}</div>
<style>
.aurora-table tbody th {{ background-color: #eef2ff; color: #1e2235; text-align: left; position: sticky; left: 0; z-index: 1; border-right: 1px solid rgba(148, 163, 184, 0.35); padding: 10px 14px; }}
.aurora-table thead th:first-child {{ position: sticky; left: 0; z-index: 2; background-color: #e0e7ff; }}
</style>
"""
    st.markdown(custom_html, unsafe_allow_html=True)
