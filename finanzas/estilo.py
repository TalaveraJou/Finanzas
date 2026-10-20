import base64
from pathlib import Path

import streamlit as st

# ----------------------------------------------------------------- Paleta ----
# Inspirada en apps tipo Trade Republic / Revolut: negro profundo, mucho aire,
# un único acento mint y verde/rojo solo para cifras positivas/negativas.

BG = "#0a0b0f"
BG_SOFT = "#0f1117"
CARD = "#15181f"
CARD_HI = "#1a1e27"
BORDER = "#23262f"
TEXT = "#eef1f5"
MUTED = "#8a92a4"
VERDE = "#2fe39b"
ROJO = "#ff5d6a"
NARANJA = "#ffb020"
AZUL = "#4cc2ff"
MORADO = "#b793ff"

PALETA_CATEGORIAS = [VERDE, AZUL, MORADO, NARANJA, ROJO, "#2dd4bf", "#f472b6", "#facc15"]

CSS = f"""
<style>
@import url('https://fonts.googleapis.com/css2?family=Inter:wght@400;500;600;700;800&display=swap');

html, body, [data-testid="stAppViewContainer"], [data-testid="stSidebar"],
input, textarea, select, button, h1, h2, h3, h4, h5, h6, p, label,
[data-testid="stMarkdownContainer"] {{
    font-family: 'Inter', -apple-system, BlinkMacSystemFont, 'Segoe UI', sans-serif;
}}
/* No pisar la tipografía de iconos de Streamlit (Material Symbols). */
[data-testid="stIconMaterial"], span.material-icons, span.material-symbols-rounded,
span.material-symbols-outlined {{
    font-family: 'Material Symbols Rounded', 'Material Symbols Outlined', 'Material Icons' !important;
}}

[data-testid="stAppViewContainer"] {{ background: {BG}; }}
[data-testid="stHeader"] {{ background: transparent; }}
.block-container {{ padding-top: 2rem !important; padding-bottom: 3rem; max-width: 1180px !important; }}

h1, h2, h3 {{ letter-spacing: -.02em; font-weight: 700; color: {TEXT}; }}
h1 {{ font-weight: 800; }}

/* ---- Barra lateral ---- */
[data-testid="stSidebar"] {{ background: {BG_SOFT}; border-right: 1px solid {BORDER}; }}
[data-testid="stSidebar"] > div:first-child {{ padding-top: 1.4rem; }}
.brand {{ display:flex; align-items:center; gap:11px; padding:2px 4px 16px; }}
.brand-logo {{ width:40px; height:40px; border-radius:12px; object-fit:cover; box-shadow:0 2px 10px rgba(0,0,0,.4); }}
.brand-name {{ font-weight:800; font-size:1.18rem; color:{TEXT}; letter-spacing:-.02em; }}

/* ---- Hero de patrimonio ---- */
.hero {{
    position: relative;
    border: 1px solid {BORDER};
    border-radius: 22px;
    padding: 26px 28px 24px;
    margin-bottom: 16px;
    background:
        radial-gradient(130% 150% at 0% 0%, rgba(47,227,155,.16), transparent 46%),
        linear-gradient(150deg, {CARD_HI} 0%, {CARD} 60%);
    overflow: hidden;
}}
.hero-top {{ display:flex; align-items:center; justify-content:space-between; gap:12px; }}
.hero-label {{ color:{MUTED}; font-size:.82rem; font-weight:600; text-transform:uppercase; letter-spacing:.08em; }}
.hero-chip {{ font-size:.8rem; font-weight:700; padding:5px 12px; border-radius:999px; white-space:nowrap; font-variant-numeric:tabular-nums; }}
.hero-chip.pos {{ color:{VERDE}; background:rgba(47,227,155,.12); }}
.hero-chip.neg {{ color:{ROJO}; background:rgba(255,93,106,.12); }}
.hero-value {{ color:{TEXT}; font-size:clamp(2.1rem,5vw,3.1rem); font-weight:800; letter-spacing:-.04em; line-height:1.05; margin:14px 0 6px; font-variant-numeric:tabular-nums; }}
.hero-sub {{ color:{MUTED}; font-size:.86rem; }}

/* ---- Rejilla de estadísticas ---- */
.stat-grid {{ display:grid; grid-template-columns:repeat(auto-fit,minmax(150px,1fr)); gap:12px; margin-bottom:8px; }}
.stat {{ border:1px solid {BORDER}; border-radius:16px; padding:16px 18px; background:{CARD}; transition:border-color .15s ease; }}
.stat:hover {{ border-color:#333a48; }}
.stat-label {{ color:{MUTED}; font-size:.78rem; font-weight:600; margin-bottom:8px; }}
.stat-value {{ color:{TEXT}; font-size:1.4rem; font-weight:700; letter-spacing:-.03em; font-variant-numeric:tabular-nums; }}
.stat-value.pos {{ color:{VERDE}; }}
.stat-value.neg {{ color:{ROJO}; }}

/* ---- Tarjetas de estadística con minigráfico ---- */
.scards {{ display:grid; grid-template-columns:repeat(auto-fit,minmax(190px,1fr)); gap:14px; margin-bottom:18px; }}
.scard {{ border:1px solid {BORDER}; border-radius:18px; padding:17px 18px 14px; background:{CARD}; display:flex; flex-direction:column; gap:11px; transition:border-color .15s ease; }}
.scard:hover {{ border-color:#333a48; }}
.scard-top {{ display:flex; align-items:center; gap:10px; }}
.scard-ic {{ width:34px; height:34px; border-radius:11px; display:flex; align-items:center; justify-content:center; font-size:15px; flex-shrink:0; }}
.scard-label {{ color:{MUTED}; font-size:.82rem; font-weight:600; }}
.scard-val {{ color:{TEXT}; font-size:1.65rem; font-weight:750; letter-spacing:-.035em; font-variant-numeric:tabular-nums; line-height:1; }}
.scard .spark {{ width:100%; height:34px; display:block; margin-top:2px; }}

/* ---- Métricas nativas de Streamlit ---- */
[data-testid="stMetric"] {{ background:{CARD}; border:1px solid {BORDER}; border-radius:16px; padding:16px 18px; }}
[data-testid="stMetricLabel"] {{ color:{MUTED} !important; font-size:.8rem; font-weight:600; }}
[data-testid="stMetricValue"] {{ color:{TEXT}; font-size:clamp(1.2rem,1.7vw,1.7rem); font-weight:750; letter-spacing:-.03em; }}

/* ---- Tarjetas / contenedores con borde ---- */
[data-testid="stVerticalBlockBorderWrapper"] {{ border-radius:18px !important; border-color:{BORDER} !important; background:{CARD}; }}

/* ---- Pestañas ---- */
button[data-baseweb="tab"] {{ font-weight:600; padding:.65rem .2rem; color:{MUTED}; }}
button[data-baseweb="tab"][aria-selected="true"] {{ color:{TEXT}; }}
[data-baseweb="tab-highlight"] {{ background-color:{VERDE}; height:3px; border-radius:3px; }}
[data-baseweb="tab-border"] {{ background-color:{BORDER}; }}

/* ---- Entradas de texto ---- */
[data-testid="stTextInput"] input, [data-testid="stNumberInput"] input,
[data-baseweb="select"] > div, [data-testid="stDateInput"] input, textarea {{
    border-radius:12px !important; background:{CARD} !important; border:1px solid {BORDER} !important; color:{TEXT} !important;
}}
[data-testid="stTextInput"] input:focus, [data-testid="stNumberInput"] input:focus {{ border-color:{VERDE} !important; }}

/* ---- Botones ---- */
[data-testid="stButton"] button, [data-testid="stFormSubmitButton"] button {{
    border-radius:12px; font-weight:650; border:1px solid {BORDER};
}}
[data-testid="stButton"] button:hover, [data-testid="stFormSubmitButton"] button:hover {{ border-color:{VERDE}; color:{VERDE}; }}
[data-testid="stFormSubmitButton"] button {{ background:{VERDE}; color:#05251a; border:none; }}
[data-testid="stFormSubmitButton"] button:hover {{ background:#45eaab; color:#05251a; }}
div[data-testid="stButton"] button p {{ text-align:left; }}
div[data-testid="stButton"] button > div {{ justify-content:flex-start !important; }}

/* ---- Tablas / expanders / formularios / progreso ---- */
[data-testid="stDataFrame"], [data-testid="stTable"] {{ border:1px solid {BORDER}; border-radius:14px; overflow:hidden; }}
[data-testid="stExpander"] {{ border:1px solid {BORDER}; border-radius:14px; background:{CARD}; }}
[data-testid="stForm"] {{ border:1px solid {BORDER}; border-radius:18px; padding:1.1rem 1.2rem; background:{CARD}; }}
[data-testid="stProgress"] div[role="progressbar"] > div {{ background:{VERDE} !important; }}
[data-testid="stFileUploader"] section {{ border-radius:14px; border:1px dashed {BORDER}; background:{CARD}; }}

/* ---- Listas de filas (movimientos, cuentas) ---- */
.fin-row {{ display:flex; align-items:center; justify-content:space-between; gap:16px; padding:14px 4px; border-bottom:1px solid {BORDER}; }}
.fin-row:last-child {{ border-bottom:none; }}
.fin-row .left {{ display:flex; align-items:center; gap:13px; min-width:0; }}
.fin-icon {{ flex-shrink:0; width:42px; height:42px; border-radius:13px; background:{CARD_HI}; border:1px solid {BORDER}; display:flex; align-items:center; justify-content:center; font-size:18px; overflow:hidden; }}
.fin-nombre {{ font-weight:650; color:{TEXT}; }}
.fin-sub {{ font-size:.78rem; color:{MUTED}; margin-top:3px; }}
.fin-importe {{ font-weight:750; white-space:nowrap; font-variant-numeric:tabular-nums; font-size:1.02rem; }}
.fin-pos {{ color:{VERDE}; }}
.fin-neg {{ color:{TEXT}; }}

/* ---- Scrollbar ---- */
::-webkit-scrollbar {{ width:10px; height:10px; }}
::-webkit-scrollbar-thumb {{ background:{BORDER}; border-radius:10px; }}
::-webkit-scrollbar-thumb:hover {{ background:#333a48; }}
::-webkit-scrollbar-track {{ background:transparent; }}

@media (max-width: 768px) {{
    .block-container {{ padding:1.2rem .8rem 2rem !important; }}
    .hero {{ padding:20px 20px 18px; border-radius:18px; }}
    .stat-value {{ font-size:1.25rem; }}
    .fin-sub {{ font-size:.72rem; }}
}}
</style>
"""


