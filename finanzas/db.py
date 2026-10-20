import datetime as dt
import os
from functools import lru_cache
from pathlib import Path

import pandas as pd
from sqlalchemy import create_engine, text
from sqlalchemy.engine import Engine, URL

DB_PATH = Path(__file__).resolve().parent.parent / "data" / "finanzas.db"


# ---------------------------------------------------------------- Conexión ----
# El almacenamiento es Postgres (Supabase) cuando hay credenciales en los
# secretos de Streamlit o en el entorno; si no, se usa un SQLite local (útil
# para desarrollo sin red). La API pública de este módulo es idéntica en ambos
# casos.
#
# Dos formas de configurar Postgres (en orden de prioridad):
#   1. Por componentes (RECOMENDADO): DB_HOST, DB_PORT, DB_USER, DB_PASSWORD,
#      DB_NAME. SQLAlchemy codifica la contraseña, así que puede llevar
#      cualquier carácter especial sin tener que escaparlo a mano.
#   2. Cadena completa: DATABASE_URL = "postgresql://usuario:pass@host:puerto/db"
#      (aquí la contraseña sí debe ir percent-encoded si tiene símbolos raros).

def _secret(clave: str) -> str | None:
    try:
        import streamlit as st

        if clave in st.secrets:
            return str(st.secrets[clave])
    except Exception:
        pass
    return os.environ.get(clave)


def _build_url() -> URL | str | None:
    password = _secret("DB_PASSWORD")
    if password:
        return URL.create(
            "postgresql+psycopg2",
            username=_secret("DB_USER"),
            password=password,
            host=_secret("DB_HOST"),
            port=int(_secret("DB_PORT") or 5432),
            database=_secret("DB_NAME") or "postgres",
        )
    return _secret("DATABASE_URL")


@lru_cache(maxsize=1)
def _get_engine() -> Engine:
    url = _build_url()
    if url is not None:
        drivername = url.drivername if isinstance(url, URL) else str(url)
        es_pg = drivername.startswith("postgres")
        # Supabase (pooler) exige SSL. pool_pre_ping evita conexiones muertas
        # cuando la app de Streamlit lleva un rato dormida.
        connect_args = {"sslmode": "require"} if es_pg else {}
        return create_engine(url, pool_pre_ping=True, pool_recycle=300, connect_args=connect_args)
    DB_PATH.parent.mkdir(parents=True, exist_ok=True)
    return create_engine(f"sqlite:///{DB_PATH}")


def _es_postgres() -> bool:
    return _get_engine().dialect.name == "postgresql"


def _pk() -> str:
    return "BIGSERIAL PRIMARY KEY" if _es_postgres() else "INTEGER PRIMARY KEY AUTOINCREMENT"


# Caché de lecturas: contra una base de datos remota (Supabase) cada SELECT es
# una ida y vuelta por red, y Streamlit reejecuta todo el script en cada clic.
# Cacheamos los resultados y vaciamos la caché solo cuando se escribe, así las
# interacciones no vuelven a consultar la base de datos salvo que algo cambie.

def _cache(func):
    try:
        import streamlit as st

        return st.cache_data(ttl=600, show_spinner=False)(func)
    except Exception:
        return func


def _invalidar() -> None:
    try:
        import streamlit as st

        st.cache_data.clear()
    except Exception:
        pass


@_cache
def _leer(sql: str, params: dict | None = None) -> pd.DataFrame:
    with _get_engine().connect() as conn:
        return pd.read_sql_query(text(sql), conn, params=params or {})


def _ejecutar(sql: str, params=None) -> None:
    with _get_engine().begin() as conn:
        if not _es_postgres():
            conn.exec_driver_sql("PRAGMA foreign_keys = ON")
        conn.execute(text(sql), params if params is not None else {})
    _invalidar()


_inicializado = False


