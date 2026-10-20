import datetime as dt
from pathlib import Path

import pandas as pd
import plotly.express as px
import streamlit as st
from PIL import Image
from streamlit_option_menu import option_menu

from finanzas import auth, db, estilo, proyeccion

LOGOS_DIR = Path(__file__).resolve().parent / "data" / "logos"
LOGO_SIZE = 64

st.set_page_config(page_title="Finanzas", page_icon="💶", layout="wide")
estilo.inyectar()

usuario = auth.require_login()

MESES_NOMBRE = [
    "Enero", "Febrero", "Marzo", "Abril", "Mayo", "Junio",
    "Julio", "Agosto", "Septiembre", "Octubre", "Noviembre", "Diciembre",
]

INSTRUMENTOS = [
    "Cuenta remunerada", "Depósito", "Fondo indexado", "ETF", "Acciones",
    "Criptomonedas", "Plan de pensiones", "Otro",
]

MODO_LABELS = {
    "fijo": "Fijo",
    "variable": "Variable (lo registro cada mes)",
    "porcentaje_ingreso": "% de los ingresos del mes",
    "remanente": "Lo que sobre (ingresos − gastos − deudas − ahorro)",
}

with st.sidebar:
    st.markdown(
        estilo.marca_sidebar("assets/logo.webp", usuario.get("nombre") or usuario["email"]),
        unsafe_allow_html=True,
    )
    opciones = ["Inicio", "Cuentas"]
    iconos = ["speedometer2", "wallet2"]
    if auth.es_superadmin():
        opciones.append("Admin")
        iconos.append("shield-lock")
    pagina = option_menu(
        menu_title=None,
        options=opciones,
        icons=iconos,
        default_index=0,
        styles={
            "container": {"padding": "0", "background-color": estilo.BG},
            "icon": {"color": estilo.VERDE, "font-size": "16px"},
            "nav-link": {
                "font-size": "15px", "text-align": "left", "margin": "2px",
                "border-radius": "10px", "color": estilo.TEXT, "white-space": "nowrap",
            },
            "nav-link-selected": {"background-color": estilo.VERDE, "color": "#06240f"},
        },
    )
    st.markdown("<div style='margin-top:18px'></div>", unsafe_allow_html=True)
    if st.button("Cerrar sesión", use_container_width=True, key="logout_btn"):
        auth.cerrar_sesion()


def mapa_cuentas(cuentas: pd.DataFrame) -> dict[str, int]:
    return dict(zip(cuentas["nombre"], cuentas["id"]))


def selector_cuenta(cuentas: pd.DataFrame, key: str, opcional: bool = False):
    opciones = list(cuentas["nombre"])
    if opcional:
        opciones = ["(sin cuenta)"] + opciones
    if not opciones:
        st.warning("Primero crea una cuenta en la pestaña Cuentas.")
        return None
    seleccion = st.selectbox("Cuenta", opciones, key=key)
    if seleccion == "(sin cuenta)":
        return None
    return mapa_cuentas(cuentas)[seleccion]


def registrar_variable(tipo_padre: str, padre_id: int, key_prefix: str, label: str = "Importe de ese mes (€)"):
    """Widget reutilizable: registrar/editar el valor de un mes para un concepto o deuda variable."""
    valores = db.cargar_valores_mensuales(tipo_padre, padre_id)
    col1, col2, col3 = st.columns([1.3, 1, 1])
    mes_elegido = col1.date_input("Mes", dt.date.today(), key=f"{key_prefix}_mes")
    importe = col2.number_input(label, min_value=0.0, step=0.01, format="%.2f", key=f"{key_prefix}_importe")
    if col3.button("Guardar mes", key=f"{key_prefix}_guardar"):
        periodo = pd.Timestamp(mes_elegido).to_period("M")
        db.registrar_valor_mensual(tipo_padre, padre_id, str(periodo), importe)
        if tipo_padre == "deuda":
            deuda = db.cargar_deudas()
            fila = deuda[deuda["id"] == padre_id].iloc[0]
            db.actualizar_deuda_pendiente(padre_id, fila.importe_pendiente - importe)
        st.rerun()
    if not valores.empty:
        with st.expander(f"Histórico registrado ({len(valores)})"):
            for v in valores.itertuples():
                c1, c2 = st.columns([4, 1])
                c1.write(f"{v.periodo}: {v.importe:,.2f} €")
                if c2.button("Eliminar", key=f"{key_prefix}_del_{v.id}"):
                    db.eliminar_valor_mensual(v.id)
                    st.rerun()


def selector_categoria(key_prefix: str, valor_actual: str | None = None) -> str:
    """Selectbox de categorías con opción de crear una nueva al vuelo."""
    categorias = db.cargar_categorias()
    opciones = categorias + ["➕ Nueva categoría…"]
    indice = categorias.index(valor_actual) if valor_actual in categorias else 0
    seleccion = st.selectbox("Categoría", opciones, index=indice, key=f"{key_prefix}_cat")
    if seleccion == "➕ Nueva categoría…":
        nueva = st.text_input("Nombre de la nueva categoría", key=f"{key_prefix}_cat_nueva")
        if nueva.strip():
            db.anadir_categoria(nueva.strip())
            return nueva.strip()
        return valor_actual or ""
    return seleccion


def _logo_valido(logo: str | None) -> bool:
    return isinstance(logo, str) and bool(logo) and Path(logo).exists()


def _guardar_logo_redimensionado(archivo, ruta: Path) -> None:
    """Recorta/escala el logo a un cuadrado de LOGO_SIZE x LOGO_SIZE, con fondo transparente."""
    imagen = Image.open(archivo).convert("RGBA")
    ancho, alto = imagen.size
    lado = min(ancho, alto)
    recorte = imagen.crop((
        (ancho - lado) // 2, (alto - lado) // 2,
        (ancho - lado) // 2 + lado, (alto - lado) // 2 + lado,
    ))
    recorte = recorte.resize((LOGO_SIZE, LOGO_SIZE), Image.LANCZOS)
    recorte.save(ruta, format="PNG")


def subir_logo(tabla: str, id_: int, key_prefix: str) -> None:
    """Selector para subir/cambiar el logo (la vista previa ya la pone la cabecera de la tarjeta)."""
    archivo = st.file_uploader(
        "Cambiar logo (opcional, se recorta y escala automáticamente a un cuadrado)",
        type=["png", "jpg", "jpeg", "webp"], key=f"{key_prefix}_logo",
    )
    if archivo is not None:
        marca = f"{archivo.name}:{archivo.size}"
        clave_marca = f"{key_prefix}_logo_procesado"
        if st.session_state.get(clave_marca) != marca:
            LOGOS_DIR.mkdir(parents=True, exist_ok=True)
            ruta = LOGOS_DIR / f"{tabla}_{id_}.png"
            _guardar_logo_redimensionado(archivo, ruta)
            db.actualizar_logo(tabla, id_, str(ruta))
            st.session_state[clave_marca] = marca
            st.rerun()


