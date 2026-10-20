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
.block-container {{ padding-top: 2rem !important; padding-bottom: 3rem; max-width: 100% !important; padding-left: 2.2rem !important; padding-right: 2.2rem !important; }}

h1, h2, h3 {{ letter-spacing: -.02em; font-weight: 700; color: {TEXT}; }}
h1 {{ font-weight: 800; }}

/* ---- Barra lateral ---- */
[data-testid="stSidebar"] {{ background: {BG_SOFT}; border-right: 1px solid {BORDER}; }}
[data-testid="stSidebar"] > div:first-child {{ padding-top: 1.4rem; }}
.login-head {{ display:flex; flex-direction:column; align-items:center; text-align:center; gap:7px; margin:5vh 0 1.8rem; }}
.login-logo {{ width:86px; height:86px; border-radius:24px; object-fit:cover; box-shadow:0 10px 30px rgba(47,227,155,.18); }}
.login-title {{ font-weight:800; font-size:1.7rem; color:{TEXT}; letter-spacing:-.02em; }}
.login-tag {{ color:{MUTED}; font-size:.95rem; }}
.profile {{ display:flex; align-items:center; gap:11px; padding:12px 6px 8px; margin-top:18px; border-top:1px solid {BORDER}; }}
.profile-av {{ width:38px; height:38px; border-radius:50%; background:{VERDE}; color:#05251a; font-weight:800; display:flex; align-items:center; justify-content:center; flex-shrink:0; }}
.profile-name {{ font-weight:700; color:{TEXT}; font-size:.92rem; line-height:1.15; }}
.profile-role {{ color:{MUTED}; font-size:.75rem; overflow:hidden; text-overflow:ellipsis; max-width:150px; white-space:nowrap; }}
.brand {{ display:flex; flex-direction:column; align-items:center; text-align:center; gap:11px; padding:4px 4px 18px; }}
.brand-logo {{ width:84px; height:84px; border-radius:22px; object-fit:cover; box-shadow:0 8px 22px rgba(0,0,0,.5); }}
.brand-logo-svg svg {{ width:150px; max-width:80%; height:auto; display:block; }}
.brand-welcome {{ font-weight:700; font-size:1.05rem; color:{TEXT}; letter-spacing:-.01em; }}

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
/* Botones dentro de una tarjeta: planos, sin doble borde. */
[data-testid="stVerticalBlockBorderWrapper"] [data-testid="stButton"] button {{
    border:none !important; background:transparent !important; color:{TEXT} !important;
    font-weight:650; border-radius:12px;
}}
[data-testid="stVerticalBlockBorderWrapper"] [data-testid="stButton"] button:hover {{
    background:{CARD_HI} !important; color:{VERDE} !important;
}}
[data-testid="stVerticalBlockBorderWrapper"] [data-testid="stButton"] button p {{ font-size:1.02rem; font-weight:650; }}
/* Chip de icono para las tarjetas plegables */
.card-ic {{ width:40px; height:40px; border-radius:12px; background:{CARD_HI}; border:1px solid {BORDER};
    display:flex; align-items:center; justify-content:center; font-size:16px; font-weight:800; color:{VERDE}; }}

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


def perfil_sidebar(nombre: str, email: str, es_admin: bool) -> str:
    inicial = (nombre or email or "?").strip()[:1].upper()
    rol = "Superadmin" if es_admin else email
    return (
        f'<div class="profile"><div class="profile-av">{inicial}</div>'
        f'<div class="profile-info"><div class="profile-name">{nombre}</div>'
        f'<div class="profile-role">{rol}</div></div></div>'
    )


# CSS del login en crudo (NO es f-string): aquí se puede escribir CSS normal con
# llaves simples sin romper nada. Solo se inyecta en la pantalla de login, así
# que estos estilos no afectan a formularios de otras páginas.
CSS_LOGIN = """
<style>
[data-testid="stAppViewContainer"] .block-container { max-width: 1040px !important; padding-top: 4vh !important; }
.login-panel {
    position: relative; overflow: hidden; height: 100%;
    border: 1px solid #222a33; border-radius: 24px; padding: 40px 34px;
    background:
        radial-gradient(120% 90% at 20% 0%, rgba(47,227,155,.18), transparent 55%),
        linear-gradient(160deg, #0f1620 0%, #0a0d13 70%);
    display: flex; flex-direction: column; justify-content: center; min-height: 460px;
}
.login-panel .lp-logo svg { width: 240px; max-width: 70%; height: auto; display: block; margin-bottom: 12px; }
.login-panel .lp-tag { color: #9aa3b2; font-size: 1rem; margin-top: 2px; line-height: 1.45; }
.login-phone {
    margin-top: 30px; align-self: flex-start; transform: rotate(-4deg);
    background: linear-gradient(150deg, #181d26, #10141b); border: 1px solid #262e39;
    border-radius: 18px; padding: 16px 18px; width: 210px;
    box-shadow: 0 24px 60px rgba(0,0,0,.5);
}
.login-phone .lp-lbl { color: #9aa3b2; font-size: .78rem; }
.login-phone .lp-val { color: #fff; font-size: 1.5rem; font-weight: 800; letter-spacing: -.03em; margin: 2px 0 8px; }
.login-phone .lp-chip { display: inline-block; color: #2fe39b; background: rgba(47,227,155,.14); font-size: .72rem; font-weight: 700; padding: 3px 8px; border-radius: 999px; }
.login-phone svg { display: block; margin-top: 10px; width: 100%; height: 40px; }

.lg-head h2 { font-weight: 800; font-size: 1.9rem; color: #eef1f5; letter-spacing: -.02em; margin: 0 0 4px; }
.lg-head p { color: #8a92a4; margin: 0 0 14px; }

/* Formulario = tarjeta derecha */
[data-testid="stForm"] {
    border: 1px solid #222a33 !important; border-radius: 22px !important;
    background: linear-gradient(150deg, #141922, #0e121a) !important; padding: 1.4rem 1.4rem 1.2rem !important;
}
[data-testid="stForm"] label { font-size: .86rem !important; font-weight: 600 !important; color: #cbd3de !important; }
[data-testid="stForm"] input {
    min-height: 50px !important; border: 1px solid #262f3a !important;
    border-radius: 13px !important; color: #eef1f5 !important; padding-left: 42px !important;
    background-color: #0b0f15 !important; background-repeat: no-repeat !important; background-position: 13px center !important;
    background-size: 18px 18px !important;
}
[data-testid="stForm"] input:focus { border-color: #2fe39b !important; box-shadow: 0 0 0 3px rgba(47,227,155,.12) !important; }
[data-testid="stForm"] input[type="text"] {
    background-image: url("data:image/svg+xml,%3Csvg xmlns='http://www.w3.org/2000/svg' width='18' height='18' fill='none' stroke='%238a92a4' stroke-width='1.7'%3E%3Crect x='2.5' y='4' width='13' height='10' rx='2'/%3E%3Cpath d='m3 5 6 5 6-5'/%3E%3C/svg%3E") !important;
}
[data-testid="stForm"] input[type="password"] {
    background-image: url("data:image/svg+xml,%3Csvg xmlns='http://www.w3.org/2000/svg' width='18' height='18' fill='none' stroke='%238a92a4' stroke-width='1.7'%3E%3Crect x='3.5' y='8' width='11' height='7' rx='2'/%3E%3Cpath d='M6 8V6a3 3 0 0 1 6 0v2'/%3E%3C/svg%3E") !important;
}
[data-testid="stFormSubmitButton"] button {
    min-height: 52px; background: linear-gradient(110deg,#5bf0bd,#2fe39b 65%,#19cc8d) !important;
    color: #05251a !important; font-weight: 800 !important; border: 0 !important; border-radius: 13px !important;
    font-size: 1rem !important; transition: transform .15s ease, filter .15s ease;
}
[data-testid="stFormSubmitButton"] button:hover { filter: brightness(1.05); transform: translateY(-1px); }
[data-testid="stFormSubmitButton"] button p::after { content: "  →"; font-weight: 700; }

.lg-forgot { text-align: right; color: #2fe39b; font-size: .86rem; font-weight: 600; padding-top: 6px; cursor: pointer; }
.lg-divider { display: flex; align-items: center; gap: 12px; color: #6b7382; margin: 14px 2px; }
.lg-divider::before, .lg-divider::after { content: ""; flex: 1; height: 1px; background: #242b35; }

@media (max-width: 760px) {
    .login-panel { min-height: auto; padding: 26px 22px; }
    .login-phone { display: none; }
}
</style>
"""


def login_panel_izq(logo_svg: str = "assets/logo-login.svg") -> str:
    p = Path(logo_svg)
    svg = p.read_text(encoding="utf-8") if p.exists() else ""
    img = f'<div class="lp-logo">{svg}</div>'
    onda = (
        '<svg viewBox="0 0 200 40" preserveAspectRatio="none">'
        '<polyline points="0,32 20,28 40,30 60,20 80,24 100,14 120,18 140,10 160,14 180,6 200,9" '
        'fill="none" stroke="#2fe39b" stroke-width="2.5" stroke-linecap="round" stroke-linejoin="round"/></svg>'
    )
    return (
        f'<div class="login-panel">{img}'
        f'<div class="lp-tag">Controla tu dinero,<br>construye tu futuro.</div>'
        f'<div class="login-phone"><div class="lp-lbl">Patrimonio neto</div>'
        f'<div class="lp-val">12.840 €</div><span class="lp-chip">↗ +2,4%</span>{onda}</div></div>'
    )


def login_header(logo_path: str) -> str:
    """Cabecera de login con el logo vectorial transparente, sin bloque de fondo."""
    candidatos = [
        Path(__file__).resolve().parent.parent / "assets" / "logo-login.svg",
        Path(logo_path),
    ]
    img = ""
    for p in candidatos:
        if p.exists():
            datos = base64.b64encode(p.read_bytes()).decode()
            mime = "image/svg+xml" if p.suffix.lower() == ".svg" else "image/webp"
            img = f'<img src="data:{mime};base64,{datos}" class="login-logo" alt="Álvaro Finanzas">'
            break
    return (
        f'<div class="login-head">{img}'
        f'<div class="login-title">Álvaro Finanzas</div>'
        f'<div class="login-tag">Tu dinero. Tus decisiones. Tu futuro.</div></div>'
    )


def marca_sidebar(logo_path: str = "assets/logo-login.svg", nombre: str = "") -> str:
    p = Path(logo_path)
    img = ""
    if p.exists():
        if p.suffix == ".svg":
            img = f'<div class="brand-logo-svg">{p.read_text(encoding="utf-8")}</div>'
        else:
            datos = base64.b64encode(p.read_bytes()).decode()
            img = f'<img src="data:image/webp;base64,{datos}" class="brand-logo">'
    bienvenida = f'<div class="brand-welcome">Bienvenido, {nombre}</div>' if nombre else ""
    return f'<div class="brand">{img}{bienvenida}</div>'


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
    """Si `icono_o_logo` ya es un data URI de imagen, o la ruta a un logo
    existente (formato antiguo, antes de guardarlos en la base de datos), lo
    incrusta como imagen; si no, lo trata como un emoji/texto corto."""
    if not icono_o_logo or not isinstance(icono_o_logo, str):
        return icono_o_logo or ""
    estilo_img = 'style="width:100%;height:100%;object-fit:cover;border-radius:11px;"'
    if icono_o_logo.startswith("data:image"):
        return f'<img src="{icono_o_logo}" {estilo_img}>'
    try:
        existe = Path(icono_o_logo).exists()
    except OSError:
        existe = False
    if existe:
        datos = base64.b64encode(Path(icono_o_logo).read_bytes()).decode()
        return f'<img src="data:image/png;base64,{datos}" {estilo_img}>'
    return ""


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
