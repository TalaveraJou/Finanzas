import datetime as dt

import pandas as pd
import plotly.express as px
import streamlit as st

from finanzas import db
from finanzas.categorias import lista_categorias

st.set_page_config(page_title="Finanzas", page_icon="💶", layout="centered")

pagina = st.sidebar.radio(
    "Menú", ["Inicio", "Movimientos", "Deudas", "Ahorros", "Planes"]
)

# ---------------------------------------------------------------- Inicio ----

if pagina == "Inicio":
    st.title("💶 Finanzas")

    df = db.cargar()
    deudas = db.cargar_deudas()
    ahorros = db.cargar_ahorros()

    ingresos = df.loc[df["importe"] > 0, "importe"].sum() if not df.empty else 0.0
    gastos = -df.loc[df["importe"] < 0, "importe"].sum() if not df.empty else 0.0
    balance = ingresos - gastos
    deuda_pendiente = deudas["importe_pendiente"].sum() if not deudas.empty else 0.0
    ahorro_total = ahorros["actual"].sum() if not ahorros.empty else 0.0

    c1, c2, c3 = st.columns(3)
    c1.metric("Ingresos", f"{ingresos:,.2f} €")
    c2.metric("Gastos", f"{gastos:,.2f} €")
    c3.metric("Balance", f"{balance:,.2f} €")

    c4, c5 = st.columns(2)
    c4.metric("Deuda pendiente", f"{deuda_pendiente:,.2f} €")
    c5.metric("Ahorrado", f"{ahorro_total:,.2f} €")

    if df.empty:
        st.caption("Aún no hay movimientos. Añádelos en la pestaña Movimientos.")
    else:
        st.subheader("Gastos por categoría")
        gastos_df = df[df["importe"] < 0].copy()
        if not gastos_df.empty:
            gastos_df["importe"] = -gastos_df["importe"]
            por_categoria = gastos_df.groupby("categoria")["importe"].sum().reset_index()
            fig_pie = px.pie(
                por_categoria, names="categoria", values="importe", hole=0.4
            )
            st.plotly_chart(fig_pie, use_container_width=True)
        else:
            st.caption("Aún no hay gastos registrados.")

        st.subheader("Ingresos vs. gastos por mes")
        mensual = df.copy()
        mensual["mes"] = mensual["fecha"].dt.to_period("M").astype(str)
        mensual["tipo"] = mensual["importe"].apply(lambda x: "Ingreso" if x > 0 else "Gasto")
        mensual["importe_abs"] = mensual["importe"].abs()
        resumen = mensual.groupby(["mes", "tipo"])["importe_abs"].sum().reset_index()
        fig_bar = px.bar(
            resumen, x="mes", y="importe_abs", color="tipo", barmode="group",
            labels={"importe_abs": "Importe (€)", "mes": "Mes", "tipo": "Tipo"},
        )
        st.plotly_chart(fig_bar, use_container_width=True)

# ----------------------------------------------------------- Movimientos ----

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
                    st.rerun()

    df = db.cargar()
    if df.empty:
        st.caption("Aún no hay movimientos.")
    else:
        st.dataframe(
            df[["fecha", "concepto", "importe", "categoria"]],
            hide_index=True, width="stretch",
        )

        with st.expander("🗑️ Eliminar un movimiento"):
            opciones = {
                f"#{row.id} · {row.fecha.date()} · {row.concepto} · {row.importe:.2f} €": row.id
                for row in df.itertuples()
            }
            seleccion = st.selectbox("Movimiento", list(opciones.keys()))
            if st.button("Eliminar"):
                db.eliminar_movimiento(opciones[seleccion])
                st.success("Eliminado")
                st.rerun()

# ---------------------------------------------------------------- Deudas ----

