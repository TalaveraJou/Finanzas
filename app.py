import datetime as dt

import streamlit as st

from finanzas import db
from finanzas.categorias import lista_categorias

st.set_page_config(page_title="Finanzas", page_icon="💶", layout="centered")

pagina = st.sidebar.radio("Menú", ["Inicio", "Movimientos"])

if pagina == "Inicio":
    st.title("💶 Finanzas")
    st.caption("Plataforma en blanco: aquí irá el resumen cuando definamos qué quieres ver.")

elif pagina == "Movimientos":
    st.header("Movimientos")

    with st.expander("➕ Añadir movimiento", expanded=True):
        with st.form("nuevo", clear_on_submit=True):
            fecha = st.date_input("Fecha", dt.date.today())
            concepto = st.text_input("Concepto")
            importe = st.number_input(
                "Importe (€)", step=0.01, format="%.2f",
                help="Negativo = gasto, positivo = ingreso",
            )
            categoria = st.selectbox("Categoría", lista_categorias())
            if st.form_submit_button("Guardar"):
                if not concepto.strip():
                    st.warning("Pon un concepto.")
                elif importe == 0:
                    st.warning("El importe no puede ser 0.")
                else:
                    db.anadir(fecha, concepto, importe, categoria)
                    st.success("Guardado")

    df = db.cargar()
    if df.empty:
        st.caption("Aún no hay movimientos.")
    else:
        st.dataframe(
            df[["fecha", "concepto", "importe", "categoria"]],
            hide_index=True, width="stretch",
        )
