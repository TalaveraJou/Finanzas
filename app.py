import base64
import datetime as dt
import io
import math
from pathlib import Path

import pandas as pd
import plotly.express as px
import streamlit as st
from PIL import Image
from streamlit_option_menu import option_menu

from finanzas import auth, db, estilo, proyeccion
LOGO_SIZE = 64

st.set_page_config(page_title="Finanzas", page_icon="💶", layout="wide", initial_sidebar_state="collapsed")
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

with st.container(key="app_header"):
    c_logo, c_logout = st.columns([5, 1])
    with c_logo:
        st.markdown(
            estilo.cabecera_app("assets/logo-login.svg", usuario.get("nombre") or usuario["email"]),
            unsafe_allow_html=True,
        )
    with c_logout:
        if st.button("⎋", key="logout_btn_header", help="Cerrar sesión"):
            auth.cerrar_sesion()

opciones = ["Inicio", "Flujo de Caja", "Inversiones", "Más"]
iconos = ["speedometer2", "arrow-left-right", "graph-up-arrow", "three-dots"]

MAS_OPCIONES = {"Metas": "Objetivos y Metas", "Ahorro": "Ahorros e Inversiones", "Cuentas": "Cuentas"}
if auth.es_superadmin():
    MAS_OPCIONES["Admin"] = "Admin"

with st.container(key="bottom_nav"):
    seleccion_nav = option_menu(
        menu_title=None,
        options=opciones,
        icons=iconos,
        default_index=0,
        orientation="horizontal",
        styles={
            "container": {
                "padding": "4px 0", "background-color": "transparent", "box-shadow": "none",
                "display": "flex", "flex-wrap": "nowrap", "justify-content": "space-around",
                "width": "100%",
            },
            "icon": {"font-size": "20px", "margin-bottom": "2px"},
            "nav-link": {
                "display": "flex", "flex-direction": "column", "align-items": "center",
                "justify-content": "center", "gap": "1px", "font-size": "10.5px", "font-weight": "600",
                "padding": "6px 4px 4px", "margin": "0", "border-radius": "12px", "flex": "1 1 0",
                "min-width": "0", "max-width": "none",
                "color": estilo.MUTED, "white-space": "nowrap", "overflow": "hidden",
                "text-overflow": "ellipsis",
            },
            "nav-link-selected": {"background-color": "transparent", "color": estilo.ACCENT},
        },
    )

if seleccion_nav == "Más":
    st.session_state.setdefault("mas_sel", "Metas")
    with st.container(key="mas_subnav"):
        elegido = st.segmented_control(
            "Más", list(MAS_OPCIONES.keys()), default=st.session_state["mas_sel"],
            label_visibility="collapsed", key="mas_segmented",
        )
    if elegido:
        st.session_state["mas_sel"] = elegido
    pagina = MAS_OPCIONES[st.session_state["mas_sel"]]
else:
    pagina = seleccion_nav


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
    if not isinstance(logo, str) or not logo:
        return False
    if logo.startswith("data:image"):
        return True
    try:
        return Path(logo).exists()
    except OSError:
        return False


def _mostrar_logo(logo: str, width: int) -> None:
    """st.image no admite data URIs directamente: si lo es, se decodifica a
    bytes primero; si es una ruta de archivo local (formato antiguo), se
    pasa tal cual."""
    if logo.startswith("data:image"):
        cabecera, datos = logo.split(",", 1)
        st.image(base64.b64decode(datos), width=width)
    else:
        st.image(logo, width=width)


