import base64
from pathlib import Path

import streamlit as st

# ----------------------------------------------------------------- Paleta ----
# "Institutional Wealth UI" (sistema de diseño generado en Stitch): banca
# privada/wealth management, fondo claro, acento cobalto, verde esmeralda solo
# para ganancias/cifras positivas, rosa para pérdidas.

BG = "#f8fafc"            # canvas
BG_SOFT = "#ffffff"        # barra lateral
CARD = "#ffffff"           # superficie de tarjeta
CARD_HI = "#f1f5f9"        # hover / elevado
BORDER = "#e2e8f0"         # línea fina
TEXT = "#0f172a"           # slate-900 (titulares, texto principal)
MUTED = "#64748b"          # slate-500 (etiquetas, metadatos)
ACCENT = "#2563eb"         # cobalto (secundario): acciones, enlaces, foco
VERDE = "#10b981"          # esmeralda (terciario): ganancias/positivo
ROJO = "#ef4444"           # rosa: pérdidas/negativo
NARANJA = "#f59e0b"        # ámbar: acento categorías
AZUL = ACCENT
MORADO = "#7c3aed"         # violeta: acento categorías
INFO = "#06b6d4"           # cian: informativo

VERDE_BG, VERDE_TXT = "#ecfdf5", "#059669"
ROJO_BG, ROJO_TXT = "#fff1f2", "#e11d48"

PALETA_CATEGORIAS = [VERDE, ACCENT, MORADO, NARANJA, ROJO, "#2dd4bf", "#f472b6", "#facc15"]