def init_db() -> None:
    # El esquema solo hace falta crearlo una vez por proceso. Repetir los
    # CREATE TABLE en cada consulta multiplicaba las idas y vueltas a la base de
    # datos remota (Supabase) y hacía lenta cada recarga.
    global _inicializado
    if _inicializado:
        return
    pk = _pk()
    with _get_engine().begin() as conn:
        if not _es_postgres():
            conn.exec_driver_sql("PRAGMA foreign_keys = ON")
        conn.execute(text(
            f"""
            CREATE TABLE IF NOT EXISTS cuentas (
                id {pk},
                nombre TEXT NOT NULL UNIQUE,
                logo TEXT
            )
            """
        ))
        conn.execute(text(
            f"""
            CREATE TABLE IF NOT EXISTS conceptos (
                id {pk},
                cuenta_id INTEGER NOT NULL REFERENCES cuentas(id) ON DELETE CASCADE,
                nombre TEXT NOT NULL,
                tipo TEXT NOT NULL CHECK (tipo IN ('ingreso', 'gasto')),
                modo TEXT NOT NULL DEFAULT 'fijo',
                grupo TEXT NOT NULL DEFAULT '',
                importe REAL NOT NULL DEFAULT 0,
                fecha_inicio TEXT NOT NULL,
                meses_duracion INTEGER,
                meses_aplicables TEXT,
                importes_meses TEXT,
                logo TEXT,
                activo INTEGER NOT NULL DEFAULT 1
            )
            """
        ))
        conn.execute(text(
            f"""
            CREATE TABLE IF NOT EXISTS deudas (
                id {pk},
                cuenta_id INTEGER REFERENCES cuentas(id) ON DELETE SET NULL,
                nombre TEXT NOT NULL,
                importe_total REAL NOT NULL,
                importe_pendiente REAL NOT NULL,
                tipo_pago TEXT NOT NULL DEFAULT 'fijo' CHECK (tipo_pago IN ('fijo', 'variable')),
                cuota_mensual REAL,
                meses_total INTEGER,
                fecha_inicio TEXT NOT NULL,
                logo TEXT,
                activa INTEGER NOT NULL DEFAULT 1
            )
            """
        ))
        conn.execute(text(
            f"""
            CREATE TABLE IF NOT EXISTS ahorros (
                id {pk},
                cuenta_id INTEGER REFERENCES cuentas(id) ON DELETE SET NULL,
                nombre TEXT NOT NULL,
                tipo TEXT NOT NULL DEFAULT 'ahorro',
                instrumento TEXT NOT NULL DEFAULT '',
                objetivo REAL NOT NULL,
                aportado REAL NOT NULL DEFAULT 0,
                actual REAL NOT NULL DEFAULT 0,
                comisiones REAL NOT NULL DEFAULT 0,
                aportacion_mensual REAL,
                fecha_objetivo TEXT,
                logo TEXT,
                activa INTEGER NOT NULL DEFAULT 1
            )
            """
        ))
        conn.execute(text(
            f"""
            CREATE TABLE IF NOT EXISTS movimientos (
                id {pk},
                cuenta_id INTEGER REFERENCES cuentas(id) ON DELETE SET NULL,
                fecha TEXT NOT NULL,
                concepto TEXT NOT NULL,
                importe REAL NOT NULL,
                categoria TEXT NOT NULL
            )
            """
        ))
        conn.execute(text(
            f"""
            CREATE TABLE IF NOT EXISTS planes (
                id {pk},
                nombre TEXT NOT NULL,
                descripcion TEXT,
                importe_objetivo REAL NOT NULL,
                fecha_objetivo TEXT,
                notas TEXT
            )
            """
        ))
        conn.execute(text(
            f"""
            CREATE TABLE IF NOT EXISTS valores_mensuales (
                id {pk},
                tipo_padre TEXT NOT NULL CHECK (tipo_padre IN ('concepto', 'deuda')),
                padre_id INTEGER NOT NULL,
                periodo TEXT NOT NULL,
                importe REAL NOT NULL,
                UNIQUE (tipo_padre, padre_id, periodo)
            )
            """
        ))
        conn.execute(text(
            f"""
            CREATE TABLE IF NOT EXISTS categorias (
                id {pk},
                nombre TEXT NOT NULL UNIQUE
            )
            """
        ))
        hay = conn.execute(text("SELECT COUNT(*) FROM categorias")).scalar()
        if not hay:
            conn.execute(
                text("INSERT INTO categorias (nombre) VALUES (:n)"),
                [{"n": n} for n in (
                    "Vivienda", "Suministros", "Alimentación", "Transporte", "Salud",
                    "Ocio", "Ropa", "Educación", "Suscripciones", "Dispositivos",
                    "Deporte", "Nómina", "Freelance", "Inversiones", "Otros",
                )],
            )
    _inicializado = True