def tarjeta_desplegable(logo_path: str | None, titulo: str, key: str):
    """Tarjeta única y plegable con el logo a la izquierda del título.
    (st.expander no admite imágenes en la etiqueta, así que montamos la cabecera a mano.)
    Devuelve (abierto, contenedor): escribe el resto del contenido con `with contenedor:`
    para que la cabecera y el cuerpo queden en la misma tarjeta."""
    abierto_key = f"abierto_{key}"
    abierto = st.session_state.get(abierto_key, False)
    contenedor = st.container(border=True)
    with contenedor:
        col_logo, col_boton = st.columns([1, 11], vertical_alignment="center")
        with col_logo:
            if _logo_valido(logo_path):
                st.image(logo_path, width=40)
            else:
                inicial = (titulo or "?").strip()[:1].upper()
                st.markdown(f'<div class="card-ic">{inicial}</div>', unsafe_allow_html=True)
        flecha = "⌄" if abierto else "›"
        if col_boton.button(f"{titulo}   {flecha}", key=f"toggle_{key}", use_container_width=True):
            abierto = not abierto
            st.session_state[abierto_key] = abierto
            st.rerun()
    return abierto, contenedor


# ================================================================= Inicio ====

if pagina == "Inicio":
    st.title("Finanzas")

    cuentas = db.cargar_cuentas()
    conceptos = db.cargar_conceptos()
    deudas = db.cargar_deudas()
    ahorros = db.cargar_ahorros()
    movimientos = db.cargar_movimientos()
    valores = db.cargar_valores_mensuales()

    if cuentas.empty:
        st.info("Empieza creando una cuenta en **Cuentas y Movimientos → Cuentas**.")
    else:
        hoy = pd.Timestamp.today().normalize()
        mes_actual = hoy.to_period("M")
        periodos = proyeccion.meses_entre(mes_actual - 1, mes_actual + 11)
        detalle = proyeccion.detalle_mensual(conceptos, deudas, ahorros, movimientos, valores, periodos)

        detalle_mes = detalle[detalle["periodo"] == mes_actual] if not detalle.empty else detalle
        ingresos_mes = detalle_mes.loc[detalle_mes["tipo"] == "ingreso", "importe"].sum()
        gastos_mes = -detalle_mes.loc[detalle_mes["tipo"] == "gasto", "importe"].sum()
        deuda_mes = -detalle_mes.loc[detalle_mes["tipo"] == "deuda", "importe"].sum()
        ahorro_mes = -detalle_mes.loc[detalle_mes["tipo"] == "ahorro", "importe"].sum()
        balance_mes = ingresos_mes - gastos_mes - deuda_mes - ahorro_mes

        deuda_pendiente = deudas.loc[deudas["activa"], "importe_pendiente"].sum() if not deudas.empty else 0.0
        ahorro_total = ahorros["actual"].sum() if not ahorros.empty else 0.0
        patrimonio_neto = ahorro_total - deuda_pendiente

        st.caption(f"Resumen de {MESES_NOMBRE[mes_actual.month - 1]} {mes_actual.year}")

        resumen_spark = proyeccion.tabla_resumen_mensual(detalle)
        s_ing = resumen_spark["ingresos"].tolist() if not resumen_spark.empty else []
        s_gas = resumen_spark["gastos"].tolist() if not resumen_spark.empty else []
        s_bal = resumen_spark["balance"].tolist() if not resumen_spark.empty else []
        s_pat = list(pd.Series(s_bal, dtype="float64").cumsum()) if s_bal else []
        n = len(s_bal) or 2
        s_deuda = [deuda_pendiente * (1 + 0.04 * (n - 1 - i)) for i in range(n)]
        s_ahorro = (
            [ahorro_total * (0.6 + 0.4 * i / (n - 1)) for i in range(n)] if n > 1 else [ahorro_total, ahorro_total]
        )

        tarjetas = [
            {"icono": "◆", "label": "Patrimonio neto", "valor": f"{patrimonio_neto:,.0f} €", "serie": s_pat or s_bal, "color": estilo.VERDE},
            {"icono": "↑", "label": "Ingresos", "valor": f"{ingresos_mes:,.0f} €", "serie": s_ing, "color": estilo.VERDE},
            {"icono": "↓", "label": "Gastos", "valor": f"{gastos_mes:,.0f} €", "serie": s_gas, "color": estilo.ROJO},
            {"icono": "≈", "label": "Balance", "valor": f"{balance_mes:,.0f} €", "serie": s_bal, "color": estilo.AZUL},
            {"icono": "▭", "label": "Deuda pendiente", "valor": f"{deuda_pendiente:,.0f} €", "serie": s_deuda, "color": estilo.NARANJA},
            {"icono": "◎", "label": "Ahorrado", "valor": f"{ahorro_total:,.0f} €", "serie": s_ahorro, "color": estilo.MORADO},
        ]
        st.markdown(estilo.tarjetas_stats(tarjetas), unsafe_allow_html=True)

        tab_resumen, tab_mes, tab_graficos, tab_deudas = st.tabs(["Resumen", "Por mes", "Gráficos", "Deudas activas"])

        with tab_resumen:
            logos_cuenta = dict(zip(cuentas["nombre"], cuentas.get("logo", pd.Series(dtype=str))))
            col_izq, col_der = st.columns([1.2, 1])
            with col_izq:
                st.markdown("**Últimos movimientos**")
                with st.container(border=True):
                    if movimientos.empty:
                        st.caption("Aún no hay movimientos puntuales.")
                    else:
                        for row in movimientos.head(6).itertuples():
                            logo = logos_cuenta.get(row.cuenta)
                            icono = logo if (isinstance(logo, str) and logo) else ("⬆️" if row.importe > 0 else "⬇️")
                            sub = f"{row.cuenta or 'sin cuenta'} · {row.fecha.strftime('%d %b')}"
                            st.markdown(
                                estilo.fila_movimiento(icono, row.concepto, sub, row.importe),
                                unsafe_allow_html=True,
                            )
            with col_der:
                st.markdown("**Por cuenta este mes**")
                por_cuenta = proyeccion.tabla_por_cuenta(detalle, mes_actual)
                with st.container(border=True):
                    if por_cuenta.empty:
                        st.caption("Añade cuentas, conceptos recurrentes o movimientos para ver el resumen.")
                    else:
                        for fila in por_cuenta.itertuples():
                            st.markdown(
                                estilo.fila_cuenta(
                                    logos_cuenta.get(fila.cuenta), fila.cuenta, fila.ingresos, fila.gastos, fila.balance,
                                ),
                                unsafe_allow_html=True,
                            )

        with tab_mes:
            periodos_mes = proyeccion.meses_entre(mes_actual - 12, mes_actual + 11)
            detalle_todo_mes = proyeccion.detalle_mensual(conceptos, deudas, ahorros, movimientos, valores, periodos_mes)
            if detalle_todo_mes.empty:
                st.caption("Añade cuentas, conceptos recurrentes o movimientos para ver el detalle por mes.")
            else:
                opciones_mes = {
                    f"{MESES_NOMBRE[p.month - 1]} {p.year}": p for p in periodos_mes
                }
                nombre_mes_elegido = st.selectbox(
                    "Mes", list(opciones_mes.keys()),
                    index=list(opciones_mes.values()).index(mes_actual),
                )
                periodo_elegido = opciones_mes[nombre_mes_elegido]
                detalle_elegido = detalle_todo_mes[detalle_todo_mes["periodo"] == periodo_elegido].copy()
                if detalle_elegido.empty:
                    st.caption("No hay nada registrado para ese mes.")
                else:
                    detalle_elegido["importe_abs"] = detalle_elegido["importe"].abs()

                    gastos_mes_elegido = detalle_elegido[detalle_elegido["tipo"].isin(["gasto", "deuda", "ahorro"])]
                    st.markdown(f"**Gastos de {nombre_mes_elegido}** ({len(gastos_mes_elegido)})")
                    if gastos_mes_elegido.empty:
                        st.caption("Sin gastos registrados para ese mes.")
                    else:
                        tabla_gastos = gastos_mes_elegido[["tipo", "cuenta", "grupo", "concepto", "importe_abs"]].rename(
                            columns={"importe_abs": "importe"}
                        ).sort_values(["tipo", "cuenta", "concepto"])
                        st.dataframe(
                            tabla_gastos.style.format({"importe": "{:,.2f} €"}),
                            hide_index=True, width="stretch",
                        )
                        st.caption(f"Total gastos: {gastos_mes_elegido['importe_abs'].sum():,.2f} €")

                    ingresos_mes_elegido = detalle_elegido[detalle_elegido["tipo"] == "ingreso"]
                    st.markdown(f"**Ingresos de {nombre_mes_elegido}** ({len(ingresos_mes_elegido)})")
                    if ingresos_mes_elegido.empty:
                        st.caption("Sin ingresos registrados para ese mes.")
                    else:
                        tabla_ingresos = ingresos_mes_elegido[["cuenta", "grupo", "concepto", "importe_abs"]].rename(
                            columns={"importe_abs": "importe"}
                        ).sort_values(["cuenta", "concepto"])
                        st.dataframe(
                            tabla_ingresos.style.format({"importe": "{:,.2f} €"}),
                            hide_index=True, width="stretch",
                        )
                        st.caption(f"Total ingresos: {ingresos_mes_elegido['importe_abs'].sum():,.2f} €")

                    st.markdown("**Total por cuenta**")
                    resumen_cuenta = detalle_elegido.copy()
                    resumen_cuenta["bloque"] = resumen_cuenta["tipo"].apply(
                        lambda t: "ingresos" if t == "ingreso" else "gastos"
                    )
                    tabla_cuenta = (
                        resumen_cuenta.groupby(["cuenta", "bloque"])["importe_abs"].sum()
                        .unstack(fill_value=0).reindex(columns=["ingresos", "gastos"], fill_value=0)
                    )
                    tabla_cuenta["balance"] = tabla_cuenta["ingresos"] - tabla_cuenta["gastos"]
                    st.dataframe(
                        tabla_cuenta.reset_index().style.format(
                            {"ingresos": "{:,.2f} €", "gastos": "{:,.2f} €", "balance": "{:,.2f} €"}
                        ),
                        hide_index=True, width="stretch",
                    )

                    total = detalle_elegido["importe"].sum()
                    st.caption(f"Balance neto de {nombre_mes_elegido}: {total:,.2f} €")

        with tab_graficos:
            if detalle.empty:
                st.caption("Añade cuentas, conceptos recurrentes o movimientos para ver gráficos.")
            else:
                col_izq, col_der = st.columns(2)
                with col_izq:
                    st.markdown("**Ingresos vs. salidas (12 meses)**")
                    resumen = proyeccion.tabla_resumen_mensual(detalle)
                    resumen_largo = resumen.melt(
                        id_vars="periodo", value_vars=["ingresos", "gastos"],
                        var_name="tipo", value_name="importe",
                    )
                    fig_bar = px.bar(
                        resumen_largo, x="periodo", y="importe", color="tipo", barmode="group",
                        labels={"importe": "Importe (€)", "periodo": "Mes", "tipo": "Tipo"},
                        color_discrete_map={"ingresos": estilo.VERDE, "gastos": estilo.ROJO},
                    )
                    estilo.aplicar_tema_plotly(fig_bar)
                    fig_bar.update_layout(height=320)
                    st.plotly_chart(fig_bar, width="stretch")

                    st.markdown("**Evolución del balance acumulado**")
                    resumen_ord = resumen.copy()
                    resumen_ord["acumulado"] = resumen_ord["balance"].cumsum()
                    fig_linea = px.area(resumen_ord, x="periodo", y="acumulado", labels={"acumulado": "€", "periodo": "Mes"})
                    fig_linea.update_traces(line_color=estilo.VERDE, fillcolor="rgba(34,197,94,0.15)")
                    estilo.aplicar_tema_plotly(fig_linea)
                    fig_linea.update_layout(height=260)
                    st.plotly_chart(fig_linea, width="stretch")
                with col_der:
                    st.markdown("**Salidas de este mes por grupo**")
                    salidas_mes = detalle_mes[detalle_mes["tipo"].isin(["gasto", "deuda", "ahorro"])].copy()
                    if not salidas_mes.empty:
                        salidas_mes["importe"] = salidas_mes["importe"].abs()
                        por_grupo = salidas_mes.groupby("grupo")["importe"].sum().reset_index()
                        fig_pie = px.pie(por_grupo, names="grupo", values="importe", hole=0.55)
                        estilo.aplicar_tema_plotly(fig_pie)
                        fig_pie.update_layout(height=320)
                        st.plotly_chart(fig_pie, width="stretch")
                    else:
                        st.caption("Sin salidas este mes.")

        with tab_deudas:
            deudas_activas = deudas[deudas["activa"]] if not deudas.empty else deudas
            if deudas_activas.empty:
                st.caption("No tienes deudas activas.")
            else:
                for row in deudas_activas.itertuples():
                    info = proyeccion.info_deuda(row, valores)
                    with st.container(border=True):
                        st.markdown(f"**{row.nombre}** · {row.cuenta or 'sin cuenta'}")
                        progreso = 1 - (row.importe_pendiente / row.importe_total) if row.importe_total else 0
                        st.progress(min(max(progreso, 0.0), 1.0))
                        fin = info["fecha_fin_estimada"]
                        fin_txt = f"{MESES_NOMBRE[fin.month - 1]} {fin.year}" if fin is not None else "sin estimar"
                        restantes_txt = info["meses_restantes"] if info["meses_restantes"] is not None else "?"
                        st.caption(
                            f"Pendiente: {row.importe_pendiente:,.2f} € de {row.importe_total:,.2f} € · "
                            f"cuota {'fija' if row.tipo_pago == 'fijo' else 'variable'}: {info['cuota_estimada']:,.2f} € · "
                            f"quedan {restantes_txt} meses (fin estimado: {fin_txt})"
                        )

