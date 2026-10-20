import math

import pandas as pd

COLOR_TIPO = {
    "ingreso": "#1e8e3e",
    "gasto": "#e07b00",
    "deuda": "#c62828",
    "ahorro": "#00796b",
}

VENTANA_MEDIA = 5  # nº de valores mensuales pasados usados para la media de algo variable


def meses_entre(inicio: pd.Period, fin: pd.Period) -> list[pd.Period]:
    if fin < inicio:
        inicio, fin = fin, inicio
    return list(pd.period_range(inicio, fin, freq="M"))


def _parse_meses_aplicables(valor) -> set[int] | None:
    if valor is None or (isinstance(valor, float) and pd.isna(valor)) or valor == "":
        return None
    return {int(m) for m in str(valor).split(",") if m.strip()}


def _vigente_en(fecha_inicio: str, meses_limite, activo: bool, periodo: pd.Period, meses_aplicables=None) -> bool:
    if not activo:
        return False
    inicio = pd.Timestamp(fecha_inicio).to_period("M")
    if periodo < inicio:
        return False
    if pd.notna(meses_limite):
        transcurridos = (periodo.year - inicio.year) * 12 + (periodo.month - inicio.month)
        if transcurridos >= meses_limite:
            return False
    meses = _parse_meses_aplicables(meses_aplicables)
    if meses is not None and periodo.month not in meses:
        return False
    return True


def valor_exacto(valores: pd.DataFrame, tipo_padre: str, padre_id: int, periodo: pd.Period) -> float | None:
    if valores.empty:
        return None
    df = valores[
        (valores["tipo_padre"] == tipo_padre) & (valores["padre_id"] == padre_id)
        & (valores["periodo"] == str(periodo))
    ]
    if df.empty:
        return None
    return float(df["importe"].iloc[0])


def media_historica(
    valores: pd.DataFrame, tipo_padre: str, padre_id: int, periodo: pd.Period, ventana: int = VENTANA_MEDIA,
) -> float | None:
    if valores.empty:
        return None
    df = valores[
        (valores["tipo_padre"] == tipo_padre) & (valores["padre_id"] == padre_id)
        & (valores["periodo"].astype(str) < str(periodo))
    ]
    if df.empty:
        return None
    df = df.sort_values("periodo", ascending=False).head(ventana)
    return float(df["importe"].mean())


def _importe_variable(valores: pd.DataFrame, tipo_padre: str, padre_id: int, periodo: pd.Period, estimacion: float) -> float:
    v = valor_exacto(valores, tipo_padre, padre_id, periodo)
    if v is not None:
        return v
    v = media_historica(valores, tipo_padre, padre_id, periodo)
    if v is not None:
        return v
    return estimacion


def info_deuda(row, valores: pd.DataFrame, hoy: pd.Timestamp | None = None) -> dict:
    """Cuota estimada, meses restantes y fecha de fin de una deuda."""
    hoy = hoy or pd.Timestamp.today().normalize()
    mes_inicio = pd.Timestamp(row.fecha_inicio).to_period("M")
    mes_hoy = hoy.to_period("M")
    meses_transcurridos = max((mes_hoy.year - mes_inicio.year) * 12 + (mes_hoy.month - mes_inicio.month), 0)

    estimacion = float(row.cuota_mensual) if pd.notna(row.cuota_mensual) else 0.0
    if row.tipo_pago == "fijo":
        cuota = estimacion
    else:
        cuota = _importe_variable(valores, "deuda", row.id, mes_hoy, estimacion)

    if pd.notna(row.meses_total):
        meses_restantes = max(int(row.meses_total) - meses_transcurridos, 0)
    elif cuota > 0:
        meses_restantes = math.ceil(row.importe_pendiente / cuota) if row.importe_pendiente > 0 else 0
    else:
        meses_restantes = None

    fecha_fin = None
    if meses_restantes is not None:
        fecha_fin = (mes_hoy + meses_restantes).to_timestamp()

    return {
        "cuota_estimada": cuota,
        "meses_transcurridos": meses_transcurridos,
        "meses_restantes": meses_restantes,
        "fecha_fin_estimada": fecha_fin,
    }