# ---------------------------------------------------------------- Cuentas ----

def anadir_cuenta(nombre: str) -> None:
    init_db()
    _ejecutar("INSERT INTO cuentas (nombre) VALUES (:nombre)", {"nombre": nombre})


def actualizar_cuenta_nombre(id_: int, nombre: str) -> None:
    _ejecutar("UPDATE cuentas SET nombre = :nombre WHERE id = :id", {"nombre": nombre, "id": id_})


def cargar_cuentas() -> pd.DataFrame:
    init_db()
    return _leer("SELECT * FROM cuentas ORDER BY nombre")


def eliminar_cuenta(id_: int) -> None:
    _ejecutar("DELETE FROM cuentas WHERE id = :id", {"id": id_})


# -------------------------------------------------- Conceptos recurrentes ----
# Ingresos y gastos que se repiten. modo='fijo' usa `importe` tal cual;
# modo='variable' usa el valor que el usuario registre cada mes en
# valores_mensuales (con la media de meses anteriores como estimación para el
# futuro). meses_aplicables restringe en qué meses del año se aplica (p.ej.
# un seguro que se paga en enero, mayo y septiembre); NULL = todos los meses.

def _serializar_importes_meses(importes_meses: dict[int, float] | None) -> str | None:
    if not importes_meses:
        return None
    return ",".join(f"{mes}:{importe}" for mes, importe in sorted(importes_meses.items()))


def anadir_concepto(
    cuenta_id: int, nombre: str, tipo: str, modo: str, grupo: str, importe: float,
    fecha_inicio: dt.date, meses_duracion: int | None, meses_aplicables: list[int] | None = None,
    importes_meses: dict[int, float] | None = None,
) -> None:
    init_db()
    meses_txt = ",".join(str(m) for m in sorted(meses_aplicables)) if meses_aplicables else None
    importes_meses_txt = _serializar_importes_meses(importes_meses)
    _ejecutar(
        """INSERT INTO conceptos
           (cuenta_id, nombre, tipo, modo, grupo, importe, fecha_inicio, meses_duracion,
            meses_aplicables, importes_meses, activo)
           VALUES (:cuenta_id, :nombre, :tipo, :modo, :grupo, :importe, :fecha_inicio,
                   :meses_duracion, :meses_aplicables, :importes_meses, 1)""",
        {
            "cuenta_id": cuenta_id, "nombre": nombre, "tipo": tipo, "modo": modo, "grupo": grupo,
            "importe": importe, "fecha_inicio": fecha_inicio.isoformat(),
            "meses_duracion": meses_duracion, "meses_aplicables": meses_txt,
            "importes_meses": importes_meses_txt,
        },
    )


def cargar_conceptos() -> pd.DataFrame:
    init_db()
    df = _leer(
        """
        SELECT conceptos.*, cuentas.nombre AS cuenta
        FROM conceptos JOIN cuentas ON cuentas.id = conceptos.cuenta_id
        ORDER BY cuentas.nombre, conceptos.tipo, conceptos.nombre
        """
    )
    if not df.empty:
        df["activo"] = df["activo"].astype(bool)
    return df


def actualizar_concepto_activo(id_: int, activo: bool) -> None:
    _ejecutar("UPDATE conceptos SET activo = :activo WHERE id = :id", {"activo": int(activo), "id": id_})


def actualizar_concepto(
    id_: int, cuenta_id: int, nombre: str, tipo: str, modo: str, grupo: str, importe: float,
    fecha_inicio: dt.date, meses_duracion: int | None, meses_aplicables: list[int] | None,
    importes_meses: dict[int, float] | None = None,
) -> None:
    meses_txt = ",".join(str(m) for m in sorted(meses_aplicables)) if meses_aplicables else None
    importes_meses_txt = _serializar_importes_meses(importes_meses)
    _ejecutar(
        """UPDATE conceptos SET
               cuenta_id = :cuenta_id, nombre = :nombre, tipo = :tipo, modo = :modo,
               grupo = :grupo, importe = :importe, fecha_inicio = :fecha_inicio,
               meses_duracion = :meses_duracion, meses_aplicables = :meses_aplicables,
               importes_meses = :importes_meses
           WHERE id = :id""",
        {
            "cuenta_id": cuenta_id, "nombre": nombre, "tipo": tipo, "modo": modo, "grupo": grupo,
            "importe": importe, "fecha_inicio": fecha_inicio.isoformat(),
            "meses_duracion": meses_duracion, "meses_aplicables": meses_txt,
            "importes_meses": importes_meses_txt, "id": id_,
        },
    )