def inyectar() -> None:
    st.markdown(CSS, unsafe_allow_html=True)


def marca_sidebar(logo_path: str, titulo: str = "Mi Finanzas") -> str:
    p = Path(logo_path)
    img = ""
    if p.exists():
        datos = base64.b64encode(p.read_bytes()).decode()
        img = f'<img src="data:image/webp;base64,{datos}" class="brand-logo">'
    return f'<div class="brand">{img}<span class="brand-name">{titulo}</span></div>'


def _sparkline(serie, color: str, idx: int = 0, w: int = 150, h: int = 36) -> str:
    vals = [float(v) for v in (serie or []) if v is not None]
    if len(vals) < 2:
        vals = [0.0, 0.0]
    lo, hi = min(vals), max(vals)
    rng = (hi - lo) or 1.0
    n = len(vals)
    pad = 4
    pts = []
    for i, v in enumerate(vals):
        x = i / (n - 1) * w
        y = (h - pad) - (v - lo) / rng * (h - 2 * pad)
        pts.append((x, y))
    linea = " ".join(f"{x:.1f},{y:.1f}" for x, y in pts)
    area = f"0,{h} " + linea + f" {w},{h}"
    gid = f"sp{idx}_{color.lstrip('#')}"
    return (
        f'<svg viewBox="0 0 {w} {h}" preserveAspectRatio="none" class="spark">'
        f'<defs><linearGradient id="{gid}" x1="0" y1="0" x2="0" y2="1">'
        f'<stop offset="0" stop-color="{color}" stop-opacity="0.28"/>'
        f'<stop offset="1" stop-color="{color}" stop-opacity="0"/></linearGradient></defs>'
        f'<polygon points="{area}" fill="url(#{gid})"/>'
        f'<polyline points="{linea}" fill="none" stroke="{color}" stroke-width="2" '
        f'stroke-linecap="round" stroke-linejoin="round" vector-effect="non-scaling-stroke"/></svg>'
    )