# ============================================= Cuentas y Movimientos ====

elif pagina == "Cuentas":
    st.title("Cuentas y Movimientos")

    tabs = st.tabs([
        "Cuentas", "Deudas", "Ingresos", "Gastos recurrentes",
        "Movimientos puntuales", "Ahorros e inversiones", "Planes", "Proyección",
    ])

    # ------------------------------------------------------------- Cuentas --
    with tabs[0]:
        with st.form("nueva_cuenta", clear_on_submit=True):
            nombre = st.text_input("Nombre (ej. ING, Trade Republic)")
            if st.form_submit_button("Añadir cuenta"):
                if not nombre.strip():
                    st.warning("Pon un nombre.")
                else:
                    try:
                        db.anadir_cuenta(nombre.strip())
                        st.success("Cuenta creada")
                        st.rerun()
                    except Exception:
                        st.error("Ya existe una cuenta con ese nombre.")

        cuentas = db.cargar_cuentas()
        if cuentas.empty:
            st.caption("Aún no tienes cuentas.")
        else:
            for row in cuentas.itertuples():
                abierto, contenedor = tarjeta_desplegable(getattr(row, "logo", None), row.nombre, f"cuenta_{row.id}")
                if abierto:
                    with contenedor:
                        subir_logo("cuentas", row.id, f"cuenta_{row.id}")
                        nuevo_nombre = st.text_input("Nombre", value=row.nombre, key=f"nombre_cuenta_{row.id}")
                        col1, col2 = st.columns(2)
                        if col1.button("Guardar", key=f"guardar_cuenta_{row.id}"):
                            if nuevo_nombre.strip() and nuevo_nombre != row.nombre:
                                db.actualizar_cuenta_nombre(row.id, nuevo_nombre.strip())
                                st.rerun()
                        if col2.button("Eliminar", key=f"del_cuenta_{row.id}"):
                            db.eliminar_cuenta(row.id)
                            st.rerun()

    # -------------------------------------------------------------- Deudas --
    with tabs[1]:
        cuentas = db.cargar_cuentas()
        with st.expander("➕ Añadir deuda", expanded=False):
            with st.form("nueva_deuda", clear_on_submit=True):
                cuenta_id = selector_cuenta(cuentas, "deuda_cuenta")
                nombre = st.text_input("Nombre (ej. Préstamo coche, Hipoteca)")
                col1, col2 = st.columns(2)
                importe_total = col1.number_input("Importe total (€)", min_value=0.0, step=0.01, format="%.2f")
                importe_pendiente = col2.number_input("Importe pendiente (€)", min_value=0.0, step=0.01, format="%.2f")
                tipo_pago = st.radio(
                    "Tipo de pago", ["fijo", "variable"], horizontal=True,
                    help="Fijo: misma cuota cada mes. Variable: cada mes registras tú la cuota pagada.",
                )
                cuota_mensual = st.number_input(
                    "Cuota mensual (€)", min_value=0.0, step=0.01, format="%.2f",
                    help="Si es variable, se usa como estimación inicial hasta que registres el primer mes. "
                         "El nº de cuotas restantes se calcula solo dividiendo el pendiente entre la cuota.",
                )
                meses_total = 0
                fecha_inicio = st.date_input("Fecha de inicio", dt.date.today())
                if st.form_submit_button("Guardar"):
                    if not nombre.strip():
                        st.warning("Pon un nombre.")
                    else:
                        db.anadir_deuda(
                            cuenta_id, nombre.strip(), importe_total, importe_pendiente, tipo_pago,
                            cuota_mensual, meses_total or None, fecha_inicio,
                        )
                        st.success("Guardada")
                        st.rerun()

        deudas = db.cargar_deudas()
        valores = db.cargar_valores_mensuales("deuda")
        cuentas = db.cargar_cuentas()
        if deudas.empty:
            st.caption("No tienes deudas registradas.")
        else:
            for row in deudas.itertuples():
                info = proyeccion.info_deuda(row, valores)
                restantes_txt = info["meses_restantes"] if info["meses_restantes"] is not None else "?"
                titulo = f"{row.nombre} · {row.cuenta or 'sin cuenta'} · pendiente {row.importe_pendiente:,.0f} € · quedan {restantes_txt} meses"
                abierto, contenedor = tarjeta_desplegable(getattr(row, "logo", None), titulo, f"deuda_{row.id}")
                if abierto:
                    with contenedor:
                        subir_logo("deudas", row.id, f"deuda_{row.id}")
                        progreso = 1 - (row.importe_pendiente / row.importe_total) if row.importe_total else 0
                        st.progress(min(max(progreso, 0.0), 1.0))
                        fin = info["fecha_fin_estimada"]
                        fin_txt = f"{MESES_NOMBRE[fin.month - 1]} {fin.year}" if fin is not None else "sin estimar"
                        st.caption(
                            f"Cuota estimada: {info['cuota_estimada']:,.2f} € · fin estimado: {fin_txt}"
                        )

                        if row.tipo_pago == "variable":
                            registrar_variable("deuda", row.id, f"deuda_{row.id}", "Cuota pagada ese mes (€)")

                        with st.form(f"editar_deuda_{row.id}"):
                            st.markdown("**Editar datos de la deuda**")
                            e_nombre = st.text_input("Nombre", value=row.nombre, key=f"e_nombre_{row.id}")
                            opciones_cuenta = list(cuentas["nombre"]) if not cuentas.empty else []
                            indice_cuenta = opciones_cuenta.index(row.cuenta) if row.cuenta in opciones_cuenta else 0
                            e_cuenta = st.selectbox(
                                "Cuenta", opciones_cuenta, index=indice_cuenta if opciones_cuenta else None,
                                key=f"e_cuenta_{row.id}",
                            )
                            c1, c2 = st.columns(2)
                            e_total = c1.number_input(
                                "Importe total (€)", min_value=0.0, step=0.01, format="%.2f",
                                value=float(row.importe_total), key=f"e_total_{row.id}",
                            )
                            e_pendiente = c2.number_input(
                                "Importe pendiente (€)", min_value=0.0, step=0.01, format="%.2f",
                                value=float(row.importe_pendiente), key=f"e_pendiente_{row.id}",
                            )
                            e_tipo_pago = st.radio(
                                "Tipo de pago", ["fijo", "variable"], horizontal=True,
                                index=0 if row.tipo_pago == "fijo" else 1, key=f"e_tipopago_{row.id}",
                            )
                            e_cuota = st.number_input(
                                "Cuota mensual (€)", min_value=0.0, step=0.01, format="%.2f",
                                value=float(row.cuota_mensual) if pd.notna(row.cuota_mensual) else 0.0,
                                key=f"e_cuota_{row.id}",
                                help="El nº de cuotas restantes se calcula solo dividiendo el pendiente entre la cuota.",
                            )
                            e_fecha_inicio = st.date_input(
                                "Fecha de inicio", value=pd.Timestamp(row.fecha_inicio).date(),
                                key=f"e_fecha_{row.id}",
                            )
                            if st.form_submit_button("Guardar cambios"):
                                cuenta_id = mapa_cuentas(cuentas).get(e_cuenta) if e_cuenta else None
                                db.actualizar_deuda(
                                    row.id, cuenta_id, e_nombre.strip(), e_total, e_pendiente,
                                    e_tipo_pago, e_cuota, None, e_fecha_inicio,
                                )
                                st.success("Guardado")
                                st.rerun()

                        c5, c6 = st.columns([1, 1], vertical_alignment="bottom")
                        activa = c5.checkbox("Activa", value=bool(row.activa), key=f"activa_deuda_{row.id}")
                        if activa != bool(row.activa):
                            db.actualizar_deuda_activa(row.id, activa)
                            st.rerun()
                        if c6.button("Eliminar deuda", key=f"del_deuda_{row.id}"):
                            db.eliminar_deuda(row.id)
                            st.rerun()

    # --------------------------------------------------- Ingresos / Gastos --
    PLANTILLAS_CONCEPTO = {
        "Nómina (variable, media de los últimos 5 meses)": {
            "modo": "variable", "tipo": "ingreso", "nombre": "Nómina", "grupo": "Nómina", "meses": [],
        },
        "Paga extra (en meses concretos)": {
            "modo": "fijo", "tipo": "ingreso", "nombre": "Paga extra", "grupo": "Nómina",
            "meses": ["Junio", "Diciembre"],
        },
        "Gasto fraccionado (varios meses del año)": {
            "modo": "variable", "tipo": "gasto", "nombre": "", "grupo": "",
            "meses": ["Marzo", "Abril", "Diciembre"],
        },
    }


    def obtener_nombres_meses(valor):
        import pandas as pd
        if pd.isna(valor):
            return []
        if isinstance(valor, (int, float)):
            if not float(valor).is_integer():
                return []
            meses = [str(int(valor))]
        else:
            meses = str(valor).split(",")
        nombres = []
        for mes in meses:
            try:
                numero = int(mes.strip())
                if 1 <= numero <= 12:
                    nombres.append(MESES_NOMBRE[numero - 1])
            except (ValueError, TypeError):
                continue
        return nombres

    def seccion_conceptos(tipo_fijo, key_ns):
        cuentas = db.cargar_cuentas()
        etiqueta = "ingreso" if tipo_fijo == "ingreso" else "gasto"
        modos_disponibles = ["fijo", "variable"] if tipo_fijo == "ingreso" else list(MODO_LABELS.keys())
        plantillas_disponibles = {
            nombre: datos for nombre, datos in PLANTILLAS_CONCEPTO.items() if datos["tipo"] == tipo_fijo
        }

        with st.expander(f"➕ Añadir {etiqueta} recurrente"):
            plantilla = st.selectbox(
                "Plantilla rápida (opcional)", ["Personalizado"] + list(plantillas_disponibles.keys()),
                key=f"{key_ns}_plantilla",
            )
            if plantilla != "Personalizado" and st.session_state.get(f"{key_ns}_plantilla_aplicada") != plantilla:
                datos = plantillas_disponibles[plantilla]
                st.session_state[f"{key_ns}_modo_nuevo"] = datos["modo"]
                st.session_state[f"{key_ns}_nombre_nuevo"] = datos["nombre"]
                if datos["grupo"]:
                    st.session_state[f"{key_ns}_cat"] = datos["grupo"]
                st.session_state[f"{key_ns}_meses_nuevo"] = datos["meses"]
                st.session_state[f"{key_ns}_plantilla_aplicada"] = plantilla
                st.rerun()
            if plantilla == "Personalizado":
                st.session_state[f"{key_ns}_plantilla_aplicada"] = "Personalizado"

            modo = st.selectbox(
                "Cómo se calcula el importe", options=modos_disponibles,
                format_func=lambda k: MODO_LABELS[k], key=f"{key_ns}_modo_nuevo",
            )
            especial = modo in ("porcentaje_ingreso", "remanente")
            grupo = selector_categoria(f"{key_ns}_nuevo")

            meses_aplicables = st.multiselect(
                "Meses concretos del año en que se aplica (vacío = todos los meses)",
                options=MESES_NOMBRE, key=f"{key_ns}_meses_nuevo",
                help="Útil para algo que no es mensual, como un seguro que se paga 3 veces al año, "
                     "o una paga extra en junio y diciembre.",
            )
            importes_meses_nuevo = {}
            if meses_aplicables and modo == "fijo":
                st.caption("Importe de cada mes seleccionado (pueden ser distintos entre sí):")
                cols_meses = st.columns(len(meses_aplicables))
                for i, nombre_mes in enumerate(meses_aplicables):
                    num_mes = MESES_NOMBRE.index(nombre_mes) + 1
                    importes_meses_nuevo[num_mes] = cols_meses[i].number_input(
                        nombre_mes, min_value=0.0, step=0.01, format="%.2f",
                        key=f"{key_ns}_importe_mes_{num_mes}",
                    )

            with st.form(f"nuevo_{key_ns}", clear_on_submit=True):
                cuenta_id = selector_cuenta(cuentas, f"{key_ns}_cuenta")
                nombre = st.text_input(
                    "Nombre (ej. Nómina, Gimnasio, Ahorro automático)", key=f"{key_ns}_nombre_nuevo",
                )
                tipo = "gasto" if especial else tipo_fijo
                if especial:
                    st.caption("Se contabiliza como salida (gasto) de ese mes.")
                col3, col4 = st.columns(2)
                if modo == "porcentaje_ingreso":
                    importe = col3.number_input(
                        "Porcentaje de los ingresos del mes (%)", min_value=0.0, max_value=100.0,
                        step=0.5, format="%.1f",
                    )
                elif modo == "remanente":
                    col3.caption("Se calcula solo: ingresos menos gastos menos cuotas de deuda menos aportaciones de ahorro de ese mes.")
                    importe = 0.0
                elif modo == "variable":
                    importe = col3.number_input(
                        "Estimación inicial (€)", min_value=0.0, step=0.01, format="%.2f",
                        help="Se usa hasta que registres el primer mes real.",
                    )
                elif importes_meses_nuevo:
                    importe = col3.number_input(
                        "Importe el resto de meses (€)", min_value=0.0, step=0.01, format="%.2f",
                        help="Para los meses marcados arriba se usa el importe que has puesto en cada uno.",
                    )
                else:
                    importe = col3.number_input("Importe mensual (€)", min_value=0.0, step=0.01, format="%.2f")
                fecha_inicio = col4.date_input("Fecha de inicio", dt.date.today(), key=f"{key_ns}_fecha")
                meses_duracion = st.number_input(
                    "Duración en meses (opcional, 0 = indefinido)", min_value=0, step=1,
                    key=f"{key_ns}_duracion_nuevo",
                )
                if st.form_submit_button("Guardar"):
                    if cuenta_id is None:
                        st.warning("Selecciona una cuenta.")
                    elif not nombre.strip():
                        st.warning("Pon un nombre.")
                    else:
                        meses_num = [MESES_NOMBRE.index(m) + 1 for m in meses_aplicables] or None
                        importes_map = importes_meses_nuevo if importes_meses_nuevo else None
                        db.anadir_concepto(
                            cuenta_id, nombre.strip(), tipo, modo, grupo, importe,
                            fecha_inicio, meses_duracion or None, meses_num, importes_map,
                        )
                        st.success("Guardado")
                        for k in (
                            f"{key_ns}_nombre_nuevo", f"{key_ns}_meses_nuevo",
                            f"{key_ns}_plantilla_aplicada", f"{key_ns}_plantilla",
                        ):
                            st.session_state.pop(k, None)
                        st.rerun()

        conceptos = db.cargar_conceptos()
        conceptos = conceptos[conceptos["tipo"] == tipo_fijo] if not conceptos.empty else conceptos
        if conceptos.empty:
            st.caption(f"Aún no tienes {etiqueta}s recurrentes.")
        else:
            for row in conceptos.itertuples():
                icono = "🟢" if row.tipo == "ingreso" else "🟠"
                if row.modo == "porcentaje_ingreso":
                    resumen_importe = f"{row.importe:.1f}% de ingresos"
                elif row.modo == "remanente":
                    resumen_importe = "remanente"
                elif row.modo == "variable":
                    resumen_importe = f"variable (~{row.importe:,.0f} €)"
                else:
                    resumen_importe = f"{row.importe:,.0f} €"
                titulo = f"{icono} {row.nombre} · {row.cuenta} · {row.grupo or row.tipo} · {resumen_importe}"
                abierto, contenedor = tarjeta_desplegable(getattr(row, "logo", None), titulo, f"{key_ns}_{row.id}")
                if abierto:
                    with contenedor:
                        subir_logo("conceptos", row.id, f"{key_ns}_{row.id}")
                        if row.modo == "variable":
                            registrar_variable("concepto", row.id, f"{key_ns}_{row.id}")

                        e_modo = st.selectbox(
                            "Cómo se calcula el importe", options=modos_disponibles,
                            format_func=lambda k: MODO_LABELS[k],
                            index=modos_disponibles.index(row.modo) if row.modo in modos_disponibles else 0,
                            key=f"e_modo_{key_ns}_{row.id}",
                        )
                        e_especial = e_modo in ("porcentaje_ingreso", "remanente")
                        e_grupo = selector_categoria(f"e_{key_ns}_{row.id}", row.grupo)
                        meses_actuales = (
                            obtener_nombres_meses(row.meses_aplicables)
                            if row.meses_aplicables else []
                        )
                        e_meses_aplicables = st.multiselect(
                            "Meses concretos (vacío = todos)", options=MESES_NOMBRE,
                            default=meses_actuales, key=f"e_meses_{key_ns}_{row.id}",
                        )
                        importes_actuales = proyeccion._parse_importes_meses(getattr(row, "importes_meses", None))
                        e_importes_meses = {}
                        if e_meses_aplicables and e_modo == "fijo":
                            st.caption("Importe de cada mes seleccionado:")
                            cols_meses = st.columns(len(e_meses_aplicables))
                            for i, nombre_mes in enumerate(e_meses_aplicables):
                                num_mes = MESES_NOMBRE.index(nombre_mes) + 1
                                e_importes_meses[num_mes] = cols_meses[i].number_input(
                                    nombre_mes, min_value=0.0, step=0.01, format="%.2f",
                                    value=float(importes_actuales.get(num_mes, row.importe)),
                                    key=f"e_importe_mes_{key_ns}_{row.id}_{num_mes}",
                                )

                        with st.form(f"editar_{key_ns}_{row.id}"):
                            opciones_cuenta = list(cuentas["nombre"]) if not cuentas.empty else []
                            indice_cuenta = opciones_cuenta.index(row.cuenta) if row.cuenta in opciones_cuenta else 0
                            e_cuenta = st.selectbox(
                                "Cuenta", opciones_cuenta, index=indice_cuenta if opciones_cuenta else None,
                                key=f"e_cuenta_{key_ns}_{row.id}",
                            )
                            e_nombre = st.text_input("Nombre", value=row.nombre, key=f"e_nombre_{key_ns}_{row.id}")
                            e_tipo = "gasto" if e_especial else tipo_fijo
                            if e_especial:
                                st.caption("Se contabiliza como salida (gasto) de ese mes.")
                            c1, c2 = st.columns(2)
                            valor_importe = float(row.importe) if pd.notna(row.importe) else 0.0
                            if e_modo == "porcentaje_ingreso":
                                e_importe = c1.number_input(
                                    "Porcentaje de los ingresos del mes (%)", min_value=0.0, max_value=100.0,
                                    step=0.5, format="%.1f", value=valor_importe,
                                    key=f"e_importe_{key_ns}_{row.id}",
                                )
                            elif e_modo == "remanente":
                                c1.caption("Se calcula solo.")
                                e_importe = 0.0
                            elif e_importes_meses:
                                e_importe = c1.number_input(
                                    "Importe el resto de meses (€)", min_value=0.0, step=0.01, format="%.2f",
                                    value=valor_importe, key=f"e_importe_{key_ns}_{row.id}",
                                )
                            else:
                                e_importe = c1.number_input(
                                    "Importe mensual (€)", min_value=0.0, step=0.01, format="%.2f",
                                    value=valor_importe, key=f"e_importe_{key_ns}_{row.id}",
                                )
                            e_fecha_inicio = c2.date_input(
                                "Fecha de inicio", value=pd.Timestamp(row.fecha_inicio).date(),
                                key=f"e_fecha_{key_ns}_{row.id}",
                            )
                            e_meses_duracion = st.number_input(
                                "Duración en meses (0 = indefinido)", min_value=0, step=1,
                                value=int(row.meses_duracion) if pd.notna(row.meses_duracion) else 0,
                                key=f"e_duracion_{key_ns}_{row.id}",
                            )
                            if st.form_submit_button("Guardar cambios"):
                                cuenta_id = mapa_cuentas(cuentas).get(e_cuenta) if e_cuenta else None
                                meses_num = [MESES_NOMBRE.index(m) + 1 for m in e_meses_aplicables] or None
                                importes_map = e_importes_meses if e_importes_meses else None
                                db.actualizar_concepto(
                                    row.id, cuenta_id, e_nombre.strip(), e_tipo, e_modo, e_grupo, e_importe,
                                    e_fecha_inicio, e_meses_duracion or None, meses_num, importes_map,
                                )
                                st.success("Guardado")
                                st.rerun()

                        c3, c4 = st.columns([1, 1], vertical_alignment="bottom")
                        activo = c3.checkbox("Activo", value=bool(row.activo), key=f"activo_{key_ns}_{row.id}")
                        if activo != bool(row.activo):
                            db.actualizar_concepto_activo(row.id, activo)
                            st.rerun()
                        if c4.button("Eliminar", key=f"del_{key_ns}_{row.id}"):
                            db.eliminar_concepto(row.id)
                            st.rerun()

    with tabs[2]:
        seccion_conceptos("ingreso", "ingreso")

    with tabs[3]:
        seccion_conceptos("gasto", "gastorec")

    with tabs[4]:
        cuentas = db.cargar_cuentas()
        conceptos_var = db.cargar_conceptos()
        conceptos_var = conceptos_var[conceptos_var["modo"] == "variable"] if not conceptos_var.empty else conceptos_var
        deudas_todas = db.cargar_deudas()

        opciones_vinculo = {"Ninguno (movimiento suelto)": None}
        for c in conceptos_var.itertuples():
            opciones_vinculo[f"Concepto: {c.nombre} ({c.cuenta})"] = ("concepto", c.id)
        for d in deudas_todas.itertuples():
            opciones_vinculo[f"Deuda: {d.nombre} ({d.cuenta or 'sin cuenta'})"] = ("deuda", d.id)

        with st.expander("➕ Añadir movimiento", expanded=False):
            vinculo_label = st.selectbox(
                "Vincular a (opcional)", list(opciones_vinculo.keys()), key="mov_vinculo",
                help="Si lo vinculas a una deuda, el importe se descuenta del pendiente de esa deuda "
                     "(aunque sea de cuota fija). Si lo vinculas a un concepto variable (p.ej. una nómina), "
                     "se registra como el valor de ese mes.",
            )
            vinculo = opciones_vinculo[vinculo_label]
            if vinculo is None:
                categoria = selector_categoria("movimiento_nuevo")
            with st.form("nuevo_movimiento", clear_on_submit=True):
                cuenta_id = selector_cuenta(cuentas, "movimiento_cuenta", opcional=True)
                fecha = st.date_input("Fecha", dt.date.today(), key="mov_fecha")
                if vinculo is None:
                    concepto = st.text_input("Concepto")
                else:
                    concepto = vinculo_label
                    tipo_vinculo, _ = vinculo
                    if tipo_vinculo == "deuda":
                        st.caption(f"El importe se descontará del pendiente de: {vinculo_label}")
                    else:
                        st.caption(f"Se registrará como el valor de ese mes para: {vinculo_label}")
                importe = st.number_input(
                    "Importe (€)", step=0.01, format="%.2f",
                    help="Negativo = gasto, positivo = ingreso",
                )
                if st.form_submit_button("Guardar"):
                    if vinculo is None and not concepto.strip():
                        st.warning("Pon un concepto.")
                    elif importe == 0:
                        st.warning("El importe no puede ser 0.")
                    else:
                        if vinculo is not None:
                            tipo_padre, padre_id = vinculo
                            periodo = pd.Timestamp(fecha).to_period("M")
                            valor = abs(importe) if tipo_padre == "deuda" else importe
                            db.registrar_valor_mensual(tipo_padre, padre_id, str(periodo), valor)
                            if tipo_padre == "deuda":
                                deudas_actual = db.cargar_deudas()
                                fila = deudas_actual[deudas_actual["id"] == padre_id].iloc[0]
                                db.actualizar_deuda_pendiente(padre_id, fila.importe_pendiente - valor)
                        else:
                            db.anadir_movimiento(cuenta_id, fecha, concepto.strip(), importe, categoria)
                        st.success("Guardado")
                        st.rerun()

        movimientos = db.cargar_movimientos()
        if movimientos.empty:
            st.caption("Aún no hay movimientos.")
        else:
            st.dataframe(
                movimientos[["fecha", "cuenta", "concepto", "importe", "categoria"]],
                hide_index=True, width="stretch",
            )
            with st.expander("🗑️ Eliminar un movimiento"):
                opciones = {
                    f"#{row.id} · {row.fecha.date()} · {row.concepto} · {row.importe:.2f} €": row.id
                    for row in movimientos.itertuples()
                }
                seleccion = st.selectbox("Movimiento", list(opciones.keys()))
                if st.button("Eliminar"):
                    db.eliminar_movimiento(opciones[seleccion])
                    st.success("Eliminado")
                    st.rerun()

    # -------------------------------------------------- Ahorros e inversiones --
    with tabs[5]:
        cuentas = db.cargar_cuentas()
        with st.expander("➕ Añadir meta de ahorro/inversión", expanded=False):
            tipo_nuevo = st.radio("Tipo", ["ahorro", "inversión"], horizontal=True, key="ahorro_tipo_nuevo")
            instrumento_nuevo = st.selectbox("Instrumento", INSTRUMENTOS, key="ahorro_instrumento_nuevo")
            with st.form("nuevo_ahorro", clear_on_submit=True):
                cuenta_id = selector_cuenta(cuentas, "ahorro_cuenta", opcional=True)
                nombre = st.text_input("Nombre (ej. Fondo de emergencia, Cuenta Trade Republic)")
                c1, c2 = st.columns(2)
                aportado = c1.number_input(
                    "Aportado en total (€)", min_value=0.0, step=0.01, format="%.2f",
                    help="Lo que has metido tú en total (principal), sin contar la revalorización.",
                )
                actual = c2.number_input(
                    "Valor actual (€)", min_value=0.0, step=0.01, format="%.2f",
                    help="Lo que vale hoy. La diferencia con lo aportado es el beneficio o pérdida.",
                )
                c3, c4 = st.columns(2)
                comisiones = c3.number_input("Comisiones pagadas (€)", min_value=0.0, step=0.01, format="%.2f")
                objetivo = c4.number_input("Objetivo (€, opcional)", min_value=0.0, step=0.01, format="%.2f")
                aportacion_mensual = st.number_input(
                    "Aportación mensual (€, opcional)", min_value=0.0, step=0.01, format="%.2f",
                )
                fecha_objetivo = st.date_input("Fecha objetivo (opcional)", value=None)
                if st.form_submit_button("Guardar"):
                    if not nombre.strip():
                        st.warning("Pon un nombre.")
                    else:
                        db.anadir_ahorro(
                            cuenta_id, nombre.strip(), tipo_nuevo, instrumento_nuevo,
                            objetivo, aportado, actual, comisiones,
                            aportacion_mensual or None, fecha_objetivo,
                        )
                        st.success("Guardado")
                        st.rerun()

        ahorros = db.cargar_ahorros()
        if ahorros.empty:
            st.caption("Aún no tienes metas de ahorro ni inversiones.")
        else:
            for row in ahorros.itertuples():
                beneficio = row.actual - row.aportado - row.comisiones
                rentabilidad = (beneficio / row.aportado * 100) if row.aportado else None
                titulo = f"{row.nombre} · {row.instrumento or row.tipo} · {row.actual:,.0f} €"
                abierto, contenedor = tarjeta_desplegable(getattr(row, "logo", None), titulo, f"ahorro_{row.id}")
                if abierto:
                    with contenedor:
                        subir_logo("ahorros", row.id, f"ahorro_{row.id}")

                        delta_txt = f"{beneficio:,.2f} €"
                        if rentabilidad is not None:
                            delta_txt += f" ({rentabilidad:+.1f} %)"
                        st.metric("Valor actual", f"{row.actual:,.2f} €", delta=delta_txt)

                        if row.objetivo:
                            progreso = row.actual / row.objetivo if row.objetivo else 0
                            st.progress(min(max(progreso, 0.0), 1.0))
                            st.caption(f"Objetivo: {row.objetivo:,.2f} €")

                        with st.form(f"editar_ahorro_{row.id}"):
                            opciones_cuenta = ["(sin cuenta)"] + (list(cuentas["nombre"]) if not cuentas.empty else [])
                            indice_cuenta = opciones_cuenta.index(row.cuenta) if row.cuenta in opciones_cuenta else 0
                            e_cuenta = st.selectbox(
                                "Cuenta", opciones_cuenta, index=indice_cuenta, key=f"e_cuenta_ahorro_{row.id}",
                            )
                            e_nombre = st.text_input("Nombre", value=row.nombre, key=f"e_nombre_ahorro_{row.id}")
                            c1, c2 = st.columns(2)
                            e_tipo = c1.radio(
                                "Tipo", ["ahorro", "inversión"], horizontal=True,
                                index=0 if row.tipo == "ahorro" else 1, key=f"e_tipo_ahorro_{row.id}",
                            )
                            indice_instr = INSTRUMENTOS.index(row.instrumento) if row.instrumento in INSTRUMENTOS else len(INSTRUMENTOS) - 1
                            e_instrumento = c2.selectbox(
                                "Instrumento", INSTRUMENTOS, index=indice_instr, key=f"e_instrumento_ahorro_{row.id}",
                            )
                            c3, c4 = st.columns(2)
                            e_aportado = c3.number_input(
                                "Aportado en total (€)", min_value=0.0, step=0.01, format="%.2f",
                                value=float(row.aportado), key=f"e_aportado_ahorro_{row.id}",
                            )
                            e_actual = c4.number_input(
                                "Valor actual (€)", min_value=0.0, step=0.01, format="%.2f",
                                value=float(row.actual), key=f"e_actual_ahorro_{row.id}",
                            )
                            c5, c6 = st.columns(2)
                            e_comisiones = c5.number_input(
                                "Comisiones pagadas (€)", min_value=0.0, step=0.01, format="%.2f",
                                value=float(row.comisiones), key=f"e_comisiones_ahorro_{row.id}",
                            )
                            e_objetivo = c6.number_input(
                                "Objetivo (€, opcional)", min_value=0.0, step=0.01, format="%.2f",
                                value=float(row.objetivo), key=f"e_objetivo_ahorro_{row.id}",
                            )
                            e_aportacion = st.number_input(
                                "Aportación mensual (€, opcional)", min_value=0.0, step=0.01, format="%.2f",
                                value=float(row.aportacion_mensual) if pd.notna(row.aportacion_mensual) else 0.0,
                                key=f"e_aportacion_ahorro_{row.id}",
                            )
                            e_fecha_objetivo = st.date_input(
                                "Fecha objetivo (opcional)",
                                value=pd.Timestamp(row.fecha_objetivo).date() if row.fecha_objetivo else None,
                                key=f"e_fechaobj_ahorro_{row.id}",
                            )
                            if st.form_submit_button("Guardar cambios"):
                                cuenta_id = mapa_cuentas(cuentas).get(e_cuenta) if e_cuenta != "(sin cuenta)" else None
                                db.actualizar_ahorro(
                                    row.id, cuenta_id, e_nombre.strip(), e_tipo, e_instrumento,
                                    e_objetivo, e_aportado, e_actual, e_comisiones,
                                    e_aportacion or None, e_fecha_objetivo,
                                )
                                st.success("Guardado")
                                st.rerun()

                        c7, c8 = st.columns([1, 1], vertical_alignment="bottom")
                        activa = c7.checkbox("Activa", value=bool(row.activa), key=f"activa_ahorro_{row.id}")
                        if activa != bool(row.activa):
                            db.actualizar_ahorro_activa(row.id, activa)
                            st.rerun()
                        if c8.button("Eliminar", key=f"del_ahorro_{row.id}"):
                            db.eliminar_ahorro(row.id)
                            st.rerun()

    # ------------------------------------------------------------- Planes --
    with tabs[6]:
        with st.expander("➕ Añadir plan", expanded=False):
            with st.form("nuevo_plan", clear_on_submit=True):
                nombre = st.text_input("Nombre (ej. Comprar casa)")
                descripcion = st.text_input("Descripción breve")
                importe_objetivo = st.number_input("Importe necesario (€)", min_value=0.0, step=0.01, format="%.2f")
                fecha_objetivo = st.date_input("Fecha objetivo (opcional)", value=None, key="plan_fecha")
                notas = st.text_area("Notas")
                if st.form_submit_button("Guardar"):
                    if not nombre.strip():
                        st.warning("Pon un nombre.")
                    else:
                        db.anadir_plan(nombre.strip(), descripcion, importe_objetivo, fecha_objetivo, notas)
                        st.success("Guardado")
                        st.rerun()

        planes = db.cargar_planes()
        if planes.empty:
            st.caption("Aún no tienes planes a largo plazo.")
        else:
            for row in planes.itertuples():
                titulo = f"{row.nombre} · {row.importe_objetivo:,.0f} €"
                with st.expander(titulo):
                    with st.form(f"editar_plan_{row.id}"):
                        e_nombre = st.text_input("Nombre", value=row.nombre, key=f"e_nombre_plan_{row.id}")
                        e_descripcion = st.text_input(
                            "Descripción breve", value=row.descripcion or "", key=f"e_desc_plan_{row.id}",
                        )
                        c1, c2 = st.columns(2)
                        e_importe = c1.number_input(
                            "Importe necesario (€)", min_value=0.0, step=0.01, format="%.2f",
                            value=float(row.importe_objetivo), key=f"e_importe_plan_{row.id}",
                        )
                        e_fecha_objetivo = c2.date_input(
                            "Fecha objetivo (opcional)",
                            value=pd.Timestamp(row.fecha_objetivo).date() if row.fecha_objetivo else None,
                            key=f"e_fecha_plan_{row.id}",
                        )
                        e_notas = st.text_area("Notas", value=row.notas or "", key=f"e_notas_plan_{row.id}")
                        if st.form_submit_button("Guardar cambios"):
                            db.actualizar_plan(
                                row.id, e_nombre.strip(), e_descripcion, e_importe, e_fecha_objetivo, e_notas,
                            )
                            st.success("Guardado")
                            st.rerun()

                    if st.button("Eliminar plan", key=f"del_plan_{row.id}"):
                        db.eliminar_plan(row.id)
                        st.rerun()

    # --------------------------------------------------------- Proyección --
    with tabs[7]:
        cuentas = db.cargar_cuentas()
        if cuentas.empty:
            st.caption("Crea al menos una cuenta para ver la proyección.")
        else:
            hoy = pd.Timestamp.today().normalize()
            mes_actual = hoy.to_period("M")
            col1, col2 = st.columns(2)
            meses_atras = col1.number_input("Meses hacia atrás", min_value=0, max_value=36, value=1)
            meses_adelante = col2.number_input("Meses hacia adelante", min_value=1, max_value=48, value=12)
            periodos = proyeccion.meses_entre(mes_actual - meses_atras, mes_actual + meses_adelante)

            conceptos = db.cargar_conceptos()
            deudas = db.cargar_deudas()
            ahorros = db.cargar_ahorros()
            movimientos = db.cargar_movimientos()
            valores = db.cargar_valores_mensuales()
            detalle = proyeccion.detalle_mensual(conceptos, deudas, ahorros, movimientos, valores, periodos)

            if detalle.empty:
                st.caption("Añade conceptos recurrentes, deudas o ahorros con aportación para ver la proyección.")
            else:
                pivot = proyeccion.tabla_proyeccion_pivot(detalle)
                st.dataframe(proyeccion.estilo_proyeccion(pivot, detalle), width="stretch")


