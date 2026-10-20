import base64
from pathlib import Path

import streamlit as st

BG = "#0b0e14"
CARD = "#161b26"
BORDER = "#232936"
TEXT = "#e2e8f0"
MUTED = "#94a3b8"
VERDE = "#22c55e"
ROJO = "#ef4444"
NARANJA = "#f59e0b"
AZUL = "#38bdf8"
MORADO = "#a78bfa"

PALETA_CATEGORIAS = [VERDE, AZUL, MORADO, NARANJA, ROJO, "#2dd4bf", "#f472b6", "#facc15"]

CSS = f"""
<style>
.block-container {{ padding-top: 1.25rem !important; padding-bottom: 2.5rem; max-width: 1500px !important; }}
[data-testid="stAppViewContainer"] {{ background: {BG}; }}
[data-testid="stHeader"] {{ background: {BG}; border-bottom: 1px solid {BORDER}; }}
[data-testid="stSidebar"] {{ background: linear-gradient(180deg,#10151f 0%,{BG} 100%); border-right: 1px solid {BORDER}; }}
[data-testid="stSidebar"] > div:first-child {{ padding-top: 1.2rem; }}
[data-testid="stSidebar"] button {{ border-radius: 10px !important; }}
[data-testid="stMetric"] {{ background: linear-gradient(145deg,#191f2c 0%,{CARD} 100%); border: 1px solid {BORDER}; border-radius: 15px; padding: 17px 18px; box-shadow: 0 5px 18px rgba(0,0,0,.12); min-height: 100px; }}
[data-testid="stMetricLabel"] {{ color: {MUTED} !important; font-size: .82rem; font-weight: 600; }}
[data-testid="stMetricValue"] {{ color: {TEXT}; font-size: clamp(1.2rem,1.7vw,1.75rem); font-weight: 750; letter-spacing: -.04em; }}
[data-testid="stVerticalBlockBorderWrapper"] {{ border-radius: 15px !important; border-color: {BORDER} !important; }}
button[data-baseweb="tab"] {{ font-weight: 650; padding: .7rem .9rem; }}
[data-baseweb="tab-highlight"] {{ background-color: {VERDE}; }}
[data-testid="stDataFrame"], [data-testid="stTable"] {{ border: 1px solid {BORDER}; border-radius: 12px; overflow: hidden; }}
[data-testid="stExpander"] {{ border: 1px solid {BORDER}; border-radius: 12px; }}
[data-testid="stForm"] {{ border: 1px solid {BORDER}; border-radius: 14px; padding: 1rem; }}
[data-testid="stButton"] button, [data-testid="stFormSubmitButton"] button {{ border-radius: 10px; font-weight: 650; }}
[data-testid="stButton"] button:hover, [data-testid="stFormSubmitButton"] button:hover {{ border-color: {VERDE}; }}
div[data-testid="stButton"] button p {{ text-align: left; }}
div[data-testid="stButton"] button > div {{ justify-content: flex-start !important; }}
.fin-row {{ display:flex; align-items:center; justify-content:space-between; gap:16px; padding:13px 5px; border-bottom:1px solid {BORDER}; }}
.fin-row:last-child {{ border-bottom:none; }}
.fin-row .left {{ display:flex; align-items:center; gap:12px; min-width:0; }}
.fin-icon {{ flex-shrink:0; width:38px; height:38px; border-radius:12px; background:{BORDER}; display:flex; align-items:center; justify-content:center; font-size:17px; overflow:hidden; }}
.fin-nombre {{ font-weight:650; color:{TEXT}; }}
.fin-sub {{ font-size:.78rem; color:{MUTED}; margin-top:3px; }}
.fin-importe {{ font-weight:750; white-space:nowrap; font-variant-numeric:tabular-nums; }}
.fin-pos {{ color:{VERDE}; }}
.fin-neg {{ color:{TEXT}; }}
@media (max-width: 768px) {{ .block-container {{ padding:1rem .8rem 2rem !important; }} [data-testid="stMetric"] {{ padding:12px; min-height:85px; }} [data-testid="stMetricValue"] {{ font-size:1.15rem; }} .fin-row {{ gap:8px; }} .fin-sub {{ font-size:.72rem; }} }}
</style>
"""


def inyectar() -> None:
    st.markdown(CSS, unsafe_allow_html=True)


def aplicar_tema_plotly(fig):
    fig.update_layout(
        paper_bgcolor="rgba(0,0,0,0)",
        plot_bgcolor="rgba(0,0,0,0)",
        font_color=TEXT,
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
        return f'<img src="data:image/png;base64,{datos}" style="width:100%;height:100%;object-fit:cover;border-radius:10px;">'
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