def _logo_a_data_uri(archivo) -> str:
    """Recorta/escala el logo a un cuadrado de LOGO_SIZE x LOGO_SIZE y lo devuelve
    como data URI base64, para guardarlo directamente en la base de datos (así
    funciona igual en local y en cualquier despliegue, sin depender de rutas
    de disco que no se comparten entre entornos)."""
    imagen = Image.open(archivo).convert("RGBA")
    ancho, alto = imagen.size
    lado = min(ancho, alto)
    recorte = imagen.crop((
        (ancho - lado) // 2, (alto - lado) // 2,
        (ancho - lado) // 2 + lado, (alto - lado) // 2 + lado,
    ))
    recorte = recorte.resize((LOGO_SIZE, LOGO_SIZE), Image.LANCZOS)
    buffer = io.BytesIO()
    recorte.save(buffer, format="PNG")
    datos = base64.b64encode(buffer.getvalue()).decode()
    return f"data:image/png;base64,{datos}"


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
            data_uri = _logo_a_data_uri(archivo)
            db.actualizar_logo(tabla, id_, data_uri)
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
                _mostrar_logo(logo_path, width=40)
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

        # Serie histórica real (meses ya transcurridos hasta hoy, sin proyectar
        # hacia el futuro) — es la única fuente de los KPIs y gráficos de esta
        # página, para que nunca muestren datos inventados.
        periodos_hist = proyeccion.meses_entre(mes_actual - 23, mes_actual)
        detalle_hist = proyeccion.detalle_mensual(conceptos, deudas, ahorros, movimientos, valores, periodos_hist)
        detalle = detalle_hist

        detalle_mes = detalle[detalle["periodo"] == mes_actual] if not detalle.empty else detalle
        ingresos_mes = detalle_mes.loc[detalle_mes["tipo"] == "ingreso", "importe"].sum()
        gastos_mes = -detalle_mes.loc[detalle_mes["tipo"] == "gasto", "importe"].sum()
        deuda_mes = -detalle_mes.loc[detalle_mes["tipo"] == "deuda", "importe"].sum()
        ahorro_mes = -detalle_mes.loc[detalle_mes["tipo"] == "ahorro", "importe"].sum()
        balance_mes = ingresos_mes - gastos_mes - deuda_mes - ahorro_mes

        deuda_pendiente = deudas.loc[deudas["activa"], "importe_pendiente"].sum() if not deudas.empty else 0.0
        ahorro_total = ahorros["actual"].sum() if not ahorros.empty else 0.0
        patrimonio_neto = ahorro_total - deuda_pendiente

        logos_cuenta = dict(zip(cuentas["nombre"], cuentas.get("logo", pd.Series(dtype=str))))

        # ---- Cabecera de saludo ----
        # El cambio de patrimonio "este mes" es el balance real del mes (ingresos
        # menos gastos, deuda y ahorro ya registrados), no una proyección.
        nombre_usuario = (auth.usuario_actual() or {}).get("nombre") or "ahí"
        delta_pat_eur = balance_mes
        patrimonio_anterior = patrimonio_neto - balance_mes
        delta_pat_pct = (delta_pat_eur / abs(patrimonio_anterior) * 100) if patrimonio_anterior else 0.0
        clase_delta = "pos" if delta_pat_eur >= 0 else "neg"
        signo = "+" if delta_pat_eur >= 0 else ""
        st.markdown(
            f'<div class="dash-greet">Hola {nombre_usuario}, tu patrimonio neto '
            f'{"creció" if delta_pat_eur >= 0 else "bajó"} un <span class="{clase_delta}">{signo}{delta_pat_pct:.1f}%</span> este mes</div>'
            f'<div class="dash-sub">Balance de {MESES_NOMBRE[mes_actual.month - 1]}: {balance_mes:,.0f} € · '
            f'{signo}{delta_pat_eur:,.0f} € frente al mes anterior</div>',
            unsafe_allow_html=True,
        )

        # ---- KPIs principales ----
        liquidez = ahorros.loc[ahorros["tipo"] == "ahorro", "actual"].sum() if not ahorros.empty else 0.0
        cartera_inversion = ahorros.loc[ahorros["tipo"] == "inversión", "actual"].sum() if not ahorros.empty else 0.0
        tasa_ahorro = (ahorro_mes / ingresos_mes * 100) if ingresos_mes else 0.0
        meta_ahorro = 40.0

        kpis_html = (
            estilo.tarjeta_kpi_pro(
                "◆", "Patrimonio neto total", f"{patrimonio_neto:,.0f} €",
                f"{'↑' if delta_pat_eur >= 0 else '↓'} {signo}{delta_pat_pct:.1f}% · {signo}{delta_pat_eur:,.0f} € este mes",
                clase_delta,
            )
            + estilo.tarjeta_kpi_pro("💶", "Liquidez disponible", f"{liquidez:,.0f} €", "Ahorro en cuentas remuneradas y depósitos")
            + estilo.tarjeta_kpi_pro("📈", "Cartera de inversión", f"{cartera_inversion:,.0f} €", "Fondos, ETF, acciones y cripto")
            + estilo.tarjeta_kpi_pro(
                "🐷", "Tasa de ahorro mensual", f"{tasa_ahorro:,.1f} %",
                f"Meta: {meta_ahorro:.0f} %", progreso=tasa_ahorro / meta_ahorro if meta_ahorro else 0,
            )
        )
        st.markdown(f'<div class="kpi-row">{kpis_html}</div>', unsafe_allow_html=True)

        # ---- Evolución + distribución de activos ----
        resumen_hist = proyeccion.tabla_resumen_mensual(detalle_hist)
        periodos_hist_str = [str(p) for p in periodos_hist]
        resumen_hist = (
            resumen_hist.set_index("periodo").reindex(periodos_hist_str, fill_value=0).reset_index(names="periodo")
            if not resumen_hist.empty else pd.DataFrame({"periodo": periodos_hist_str, "balance": 0})
        )
        s_bal_hist = resumen_hist["balance"].tolist()
        s_pat_hist = list(pd.Series(s_bal_hist, dtype="float64").cumsum())

        col_izq, col_der = st.columns([2, 1])
        with col_izq:
            with st.container(border=True):
                c1, c2 = st.columns([2, 1], vertical_alignment="center")
                c1.markdown("**Evolución y rendimiento acumulado**")
                rango = c2.segmented_control(
                    "Rango", ["3M", "6M", "1A", "Histórico"], default="1A",
                    key="rango_evolucion", label_visibility="collapsed",
                )
                largo = {"3M": 3, "6M": 6, "1A": 12, "Histórico": len(s_bal_hist)}.get(rango, 12)
                serie_rango = s_pat_hist[-largo:] if largo else s_pat_hist
                periodos_rango = periodos_hist_str[-largo:] if largo else periodos_hist_str
                if serie_rango:
                    fig_evo = px.area(
                        x=periodos_rango or list(range(len(serie_rango))), y=serie_rango,
                        labels={"x": "Mes", "y": "€"},
                    )
                    fig_evo.update_traces(line_color=estilo.ACCENT, fillcolor="rgba(37,99,235,0.12)")
                    estilo.aplicar_tema_plotly(fig_evo)
                    fig_evo.update_xaxes(type="category")
                    fig_evo.update_layout(height=280)
                    st.plotly_chart(fig_evo, width="stretch")

                    aportado_acum = ahorros["aportado"].sum() if not ahorros.empty else 0.0
                    plusvalia_neta = (
                        (ahorros["actual"] - ahorros["aportado"] - ahorros["comisiones"]).sum()
                        if not ahorros.empty else 0.0
                    )
                    pico = serie_rango[0]
                    peor_caida = 0.0
                    for v in serie_rango:
                        pico = max(pico, v)
                        if pico:
                            peor_caida = min(peor_caida, (v - pico) / abs(pico) * 100)
                    st.markdown(
                        estilo.pie_estadisticas([
                            ("Aportado acumulado", f"{aportado_acum:,.0f} €"),
                            ("Plusvalía neta", f"{plusvalia_neta:,.0f} €"),
                            ("Máximo retroceso", f"{peor_caida:.1f} %"),
                        ]),
                        unsafe_allow_html=True,
                    )
                else:
                    st.caption("Añade cuentas, conceptos recurrentes o movimientos para ver la evolución.")
        with col_der:
            with st.container(border=True):
                st.markdown("**Distribución de activos**")
                if not ahorros.empty and ahorros["actual"].sum() > 0:
                    por_instrumento = ahorros.groupby("instrumento")["actual"].sum().sort_values(ascending=False)
                    total_activos = por_instrumento.sum()
                    fig_dist = px.pie(
                        names=por_instrumento.index, values=por_instrumento.values, hole=0.62,
                    )
                    estilo.aplicar_tema_plotly(fig_dist)
                    fig_dist.update_layout(height=200, showlegend=False, margin=dict(l=0, r=0, t=0, b=0))
                    fig_dist.update_traces(textinfo="none")
                    st.plotly_chart(fig_dist, width="stretch")
                    colores_ciclo = estilo.PALETA_CATEGORIAS
                    leyenda = "".join(
                        estilo.fila_leyenda(
                            colores_ciclo[i % len(colores_ciclo)], (instr or "Sin clasificar"), valor,
                            (valor / total_activos * 100) if total_activos else 0,
                        )
                        for i, (instr, valor) in enumerate(por_instrumento.items())
                    )
                    st.markdown(leyenda, unsafe_allow_html=True)
                else:
                    st.caption("Añade ahorros o inversiones para ver la distribución.")

        # ---- Movimientos recientes + avisos ----
        col_izq, col_der = st.columns([2, 1])
        with col_izq:
            st.markdown("**Últimos movimientos relevantes**")
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
            st.markdown("**Estado y próximos hitos**")
            emergencia = ahorros[ahorros["nombre"].str.contains("emergencia", case=False, na=False)] if not ahorros.empty else ahorros
            if not emergencia.empty and gastos_mes:
                fila_emg = emergencia.iloc[0]
                meses_cubiertos = fila_emg["actual"] / gastos_mes
                st.markdown(
                    estilo.tarjeta_info(
                        "ok" if meses_cubiertos >= 3 else "info", "Salud fiduciaria",
                        "Fondo de emergencia" + (" cubierto" if meses_cubiertos >= 3 else ""),
                        f"Tu liquidez de \"{fila_emg['nombre']}\" cubre {meses_cubiertos:.1f} meses de gastos actuales.",
                    ),
                    unsafe_allow_html=True,
                )
            aportacion_prog = ahorros[ahorros["aportacion_mensual"].notna() & (ahorros["aportacion_mensual"] > 0)] if not ahorros.empty else ahorros
            if not aportacion_prog.empty:
                fila_ap = aportacion_prog.iloc[0]
                st.markdown(
                    estilo.tarjeta_info(
                        "info", "Próximo hito", "Aportación periódica programada",
                        f"\"{fila_ap['nombre']}\" recibirá {fila_ap['aportacion_mensual']:,.0f} €/mes de forma automática.",
                    ),
                    unsafe_allow_html=True,
                )
            if emergencia.empty and aportacion_prog.empty:
                st.caption("Sin avisos por ahora.")

        tab_resumen, tab_mes, tab_graficos, tab_deudas = st.tabs(["Por cuenta", "Por mes", "Gráficos", "Deudas activas"])

        with tab_resumen:
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
                    resumen = proyeccion.tabla_resumen_mensual(detalle).tail(12)
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
                    fig_linea.update_traces(line_color=estilo.VERDE, fillcolor="rgba(16,185,129,0.15)")
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