def eliminar_concepto(id_: int) -> None:
    _ejecutar("DELETE FROM conceptos WHERE id = :id", {"id": id_})
    _ejecutar(
        "DELETE FROM valores_mensuales WHERE tipo_padre = 'concepto' AND padre_id = :id",
        {"id": id_},
    )


# ---------------------------------------------------------------- Deudas ----
# tipo_pago='fijo': cuota_mensual constante. tipo_pago='variable': la cuota
# de cada mes se registra en valores_mensuales.

def anadir_deuda(
    cuenta_id: int | None, nombre: str, importe_total: float, importe_pendiente: float,
    tipo_pago: str, cuota_mensual: float | None, meses_total: int | None,
    fecha_inicio: dt.date,
) -> None:
    init_db()
    _ejecutar(
        """INSERT INTO deudas
           (cuenta_id, nombre, importe_total, importe_pendiente, tipo_pago,
            cuota_mensual, meses_total, fecha_inicio, activa)
           VALUES (:cuenta_id, :nombre, :importe_total, :importe_pendiente, :tipo_pago,
                   :cuota_mensual, :meses_total, :fecha_inicio, 1)""",
        {
            "cuenta_id": cuenta_id, "nombre": nombre, "importe_total": importe_total,
            "importe_pendiente": importe_pendiente, "tipo_pago": tipo_pago,
            "cuota_mensual": cuota_mensual, "meses_total": meses_total,
            "fecha_inicio": fecha_inicio.isoformat(),
        },
    )


def cargar_deudas() -> pd.DataFrame:
    init_db()
    df = _leer(
        """
        SELECT deudas.*, cuentas.nombre AS cuenta
        FROM deudas LEFT JOIN cuentas ON cuentas.id = deudas.cuenta_id
        ORDER BY fecha_inicio
        """
    )
    if not df.empty:
        df["activa"] = df["activa"].astype(bool)
    return df


def actualizar_deuda_pendiente(id_: int, nuevo_pendiente: float) -> None:
    _ejecutar(
        "UPDATE deudas SET importe_pendiente = :p WHERE id = :id",
        {"p": max(nuevo_pendiente, 0.0), "id": id_},
    )


def actualizar_deuda(
    id_: int, cuenta_id: int | None, nombre: str, importe_total: float, importe_pendiente: float,
    tipo_pago: str, cuota_mensual: float | None, meses_total: int | None, fecha_inicio: dt.date,
) -> None:
    _ejecutar(
        """UPDATE deudas SET
               cuenta_id = :cuenta_id, nombre = :nombre, importe_total = :importe_total,
               importe_pendiente = :importe_pendiente, tipo_pago = :tipo_pago,
               cuota_mensual = :cuota_mensual, meses_total = :meses_total,
               fecha_inicio = :fecha_inicio
           WHERE id = :id""",
        {
            "cuenta_id": cuenta_id, "nombre": nombre, "importe_total": importe_total,
            "importe_pendiente": max(importe_pendiente, 0.0), "tipo_pago": tipo_pago,
            "cuota_mensual": cuota_mensual, "meses_total": meses_total,
            "fecha_inicio": fecha_inicio.isoformat(), "id": id_,
        },
    )


def actualizar_deuda_activa(id_: int, activa: bool) -> None:
    _ejecutar("UPDATE deudas SET activa = :activa WHERE id = :id", {"activa": int(activa), "id": id_})


def eliminar_deuda(id_: int) -> None:
    _ejecutar("DELETE FROM deudas WHERE id = :id", {"id": id_})
    _ejecutar(
        "DELETE FROM valores_mensuales WHERE tipo_padre = 'deuda' AND padre_id = :id",
        {"id": id_},
    )


# ------------------------------------------------------ Ahorros / inversiones ----

