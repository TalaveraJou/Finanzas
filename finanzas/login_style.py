from pathlib import Path
import base64
import streamlit as st

_LOGO = Path(__file__).resolve().parent.parent / "assets" / "logo-login.svg"

CSS = """
<style>
@import url('https://fonts.googleapis.com/css2?family=Inter:wght@400;500;600;700;800&display=swap');
:root{--af-bg:#070B10;--af-panel:#0B1218;--af-border:#24333D;--af-text:#F7FAFC;--af-muted:#91A2AF;--af-green:#00D985;--af-mint:#65FFC5}
[data-testid="stAppViewContainer"]{background:radial-gradient(ellipse at 15% 48%,rgba(0,217,133,.12),transparent 38%),radial-gradient(ellipse at 85% 5%,rgba(0,217,133,.07),transparent 30%),#070B10}
.block-container{max-width:1120px!important;padding-top:3vh!important}
html,body,[data-testid="stAppViewContainer"],input,button,label,p,h1,h2,h3{font-family:Inter,-apple-system,BlinkMacSystemFont,'Segoe UI',sans-serif}
.login-hero{display:flex;flex-direction:column;align-items:center;text-align:center;margin:2vh auto 2.5rem;max-width:520px}
.login-brand-logo{width:min(290px,70vw);height:auto;filter:drop-shadow(0 10px 35px rgba(0,217,133,.13));margin-bottom:14px}
.login-tagline{color:#91A2AF;font-size:1rem;letter-spacing:.02em}
.login-card-title{font-size:1.55rem;font-weight:750;letter-spacing:-.035em;margin:.4rem 0 .25rem;color:#F7FAFC}
.login-card-sub{color:#91A2AF;margin-bottom:1.25rem;font-size:.92rem}
[data-testid="stTextInput"] input{background:#0D171E!important;border:1px solid #2A3B45!important;border-radius:13px!important;color:#F7FAFC!important;min-height:48px}
[data-testid="stTextInput"] input:focus{border-color:#00D985!important;box-shadow:0 0 0 3px rgba(0,217,133,.13)!important}
[data-testid="stButton"] button{border-radius:13px!important;min-height:47px;font-weight:700!important;border:1px solid #24333D!important;background:#101A22!important;color:#F7FAFC!important}
[data-testid="stButton"] button[kind="primary"], [data-testid="stButton"] button[kind="primaryFormSubmit"]{background:linear-gradient(110deg,#65FFC5,#00D985 65%,#00B977)!important;color:#04130D!important;border:0!important}
[data-testid="stButton"] button:hover{border-color:#00D985!important}
[data-testid="stAlert"]{border-radius:12px}
@media(max-width:700px){.block-container{padding:1.2rem 1rem 2rem!important}.login-hero{margin-top:1vh}.login-brand-logo{width:min(245px,72vw)}}
</style>
"""

def inyectar():
    st.markdown(CSS, unsafe_allow_html=True)

def cabecera():
    if _LOGO.exists():
        encoded = base64.b64encode(_LOGO.read_bytes()).decode("ascii")
        logo = f'<img class="login-brand-logo" alt="Álvaro Finanzas" src="data:image/svg+xml;base64,{encoded}">'
    else:
        logo = '<div style="font-size:2rem;font-weight:800;color:#00D985">ÁLVARO FINANZAS</div>'
    st.markdown(f'<div class="login-hero">{logo}<div class="login-tagline">Controla tu dinero, construye tu futuro.</div></div>', unsafe_allow_html=True)