CSS = f"""
<style>
@import url('https://fonts.googleapis.com/css2?family=Inter:wght@400;500;600;700;800&family=Plus+Jakarta+Sans:wght@500;600;700;800&display=swap');

html, body, [data-testid="stAppViewContainer"], [data-testid="stSidebar"],
input, textarea, select, button, label,
[data-testid="stMarkdownContainer"] {{
    font-family: 'Inter', -apple-system, BlinkMacSystemFont, 'Segoe UI', sans-serif;
}}
h1, h2, h3, h4, h5, h6 {{ font-family: 'Plus Jakarta Sans', 'Inter', sans-serif; }}
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
.login-logo {{ width:86px; height:86px; border-radius:16px; object-fit:cover; box-shadow:0 10px 30px rgba(37,99,235,.16); }}
.login-title {{ font-family:'Plus Jakarta Sans',sans-serif; font-weight:800; font-size:1.7rem; color:{TEXT}; letter-spacing:-.02em; }}
.login-tag {{ color:{MUTED}; font-size:.95rem; }}
.profile {{ display:flex; align-items:center; gap:11px; padding:12px 6px 8px; margin-top:18px; border-top:1px solid {BORDER}; }}
.profile-av {{ width:38px; height:38px; border-radius:50%; background:{ACCENT}; color:#ffffff; font-weight:800; display:flex; align-items:center; justify-content:center; flex-shrink:0; }}
.profile-name {{ font-weight:700; color:{TEXT}; font-size:.92rem; line-height:1.15; }}
.profile-role {{ color:{MUTED}; font-size:.75rem; overflow:hidden; text-overflow:ellipsis; max-width:150px; white-space:nowrap; }}
.brand {{ display:flex; flex-direction:column; align-items:center; text-align:center; gap:11px; padding:4px 4px 18px; }}
.brand-logo {{ width:84px; height:84px; border-radius:16px; object-fit:cover; box-shadow:0 8px 22px rgba(15,23,42,.12); }}
.brand-logo-svg svg {{ width:150px; max-width:80%; height:auto; display:block; }}
.brand-welcome {{ font-family:'Plus Jakarta Sans',sans-serif; font-weight:700; font-size:1.05rem; color:{TEXT}; letter-spacing:-.01em; }}

/* ---- Hero de patrimonio ---- */
.hero {{
    position: relative;
    border: 1px solid {BORDER};
    border-radius: 16px;
    padding: 26px 28px 24px;
    margin-bottom: 16px;
    background:
        radial-gradient(130% 150% at 0% 0%, rgba(37,99,235,.08), transparent 46%),
        linear-gradient(150deg, #ffffff 0%, {CARD_HI} 120%);
    overflow: hidden;
}}
.hero-top {{ display:flex; align-items:center; justify-content:space-between; gap:12px; }}
.hero-label {{ color:{MUTED}; font-size:.82rem; font-weight:600; text-transform:uppercase; letter-spacing:.08em; }}
.hero-chip {{ font-size:.8rem; font-weight:700; padding:5px 12px; border-radius:999px; white-space:nowrap; font-variant-numeric:tabular-nums; }}
.hero-chip.pos {{ color:{VERDE_TXT}; background:{VERDE_BG}; }}
.hero-chip.neg {{ color:{ROJO_TXT}; background:{ROJO_BG}; }}
.hero-value {{ font-family:'Plus Jakarta Sans',sans-serif; color:{TEXT}; font-size:clamp(2.1rem,5vw,3.1rem); font-weight:800; letter-spacing:-.04em; line-height:1.05; margin:14px 0 6px; font-variant-numeric:tabular-nums; }}
.hero-sub {{ color:{MUTED}; font-size:.86rem; }}

/* ---- Rejilla de estadísticas ---- */
.stat-grid {{ display:grid; grid-template-columns:repeat(auto-fit,minmax(150px,1fr)); gap:12px; margin-bottom:8px; }}
.stat {{ border:1px solid {BORDER}; border-radius:16px; padding:16px 18px; background:{CARD}; transition:border-color .15s ease; }}
.stat:hover {{ border-color:#cbd5e1; }}
.stat-label {{ color:{MUTED}; font-size:.78rem; font-weight:600; margin-bottom:8px; }}
.stat-value {{ font-family:'Plus Jakarta Sans',sans-serif; color:{TEXT}; font-size:1.4rem; font-weight:700; letter-spacing:-.03em; font-variant-numeric:tabular-nums; }}
.stat-value.pos {{ color:{VERDE_TXT}; }}
.stat-value.neg {{ color:{ROJO_TXT}; }}

/* ---- Tarjetas de estadística con minigráfico ---- */
.scards {{ display:grid; grid-template-columns:repeat(auto-fit,minmax(190px,1fr)); gap:14px; margin-bottom:18px; }}
.scard {{ border:1px solid {BORDER}; border-radius:16px; padding:17px 18px 14px; background:{CARD}; display:flex; flex-direction:column; gap:11px; transition:border-color .15s ease, box-shadow .15s ease; box-shadow:0 1px 2px rgba(15,23,42,.03); }}
.scard:hover {{ border-color:#cbd5e1; box-shadow:0 4px 12px rgba(15,23,42,.06); }}
.scard-top {{ display:flex; align-items:center; gap:10px; }}
.scard-ic {{ width:34px; height:34px; border-radius:10px; display:flex; align-items:center; justify-content:center; font-size:15px; flex-shrink:0; }}
.scard-label {{ color:{MUTED}; font-size:.82rem; font-weight:600; }}
.scard-val {{ font-family:'Plus Jakarta Sans',sans-serif; color:{TEXT}; font-size:1.65rem; font-weight:750; letter-spacing:-.035em; font-variant-numeric:tabular-nums; line-height:1; }}
.scard .spark {{ width:100%; height:34px; display:block; margin-top:2px; }}

/* ---- Métricas nativas de Streamlit ---- */
[data-testid="stMetric"] {{ background:{CARD}; border:1px solid {BORDER}; border-radius:16px; padding:16px 18px; box-shadow:0 1px 2px rgba(15,23,42,.03); }}
[data-testid="stMetricLabel"] {{ color:{MUTED} !important; font-size:.8rem; font-weight:600; }}
[data-testid="stMetricValue"] {{ font-family:'Plus Jakarta Sans',sans-serif; color:{TEXT}; font-size:clamp(1.2rem,1.7vw,1.7rem); font-weight:750; letter-spacing:-.03em; }}

/* ---- Tarjetas / contenedores con borde ---- */
[data-testid="stVerticalBlockBorderWrapper"] {{ border-radius:16px !important; border-color:{BORDER} !important; background:{CARD}; }}
/* Botones dentro de una tarjeta: planos, sin doble borde. */
[data-testid="stVerticalBlockBorderWrapper"] [data-testid="stButton"] button {{
    border:none !important; background:transparent !important; color:{TEXT} !important;
    font-weight:650; border-radius:8px;
}}
[data-testid="stVerticalBlockBorderWrapper"] [data-testid="stButton"] button:hover {{
    background:{CARD_HI} !important; color:{ACCENT} !important;
}}
[data-testid="stVerticalBlockBorderWrapper"] [data-testid="stButton"] button p {{ font-size:1.02rem; font-weight:650; }}
/* Chip de icono para las tarjetas plegables */
.card-ic {{ width:40px; height:40px; border-radius:10px; background:{CARD_HI}; border:1px solid {BORDER};
    display:flex; align-items:center; justify-content:center; font-size:16px; font-weight:800; color:{ACCENT}; }}

/* ---- Pestañas ---- */
button[data-baseweb="tab"] {{ font-weight:600; padding:.65rem .2rem; color:{MUTED}; }}
button[data-baseweb="tab"][aria-selected="true"] {{ color:{TEXT}; }}
[data-baseweb="tab-highlight"] {{ background-color:{ACCENT}; height:3px; border-radius:3px; }}
[data-baseweb="tab-border"] {{ background-color:{BORDER}; }}

/* ---- Entradas de texto ---- */
[data-testid="stTextInput"] input, [data-testid="stNumberInput"] input,
[data-baseweb="select"] > div, [data-testid="stDateInput"] input, textarea {{
    border-radius:8px !important; background:{CARD} !important; border:1px solid {BORDER} !important; color:{TEXT} !important;
}}
[data-testid="stTextInput"] input:focus, [data-testid="stNumberInput"] input:focus {{ border-color:{ACCENT} !important; box-shadow:0 0 0 3px rgba(37,99,235,.12) !important; }}

/* ---- Botones ---- */
[data-testid="stButton"] button, [data-testid="stFormSubmitButton"] button {{
    border-radius:8px; font-weight:650; border:1px solid {BORDER};
}}
[data-testid="stButton"] button:hover, [data-testid="stFormSubmitButton"] button:hover {{ border-color:{ACCENT}; color:{ACCENT}; }}
[data-testid="stFormSubmitButton"] button {{ background:{ACCENT}; color:#ffffff; border:none; }}
[data-testid="stFormSubmitButton"] button:hover {{ background:#1d4ed8; color:#ffffff; }}
div[data-testid="stButton"] button p {{ text-align:left; }}
div[data-testid="stButton"] button > div {{ justify-content:flex-start !important; }}

/* ---- Tablas / expanders / formularios / progreso ---- */
[data-testid="stDataFrame"], [data-testid="stTable"] {{ border:1px solid {BORDER}; border-radius:14px; overflow:hidden; }}
[data-testid="stExpander"] {{ border:1px solid {BORDER}; border-radius:14px; background:{CARD}; }}
[data-testid="stForm"] {{ border:1px solid {BORDER}; border-radius:16px; padding:1.1rem 1.2rem; background:{CARD}; }}
[data-testid="stProgress"] div[role="progressbar"] > div {{ background:{VERDE} !important; }}
[data-testid="stFileUploader"] section {{ border-radius:14px; border:1px dashed {BORDER}; background:{CARD}; }}

/* ---- Dashboard: cabecera de saludo ---- */
.dash-greet {{ font-family:'Plus Jakarta Sans',sans-serif; font-size:clamp(1.3rem,2.4vw,1.7rem); font-weight:800; color:{TEXT}; letter-spacing:-.02em; margin-bottom:4px; }}
.dash-greet .pos {{ color:{VERDE_TXT}; }}
.dash-greet .neg {{ color:{ROJO_TXT}; }}
.dash-sub {{ color:{MUTED}; font-size:.9rem; margin-bottom:18px; }}

/* ---- KPI "pro" (dashboard principal) ---- */
.kpi-row {{ display:grid; grid-template-columns:repeat(auto-fit,minmax(220px,1fr)); gap:14px; margin-bottom:20px; }}
.kpi-pro {{ border:1px solid {BORDER}; border-radius:16px; padding:18px 20px; background:{CARD}; box-shadow:0 1px 2px rgba(15,23,42,.03); }}
.kpi-pro-top {{ display:flex; align-items:center; justify-content:space-between; margin-bottom:12px; }}
.kpi-pro-label {{ color:{MUTED}; font-size:.72rem; font-weight:700; letter-spacing:.06em; text-transform:uppercase; }}
.kpi-pro-ic {{ width:30px; height:30px; border-radius:9px; background:{CARD_HI}; display:flex; align-items:center; justify-content:center; font-size:14px; flex-shrink:0; }}
.kpi-pro-val {{ font-family:'Plus Jakarta Sans',sans-serif; font-size:1.6rem; font-weight:800; color:{TEXT}; letter-spacing:-.03em; margin-bottom:8px; font-variant-numeric:tabular-nums; }}
.kpi-pro-chip {{ font-size:.78rem; font-weight:600; color:{MUTED}; }}
.kpi-pro-chip.pos {{ color:{VERDE_TXT}; }}
.kpi-pro-chip.neg {{ color:{ROJO_TXT}; }}
.kpi-pro-bar {{ height:6px; border-radius:999px; background:{CARD_HI}; margin-top:12px; overflow:hidden; }}
.kpi-pro-bar > div {{ height:100%; background:{ACCENT}; border-radius:999px; }}

/* ---- Leyenda de donut / distribución ---- */
.leg-row {{ display:flex; align-items:center; justify-content:space-between; padding:9px 0; border-bottom:1px solid {BORDER}; font-size:.85rem; }}
.leg-row:last-child {{ border-bottom:none; }}
.leg-left {{ display:flex; align-items:center; gap:9px; color:{TEXT}; font-weight:600; min-width:0; }}
.leg-dot {{ width:10px; height:10px; border-radius:50%; flex-shrink:0; }}
.leg-val {{ color:{MUTED}; font-variant-numeric:tabular-nums; white-space:nowrap; padding-left:10px; }}

/* ---- Tarjetas de aviso (salud / próximo hito) ---- */
.info-card {{ border:1px solid {BORDER}; border-radius:16px; padding:16px 18px; background:{CARD}; margin-bottom:12px; }}
.info-card .tag {{ font-size:.7rem; font-weight:800; letter-spacing:.06em; text-transform:uppercase; }}
.info-card.ok .tag {{ color:{VERDE_TXT}; }}
.info-card.info .tag {{ color:{ACCENT}; }}
.info-card h4 {{ margin:7px 0 4px; font-size:.96rem; color:{TEXT}; font-weight:700; }}
.info-card p {{ margin:0; font-size:.82rem; color:{MUTED}; line-height:1.5; }}

/* ---- Pie de estadísticas bajo un gráfico ---- */
.stat-foot {{ display:flex; gap:24px; margin-top:10px; flex-wrap:wrap; }}
.stat-foot .item {{ display:flex; flex-direction:column; gap:3px; }}
.stat-foot .lbl {{ color:{MUTED}; font-size:.74rem; }}
.stat-foot .val {{ color:{TEXT}; font-weight:700; font-size:.95rem; font-variant-numeric:tabular-nums; }}

/* ---- Ejecución presupuestaria por categoría ---- */
.pres-row {{ padding:14px 0; border-bottom:1px solid {BORDER}; }}
.pres-row:last-child {{ border-bottom:none; }}
.pres-top {{ display:flex; align-items:center; justify-content:space-between; margin-bottom:8px; gap:10px; }}
.pres-cat {{ display:flex; align-items:center; gap:9px; font-weight:650; color:{TEXT}; font-size:.9rem; min-width:0; }}
.pres-vals {{ font-size:.78rem; color:{MUTED}; font-variant-numeric:tabular-nums; margin-top:6px; }}
.pres-bar {{ height:8px; border-radius:999px; background:{CARD_HI}; overflow:hidden; }}
.pres-bar > div {{ height:100%; border-radius:999px; }}
.pres-pill {{ font-size:.7rem; font-weight:800; padding:3px 10px; border-radius:999px; white-space:nowrap; flex-shrink:0; }}
.pres-pill.ok {{ color:{VERDE_TXT}; background:{VERDE_BG}; }}
.pres-pill.warn {{ color:#b45309; background:#fffbeb; }}
.pres-pill.over {{ color:{ROJO_TXT}; background:{ROJO_BG}; }}

/* ---- Listas de filas (movimientos, cuentas) ---- */
.fin-row {{ display:flex; align-items:center; justify-content:space-between; gap:16px; padding:14px 4px; border-bottom:1px solid {BORDER}; }}
.fin-row:last-child {{ border-bottom:none; }}
.fin-row .left {{ display:flex; align-items:center; gap:13px; min-width:0; }}
.fin-icon {{ flex-shrink:0; width:42px; height:42px; border-radius:11px; background:{CARD_HI}; border:1px solid {BORDER}; display:flex; align-items:center; justify-content:center; font-size:18px; overflow:hidden; }}
.fin-nombre {{ font-weight:650; color:{TEXT}; }}
.fin-sub {{ font-size:.78rem; color:{MUTED}; margin-top:3px; }}
.fin-importe {{ font-weight:750; white-space:nowrap; font-variant-numeric:tabular-nums; font-size:1.02rem; }}
.fin-pos {{ color:{VERDE_TXT}; }}
.fin-neg {{ color:{TEXT}; }}

/* ---- Scrollbar ---- */
::-webkit-scrollbar {{ width:10px; height:10px; }}
::-webkit-scrollbar-thumb {{ background:{BORDER}; border-radius:10px; }}
::-webkit-scrollbar-thumb:hover {{ background:#cbd5e1; }}
::-webkit-scrollbar-track {{ background:transparent; }}

@media (max-width: 768px) {{
    .block-container {{ padding:1.2rem .8rem 2rem !important; }}
    .hero {{ padding:20px 20px 18px; border-radius:16px; }}
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
[data-testid="stAppViewContainer"] .block-container { max-width: 1120px !important; padding-top: 4vh !important; }

/* ---- Panel izquierdo: institucional, oscuro, con rejilla ---- */
.login-panel {
    position: relative; overflow: hidden; height: 100%;
    border: 1px solid #1e293b; border-radius: 16px; padding: 40px 36px;
    background-color: #0b1220;
    background-image:
        linear-gradient(rgba(255,255,255,.04) 1px, transparent 1px),
        linear-gradient(90deg, rgba(255,255,255,.04) 1px, transparent 1px);
    background-size: 28px 28px;
    display: flex; flex-direction: column; justify-content: center; gap: 22px; min-height: 620px;
}
.lp-brand { display: flex; align-items: center; gap: 12px; }
.lp-badge {
    width: 44px; height: 44px; border-radius: 12px; flex-shrink: 0;
    background: #111827; border: 1px solid rgba(255,255,255,.14);
    display: flex; align-items: center; justify-content: center;
}
.lp-badge svg { width: 24px; height: 24px; }
.lp-brand-name { color: #ffffff; font-weight: 800; font-size: 1.05rem; line-height: 1.1; }
.lp-brand-sub { color: #64748b; font-size: .68rem; font-weight: 700; letter-spacing: .1em; text-transform: uppercase; }
.lp-pill {
    display: inline-flex; align-items: center; gap: 7px; width: fit-content;
    background: rgba(255,255,255,.06); border: 1px solid rgba(255,255,255,.12);
    color: #cbd5e1; font-size: .78rem; font-weight: 600; padding: 6px 13px; border-radius: 999px;
}
.lp-pill .dot { color: #34d399; }
.lp-title { font-family: 'Plus Jakarta Sans', sans-serif; color: #ffffff; font-size: clamp(1.7rem,2.6vw,2.2rem); font-weight: 800; letter-spacing: -.02em; line-height: 1.15; margin: 0; }
.lp-desc { color: #94a3b8; font-size: .95rem; line-height: 1.55; max-width: 46ch; }
.lp-features { display: flex; flex-direction: column; gap: 16px; }
.lp-feature { display: flex; align-items: flex-start; gap: 13px; }
.lp-feature-ic {
    width: 34px; height: 34px; border-radius: 10px; flex-shrink: 0; margin-top: 1px;
    background: rgba(255,255,255,.06); border: 1px solid rgba(255,255,255,.1);
    display: flex; align-items: center; justify-content: center; font-size: 15px;
}
.lp-feature-title { color: #e2e8f0; font-weight: 700; font-size: .9rem; margin-bottom: 2px; }
.lp-feature-desc { color: #64748b; font-size: .8rem; line-height: 1.45; }
.lp-status {
    margin-top: auto; display: flex; align-items: center; justify-content: space-between;
    background: rgba(255,255,255,.04); border: 1px solid rgba(255,255,255,.1);
    border-radius: 12px; padding: 11px 16px; font-size: .78rem;
}
.lp-status .ok { color: #34d399; font-weight: 700; display: flex; align-items: center; gap: 7px; }
.lp-status .ok .dot-live { width: 7px; height: 7px; border-radius: 50%; background: #34d399; display: inline-block; box-shadow: 0 0 0 3px rgba(52,211,153,.2); }
.lp-status .latency { color: #34d399; font-weight: 700; }

/* ---- Cabecera del formulario derecho ---- */
.lg-top { display: flex; align-items: center; justify-content: space-between; margin-bottom: 2px; }
.lg-eyebrow { color: #2563eb; font-size: .76rem; font-weight: 800; letter-spacing: .1em; text-transform: uppercase; }
.lg-tls {
    display: inline-flex; align-items: center; gap: 6px;
    background: #eff6ff; color: #2563eb; font-size: .74rem; font-weight: 700;
    padding: 5px 11px; border-radius: 999px;
}
.lg-head h2 { font-family: 'Plus Jakarta Sans', sans-serif; font-weight: 800; font-size: 1.9rem; color: #0f172a; letter-spacing: -.02em; margin: 2px 0 14px; }

/* Formulario = tarjeta derecha */
[data-testid="stForm"] {
    border: 1px solid #e2e8f0 !important; border-radius: 16px !important;
    background: #ffffff !important; padding: 1.4rem 1.4rem 1.2rem !important;
    box-shadow: 0 1px 3px rgba(15,23,42,.05) !important;
}
[data-testid="stForm"] label { font-size: .86rem !important; font-weight: 600 !important; color: #475569 !important; }
[data-testid="stForm"] input {
    min-height: 50px !important; border: 1px solid #e2e8f0 !important;
    border-radius: 8px !important; color: #0f172a !important; padding-left: 42px !important;
    background-color: #f8fafc !important; background-repeat: no-repeat !important; background-position: 13px center !important;
    background-size: 18px 18px !important;
}
[data-testid="stForm"] input:focus { border-color: #2563eb !important; box-shadow: 0 0 0 3px rgba(37,99,235,.12) !important; }
[data-testid="stForm"] input[type="text"] {
    background-image: url("data:image/svg+xml,%3Csvg xmlns='http://www.w3.org/2000/svg' width='18' height='18' fill='none' stroke='%2364748b' stroke-width='1.7'%3E%3Crect x='2.5' y='4' width='13' height='10' rx='2'/%3E%3Cpath d='m3 5 6 5 6-5'/%3E%3C/svg%3E") !important;
}
[data-testid="stForm"] input[type="password"] {
    background-image: url("data:image/svg+xml,%3Csvg xmlns='http://www.w3.org/2000/svg' width='18' height='18' fill='none' stroke='%2364748b' stroke-width='1.7'%3E%3Crect x='3.5' y='8' width='11' height='7' rx='2'/%3E%3Cpath d='M6 8V6a3 3 0 0 1 6 0v2'/%3E%3C/svg%3E") !important;
}
[data-testid="stFormSubmitButton"] button {
    min-height: 52px; background: #0f172a !important;
    color: #ffffff !important; font-weight: 700 !important; border: 0 !important; border-radius: 8px !important;
    font-size: .98rem !important; transition: transform .15s ease, filter .15s ease;
}
[data-testid="stFormSubmitButton"] button:hover { filter: brightness(1.3); transform: translateY(-1px); }
[data-testid="stFormSubmitButton"] button p::after { content: "  →"; font-weight: 700; }

.lg-forgot { text-align: right; color: #2563eb; font-size: .86rem; font-weight: 600; padding-top: 6px; cursor: pointer; }
.lg-divider { display: flex; align-items: center; gap: 12px; color: #94a3b8; font-size: .74rem; font-weight: 700; letter-spacing: .06em; text-transform: uppercase; margin: 16px 2px 10px; }
.lg-divider::before, .lg-divider::after { content: ""; flex: 1; height: 1px; background: #e2e8f0; }
.lg-passkey {
    display: flex; align-items: center; justify-content: center; gap: 10px; width: 100%;
    background: #eff6ff; border: 1px solid #dbeafe; color: #1e3a8a; font-weight: 600; font-size: .92rem;
    padding: 13px 14px; border-radius: 8px; cursor: pointer;
}
.lg-passkey .badge { background: #dbeafe; color: #2563eb; font-size: .68rem; font-weight: 800; padding: 2px 8px; border-radius: 999px; }
.lg-footer {
    margin-top: 16px; display: flex; align-items: center; justify-content: space-between; gap: 10px;
    background: linear-gradient(90deg, #ecfdf5, #eff6ff); border-radius: 10px; padding: 10px 14px;
    color: #475569; font-size: .74rem; font-weight: 600;
}

@media (max-width: 760px) {
    .login-panel { min-height: auto; padding: 26px 22px; }
    .lp-features { display: none; }
    .lg-footer { flex-direction: column; align-items: flex-start; gap: 4px; }
}
</style>
"""