def anadir_ahorro(
    cuenta_id: int | None, nombre: str, tipo: str, instrumento: str,
    objetivo: float, aportado: float, actual: float, comisiones: float,
    aportacion_mensual: float | None, fecha_objetivo: dt.date | None,
) -> None:
    init_db()
    _ejecutar(
        """INSERT INTO ahorros
           (cuenta_id, nombre, tipo, instrumento, objetivo, aportado, actual, comisiones,
            aportacion_mensual, fecha_objetivo, activa)
           VALUES (:cuenta_id, :nombre, :tipo, :instrumento, :objetivo, :aportado, :actual,
                   :comisiones, :aportacion_mensual, :fecha_objetivo, 1)""",
        {
            "cuenta_id": cuenta_id, "nombre": nombre, "tipo": tipo, "instrumento": instrumento,
            "objetivo": objetivo, "aportado": aportado, "actual": actual, "comisiones": comisiones,
            "aportacion_mensual": aportacion_mensual,
            "fecha_objetivo": fecha_objetivo.isoformat() if fecha_objetivo else None,
        },
    )


def cargar_ahorros() -> pd.DataFrame:
    init_db()
    df = _leer(
        """
        SELECT ahorros.*, cuentas.nombre AS cuenta
        FROM ahorros LEFT JOIN cuentas ON cuentas.id = ahorros.cuenta_id
        ORDER BY ahorros.id
        """
    )
    if not df.empty:
        df["activa"] = df["activa"].astype(bool)
    return df


def actualizar_ahorro_actual(id_: int, nuevo_actual: float) -> None:
    _ejecutar("UPDATE ahorros SET actual = :a WHERE id = :id", {"a": nuevo_actual, "id": id_})


def actualizar_ahorro(
    id_: int, cuenta_id: int | None, nombre: str, tipo: str, instrumento: str,
    objetivo: float, aportado: float, actual: float, comisiones: float,
    aportacion_mensual: float | None, fecha_objetivo: dt.date | None,
) -> None:
    _ejecutar(
        """UPDATE ahorros SET
               cuenta_id = :cuenta_id, nombre = :nombre, tipo = :tipo, instrumento = :instrumento,
               objetivo = :objetivo, aportado = :aportado, actual = :actual, comisiones = :comisiones,
               aportacion_mensual = :aportacion_mensual, fecha_objetivo = :fecha_objetivo
           WHERE id = :id""",
        {
            "cuenta_id": cuenta_id, "nombre": nombre, "tipo": tipo, "instrumento": instrumento,
            "objetivo": objetivo, "aportado": aportado, "actual": actual, "comisiones": comisiones,
            "aportacion_mensual": aportacion_mensual,
            "fecha_objetivo": fecha_objetivo.isoformat() if fecha_objetivo else None, "id": id_,
        },
    )


def actualizar_ahorro_activa(id_: int, activa: bool) -> None:
    _ejecutar("UPDATE ahorros SET activa = :activa WHERE id = :id", {"activa": int(activa), "id": id_})


def eliminar_ahorro(id_: int) -> None:
    _ejecutar("DELETE FROM ahorros WHERE id = :id", {"id": id_})


# ---------------------------------------------------------- Movimientos puntuales ----
# Entradas manuales de un gasto o ingreso de un mes concreto, sin relación con
# ningún concepto recurrente ni deuda (p.ej. una compra puntual).

def anadir_movimiento(
    cuenta_id: int | None, fecha: dt.date, concepto: str, importe: float, categoria: str,
) -> None:
    init_db()
    _ejecutar(
        """INSERT INTO movimientos (cuenta_id, fecha, concepto, importe, categoria)
           VALUES (:cuenta_id, :fecha, :concepto, :importe, :categoria)""",
        {
            "cuenta_id": cuenta_id, "fecha": fecha.isoformat(), "concepto": concepto,
            "importe": importe, "categoria": categoria,
        },
    )


def cargar_movimientos() -> pd.DataFrame:
    init_db()
    df = _leer(
        """
        SELECT movimientos.*, cuentas.nombre AS cuenta
        FROM movimientos LEFT JOIN cuentas ON cuentas.id = movimientos.cuenta_id
        ORDER BY fecha DESC, movimientos.id DESC
        """
    )
    if not df.empty:
        df["fecha"] = pd.to_datetime(df["fecha"])
    return df


def eliminar_movimiento(id_: int) -> None:
    _ejecutar("DELETE FROM movimientos WHERE id = :id", {"id": id_})