# ===================================================================== Flujo de Caja ====

elif pagina == "Flujo de Caja":
    st.title("Flujo de Caja")

    cuentas = db.cargar_cuentas()
    conceptos = db.cargar_conceptos()
    deudas = db.cargar_deudas()
    ahorros = db.cargar_ahorros()
    movimientos = db.cargar_movimientos()
    valores = db.cargar_valores_mensuales()
    presupuestos = db.cargar_presupuestos()

    if cuentas.empty:
        st.info("Empieza creando una cuenta en **Cuentas y Movimientos → Cuentas**.")
    else:
        hoy = pd.Timestamp.today().normalize()
        mes_actual = hoy.to_period("M")
        st.session_state.setdefault("flujo_offset", 0)

        c_prev, c_mid, c_next = st.columns([1, 4, 1])
        if c_prev.button("←", key="flujo_prev"):
            st.session_state["flujo_offset"] -= 1
            st.rerun()
        periodo_sel = mes_actual + st.session_state["flujo_offset"]
        c_mid.markdown(
            f"<div style='text-align:center;font-weight:700;font-size:1.1rem;'>"
            f"{MESES_NOMBRE[periodo_sel.month - 1]} {periodo_sel.year}</div>",
            unsafe_allow_html=True,
        )
        if c_next.button("→", key="flujo_next"):
            st.session_state["flujo_offset"] += 1
            st.rerun()

        periodos = proyeccion.meses_entre(periodo_sel, periodo_sel)
        detalle = proyeccion.detalle_mensual(conceptos, deudas, ahorros, movimientos, valores, periodos)
        detalle_mes = detalle[detalle["periodo"] == periodo_sel] if not detalle.empty else detalle

        ingresos_mes = detalle_mes.loc[detalle_mes["tipo"] == "ingreso", "importe"].sum()
        gastos_mes = detalle_mes.loc[detalle_mes["tipo"] == "gasto", "importe"].abs().sum()
        deuda_mes = detalle_mes.loc[detalle_mes["tipo"] == "deuda", "importe"].abs().sum()
        ahorro_mes = detalle_mes.loc[detalle_mes["tipo"] == "ahorro", "importe"].abs().sum()
        flujo_neto = ingresos_mes - gastos_mes - deuda_mes - ahorro_mes
        tasa_ahorro = (ahorro_mes / ingresos_mes * 100) if ingresos_mes else 0.0

        kpis_html = (
            estilo.tarjeta_kpi_pro(
                "⬆️", "Ingresos consolidados", f"{ingresos_mes:,.0f} €",
                f"{int((detalle_mes['tipo'] == 'ingreso').sum())} partidas este mes",
            )
            + estilo.tarjeta_kpi_pro(
                "⬇️", "Gastos devengados", f"{gastos_mes:,.0f} €",
                f"{int((detalle_mes['tipo'] == 'gasto').sum())} partidas este mes",
            )
            + estilo.tarjeta_kpi_pro(
                "⚖️", "Flujo de caja neto", f"{flujo_neto:,.0f} €",
                f"Tasa de ahorro: {tasa_ahorro:.1f} %", "pos" if flujo_neto >= 0 else "neg",
            )
        )
        st.markdown(f'<div class="kpi-row">{kpis_html}</div>', unsafe_allow_html=True)

        col_izq, col_der = st.columns([3, 2])
        with col_izq:
            with st.container(border=True):
                st.markdown("**Ejecución presupuestaria por partida**")
                if presupuestos.empty:
                    st.caption(
                        "Fija límites por categoría en **Cuentas y Movimientos → Presupuestos** "
                        "para ver aquí la ejecución."
                    )
                else:
                    gastos_por_cat = (
                        detalle_mes[detalle_mes["tipo"] == "gasto"].groupby("grupo")["importe"].sum().abs()
                        if not detalle_mes.empty else pd.Series(dtype=float)
                    )
                    filas_presu = "".join(
                        estilo.fila_presupuesto(
                            row.categoria, gastos_por_cat.get(row.categoria, 0.0), row.limite_mensual,
                        )
                        for row in presupuestos.itertuples()
                    )
                    st.markdown(filas_presu, unsafe_allow_html=True)
        with col_der:
            with st.container(border=True):
                st.markdown("**Distribución del flujo**")
                remanente = max(flujo_neto, 0.0)
                etiquetas = ["Inversión y ahorro", "Deudas", "Gastos variables", "Remanente"]
                valores_dist = [ahorro_mes, deuda_mes, gastos_mes, remanente]
                total_dist = sum(v for v in valores_dist if v > 0)
                if total_dist > 0:
                    fig_dist = px.pie(names=etiquetas, values=valores_dist, hole=0.62)
                    estilo.aplicar_tema_plotly(fig_dist)
                    fig_dist.update_layout(height=200, showlegend=False, margin=dict(l=0, r=0, t=0, b=0))
                    fig_dist.update_traces(textinfo="none")
                    st.plotly_chart(fig_dist, width="stretch")
                    colores_ciclo = estilo.PALETA_CATEGORIAS
                    leyenda = "".join(
                        estilo.fila_leyenda(
                            colores_ciclo[i % len(colores_ciclo)], etq, val,
                            (val / total_dist * 100) if total_dist else 0,
                        )
                        for i, (etq, val) in enumerate(zip(etiquetas, valores_dist)) if val > 0
                    )
                    st.markdown(leyenda, unsafe_allow_html=True)
                else:
                    st.caption("Sin movimientos este mes para distribuir.")

        st.markdown("**Movimientos consolidados**")
        with st.container(border=True):
            if detalle_mes.empty:
                st.caption("No hay movimientos para este periodo.")
            else:
                tabla = detalle_mes.copy()
                col1, col2 = st.columns(2)
                cuentas_disp = sorted(tabla["cuenta"].dropna().unique().tolist())
                tipos_disp = sorted(tabla["tipo"].dropna().unique().tolist())
                f_cuentas = col1.multiselect("Cuenta", cuentas_disp, key="flujo_f_cuenta")
                f_tipos = col2.multiselect("Tipo", tipos_disp, key="flujo_f_tipo")
                if f_cuentas:
                    tabla = tabla[tabla["cuenta"].isin(f_cuentas)]
                if f_tipos:
                    tabla = tabla[tabla["tipo"].isin(f_tipos)]
                tabla["importe_abs"] = tabla["importe"].abs()
                tabla_mostrar = tabla[["tipo", "cuenta", "grupo", "concepto", "importe_abs"]].rename(
                    columns={"grupo": "categoria", "importe_abs": "importe"}
                ).sort_values(["tipo", "cuenta", "concepto"])
                st.dataframe(
                    tabla_mostrar.style.format({"importe": "{:,.2f} €"}),
                    hide_index=True, width="stretch",
                )

