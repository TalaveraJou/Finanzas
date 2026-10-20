import datetime as dt
import os
from functools import lru_cache
from pathlib import Path

import pandas as pd
from sqlalchemy import create_engine, text
from sqlalchemy.engine import Engine, URL
from sqlalchemy.pool import NullPool

DB_PATH = Path(__file__).resolve().parent.parent / "data" / "finanzas.db"

SUPERADMIN_EMAIL = "alvarotalaverajou@icloud.com"

# Tablas de datos financieros: cada fila pertenece a un usuario (columna
# `propietario`, su email). Las tablas usuarios/accesos son globales.
TABLAS_DATOS = (
    "cuentas", "conceptos", "deudas", "ahorros", "movimientos", "planes",
    "categorias", "valores_mensuales",
)

CATEGORIAS_DEFECTO = (
    "Vivienda", "Suministros", "Alimentación", "Transporte", "Salud",
    "Ocio", "Ropa", "Educación", "Suscripciones", "Dispositivos",
    "Deporte", "Nómina", "Freelance", "Inversiones", "Otros",
)


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
    valor = None
    try:
        import streamlit as st

        if clave in st.secrets:
            valor = str(st.secrets[clave])
    except Exception:
        pass
    if valor is None:
        valor = os.environ.get(clave)
    # Un valor vacío (p. ej. una variable de entorno definida pero en blanco)
    # cuenta como "no configurado".
    if valor is not None and valor.strip() == "":
        return None
    return valor


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
        if es_pg:
            # Supabase usa un pooler (Supavisor/pgbouncer) que ya agrupa las
            # conexiones. Agrupar también en el cliente provoca errores
            # intermitentes (p. ej. InvalidSchemaName) cuando una conexión
            # reutilizada cae en otro backend. Con NullPool abrimos una conexión
            # por operación y la cerramos; además exigimos SSL y fijamos el
            # esquema `public` para evitar problemas de resolución de nombres.
            connect_args = {"sslmode": "require", "options": "-c search_path=public"}
            return create_engine(url, poolclass=NullPool, connect_args=connect_args)
        return create_engine(url, pool_pre_ping=True, pool_recycle=300)
    DB_PATH.parent.mkdir(parents=True, exist_ok=True)
    return create_engine(f"sqlite:///{DB_PATH}")


def _es_postgres() -> bool:
    return _get_engine().dialect.name == "postgresql"


def _pk() -> str:
    return "BIGSERIAL PRIMARY KEY" if _es_postgres() else "INTEGER PRIMARY KEY AUTOINCREMENT"


def _propietario() -> str:
    """Email del usuario en sesión (cada uno solo ve sus datos). Fuera de una
    sesión de Streamlit (scripts, pruebas) se usa el superadmin."""
    try:
        import streamlit as st

        u = st.session_state.get("usuario")
        if u and u.get("email"):
            return str(u["email"]).strip().lower()
    except Exception:
        pass
    return SUPERADMIN_EMAIL