def tarjeta_stat(icono: str, label: str, valor: str, serie, color: str, idx: int = 0) -> str:
    return (
        f'<div class="scard">'
        f'<div class="scard-top">'
        f'<span class="scard-ic" style="background:{color}1f;color:{color};">{icono}</span>'
        f'<span class="scard-label">{label}</span></div>'
        f'<div class="scard-val">{valor}</div>'
        f'{_sparkline(serie, color, idx)}</div>'
    )


def tarjetas_stats(cards: list[dict]) -> str:
    cuerpo = "".join(
        tarjeta_stat(c["icono"], c["label"], c["valor"], c.get("serie"), c["color"], i)
        for i, c in enumerate(cards)
    )
    return f'<div class="scards">{cuerpo}</div>'


def aplicar_tema_plotly(fig):
    fig.update_layout(
        paper_bgcolor="rgba(0,0,0,0)",
        plot_bgcolor="rgba(0,0,0,0)",
        font_color=MUTED,
        font_family="Inter, sans-serif",
        colorway=PALETA_CATEGORIAS,
        legend_title_text="",
        margin=dict(l=10, r=10, t=10, b=10),
    )
    fig.update_xaxes(gridcolor=BORDER, zerolinecolor=BORDER)
    fig.update_yaxes(gridcolor=BORDER, zerolinecolor=BORDER)
    return fig