# ---------------------------------------------------------- Planes a largo plazo ----

def anadir_plan(
    nombre: str, descripcion: str, importe_objetivo: float,
    fecha_objetivo: dt.date | None, notas: str,
) -> None:
    init_db()
    _ejecutar(
        """INSERT INTO planes (nombre, descripcion, importe_objetivo, fecha_objetivo, notas)
           VALUES (:nombre, :descripcion, :importe_objetivo, :fecha_objetivo, :notas)""",
        {
            "nombre": nombre, "descripcion": descripcion, "importe_objetivo": importe_objetivo,
            "fecha_objetivo": fecha_objetivo.isoformat() if fecha_objetivo else None, "notas": notas,
        },
    )


def cargar_planes() -> pd.DataFrame:
    init_db()
    return _leer("SELECT * FROM planes ORDER BY fecha_objetivo")


def actualizar_plan(
    id_: int, nombre: str, descripcion: str, importe_objetivo: float,
    fecha_objetivo: dt.date | None, notas: str,
) -> None:
    _ejecutar(
        """UPDATE planes SET
               nombre = :nombre, descripcion = :descripcion, importe_objetivo = :importe_objetivo,
               fecha_objetivo = :fecha_objetivo, notas = :notas
           WHERE id = :id""",
        {
            "nombre": nombre, "descripcion": descripcion, "importe_objetivo": importe_objetivo,
            "fecha_objetivo": fecha_objetivo.isoformat() if fecha_objetivo else None,
            "notas": notas, "id": id_,
        },
    )


def eliminar_plan(id_: int) -> None:
    _ejecutar("DELETE FROM planes WHERE id = :id", {"id": id_})


# -------------------------------------------- Valores mensuales (variable) ----
# Importe real registrado para un mes concreto de un concepto o deuda
# "variable". Si no hay valor para un mes (normalmente futuro), la proyección
# usa la media de los últimos registrados como estimación.

def registrar_valor_mensual(tipo_padre: str, padre_id: int, periodo: str, importe: float) -> None:
    init_db()
    _ejecutar(
        """INSERT INTO valores_mensuales (tipo_padre, padre_id, periodo, importe)
           VALUES (:tipo_padre, :padre_id, :periodo, :importe)
           ON CONFLICT (tipo_padre, padre_id, periodo) DO UPDATE SET importe = excluded.importe""",
        {"tipo_padre": tipo_padre, "padre_id": padre_id, "periodo": periodo, "importe": importe},
    )


def cargar_valores_mensuales(tipo_padre: str | None = None, padre_id: int | None = None) -> pd.DataFrame:
    init_db()
    query = "SELECT * FROM valores_mensuales WHERE 1=1"
    params: dict = {}
    if tipo_padre:
        query += " AND tipo_padre = :tipo_padre"
        params["tipo_padre"] = tipo_padre
    if padre_id is not None:
        query += " AND padre_id = :padre_id"
        params["padre_id"] = padre_id
    query += " ORDER BY periodo DESC"
    return _leer(query, params)


def eliminar_valor_mensual(id_: int) -> None:
    _ejecutar("DELETE FROM valores_mensuales WHERE id = :id", {"id": id_})


# ---------------------------------------------------------------- Categorías ----

def anadir_categoria(nombre: str) -> None:
    init_db()
    _ejecutar(
        "INSERT INTO categorias (nombre) VALUES (:nombre) ON CONFLICT (nombre) DO NOTHING",
        {"nombre": nombre},
    )


def cargar_categorias() -> list[str]:
    init_db()
    df = _leer("SELECT nombre FROM categorias ORDER BY nombre")
    return df["nombre"].tolist() if not df.empty else []


def eliminar_categoria(nombre: str) -> None:
    _ejecutar("DELETE FROM categorias WHERE nombre = :nombre", {"nombre": nombre})


# ---------------------------------------------------------------- Logos ----

TABLAS_CON_LOGO = ("cuentas", "conceptos", "deudas", "ahorros")


def actualizar_logo(tabla: str, id_: int, ruta: str | None) -> None:
    if tabla not in TABLAS_CON_LOGO:
        raise ValueError(f"Tabla sin columna logo: {tabla}")
    _ejecutar(f"UPDATE {tabla} SET logo = :ruta WHERE id = :id", {"ruta": ruta, "id": id_})