# Caché de lecturas: contra una base de datos remota (Supabase) cada SELECT es
# una ida y vuelta por red, y Streamlit reejecuta todo el script en cada clic.
# Cacheamos los resultados y vaciamos la caché solo cuando se escribe, así las
# interacciones no vuelven a consultar la base de datos salvo que algo cambie.
# La caché se indexa por los parámetros (incluido `propietario`), así que no
# mezcla datos entre usuarios.

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
                nombre TEXT NOT NULL,
                logo TEXT,
                propietario TEXT
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
                activo INTEGER NOT NULL DEFAULT 1,
                propietario TEXT
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
                activa INTEGER NOT NULL DEFAULT 1,
                propietario TEXT
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
                activa INTEGER NOT NULL DEFAULT 1,
                propietario TEXT
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
                categoria TEXT NOT NULL,
                propietario TEXT
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
                notas TEXT,
                propietario TEXT
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
                propietario TEXT,
                UNIQUE (tipo_padre, padre_id, periodo)
            )
            """
        ))
        conn.execute(text(
            f"""
            CREATE TABLE IF NOT EXISTS categorias (
                id {pk},
                nombre TEXT NOT NULL,
                propietario TEXT
            )
            """
        ))
        conn.execute(text(
            f"""
            CREATE TABLE IF NOT EXISTS preferencias (
                id {pk},
                propietario TEXT NOT NULL,
                clave TEXT NOT NULL,
                valor TEXT,
                UNIQUE (propietario, clave)
            )
            """
        ))
        conn.execute(text(
            f"""
            CREATE TABLE IF NOT EXISTS usuarios (
                id {pk},
                email TEXT NOT NULL UNIQUE,
                nombre TEXT NOT NULL DEFAULT '',
                password_hash TEXT,
                rol TEXT NOT NULL DEFAULT 'usuario' CHECK (rol IN ('usuario', 'superadmin')),
                activo INTEGER NOT NULL DEFAULT 1,
                creado TEXT NOT NULL,
                ultimo_acceso TEXT
            )
            """
        ))
        conn.execute(text(
            f"""
            CREATE TABLE IF NOT EXISTS accesos (
                id {pk},
                email TEXT NOT NULL,
                ts TEXT NOT NULL,
                evento TEXT NOT NULL,
                detalle TEXT
            )
            """
        ))

        # --- Migración multiusuario -------------------------------------
        # Para bases creadas antes de añadir `propietario`: añade la columna,
        # asigna los datos existentes al superadmin y quita los UNIQUE(nombre)
        # que impedirían que dos usuarios tengan cuentas/categorías homónimas.
        for tabla in TABLAS_DATOS:
            try:
                if _es_postgres():
                    conn.execute(text(f"ALTER TABLE {tabla} ADD COLUMN IF NOT EXISTS propietario TEXT"))
                else:
                    cols = {r[1] for r in conn.execute(text(f"PRAGMA table_info({tabla})"))}
                    if "propietario" not in cols:
                        conn.execute(text(f"ALTER TABLE {tabla} ADD COLUMN propietario TEXT"))
            except Exception:
                pass
            try:
                conn.execute(
                    text(f"UPDATE {tabla} SET propietario = :su WHERE propietario IS NULL"),
                    {"su": SUPERADMIN_EMAIL},
                )
            except Exception:
                pass
        if _es_postgres():
            for tabla, cons in (("cuentas", "cuentas_nombre_key"), ("categorias", "categorias_nombre_key")):
                try:
                    conn.execute(text(f"ALTER TABLE {tabla} DROP CONSTRAINT IF EXISTS {cons}"))
                except Exception:
                    pass

        # El superadmin existe desde el principio, sin contraseña: la crea él
        # mismo la primera vez que entra.
        conn.execute(
            text(
                "INSERT INTO usuarios (email, nombre, rol, activo, creado) "
                "VALUES (:email, :nombre, 'superadmin', 1, :creado) "
                "ON CONFLICT (email) DO NOTHING"
            ),
            {"email": SUPERADMIN_EMAIL, "nombre": "Álvaro", "creado": dt.datetime.utcnow().isoformat()},
        )
    _inicializado = True


def _prop(propietario: str | None) -> str:
    return (propietario or _propietario()).strip().lower()


# ---------------------------------------------------------------- Cuentas ----

def anadir_cuenta(nombre: str, propietario: str | None = None) -> None:
    init_db()
    _ejecutar(
        "INSERT INTO cuentas (nombre, propietario) VALUES (:nombre, :prop)",
        {"nombre": nombre, "prop": _prop(propietario)},
    )


def actualizar_cuenta_nombre(id_: int, nombre: str, propietario: str | None = None) -> None:
    _ejecutar(
        "UPDATE cuentas SET nombre = :nombre WHERE id = :id AND propietario = :prop",
        {"nombre": nombre, "id": id_, "prop": _prop(propietario)},
    )


def cargar_cuentas(propietario: str | None = None) -> pd.DataFrame:
    init_db()
    return _leer(
        "SELECT * FROM cuentas WHERE propietario = :prop ORDER BY nombre",
        {"prop": _prop(propietario)},
    )


def eliminar_cuenta(id_: int, propietario: str | None = None) -> None:
    _ejecutar(
        "DELETE FROM cuentas WHERE id = :id AND propietario = :prop",
        {"id": id_, "prop": _prop(propietario)},
    )


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
    importes_meses: dict[int, float] | None = None, propietario: str | None = None,
) -> None:
    init_db()
    meses_txt = ",".join(str(m) for m in sorted(meses_aplicables)) if meses_aplicables else None
    importes_meses_txt = _serializar_importes_meses(importes_meses)
    _ejecutar(
        """INSERT INTO conceptos
           (cuenta_id, nombre, tipo, modo, grupo, importe, fecha_inicio, meses_duracion,
            meses_aplicables, importes_meses, activo, propietario)
           VALUES (:cuenta_id, :nombre, :tipo, :modo, :grupo, :importe, :fecha_inicio,
                   :meses_duracion, :meses_aplicables, :importes_meses, 1, :prop)""",
        {
            "cuenta_id": cuenta_id, "nombre": nombre, "tipo": tipo, "modo": modo, "grupo": grupo,
            "importe": importe, "fecha_inicio": fecha_inicio.isoformat(),
            "meses_duracion": meses_duracion, "meses_aplicables": meses_txt,
            "importes_meses": importes_meses_txt, "prop": _prop(propietario),
        },
    )


def cargar_conceptos(propietario: str | None = None) -> pd.DataFrame:
    init_db()
    df = _leer(
        """
        SELECT conceptos.*, cuentas.nombre AS cuenta
        FROM conceptos JOIN cuentas ON cuentas.id = conceptos.cuenta_id
        WHERE conceptos.propietario = :prop
        ORDER BY cuentas.nombre, conceptos.tipo, conceptos.nombre
        """,
        {"prop": _prop(propietario)},
    )
    if not df.empty:
        df["activo"] = df["activo"].astype(bool)
    return df


def actualizar_concepto_activo(id_: int, activo: bool, propietario: str | None = None) -> None:
    _ejecutar(
        "UPDATE conceptos SET activo = :activo WHERE id = :id AND propietario = :prop",
        {"activo": int(activo), "id": id_, "prop": _prop(propietario)},
    )


def actualizar_concepto(
    id_: int, cuenta_id: int, nombre: str, tipo: str, modo: str, grupo: str, importe: float,
    fecha_inicio: dt.date, meses_duracion: int | None, meses_aplicables: list[int] | None,
    importes_meses: dict[int, float] | None = None, propietario: str | None = None,
) -> None:
    meses_txt = ",".join(str(m) for m in sorted(meses_aplicables)) if meses_aplicables else None
    importes_meses_txt = _serializar_importes_meses(importes_meses)
    _ejecutar(
        """UPDATE conceptos SET
               cuenta_id = :cuenta_id, nombre = :nombre, tipo = :tipo, modo = :modo,
               grupo = :grupo, importe = :importe, fecha_inicio = :fecha_inicio,
               meses_duracion = :meses_duracion, meses_aplicables = :meses_aplicables,
               importes_meses = :importes_meses
           WHERE id = :id AND propietario = :prop""",
        {
            "cuenta_id": cuenta_id, "nombre": nombre, "tipo": tipo, "modo": modo, "grupo": grupo,
            "importe": importe, "fecha_inicio": fecha_inicio.isoformat(),
            "meses_duracion": meses_duracion, "meses_aplicables": meses_txt,
            "importes_meses": importes_meses_txt, "id": id_, "prop": _prop(propietario),
        },
    )


def eliminar_concepto(id_: int, propietario: str | None = None) -> None:
    prop = _prop(propietario)
    _ejecutar("DELETE FROM conceptos WHERE id = :id AND propietario = :prop", {"id": id_, "prop": prop})
    _ejecutar(
        "DELETE FROM valores_mensuales WHERE tipo_padre = 'concepto' AND padre_id = :id AND propietario = :prop",
        {"id": id_, "prop": prop},
    )


# ---------------------------------------------------------------- Deudas ----
# tipo_pago='fijo': cuota_mensual constante. tipo_pago='variable': la cuota
# de cada mes se registra en valores_mensuales.

def anadir_deuda(
    cuenta_id: int | None, nombre: str, importe_total: float, importe_pendiente: float,
    tipo_pago: str, cuota_mensual: float | None, meses_total: int | None,
    fecha_inicio: dt.date, propietario: str | None = None,
) -> None:
    init_db()
    _ejecutar(
        """INSERT INTO deudas
           (cuenta_id, nombre, importe_total, importe_pendiente, tipo_pago,
            cuota_mensual, meses_total, fecha_inicio, activa, propietario)
           VALUES (:cuenta_id, :nombre, :importe_total, :importe_pendiente, :tipo_pago,
                   :cuota_mensual, :meses_total, :fecha_inicio, 1, :prop)""",
        {
            "cuenta_id": cuenta_id, "nombre": nombre, "importe_total": importe_total,
            "importe_pendiente": importe_pendiente, "tipo_pago": tipo_pago,
            "cuota_mensual": cuota_mensual, "meses_total": meses_total,
            "fecha_inicio": fecha_inicio.isoformat(), "prop": _prop(propietario),
        },
    )


def cargar_deudas(propietario: str | None = None) -> pd.DataFrame:
    init_db()
    df = _leer(
        """
        SELECT deudas.*, cuentas.nombre AS cuenta
        FROM deudas LEFT JOIN cuentas ON cuentas.id = deudas.cuenta_id
        WHERE deudas.propietario = :prop
        ORDER BY fecha_inicio
        """,
        {"prop": _prop(propietario)},
    )
    if not df.empty:
        df["activa"] = df["activa"].astype(bool)
    return df


def actualizar_deuda_pendiente(id_: int, nuevo_pendiente: float, propietario: str | None = None) -> None:
    _ejecutar(
        "UPDATE deudas SET importe_pendiente = :p WHERE id = :id AND propietario = :prop",
        {"p": max(nuevo_pendiente, 0.0), "id": id_, "prop": _prop(propietario)},
    )


def actualizar_deuda(
    id_: int, cuenta_id: int | None, nombre: str, importe_total: float, importe_pendiente: float,
    tipo_pago: str, cuota_mensual: float | None, meses_total: int | None, fecha_inicio: dt.date,
    propietario: str | None = None,
) -> None:
    _ejecutar(
        """UPDATE deudas SET
               cuenta_id = :cuenta_id, nombre = :nombre, importe_total = :importe_total,
               importe_pendiente = :importe_pendiente, tipo_pago = :tipo_pago,
               cuota_mensual = :cuota_mensual, meses_total = :meses_total,
               fecha_inicio = :fecha_inicio
           WHERE id = :id AND propietario = :prop""",
        {
            "cuenta_id": cuenta_id, "nombre": nombre, "importe_total": importe_total,
            "importe_pendiente": max(importe_pendiente, 0.0), "tipo_pago": tipo_pago,
            "cuota_mensual": cuota_mensual, "meses_total": meses_total,
            "fecha_inicio": fecha_inicio.isoformat(), "id": id_, "prop": _prop(propietario),
        },
    )


def actualizar_deuda_activa(id_: int, activa: bool, propietario: str | None = None) -> None:
    _ejecutar(
        "UPDATE deudas SET activa = :activa WHERE id = :id AND propietario = :prop",
        {"activa": int(activa), "id": id_, "prop": _prop(propietario)},
    )


def eliminar_deuda(id_: int, propietario: str | None = None) -> None:
    prop = _prop(propietario)
    _ejecutar("DELETE FROM deudas WHERE id = :id AND propietario = :prop", {"id": id_, "prop": prop})
    _ejecutar(
        "DELETE FROM valores_mensuales WHERE tipo_padre = 'deuda' AND padre_id = :id AND propietario = :prop",
        {"id": id_, "prop": prop},
    )


# ------------------------------------------------------ Ahorros / inversiones ----

def anadir_ahorro(
    cuenta_id: int | None, nombre: str, tipo: str, instrumento: str,
    objetivo: float, aportado: float, actual: float, comisiones: float,
    aportacion_mensual: float | None, fecha_objetivo: dt.date | None, propietario: str | None = None,
) -> None:
    init_db()
    _ejecutar(
        """INSERT INTO ahorros
           (cuenta_id, nombre, tipo, instrumento, objetivo, aportado, actual, comisiones,
            aportacion_mensual, fecha_objetivo, activa, propietario)
           VALUES (:cuenta_id, :nombre, :tipo, :instrumento, :objetivo, :aportado, :actual,
                   :comisiones, :aportacion_mensual, :fecha_objetivo, 1, :prop)""",
        {
            "cuenta_id": cuenta_id, "nombre": nombre, "tipo": tipo, "instrumento": instrumento,
            "objetivo": objetivo, "aportado": aportado, "actual": actual, "comisiones": comisiones,
            "aportacion_mensual": aportacion_mensual,
            "fecha_objetivo": fecha_objetivo.isoformat() if fecha_objetivo else None,
            "prop": _prop(propietario),
        },
    )


def cargar_ahorros(propietario: str | None = None) -> pd.DataFrame:
    init_db()
    df = _leer(
        """
        SELECT ahorros.*, cuentas.nombre AS cuenta
        FROM ahorros LEFT JOIN cuentas ON cuentas.id = ahorros.cuenta_id
        WHERE ahorros.propietario = :prop
        ORDER BY ahorros.id
        """,
        {"prop": _prop(propietario)},
    )
    if not df.empty:
        df["activa"] = df["activa"].astype(bool)
    return df


def actualizar_ahorro_actual(id_: int, nuevo_actual: float, propietario: str | None = None) -> None:
    _ejecutar(
        "UPDATE ahorros SET actual = :a WHERE id = :id AND propietario = :prop",
        {"a": nuevo_actual, "id": id_, "prop": _prop(propietario)},
    )


def actualizar_ahorro(
    id_: int, cuenta_id: int | None, nombre: str, tipo: str, instrumento: str,
    objetivo: float, aportado: float, actual: float, comisiones: float,
    aportacion_mensual: float | None, fecha_objetivo: dt.date | None, propietario: str | None = None,
) -> None:
    _ejecutar(
        """UPDATE ahorros SET
               cuenta_id = :cuenta_id, nombre = :nombre, tipo = :tipo, instrumento = :instrumento,
               objetivo = :objetivo, aportado = :aportado, actual = :actual, comisiones = :comisiones,
               aportacion_mensual = :aportacion_mensual, fecha_objetivo = :fecha_objetivo
           WHERE id = :id AND propietario = :prop""",
        {
            "cuenta_id": cuenta_id, "nombre": nombre, "tipo": tipo, "instrumento": instrumento,
            "objetivo": objetivo, "aportado": aportado, "actual": actual, "comisiones": comisiones,
            "aportacion_mensual": aportacion_mensual,
            "fecha_objetivo": fecha_objetivo.isoformat() if fecha_objetivo else None,
            "id": id_, "prop": _prop(propietario),
        },
    )


def actualizar_ahorro_activa(id_: int, activa: bool, propietario: str | None = None) -> None:
    _ejecutar(
        "UPDATE ahorros SET activa = :activa WHERE id = :id AND propietario = :prop",
        {"activa": int(activa), "id": id_, "prop": _prop(propietario)},
    )


def eliminar_ahorro(id_: int, propietario: str | None = None) -> None:
    _ejecutar(
        "DELETE FROM ahorros WHERE id = :id AND propietario = :prop",
        {"id": id_, "prop": _prop(propietario)},
    )


# ---------------------------------------------------------- Movimientos puntuales ----
# Entradas manuales de un gasto o ingreso de un mes concreto, sin relación con
# ningún concepto recurrente ni deuda (p.ej. una compra puntual).

def anadir_movimiento(
    cuenta_id: int | None, fecha: dt.date, concepto: str, importe: float, categoria: str,
    propietario: str | None = None,
) -> None:
    init_db()
    _ejecutar(
        """INSERT INTO movimientos (cuenta_id, fecha, concepto, importe, categoria, propietario)
           VALUES (:cuenta_id, :fecha, :concepto, :importe, :categoria, :prop)""",
        {
            "cuenta_id": cuenta_id, "fecha": fecha.isoformat(), "concepto": concepto,
            "importe": importe, "categoria": categoria, "prop": _prop(propietario),
        },
    )


def cargar_movimientos(propietario: str | None = None) -> pd.DataFrame:
    init_db()
    df = _leer(
        """
        SELECT movimientos.*, cuentas.nombre AS cuenta
        FROM movimientos LEFT JOIN cuentas ON cuentas.id = movimientos.cuenta_id
        WHERE movimientos.propietario = :prop
        ORDER BY fecha DESC, movimientos.id DESC
        """,
        {"prop": _prop(propietario)},
    )
    if not df.empty:
        df["fecha"] = pd.to_datetime(df["fecha"])
    return df


def eliminar_movimiento(id_: int, propietario: str | None = None) -> None:
    _ejecutar(
        "DELETE FROM movimientos WHERE id = :id AND propietario = :prop",
        {"id": id_, "prop": _prop(propietario)},
    )


# ---------------------------------------------------------- Planes a largo plazo ----

def anadir_plan(
    nombre: str, descripcion: str, importe_objetivo: float,
    fecha_objetivo: dt.date | None, notas: str, propietario: str | None = None,
) -> None:
    init_db()
    _ejecutar(
        """INSERT INTO planes (nombre, descripcion, importe_objetivo, fecha_objetivo, notas, propietario)
           VALUES (:nombre, :descripcion, :importe_objetivo, :fecha_objetivo, :notas, :prop)""",
        {
            "nombre": nombre, "descripcion": descripcion, "importe_objetivo": importe_objetivo,
            "fecha_objetivo": fecha_objetivo.isoformat() if fecha_objetivo else None,
            "notas": notas, "prop": _prop(propietario),
        },
    )


def cargar_planes(propietario: str | None = None) -> pd.DataFrame:
    init_db()
    return _leer(
        "SELECT * FROM planes WHERE propietario = :prop ORDER BY fecha_objetivo",
        {"prop": _prop(propietario)},
    )


def actualizar_plan(
    id_: int, nombre: str, descripcion: str, importe_objetivo: float,
    fecha_objetivo: dt.date | None, notas: str, propietario: str | None = None,
) -> None:
    _ejecutar(
        """UPDATE planes SET
               nombre = :nombre, descripcion = :descripcion, importe_objetivo = :importe_objetivo,
               fecha_objetivo = :fecha_objetivo, notas = :notas
           WHERE id = :id AND propietario = :prop""",
        {
            "nombre": nombre, "descripcion": descripcion, "importe_objetivo": importe_objetivo,
            "fecha_objetivo": fecha_objetivo.isoformat() if fecha_objetivo else None,
            "notas": notas, "id": id_, "prop": _prop(propietario),
        },
    )


def eliminar_plan(id_: int, propietario: str | None = None) -> None:
    _ejecutar(
        "DELETE FROM planes WHERE id = :id AND propietario = :prop",
        {"id": id_, "prop": _prop(propietario)},
    )


# -------------------------------------------- Valores mensuales (variable) ----
# Importe real registrado para un mes concreto de un concepto o deuda
# "variable". Si no hay valor para un mes (normalmente futuro), la proyección
# usa la media de los últimos registrados como estimación.

def registrar_valor_mensual(
    tipo_padre: str, padre_id: int, periodo: str, importe: float, propietario: str | None = None,
) -> None:
    init_db()
    _ejecutar(
        """INSERT INTO valores_mensuales (tipo_padre, padre_id, periodo, importe, propietario)
           VALUES (:tipo_padre, :padre_id, :periodo, :importe, :prop)
           ON CONFLICT (tipo_padre, padre_id, periodo) DO UPDATE SET importe = excluded.importe""",
        {"tipo_padre": tipo_padre, "padre_id": padre_id, "periodo": periodo,
         "importe": importe, "prop": _prop(propietario)},
    )


def cargar_valores_mensuales(
    tipo_padre: str | None = None, padre_id: int | None = None, propietario: str | None = None,
) -> pd.DataFrame:
    init_db()
    query = "SELECT * FROM valores_mensuales WHERE propietario = :prop"
    params: dict = {"prop": _prop(propietario)}
    if tipo_padre:
        query += " AND tipo_padre = :tipo_padre"
        params["tipo_padre"] = tipo_padre
    if padre_id is not None:
        query += " AND padre_id = :padre_id"
        params["padre_id"] = padre_id
    query += " ORDER BY periodo DESC"
    return _leer(query, params)


def eliminar_valor_mensual(id_: int, propietario: str | None = None) -> None:
    _ejecutar(
        "DELETE FROM valores_mensuales WHERE id = :id AND propietario = :prop",
        {"id": id_, "prop": _prop(propietario)},
    )


# ---------------------------------------------------------------- Categorías ----
# Cada usuario tiene su propia lista. La primera vez se siembran las de defecto.

def anadir_categoria(nombre: str, propietario: str | None = None) -> None:
    init_db()
    prop = _prop(propietario)
    existentes = {c.lower() for c in cargar_categorias(prop)}
    if nombre.strip().lower() not in existentes:
        _ejecutar(
            "INSERT INTO categorias (nombre, propietario) VALUES (:nombre, :prop)",
            {"nombre": nombre.strip(), "prop": prop},
        )


def cargar_categorias(propietario: str | None = None) -> list[str]:
    init_db()
    prop = _prop(propietario)
    df = _leer(
        "SELECT nombre FROM categorias WHERE propietario = :prop ORDER BY nombre",
        {"prop": prop},
    )
    if df.empty:
        _ejecutar(
            "INSERT INTO categorias (nombre, propietario) VALUES (:nombre, :prop)",
            [{"nombre": n, "prop": prop} for n in CATEGORIAS_DEFECTO],
        )
        df = _leer(
            "SELECT nombre FROM categorias WHERE propietario = :prop ORDER BY nombre",
            {"prop": prop},
        )
    return df["nombre"].tolist() if not df.empty else []


def eliminar_categoria(nombre: str, propietario: str | None = None) -> None:
    _ejecutar(
        "DELETE FROM categorias WHERE nombre = :nombre AND propietario = :prop",
        {"nombre": nombre, "prop": _prop(propietario)},
    )


# ---------------------------------------------------------------- Logos ----

TABLAS_CON_LOGO = ("cuentas", "conceptos", "deudas", "ahorros")


def actualizar_logo(tabla: str, id_: int, ruta: str | None, propietario: str | None = None) -> None:
    if tabla not in TABLAS_CON_LOGO:
        raise ValueError(f"Tabla sin columna logo: {tabla}")
    _ejecutar(
        f"UPDATE {tabla} SET logo = :ruta WHERE id = :id AND propietario = :prop",
        {"ruta": ruta, "id": id_, "prop": _prop(propietario)},
    )


# ---------------------------------------------------------- Usuarios / accesos ----
# Tablas globales (no llevan propietario): gestión de cuentas de acceso y log.

def obtener_usuario(email: str) -> dict | None:
    init_db()
    df = _leer("SELECT * FROM usuarios WHERE email = :email", {"email": email.strip().lower()})
    return df.iloc[0].to_dict() if not df.empty else None


def crear_usuario(email: str, nombre: str, rol: str = "usuario") -> None:
    init_db()
    _ejecutar(
        "INSERT INTO usuarios (email, nombre, rol, activo, creado) "
        "VALUES (:email, :nombre, :rol, 1, :creado) ON CONFLICT (email) DO NOTHING",
        {"email": email.strip().lower(), "nombre": nombre, "rol": rol,
         "creado": dt.datetime.utcnow().isoformat()},
    )


def establecer_password(email: str, password_hash: str) -> None:
    _ejecutar(
        "UPDATE usuarios SET password_hash = :h WHERE email = :email",
        {"h": password_hash, "email": email.strip().lower()},
    )


def actualizar_ultimo_acceso(email: str) -> None:
    _ejecutar(
        "UPDATE usuarios SET ultimo_acceso = :ts WHERE email = :email",
        {"ts": dt.datetime.utcnow().isoformat(), "email": email.strip().lower()},
    )


def set_usuario_activo(email: str, activo: bool) -> None:
    _ejecutar(
        "UPDATE usuarios SET activo = :a WHERE email = :email",
        {"a": int(activo), "email": email.strip().lower()},
    )


def eliminar_usuario(email: str) -> None:
    _ejecutar("DELETE FROM usuarios WHERE email = :email AND rol <> 'superadmin'",
              {"email": email.strip().lower()})


def cargar_usuarios() -> pd.DataFrame:
    init_db()
    df = _leer("SELECT * FROM usuarios ORDER BY creado")
    if not df.empty:
        df["activo"] = df["activo"].astype(bool)
    return df


def registrar_acceso(email: str, evento: str, detalle: str = "") -> None:
    init_db()
    _ejecutar(
        "INSERT INTO accesos (email, ts, evento, detalle) VALUES (:email, :ts, :evento, :detalle)",
        {"email": email.strip().lower(), "ts": dt.datetime.utcnow().isoformat(),
         "evento": evento, "detalle": detalle},
    )


def cargar_accesos(limite: int = 200) -> pd.DataFrame:
    init_db()
    return _leer("SELECT * FROM accesos ORDER BY ts DESC LIMIT :lim", {"lim": limite})


# ---------------------------------------------------------- Preferencias ----
# Ajustes por usuario (p. ej. qué KPIs mostrar en Inicio).

def get_preferencia(clave: str, default: str = "", propietario: str | None = None) -> str:
    init_db()
    df = _leer(
        "SELECT valor FROM preferencias WHERE propietario = :p AND clave = :c",
        {"p": _prop(propietario), "c": clave},
    )
    if df.empty:
        return default
    valor = df.iloc[0]["valor"]
    return default if valor is None else str(valor)


def set_preferencia(clave: str, valor: str, propietario: str | None = None) -> None:
    init_db()
    _ejecutar(
        "INSERT INTO preferencias (propietario, clave, valor) VALUES (:p, :c, :v) "
        "ON CONFLICT (propietario, clave) DO UPDATE SET valor = excluded.valor",
        {"p": _prop(propietario), "c": clave, "v": valor},
    )