# ===================================================================== Inversiones ====

elif pagina == "Inversiones":
    st.title("Cartera de Inversión")

    ahorros = db.cargar_ahorros()
    cartera = ahorros[(ahorros["tipo"] == "inversión") & ahorros["activa"]] if not ahorros.empty else ahorros

    if cartera.empty:
        st.info(
            "Añade una inversión en **Cuentas y Movimientos → Ahorros e inversiones** "
            "(tipo \"Inversión\") para ver tu cartera aquí."
        )
    else:
        capital_invertido = cartera["aportado"].sum()
        valor_mercado = cartera["actual"].sum()
        comisiones_total = cartera["comisiones"].sum()
        plusvalia = valor_mercado - capital_invertido - comisiones_total
        rentabilidad = (plusvalia / capital_invertido * 100) if capital_invertido else 0.0
        clase_plus = "pos" if plusvalia >= 0 else "neg"
        signo = "+" if plusvalia >= 0 else ""

        kpis_html = (
            estilo.tarjeta_kpi_pro(
                "💰", "Capital invertido", f"{capital_invertido:,.0f} €", f"{len(cartera)} posiciones activas",
            )
            + estilo.tarjeta_kpi_pro("📊", "Valor de mercado", f"{valor_mercado:,.0f} €", "Valor actual de la cartera")
            + estilo.tarjeta_kpi_pro(
                "📈" if plusvalia >= 0 else "📉", "Plusvalía latente", f"{signo}{plusvalia:,.0f} €",
                f"{signo}{rentabilidad:.1f} % sobre lo aportado", clase_plus,
            )
            + estilo.tarjeta_kpi_pro("🏦", "Comisiones pagadas", f"{comisiones_total:,.0f} €", "Acumulado histórico")
        )
        st.markdown(f'<div class="kpi-row">{kpis_html}</div>', unsafe_allow_html=True)

        col_izq, col_der = st.columns([3, 2])
        with col_izq:
            with st.container(border=True):
                st.markdown("**Posiciones**")
                tabla = cartera.copy()
                tabla["plusvalia"] = tabla["actual"] - tabla["aportado"] - tabla["comisiones"]
                tabla["rentabilidad %"] = tabla.apply(
                    lambda r: (r["plusvalia"] / r["aportado"] * 100) if r["aportado"] else 0.0, axis=1,
                )
                tabla_mostrar = tabla[
                    ["nombre", "instrumento", "cuenta", "aportado", "actual", "plusvalia", "rentabilidad %"]
                ].sort_values("actual", ascending=False)

                def _color_plusvalia(val):
                    return f"color: {estilo.VERDE_TXT}" if val >= 0 else f"color: {estilo.ROJO_TXT}"

                st.dataframe(
                    tabla_mostrar.style.format({
                        "aportado": "{:,.2f} €", "actual": "{:,.2f} €",
                        "plusvalia": "{:,.2f} €", "rentabilidad %": "{:+.1f} %",
                    }).map(_color_plusvalia, subset=["plusvalia", "rentabilidad %"]),
                    hide_index=True, width="stretch",
                )
        with col_der:
            with st.container(border=True):
                st.markdown("**Salud de la cartera**")
                por_instrumento = cartera.groupby("instrumento")["actual"].sum().sort_values(ascending=False)
                total_cartera = por_instrumento.sum()
                if total_cartera > 0:
                    colores_ciclo = estilo.PALETA_CATEGORIAS
                    barras = "".join(
                        estilo.fila_diversificacion(
                            colores_ciclo[i % len(colores_ciclo)], (instr or "Sin clasificar"), valor,
                            (valor / total_cartera * 100) if total_cartera else 0,
                        )
                        for i, (instr, valor) in enumerate(por_instrumento.items())
                    )
                    st.markdown(barras, unsafe_allow_html=True)
                else:
                    st.caption("Sin valor en cartera para mostrar diversificación.")

                n_instrumentos = cartera["instrumento"].nunique()
                diversificada = n_instrumentos >= 3
                st.markdown(
                    estilo.tarjeta_info(
                        "ok" if diversificada else "info", "Diversificación",
                        f"Cartera {'bien diversificada' if diversificada else 'concentrada en pocos instrumentos'}",
                        f"Tienes posiciones en {n_instrumentos} tipo(s) de instrumento distinto(s).",
                    ),
                    unsafe_allow_html=True,
                )