def _icono_html(icono_o_logo: str | None) -> str:
    """Si `icono_o_logo` es la ruta a un logo existente, lo incrusta como imagen;
    si no, lo trata como un emoji/texto corto."""
    if icono_o_logo and isinstance(icono_o_logo, str) and Path(icono_o_logo).exists():
        datos = base64.b64encode(Path(icono_o_logo).read_bytes()).decode()
        return f'<img src="data:image/png;base64,{datos}" style="width:100%;height:100%;object-fit:cover;border-radius:11px;">'
    return icono_o_logo or ""


def fila_movimiento(icono: str | None, nombre: str, sub: str, importe: float) -> str:
    clase = "fin-pos" if importe > 0 else "fin-neg"
    signo = "+" if importe > 0 else ""
    return f"""
    <div class="fin-row">
        <div class="left">
            <div class="fin-icon">{_icono_html(icono)}</div>
            <div>
                <div class="fin-nombre">{nombre}</div>
                <div class="fin-sub">{sub}</div>
            </div>
        </div>
        <div class="fin-importe {clase}">{signo}{importe:,.2f} €</div>
    </div>
    """


def fila_cuenta(logo: str | None, nombre: str, ingresos: float, gastos: float, balance: float) -> str:
    clase = "fin-pos" if balance >= 0 else "fin-neg"
    return f"""
    <div class="fin-row">
        <div class="left">
            <div class="fin-icon">{_icono_html(logo) or '🏦'}</div>
            <div>
                <div class="fin-nombre">{nombre}</div>
                <div class="fin-sub">Ingresos {ingresos:,.2f} € · Gastos {gastos:,.2f} €</div>
            </div>
        </div>
        <div class="fin-importe {clase}">{balance:,.2f} €</div>
    </div>
    """