elif pagina == "Deudas":
    st.header("Deudas")

    with st.expander("➕ Añadir deuda", expanded=True):
        with st.form("nueva_deuda", clear_on_submit=True):
            nombre = st.text_input("Nombre (ej. Préstamo coche)")
            importe_total = st.number_input("Importe total (€)", min_value=0.0, step=0.01, format="%.2f")
            importe_pendiente = st.number_input("Importe pendiente (€)", min_value=0.0, step=0.01, format="%.2f")
            cuota_mensual = st.number_input("Cuota mensual (€)", min_value=0.0, step=0.01, format="%.2f")
            fecha_inicio = st.date_input("Fecha de inicio", dt.date.today())
            if st.form_submit_button("Guardar"):
                if not nombre.strip():
                    st.warning("Pon un nombre.")
                else:
                    db.anadir_deuda(nombre, importe_total, importe_pendiente, cuota_mensual, fecha_inicio)
                    st.success("Guardada")
                    st.rerun()

    deudas = db.cargar_deudas()
    if deudas.empty:
        st.caption("No tienes deudas registradas.")
    else:
        for row in deudas.itertuples():
            with st.container(border=True):
                st.markdown(f"**{row.nombre}**  ·  cuota mensual: {row.cuota_mensual:,.2f} €")
                progreso = 1 - (row.importe_pendiente / row.importe_total) if row.importe_total else 0
                st.progress(min(max(progreso, 0.0), 1.0))
                st.caption(f"Pendiente: {row.importe_pendiente:,.2f} € de {row.importe_total:,.2f} €")
                col1, col2 = st.columns([2, 1])
                nuevo_pendiente = col1.number_input(
                    "Actualizar pendiente", min_value=0.0, step=0.01, format="%.2f",
                    value=float(row.importe_pendiente), key=f"deuda_{row.id}",
                )
                if col2.button("Actualizar", key=f"act_deuda_{row.id}"):
                    db.actualizar_deuda_pendiente(row.id, nuevo_pendiente)
                    st.rerun()
                if st.button("Eliminar deuda", key=f"del_deuda_{row.id}"):
                    db.eliminar_deuda(row.id)
                    st.rerun()

# --------------------------------------------------------------- Ahorros ----

elif pagina == "Ahorros":
    st.header("Ahorros")

    with st.expander("➕ Añadir meta de ahorro", expanded=True):
        with st.form("nuevo_ahorro", clear_on_submit=True):
            nombre = st.text_input("Nombre (ej. Fondo de emergencia)")
            objetivo = st.number_input("Objetivo (€)", min_value=0.0, step=0.01, format="%.2f")
            actual = st.number_input("Ahorrado actualmente (€)", min_value=0.0, step=0.01, format="%.2f")
            fecha_objetivo = st.date_input("Fecha objetivo (opcional)", value=None)
            if st.form_submit_button("Guardar"):
                if not nombre.strip():
                    st.warning("Pon un nombre.")
                else:
                    db.anadir_ahorro(nombre, objetivo, actual, fecha_objetivo)
                    st.success("Guardado")
                    st.rerun()

    ahorros = db.cargar_ahorros()
    if ahorros.empty:
        st.caption("Aún no tienes metas de ahorro.")
    else:
        for row in ahorros.itertuples():
            with st.container(border=True):
                st.markdown(f"**{row.nombre}**")
                progreso = row.actual / row.objetivo if row.objetivo else 0
                st.progress(min(max(progreso, 0.0), 1.0))
                extra = f" · objetivo: {row.fecha_objetivo}" if row.fecha_objetivo else ""
                st.caption(f"{row.actual:,.2f} € de {row.objetivo:,.2f} €{extra}")
                col1, col2 = st.columns([2, 1])
                nuevo_actual = col1.number_input(
                    "Actualizar ahorrado", min_value=0.0, step=0.01, format="%.2f",
                    value=float(row.actual), key=f"ahorro_{row.id}",
                )
                if col2.button("Actualizar", key=f"act_ahorro_{row.id}"):
                    db.actualizar_ahorro_actual(row.id, nuevo_actual)
                    st.rerun()
                if st.button("Eliminar meta", key=f"del_ahorro_{row.id}"):
                    db.eliminar_ahorro(row.id)
                    st.rerun()

# --------------------------------------------------------------- Planes ----

elif pagina == "Planes":
    st.header("Planes a largo plazo")

    with st.expander("➕ Añadir plan", expanded=True):
        with st.form("nuevo_plan", clear_on_submit=True):
            nombre = st.text_input("Nombre (ej. Comprar casa)")
            descripcion = st.text_input("Descripción breve")
            importe_objetivo = st.number_input("Importe necesario (€)", min_value=0.0, step=0.01, format="%.2f")
            fecha_objetivo = st.date_input("Fecha objetivo (opcional)", value=None)
            notas = st.text_area("Notas")
            if st.form_submit_button("Guardar"):
                if not nombre.strip():
                    st.warning("Pon un nombre.")
                else:
                    db.anadir_plan(nombre, descripcion, importe_objetivo, fecha_objetivo, notas)
                    st.success("Guardado")
                    st.rerun()

    planes = db.cargar_planes()
    if planes.empty:
        st.caption("Aún no tienes planes a largo plazo.")
    else:
        for row in planes.itertuples():
            with st.container(border=True):
                st.markdown(f"**{row.nombre}**")
                if row.descripcion:
                    st.caption(row.descripcion)
                extra = f" · objetivo: {row.fecha_objetivo}" if row.fecha_objetivo else ""
                st.caption(f"Importe necesario: {row.importe_objetivo:,.2f} €{extra}")
                if row.notas:
                    st.write(row.notas)
                if st.button("Eliminar plan", key=f"del_plan_{row.id}"):
                    db.eliminar_plan(row.id)
                    st.rerun()