# ===================================================================== Objetivos y Metas ====

elif pagina == "Objetivos y Metas":
    st.title("Objetivos y Metas")

    ahorros = db.cargar_ahorros()
    planes = db.cargar_planes()
    metas = ahorros[(ahorros["objetivo"] > 0) & ahorros["activa"]] if not ahorros.empty else ahorros

    st.markdown("**Tus metas de ahorro e inversión**")
    if metas.empty:
        st.caption(
            "Pon un objetivo (€) en una meta de ahorro o inversión en "
            "**Ahorros e Inversiones** para verla aquí con su progreso."
        )
    else:
        for row in metas.itertuples():
            progreso = min(max(row.actual / row.objetivo, 0.0), 1.0) if row.objetivo else 0.0
            with st.container(border=True):
                c1, c2 = st.columns([3, 1])
                c1.markdown(f"**{row.nombre}**")
                c2.markdown(f"{row.actual:,.0f} € / {row.objetivo:,.0f} €")
                st.progress(progreso)
                if row.actual >= row.objetivo:
                    st.caption("¡Objetivo alcanzado! 🎉")
                elif row.aportacion_mensual and row.aportacion_mensual > 0:
                    meses_restantes = math.ceil((row.objetivo - row.actual) / row.aportacion_mensual)
                    fecha_estim = (pd.Timestamp.today().to_period("M") + meses_restantes).to_timestamp()
                    st.caption(
                        f"{progreso * 100:.0f} % completado · a {row.aportacion_mensual:,.0f} €/mes, "
                        f"lo alcanzarás en ~{meses_restantes} meses "
                        f"({MESES_NOMBRE[fecha_estim.month - 1]} {fecha_estim.year})"
                    )
                else:
                    st.caption(f"{progreso * 100:.0f} % completado · sin aportación mensual programada")

    st.markdown("**Planes a largo plazo**")
    if planes.empty:
        st.caption("Aún no tienes planes a largo plazo. Añádelos en **Cuentas y Movimientos → Planes**.")
    else:
        for row in planes.itertuples():
            with st.container(border=True):
                st.markdown(f"**{row.nombre}** · {row.importe_objetivo:,.0f} €")
                if row.descripcion:
                    st.caption(row.descripcion)
                if row.fecha_objetivo:
                    fecha = pd.Timestamp(row.fecha_objetivo)
                    dias = (fecha - pd.Timestamp.today().normalize()).days
                    if dias > 0:
                        st.caption(f"Objetivo: {fecha.strftime('%d %b %Y')} · faltan {dias} días")
                    else:
                        st.caption(f"Fecha objetivo: {fecha.strftime('%d %b %Y')} (ya pasada)")

    st.divider()
    st.markdown("### Simulador de interés compuesto")
    st.caption("Proyección orientativa a partir de los datos que indiques abajo: no tiene en cuenta inflación, impuestos ni comisiones.")
    c1, c2, c3, c4 = st.columns(4)
    capital_inicial = c1.slider("Capital inicial (€)", 0, 100_000, 1_000, step=100)
    aportacion_sim = c2.slider("Aportación mensual (€)", 0, 2_000, 100, step=10)
    anos_sim = c3.slider("Años", 1, 40, 10)
    rentabilidad_sim = c4.slider("Rentabilidad anual esperada (%)", 0.0, 15.0, 6.0, step=0.5)

    r_mensual = rentabilidad_sim / 100 / 12
    meses_sim = anos_sim * 12
    valores_sim = []
    saldo = float(capital_inicial)
    for _ in range(meses_sim + 1):
        valores_sim.append(saldo)
        saldo = saldo * (1 + r_mensual) + aportacion_sim

    total_aportado = capital_inicial + aportacion_sim * meses_sim
    valor_final = valores_sim[-1]
    intereses_generados = valor_final - total_aportado

    k1, k2, k3 = st.columns(3)
    k1.metric("Aportado total", f"{total_aportado:,.0f} €")
    k2.metric("Intereses generados", f"{intereses_generados:,.0f} €")
    k3.metric("Valor final estimado", f"{valor_final:,.0f} €")

    fechas_sim = [pd.Timestamp.today().normalize() + pd.DateOffset(months=i) for i in range(meses_sim + 1)]
    fig_sim = px.area(x=fechas_sim, y=valores_sim, labels={"x": "Fecha", "y": "€"})
    fig_sim.update_traces(line_color=estilo.ACCENT, fillcolor="rgba(37,99,235,0.12)")
    estilo.aplicar_tema_plotly(fig_sim)
    fig_sim.update_layout(height=320)
    st.plotly_chart(fig_sim, width="stretch")

    st.divider()
    st.markdown("### Recomendaciones")

    conceptos = db.cargar_conceptos()
    deudas = db.cargar_deudas()
    movimientos = db.cargar_movimientos()
    valores = db.cargar_valores_mensuales()
    hoy = pd.Timestamp.today().normalize()
    mes_actual = hoy.to_period("M")
    periodos_hist = proyeccion.meses_entre(mes_actual - 23, mes_actual)
    detalle_hist = proyeccion.detalle_mensual(conceptos, deudas, ahorros, movimientos, valores, periodos_hist)
    detalle_mes = detalle_hist[detalle_hist["periodo"] == mes_actual] if not detalle_hist.empty else detalle_hist
    ingresos_mes = detalle_mes.loc[detalle_mes["tipo"] == "ingreso", "importe"].sum()
    gastos_mes = detalle_mes.loc[detalle_mes["tipo"] == "gasto", "importe"].abs().sum()
    ahorro_mes = detalle_mes.loc[detalle_mes["tipo"] == "ahorro", "importe"].abs().sum()
    tasa_ahorro = (ahorro_mes / ingresos_mes * 100) if ingresos_mes else 0.0
    deuda_pendiente = deudas.loc[deudas["activa"], "importe_pendiente"].sum() if not deudas.empty else 0.0

    meta_ahorro = 20.0
    recomendaciones = []
    if ingresos_mes > 0:
        if tasa_ahorro < meta_ahorro:
            recomendaciones.append((
                "info", "Tasa de ahorro",
                f"Ahorras un {tasa_ahorro:.1f} % de tus ingresos este mes, por debajo del {meta_ahorro:.0f} % "
                "recomendado. Revisa tus gastos variables para aumentar el margen.",
            ))
        else:
            recomendaciones.append((
                "ok", "Tasa de ahorro",
                f"Ahorras un {tasa_ahorro:.1f} % de tus ingresos este mes, por encima del {meta_ahorro:.0f} % "
                "recomendado. Vas bien encaminado.",
            ))

    emergencia = ahorros[ahorros["nombre"].str.contains("emergencia", case=False, na=False)] if not ahorros.empty else ahorros
    if not emergencia.empty and gastos_mes:
        meses_cubiertos = emergencia.iloc[0]["actual"] / gastos_mes
        if meses_cubiertos < 3:
            recomendaciones.append((
                "info", "Fondo de emergencia",
                f"Tu fondo de emergencia cubre {meses_cubiertos:.1f} meses de gastos; lo recomendable son al menos 3.",
            ))
        else:
            recomendaciones.append((
                "ok", "Fondo de emergencia",
                f"Tu fondo de emergencia cubre {meses_cubiertos:.1f} meses de gastos. Nivel saludable.",
            ))
    elif emergencia.empty:
        recomendaciones.append((
            "info", "Fondo de emergencia",
            "No tienes ninguna meta de ahorro llamada \"emergencia\". Considera crear una con 3-6 meses de gastos.",
        ))

    if deuda_pendiente > 0 and ingresos_mes:
        ratio_deuda = deuda_pendiente / (ingresos_mes * 12) * 100
        recomendaciones.append((
            "info", "Deuda pendiente",
            f"Tu deuda pendiente equivale a un {ratio_deuda:.0f} % de tus ingresos anuales "
            "estimados (sobre la base de este mes).",
        ))

    cartera = ahorros[(ahorros["tipo"] == "inversión") & ahorros["activa"]] if not ahorros.empty else ahorros
    if not cartera.empty:
        n_instrumentos = cartera["instrumento"].nunique()
        if n_instrumentos < 3:
            recomendaciones.append((
                "info", "Diversificación",
                f"Tu cartera de inversión está en {n_instrumentos} tipo(s) de instrumento. "
                "Diversificar entre más tipos reduce el riesgo.",
            ))

    if not recomendaciones:
        st.caption("Añade ingresos, gastos o metas de ahorro para recibir recomendaciones.")
    else:
        for tono, titulo, texto in recomendaciones:
            st.markdown(estilo.tarjeta_info(tono, "Recomendación", titulo, texto), unsafe_allow_html=True)