# ===================================================================== Admin ====

elif pagina == "Admin" and auth.es_superadmin():
    st.title("Administración")
    tab_users, tab_log = st.tabs(["Usuarios", "Accesos"])

    with tab_users:
        with st.form("nuevo_usuario", clear_on_submit=True):
            st.markdown("**Crear usuario**")
            c1, c2 = st.columns(2)
            nuevo_email = c1.text_input("Email")
            nuevo_nombre = c2.text_input("Nombre")
            if st.form_submit_button("Crear usuario", type="primary"):
                em = (nuevo_email or "").strip().lower()
                if "@" not in em:
                    st.error("Email no válido.")
                elif db.obtener_usuario(em):
                    st.warning("Ese usuario ya existe.")
                else:
                    db.crear_usuario(em, nuevo_nombre.strip(), "usuario")
                    st.success(f"Usuario {em} creado. Creará su contraseña la primera vez que entre.")

        st.markdown("**Usuarios**")
        for u in db.cargar_usuarios().itertuples():
            with st.container(border=True):
                c1, c2, c3 = st.columns([4, 3, 2])
                c1.markdown(f"**{u.nombre or '—'}**  \n{u.email}")
                tiene_pw = isinstance(u.password_hash, str) and u.password_hash
                c2.caption(
                    f"Rol: {u.rol} · {'🟢 Activo' if u.activo else '🔴 Inactivo'}\n\n"
                    f"{'🔑 Con contraseña' if tiene_pw else '⏳ Sin contraseña'}"
                )
                if u.rol != "superadmin":
                    if c3.button("Desactivar" if u.activo else "Activar", key=f"tog_{u.email}", use_container_width=True):
                        db.set_usuario_activo(u.email, not bool(u.activo))
                        st.rerun()
                    if c3.button("Eliminar", key=f"del_u_{u.email}", use_container_width=True):
                        db.eliminar_usuario(u.email)
                        st.rerun()

    with tab_log:
        st.markdown("**Registro de accesos**")
        accesos = db.cargar_accesos(200)
        if accesos.empty:
            st.caption("Sin accesos registrados todavía.")
        else:
            st.dataframe(
                accesos[["ts", "email", "evento", "detalle"]].rename(
                    columns={"ts": "Fecha (UTC)", "email": "Email", "evento": "Evento", "detalle": "Detalle"}
                ),
                hide_index=True, width="stretch",
            )