def detalle_mensual(
    conceptos: pd.DataFrame, deudas: pd.DataFrame, ahorros: pd.DataFrame,
    movimientos: pd.DataFrame, valores: pd.DataFrame, periodos: list[pd.Period],
) -> pd.DataFrame:
    """Devuelve un DataFrame en formato largo: una fila por (periodo, concepto)."""
    filas = []

    especiales = ("porcentaje_ingreso", "remanente")
    conceptos_normales = conceptos[~conceptos["modo"].isin(especiales)] if not conceptos.empty else conceptos
    conceptos_especiales = conceptos[conceptos["modo"].isin(especiales)] if not conceptos.empty else conceptos

    if not conceptos_normales.empty:
        for _, row in conceptos_normales.iterrows():
            signo = 1 if row.tipo == "ingreso" else -1
            for periodo in periodos:
                if not _vigente_en(row.fecha_inicio, row.meses_duracion, row.activo, periodo, row.meses_aplicables):
                    continue
                if row.modo == "variable":
                    importe = signo * _importe_variable(valores, "concepto", row.id, periodo, row.importe)
                else:
                    importe = signo * row.importe
                filas.append({
                    "periodo": periodo, "cuenta": row.cuenta, "tipo": row.tipo,
                    "grupo": row.grupo or row.tipo.capitalize(), "concepto": row.nombre,
                    "importe": importe,
                })

    if not deudas.empty:
        for _, row in deudas.iterrows():
            cuenta = row.cuenta if pd.notna(row.cuenta) else "Sin cuenta"
            estimacion = float(row.cuota_mensual) if pd.notna(row.cuota_mensual) else 0.0
            for periodo in periodos:
                if not _vigente_en(row.fecha_inicio, row.meses_total, row.activa, periodo):
                    continue
                if row.tipo_pago == "variable":
                    cuota = _importe_variable(valores, "deuda", row.id, periodo, estimacion)
                else:
                    cuota = estimacion
                filas.append({
                    "periodo": periodo, "cuenta": cuenta, "tipo": "deuda",
                    "grupo": "Deudas", "concepto": row.nombre, "importe": -cuota,
                })

    if not ahorros.empty:
        for _, row in ahorros.iterrows():
            if not row.activa or pd.isna(row.aportacion_mensual) or row.aportacion_mensual == 0:
                continue
            cuenta = row.cuenta if pd.notna(row.cuenta) else "Sin cuenta"
            for periodo in periodos:
                filas.append({
                    "periodo": periodo, "cuenta": cuenta, "tipo": "ahorro",
                    "grupo": "Ahorro", "concepto": row.nombre, "importe": -float(row.aportacion_mensual),
                })

    if not movimientos.empty:
        mov = movimientos.copy()
        mov["periodo"] = mov["fecha"].dt.to_period("M")
        mov = mov[mov["periodo"].isin(periodos)]
        for _, row in mov.iterrows():
            filas.append({
                "periodo": row.periodo,
                "cuenta": row.cuenta if pd.notna(row.cuenta) else "Sin cuenta",
                "tipo": "ingreso" if row.importe > 0 else "gasto",
                "grupo": row.categoria, "concepto": row.concepto, "importe": row.importe,
            })

    if not conceptos_especiales.empty:
        base = pd.DataFrame(filas) if filas else pd.DataFrame(columns=["periodo", "tipo", "importe"])
        agregados: dict[pd.Period, dict[str, float]] = {}
        if not base.empty:
            for periodo, grupo in base.groupby("periodo"):
                agregados[periodo] = {
                    "ingresos": grupo.loc[grupo["tipo"] == "ingreso", "importe"].sum(),
                    "gastos": -grupo.loc[grupo["tipo"] == "gasto", "importe"].sum(),
                    "deuda": -grupo.loc[grupo["tipo"] == "deuda", "importe"].sum(),
                    "ahorro": -grupo.loc[grupo["tipo"] == "ahorro", "importe"].sum(),
                }
        for _, row in conceptos_especiales.iterrows():
            signo = 1 if row.tipo == "ingreso" else -1
            for periodo in periodos:
                if not _vigente_en(row.fecha_inicio, row.meses_duracion, row.activo, periodo, row.meses_aplicables):
                    continue
                agg = agregados.get(periodo, {"ingresos": 0.0, "gastos": 0.0, "deuda": 0.0, "ahorro": 0.0})
                if row.modo == "porcentaje_ingreso":
                    importe_calc = agg["ingresos"] * (row.importe / 100.0)
                else:  # remanente
                    importe_calc = max(agg["ingresos"] - agg["gastos"] - agg["deuda"] - agg["ahorro"], 0.0)
                filas.append({
                    "periodo": periodo, "cuenta": row.cuenta, "tipo": row.tipo,
                    "grupo": row.grupo or "Ahorro automático", "concepto": row.nombre,
                    "importe": signo * importe_calc,
                })

    if not filas:
        return pd.DataFrame(columns=["periodo", "cuenta", "tipo", "grupo", "concepto", "importe"])
    return pd.DataFrame(filas)