_ICONO_CANDADO = (
    '<svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="1.8">'
    '<rect x="4" y="11" width="16" height="9" rx="2"/><path d="M8 11V7a4 4 0 0 1 8 0v4"/></svg>'
)
_ICONO_SYNC = (
    '<svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="1.8">'
    '<path d="M4 10a8 8 0 0 1 14-4.9M20 14a8 8 0 0 1-14 4.9"/>'
    '<path d="M18 2v4h-4M6 22v-4h4"/></svg>'
)
_ICONO_CHART = (
    '<svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="1.8">'
    '<rect x="4" y="12" width="4" height="8"/><rect x="10" y="7" width="4" height="13"/>'
    '<rect x="16" y="3" width="4" height="17"/></svg>'
)
_ICONO_ESCUDO = (
    '<svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="1.8">'
    '<path d="M12 3 5 6v5c0 5 3 8 7 10 4-2 7-5 7-10V6l-7-3Z"/></svg>'
)

_FEATURES_LOGIN = [
    (_ICONO_CANDADO, "Seguridad cifrada grado bancario 256-bit",
     "Protocolos fiduciarios HSM y claves tokenizadas sin custodia local."),
    (_ICONO_SYNC, "Sincronización en tiempo real con Open Banking",
     "Conexión directa PSD2 con más de 120 instituciones financieras."),
    (_ICONO_CHART, "Análisis algorítmico de carteras",
     "Métricas avanzadas de volatilidad, Alpha, Sharpe y diversificación."),
]