# ===================================================================== Ahorros e Inversiones ====

elif pagina == "Ahorros e Inversiones":
    st.title("Ahorros e Inversiones")

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

# ============================================= Cuentas y Movimientos ====

elif pagina == "Cuentas":
    st.title("Cuentas y Movimientos")

    tabs = st.tabs([
        "Cuentas", "Deudas", "Ingresos", "Gastos recurrentes",
        "Movimientos puntuales", "Planes", "Proyección",
        "Presupuestos",
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

    # ------------------------------------------------------------- Planes --
    with tabs[5]:
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
    with tabs[6]:
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

    # -------------------------------------------------------- Presupuestos --
    with tabs[7]:
        st.caption("Pon un límite de gasto mensual por categoría. El Flujo de Caja comparará el gasto real contra este límite.")
        categorias = db.cargar_categorias()
        presupuestos = db.cargar_presupuestos()
        limites = dict(zip(presupuestos["categoria"], presupuestos["limite_mensual"])) if not presupuestos.empty else {}

        with st.form("nuevo_presupuesto"):
            c1, c2 = st.columns([3, 2])
            categoria = c1.selectbox("Categoría", categorias, key="presu_cat")
            limite = c2.number_input("Límite mensual (€)", min_value=0.0, step=10.0, format="%.2f", key="presu_limite")
            if st.form_submit_button("Guardar límite", type="primary"):
                db.guardar_presupuesto(categoria, limite)
                st.success(f"Límite de {categoria} guardado")
                st.rerun()

        if presupuestos.empty:
            st.caption("Aún no has fijado ningún límite.")
        else:
            for row in presupuestos.itertuples():
                c1, c2, c3 = st.columns([3, 2, 1])
                c1.write(f"**{row.categoria}**")
                c2.write(f"{row.limite_mensual:,.2f} € / mes")
                if c3.button("Eliminar", key=f"presu_del_{row.id}"):
                    db.eliminar_presupuesto(row.id)
                    st.rerun()


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