def tabla_resumen_mensual(detalle: pd.DataFrame) -> pd.DataFrame:
    """Totales de ingresos y salidas (gasto + deuda + ahorro) por mes."""
    if detalle.empty:
        return pd.DataFrame(columns=["periodo", "ingresos", "gastos", "balance"])
    df = detalle.copy()
    df["bloque"] = df["tipo"].apply(lambda t: "ingresos" if t == "ingreso" else "gastos")
    df["importe_abs"] = df["importe"].abs()
    resumen = df.groupby(["periodo", "bloque"])["importe_abs"].sum().unstack(fill_value=0)
    resumen = resumen.reindex(columns=["ingresos", "gastos"], fill_value=0)
    resumen["balance"] = resumen["ingresos"] - resumen["gastos"]
    resumen = resumen.reset_index()
    resumen["periodo"] = resumen["periodo"].astype(str)
    return resumen


def tabla_por_cuenta(detalle: pd.DataFrame, periodo_actual: pd.Period) -> pd.DataFrame:
    if detalle.empty:
        return pd.DataFrame(columns=["cuenta", "ingresos", "gastos", "balance"])
    df = detalle[detalle["periodo"] == periodo_actual].copy()
    if df.empty:
        return pd.DataFrame(columns=["cuenta", "ingresos", "gastos", "balance"])
    df["bloque"] = df["tipo"].apply(lambda t: "ingresos" if t == "ingreso" else "gastos")
    df["importe_abs"] = df["importe"].abs()
    resumen = df.groupby(["cuenta", "bloque"])["importe_abs"].sum().unstack(fill_value=0)
    resumen = resumen.reindex(columns=["ingresos", "gastos"], fill_value=0)
    resumen["balance"] = resumen["ingresos"] - resumen["gastos"]
    return resumen.reset_index()


def tabla_proyeccion_pivot(detalle: pd.DataFrame) -> pd.DataFrame:
    if detalle.empty:
        return pd.DataFrame()
    pivot = pd.pivot_table(
        detalle, index="periodo", columns=["cuenta", "concepto"],
        values="importe", aggfunc="sum", fill_value=0,
    )
    pivot = pivot.sort_index(axis=1, level=[0, 1])
    pivot.index = pivot.index.astype(str)
    return pivot


def estilo_proyeccion(pivot: pd.DataFrame, detalle: pd.DataFrame):
    tipo_por_columna = {}
    if not detalle.empty:
        for (cuenta, concepto), grupo in detalle.groupby(["cuenta", "concepto"]):
            tipo_por_columna[(cuenta, concepto)] = grupo["tipo"].iloc[0]

    def color_columna(col: pd.Series):
        tipo = tipo_por_columna.get(col.name)
        color = COLOR_TIPO.get(tipo, "#444444")
        return [f"color: {color}"] * len(col)

    return pivot.style.apply(color_columna, axis=0).format("{:,.2f} €")
