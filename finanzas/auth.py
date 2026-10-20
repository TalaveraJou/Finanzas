"""Autenticación: login con contraseña (bcrypt), bootstrap del superadmin y
registro de accesos. La sesión vive en st.session_state (se pide login de nuevo
si se refresca del todo la página)."""

import bcrypt
import pandas as pd
import streamlit as st

from finanzas import db, estilo


def _hash(password: str) -> str:
    return bcrypt.hashpw(password.encode("utf-8"), bcrypt.gensalt()).decode("utf-8")


def _verificar(password: str, hash_: str) -> bool:
    try:
        return bcrypt.checkpw(password.encode("utf-8"), hash_.encode("utf-8"))
    except Exception:
        return False


def _hash_valido(ph) -> bool:
    return isinstance(ph, str) and ph != "" and not (isinstance(ph, float) and pd.isna(ph))


def usuario_actual() -> dict | None:
    return st.session_state.get("usuario")


def es_superadmin() -> bool:
    u = usuario_actual()
    return bool(u and u.get("rol") == "superadmin")


def _iniciar_sesion(email: str) -> None:
    u = db.obtener_usuario(email)
    st.session_state["usuario"] = {
        "email": u["email"], "nombre": u.get("nombre", ""), "rol": u.get("rol", "usuario"),
    }
    st.session_state.pop("set_pw_email", None)
    db.actualizar_ultimo_acceso(email)
    db.registrar_acceso(email, "login_ok")
    st.rerun()


def cerrar_sesion() -> None:
    u = usuario_actual()
    if u:
        db.registrar_acceso(u["email"], "logout")
    st.session_state.pop("usuario", None)
    st.rerun()


def _procesar_login(email: str, password: str) -> None:
    email = (email or "").strip().lower()
    if not email:
        st.error("Introduce tu email.")
        return
    u = db.obtener_usuario(email)
    if not u or not bool(u.get("activo", 0)):
        db.registrar_acceso(email, "login_fallido", "email no autorizado o inactivo")
        st.error("Email no autorizado o cuenta desactivada.")
        return
    if not _hash_valido(u.get("password_hash")):
        # Primera vez de este usuario: debe crear su contraseña.
        st.session_state["set_pw_email"] = email
        st.rerun()
        return
    if _verificar(password, u["password_hash"]):
        _iniciar_sesion(email)
    else:
        db.registrar_acceso(email, "login_fallido", "contraseña incorrecta")
        st.error("Contraseña incorrecta.")


def _guardar_password(email: str, p1: str, p2: str) -> None:
    if len(p1) < 8:
        st.error("La contraseña debe tener al menos 8 caracteres.")
    elif p1 != p2:
        st.error("Las contraseñas no coinciden.")
    else:
        db.establecer_password(email, _hash(p1))
        db.registrar_acceso(email, "password_creada")
        _iniciar_sesion(email)


def _pantalla_login() -> None:
    st.markdown(estilo.CSS_LOGIN, unsafe_allow_html=True)
    col_izq, col_der = st.columns([1, 1.08], gap="medium")
    with col_izq:
        st.markdown(estilo.login_panel_izq(), unsafe_allow_html=True)
    with col_der:
        email_pendiente = st.session_state.get("set_pw_email")
        if email_pendiente:
            st.markdown(
                f'<div class="lg-head"><h2>Crea tu contraseña</h2>'
                f'<p>Primer acceso de {email_pendiente}</p></div>',
                unsafe_allow_html=True,
            )
            # Dentro de un form los valores se envían juntos al pulsar el botón,
            # así no se pierde la contraseña por latencia (campo suelto + clic).
            with st.form("crear_password", clear_on_submit=False):
                p1 = st.text_input("Contraseña", type="password", placeholder="Mínimo 8 caracteres")
                p2 = st.text_input("Repite la contraseña", type="password", placeholder="Repite la contraseña")
                if st.form_submit_button("Guardar y entrar", use_container_width=True, type="primary"):
                    _guardar_password(email_pendiente, p1, p2)
            if st.button("← Volver", use_container_width=True):
                st.session_state.pop("set_pw_email", None)
                st.rerun()
        else:
            st.markdown(estilo.login_cabecera_derecha(), unsafe_allow_html=True)
            st.markdown('<div class="lg-head"><h2>Acceso a Clientes</h2></div>', unsafe_allow_html=True)
            with st.form("login", clear_on_submit=False):
                email = st.text_input(
                    "Correo electrónico o Identificador de Acceso", placeholder="usuario@institucion.com",
                )
                password = st.text_input("Contraseña maestra", type="password", placeholder="Tu contraseña")
                st.markdown('<div class="lg-forgot">¿Olvidaste tu contraseña?</div>', unsafe_allow_html=True)
                st.checkbox("Mantener sesión iniciada en este equipo", value=True)
                if st.form_submit_button("Iniciar Sesión en Álvaro Finanzas", use_container_width=True, type="primary"):
                    _procesar_login(email, password)
            st.markdown('<div class="lg-divider">O accede de forma segura con</div>', unsafe_allow_html=True)
            if st.button("🔑  Clave Digital / Passkey / Biometría   ·  FIDO2", use_container_width=True, key="passkey_btn"):
                st.info("La clave de acceso (passkey) aún no está disponible. Entra con tu email y contraseña.")
            st.markdown(estilo.login_footer(), unsafe_allow_html=True)


def require_login() -> dict:
    """Si no hay sesión, muestra el login y detiene la ejecución."""
    u = usuario_actual()
    if u:
        return u
    _pantalla_login()
    st.stop()