def login_panel_izq(logo_svg: str = "assets/logo-login.svg") -> str:
    features = "".join(
        f'<div class="lp-feature"><div class="lp-feature-ic">{ic}</div>'
        f'<div><div class="lp-feature-title">{t}</div><div class="lp-feature-desc">{d}</div></div></div>'
        for ic, t, d in _FEATURES_LOGIN
    )
    return f"""
    <div class="login-panel">
        <div class="lp-brand">
            <div class="lp-badge">{_ICONO_ESCUDO.replace('currentColor', '#ffffff')}</div>
            <div><div class="lp-brand-name">Álvaro Finanzas</div><div class="lp-brand-sub">Gestión Patrimonial</div></div>
        </div>
        <div class="lp-pill"><span class="dot">●</span> Entorno Certificado ISO-27001</div>
        <div>
            <div class="lp-title">Bienvenido a tu centro de control financiero</div>
            <div class="lp-desc" style="margin-top:10px;">Supervisa activos consolidados, rendimiento en tiempo real y
            transacciones fiduciarias con total rigurosidad institucional.</div>
        </div>
        <div class="lp-features">{features}</div>
        <div class="lp-status">
            <span class="ok"><span class="dot-live"></span>Sistemas Operativos 100%</span>
            <span class="latency">Latencia 18ms</span>
        </div>
    </div>
    """


