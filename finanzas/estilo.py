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
.block-container {{ padding-top: 1.6rem; max-width: 1200px; }}

[data-testid="stMetric"] {{
    background: {CARD};
    border: 1px solid {BORDER};
    border-radius: 16px;
    padding: 14px 16px 12px 16px;
}}
[data-testid="stMetricLabel"] {{ font-weight: 600; color: {MUTED}; }}
[data-testid="stMetricValue"] {{ font-size: 1.5rem; }}

div[data-testid="stVerticalBlockBorderWrapper"] {{
    border-radius: 16px !important;
    border-color: {BORDER} !important;
}}

button[data-baseweb="tab"] {{ font-weight: 600; }}

section[data-testid="stSidebar"] {{ background: {BG}; border-right: 1px solid {BORDER}; }}

.fin-row {{
    display: flex; align-items: center; justify-content: space-between;
    padding: 10px 4px; border-bottom: 1px solid {BORDER};
}}
.fin-row:last-child {{ border-bottom: none; }}
.fin-row .left {{ display: flex; align-items: center; gap: 10px; }}
.fin-icon {{
    width: 34px; height: 34px; border-radius: 10px;
    background: {BORDER}; display: flex; align-items: center; justify-content: center;
    font-size: 16px;
}}
.fin-nombre {{ font-weight: 600; color: {TEXT}; }}
.fin-sub {{ font-size: 0.8rem; color: {MUTED}; }}
.fin-importe {{ font-weight: 700; }}
.fin-pos {{ color: {VERDE}; }}
.fin-neg {{ color: {TEXT}; }}
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


def fila_movimiento(icono: str, nombre: str, sub: str, importe: float) -> str:
    clase = "fin-pos" if importe > 0 else "fin-neg"
    signo = "+" if importe > 0 else ""
    return f"""
    <div class="fin-row">
        <div class="left">
            <div class="fin-icon">{icono}</div>
            <div>
                <div class="fin-nombre">{nombre}</div>
                <div class="fin-sub">{sub}</div>
            </div>
        </div>
        <div class="fin-importe {clase}">{signo}{importe:,.2f} €</div>
    </div>
    """