def login_cabecera_derecha() -> str:
    return (
        '<div class="lg-top"><span class="lg-eyebrow">Autenticación segura</span>'
        '<span class="lg-tls">🛡 Canal Privado TLS 1.3</span></div>'
    )


def login_footer() -> str:
    return (
        '<div class="lg-footer">'
        '<span>🛡️ Certificación PCI DSS &amp; RGPD Fiduciario activo.</span>'
        '<span>🎧 Soporte Financiero 24/7</span></div>'
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


def tarjeta_kpi_pro(
    icono: str, label: str, valor: str, chip_texto: str, chip_tono: str = "",
    progreso: float | None = None, meta_texto: str = "",
) -> str:
    """Tarjeta KPI estilo 'wealth dashboard': icono, etiqueta, valor grande y
    una línea de contexto (chip) debajo, con barra de progreso opcional."""
    clase_chip = f"kpi-pro-chip {chip_tono}".strip()
    barra = ""
    if progreso is not None:
        pct = max(0.0, min(progreso, 1.0)) * 100
        barra = (
            f'<div class="kpi-pro-bar"><div style="width:{pct:.0f}%"></div></div>'
            + (f'<div class="kpi-pro-chip" style="margin-top:4px;">{meta_texto}</div>' if meta_texto else "")
        )
    return (
        f'<div class="kpi-pro"><div class="kpi-pro-top">'
        f'<span class="kpi-pro-label">{label}</span><span class="kpi-pro-ic">{icono}</span></div>'
        f'<div class="kpi-pro-val">{valor}</div>'
        f'<div class="{clase_chip}">{chip_texto}</div>{barra}</div>'
    )


def fila_leyenda(color: str, label: str, valor: float, pct: float) -> str:
    return (
        f'<div class="leg-row"><div class="leg-left">'
        f'<span class="leg-dot" style="background:{color};"></span>{label}</div>'
        f'<div class="leg-val">{valor:,.0f} € · {pct:.0f}%</div></div>'
    )


def fila_presupuesto(categoria: str, gasto: float, limite: float) -> str:
    """Una partida de la ejecución presupuestaria: barra de progreso del gasto
    real frente al límite mensual fijado, con una píldora de estado."""
    pct = (gasto / limite * 100) if limite else 0.0
    pct_barra = max(0.0, min(pct, 100.0))
    if pct < 80:
        tono, color_barra = "ok", VERDE
    elif pct <= 100:
        tono, color_barra = "warn", NARANJA
    else:
        tono, color_barra = "over", ROJO
    return (
        f'<div class="pres-row"><div class="pres-top">'
        f'<div class="pres-cat">🏷️ {categoria}</div>'
        f'<div class="pres-pill {tono}">{pct:.0f}%</div></div>'
        f'<div class="pres-bar"><div style="width:{pct_barra:.0f}%;background:{color_barra};"></div></div>'
        f'<div class="pres-vals">{gasto:,.2f} € de {limite:,.2f} €</div></div>'
    )


def tarjeta_info(tono: str, etiqueta: str, titulo: str, texto: str) -> str:
    return (
        f'<div class="info-card {tono}"><div class="tag">{etiqueta}</div>'
        f'<h4>{titulo}</h4><p>{texto}</p></div>'
    )


def pie_estadisticas(items: list[tuple[str, str]]) -> str:
    cuerpo = "".join(f'<div class="item"><span class="lbl">{l}</span><span class="val">{v}</span></div>' for l, v in items)
    return f'<div class="stat-foot">{cuerpo}</div>'


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
    if isinstance(icono_o_logo, float):
        return ""  # NaN (p.ej. columna `logo` vacía leída de la base de datos)
    if not icono_o_logo or not isinstance(icono_o_logo, str):
        return ""
    estilo_img = 'style="width:100%;height:100%;object-fit:cover;border-radius:10px;"'
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
