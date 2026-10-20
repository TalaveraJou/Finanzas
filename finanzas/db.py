import datetime as dt
import sqlite3
from pathlib import Path

import pandas as pd

DB_PATH = Path(__file__).resolve().parent.parent / "data" / "finanzas.db"


def _conectar() -> sqlite3.Connection:
    DB_PATH.parent.mkdir(parents=True, exist_ok=True)
    conn = sqlite3.connect(DB_PATH)
    conn.execute("PRAGMA foreign_keys = ON")
    return conn


def init_db() -> None:
    with _conectar() as conn:
        conn.execute(
            """
            CREATE TABLE IF NOT EXISTS cuentas (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                nombre TEXT NOT NULL UNIQUE
            )
            """
        )
        columnas_cuentas = {r[1] for r in conn.execute("PRAGMA table_info(cuentas)")}
        if "logo" not in columnas_cuentas:
            conn.execute("ALTER TABLE cuentas ADD COLUMN logo TEXT")
        conn.execute(
            """
            CREATE TABLE IF NOT EXISTS conceptos (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
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
                activo INTEGER NOT NULL DEFAULT 1
            )
            """
        )
        columnas_conceptos = {r[1] for r in conn.execute("PRAGMA table_info(conceptos)")}
        if "meses_aplicables" not in columnas_conceptos:
            conn.execute("ALTER TABLE conceptos ADD COLUMN meses_aplicables TEXT")
        if "importes_meses" not in columnas_conceptos:
            conn.execute("ALTER TABLE conceptos ADD COLUMN importes_meses TEXT")

        definicion = conn.execute(
            "SELECT sql FROM sqlite_master WHERE type='table' AND name='conceptos'"
        ).fetchone()
        if definicion and "CHECK (modo IN" in definicion[0]:
            # Migración: quitamos el CHECK antiguo de `modo` para poder añadir
            # los modos 'porcentaje_ingreso' y 'remanente' sin romper datos existentes.
            conn.execute("ALTER TABLE conceptos RENAME TO conceptos_old")
            conn.execute(
                """
                CREATE TABLE conceptos (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    cuenta_id INTEGER NOT NULL REFERENCES cuentas(id) ON DELETE CASCADE,
                    nombre TEXT NOT NULL,
                    tipo TEXT NOT NULL CHECK (tipo IN ('ingreso', 'gasto')),
                    modo TEXT NOT NULL DEFAULT 'fijo',
                    grupo TEXT NOT NULL DEFAULT '',
                    importe REAL NOT NULL DEFAULT 0,
                    fecha_inicio TEXT NOT NULL,
                    meses_duracion INTEGER,
                    meses_aplicables TEXT,
                    activo INTEGER NOT NULL DEFAULT 1
                )
                """
            )
            conn.execute(
                """INSERT INTO conceptos
                   (id, cuenta_id, nombre, tipo, modo, grupo, importe, fecha_inicio,
                    meses_duracion, meses_aplicables, activo)
                   SELECT id, cuenta_id, nombre, tipo, modo, grupo, importe, fecha_inicio,
                          meses_duracion, meses_aplicables, activo
                   FROM conceptos_old"""
            )
            conn.execute("DROP TABLE conceptos_old")

        columnas_conceptos = {r[1] for r in conn.execute("PRAGMA table_info(conceptos)")}
        if "logo" not in columnas_conceptos:
            conn.execute("ALTER TABLE conceptos ADD COLUMN logo TEXT")

        conn.execute(
            """
            CREATE TABLE IF NOT EXISTS deudas (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                cuenta_id INTEGER REFERENCES cuentas(id) ON DELETE SET NULL,
                nombre TEXT NOT NULL,
                importe_total REAL NOT NULL,
                importe_pendiente REAL NOT NULL,
                tipo_pago TEXT NOT NULL DEFAULT 'fijo' CHECK (tipo_pago IN ('fijo', 'variable')),
                cuota_mensual REAL,
                meses_total INTEGER,
                fecha_inicio TEXT NOT NULL,
                activa INTEGER NOT NULL DEFAULT 1
            )
            """
        )
        columnas_deudas = {r[1] for r in conn.execute("PRAGMA table_info(deudas)")}
        if "logo" not in columnas_deudas:
            conn.execute("ALTER TABLE deudas ADD COLUMN logo TEXT")
        conn.execute(
            """
            CREATE TABLE IF NOT EXISTS ahorros (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                cuenta_id INTEGER REFERENCES cuentas(id) ON DELETE SET NULL,
                nombre TEXT NOT NULL,
                objetivo REAL NOT NULL,
                actual REAL NOT NULL DEFAULT 0,
                aportacion_mensual REAL,
                fecha_objetivo TEXT,
                activa INTEGER NOT NULL DEFAULT 1
            )
            """
        )
        columnas_ahorros = {r[1] for r in conn.execute("PRAGMA table_info(ahorros)")}
        if "tipo" not in columnas_ahorros:
            conn.execute("ALTER TABLE ahorros ADD COLUMN tipo TEXT NOT NULL DEFAULT 'ahorro'")
        if "instrumento" not in columnas_ahorros:
            conn.execute("ALTER TABLE ahorros ADD COLUMN instrumento TEXT NOT NULL DEFAULT ''")
        if "aportado" not in columnas_ahorros:
            conn.execute("ALTER TABLE ahorros ADD COLUMN aportado REAL NOT NULL DEFAULT 0")
            conn.execute("UPDATE ahorros SET aportado = actual")
        if "comisiones" not in columnas_ahorros:
            conn.execute("ALTER TABLE ahorros ADD COLUMN comisiones REAL NOT NULL DEFAULT 0")
        if "logo" not in columnas_ahorros:
            conn.execute("ALTER TABLE ahorros ADD COLUMN logo TEXT")
        conn.execute(
            """
            CREATE TABLE IF NOT EXISTS movimientos (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                cuenta_id INTEGER REFERENCES cuentas(id) ON DELETE SET NULL,
                fecha TEXT NOT NULL,
                concepto TEXT NOT NULL,
                importe REAL NOT NULL,
                categoria TEXT NOT NULL
            )
            """
        )
        conn.execute(
            """
            CREATE TABLE IF NOT EXISTS planes (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                nombre TEXT NOT NULL,
                descripcion TEXT,
                importe_objetivo REAL NOT NULL,
                fecha_objetivo TEXT,
                notas TEXT
            )
            """
        )
        conn.execute(
            """
            CREATE TABLE IF NOT EXISTS valores_mensuales (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                tipo_padre TEXT NOT NULL CHECK (tipo_padre IN ('concepto', 'deuda')),
                padre_id INTEGER NOT NULL,
                periodo TEXT NOT NULL,
                importe REAL NOT NULL,
                UNIQUE (tipo_padre, padre_id, periodo)
            )
            """
        )
        conn.execute(
            """
            CREATE TABLE IF NOT EXISTS categorias (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                nombre TEXT NOT NULL UNIQUE
            )
            """
        )
        if conn.execute("SELECT COUNT(*) FROM categorias").fetchone()[0] == 0:
            conn.executemany(
                "INSERT INTO categorias (nombre) VALUES (?)",
                [(n,) for n in (
                    "Vivienda", "Suministros", "Alimentación", "Transporte", "Salud",
                    "Ocio", "Ropa", "Educación", "Suscripciones", "Dispositivos",
                    "Deporte", "Nómina", "Freelance", "Inversiones", "Otros",
                )],
            )


# ---------------------------------------------------------------- Cuentas ----

def anadir_cuenta(nombre: str) -> None:
    init_db()
    with _conectar() as conn:
        conn.execute("INSERT INTO cuentas (nombre) VALUES (?)", (nombre,))


def actualizar_cuenta_nombre(id_: int, nombre: str) -> None:
    with _conectar() as conn:
        conn.execute("UPDATE cuentas SET nombre = ? WHERE id = ?", (nombre, id_))


def cargar_cuentas() -> pd.DataFrame:
    init_db()
    with _conectar() as conn:
        return pd.read_sql_query("SELECT * FROM cuentas ORDER BY nombre", conn)


def eliminar_cuenta(id_: int) -> None:
    with _conectar() as conn:
        conn.execute("DELETE FROM cuentas WHERE id = ?", (id_,))


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
    with _conectar() as conn:
        conn.execute(
            """INSERT INTO conceptos
               (cuenta_id, nombre, tipo, modo, grupo, importe, fecha_inicio, meses_duracion,
                meses_aplicables, importes_meses, activo)
               VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, 1)""",
            (cuenta_id, nombre, tipo, modo, grupo, importe, fecha_inicio.isoformat(),
             meses_duracion, meses_txt, importes_meses_txt),
        )


def cargar_conceptos() -> pd.DataFrame:
    init_db()
    with _conectar() as conn:
        df = pd.read_sql_query(
            """
            SELECT conceptos.*, cuentas.nombre AS cuenta
            FROM conceptos JOIN cuentas ON cuentas.id = conceptos.cuenta_id
            ORDER BY cuentas.nombre, conceptos.tipo, conceptos.nombre
            """,
            conn,
        )
    if not df.empty:
        df["activo"] = df["activo"].astype(bool)
    return df


def actualizar_concepto_activo(id_: int, activo: bool) -> None:
    with _conectar() as conn:
        conn.execute("UPDATE conceptos SET activo = ? WHERE id = ?", (int(activo), id_))


def actualizar_concepto(
    id_: int, cuenta_id: int, nombre: str, tipo: str, modo: str, grupo: str, importe: float,
    fecha_inicio: dt.date, meses_duracion: int | None, meses_aplicables: list[int] | None,
    importes_meses: dict[int, float] | None = None,
) -> None:
    meses_txt = ",".join(str(m) for m in sorted(meses_aplicables)) if meses_aplicables else None
    importes_meses_txt = _serializar_importes_meses(importes_meses)
    with _conectar() as conn:
        conn.execute(
            """UPDATE conceptos SET
                   cuenta_id = ?, nombre = ?, tipo = ?, modo = ?, grupo = ?, importe = ?,
                   fecha_inicio = ?, meses_duracion = ?, meses_aplicables = ?, importes_meses = ?
               WHERE id = ?""",
            (cuenta_id, nombre, tipo, modo, grupo, importe, fecha_inicio.isoformat(),
             meses_duracion, meses_txt, importes_meses_txt, id_),
        )


def eliminar_concepto(id_: int) -> None:
    with _conectar() as conn:
        conn.execute("DELETE FROM conceptos WHERE id = ?", (id_,))
        conn.execute("DELETE FROM valores_mensuales WHERE tipo_padre = 'concepto' AND padre_id = ?", (id_,))


# ---------------------------------------------------------------- Deudas ----
# tipo_pago='fijo': cuota_mensual constante. tipo_pago='variable': la cuota
# de cada mes se registra en valores_mensuales.

def anadir_deuda(
    cuenta_id: int | None, nombre: str, importe_total: float, importe_pendiente: float,
    tipo_pago: str, cuota_mensual: float | None, meses_total: int | None,
    fecha_inicio: dt.date,
) -> None:
    init_db()
    with _conectar() as conn:
        conn.execute(
            """INSERT INTO deudas
               (cuenta_id, nombre, importe_total, importe_pendiente, tipo_pago,
                cuota_mensual, meses_total, fecha_inicio, activa)
               VALUES (?, ?, ?, ?, ?, ?, ?, ?, 1)""",
            (cuenta_id, nombre, importe_total, importe_pendiente, tipo_pago,
             cuota_mensual, meses_total, fecha_inicio.isoformat()),
        )


def cargar_deudas() -> pd.DataFrame:
    init_db()
    with _conectar() as conn:
        df = pd.read_sql_query(
            """
            SELECT deudas.*, cuentas.nombre AS cuenta
            FROM deudas LEFT JOIN cuentas ON cuentas.id = deudas.cuenta_id
            ORDER BY fecha_inicio
            """,
            conn,
        )
    if not df.empty:
        df["activa"] = df["activa"].astype(bool)
    return df


def actualizar_deuda_pendiente(id_: int, nuevo_pendiente: float) -> None:
    with _conectar() as conn:
        conn.execute(
            "UPDATE deudas SET importe_pendiente = ? WHERE id = ?", (max(nuevo_pendiente, 0.0), id_)
        )


def actualizar_deuda(
    id_: int, cuenta_id: int | None, nombre: str, importe_total: float, importe_pendiente: float,
    tipo_pago: str, cuota_mensual: float | None, meses_total: int | None, fecha_inicio: dt.date,
) -> None:
    with _conectar() as conn:
        conn.execute(
            """UPDATE deudas SET
                   cuenta_id = ?, nombre = ?, importe_total = ?, importe_pendiente = ?,
                   tipo_pago = ?, cuota_mensual = ?, meses_total = ?, fecha_inicio = ?
               WHERE id = ?""",
            (cuenta_id, nombre, importe_total, max(importe_pendiente, 0.0), tipo_pago,
             cuota_mensual, meses_total, fecha_inicio.isoformat(), id_),
        )


def actualizar_deuda_activa(id_: int, activa: bool) -> None:
    with _conectar() as conn:
        conn.execute("UPDATE deudas SET activa = ? WHERE id = ?", (int(activa), id_))


def eliminar_deuda(id_: int) -> None:
    with _conectar() as conn:
        conn.execute("DELETE FROM deudas WHERE id = ?", (id_,))
        conn.execute("DELETE FROM valores_mensuales WHERE tipo_padre = 'deuda' AND padre_id = ?", (id_,))


# ------------------------------------------------------ Ahorros / inversiones ----

def anadir_ahorro(
    cuenta_id: int | None, nombre: str, tipo: str, instrumento: str,
    objetivo: float, aportado: float, actual: float, comisiones: float,
    aportacion_mensual: float | None, fecha_objetivo: dt.date | None,
) -> None:
    init_db()
    with _conectar() as conn:
        conn.execute(
            """INSERT INTO ahorros
               (cuenta_id, nombre, tipo, instrumento, objetivo, aportado, actual, comisiones,
                aportacion_mensual, fecha_objetivo, activa)
               VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, 1)""",
            (cuenta_id, nombre, tipo, instrumento, objetivo, aportado, actual, comisiones,
             aportacion_mensual, fecha_objetivo.isoformat() if fecha_objetivo else None),
        )


def cargar_ahorros() -> pd.DataFrame:
    init_db()
    with _conectar() as conn:
        df = pd.read_sql_query(
            """
            SELECT ahorros.*, cuentas.nombre AS cuenta
            FROM ahorros LEFT JOIN cuentas ON cuentas.id = ahorros.cuenta_id
            ORDER BY ahorros.id
            """,
            conn,
        )
    if not df.empty:
        df["activa"] = df["activa"].astype(bool)
    return df


def actualizar_ahorro_actual(id_: int, nuevo_actual: float) -> None:
    with _conectar() as conn:
        conn.execute("UPDATE ahorros SET actual = ? WHERE id = ?", (nuevo_actual, id_))


def actualizar_ahorro(
    id_: int, cuenta_id: int | None, nombre: str, tipo: str, instrumento: str,
    objetivo: float, aportado: float, actual: float, comisiones: float,
    aportacion_mensual: float | None, fecha_objetivo: dt.date | None,
) -> None:
    with _conectar() as conn:
        conn.execute(
            """UPDATE ahorros SET
                   cuenta_id = ?, nombre = ?, tipo = ?, instrumento = ?, objetivo = ?,
                   aportado = ?, actual = ?, comisiones = ?,
                   aportacion_mensual = ?, fecha_objetivo = ?
               WHERE id = ?""",
            (cuenta_id, nombre, tipo, instrumento, objetivo, aportado, actual, comisiones,
             aportacion_mensual, fecha_objetivo.isoformat() if fecha_objetivo else None, id_),
        )


def actualizar_ahorro_activa(id_: int, activa: bool) -> None:
    with _conectar() as conn:
        conn.execute("UPDATE ahorros SET activa = ? WHERE id = ?", (int(activa), id_))


def eliminar_ahorro(id_: int) -> None:
    with _conectar() as conn:
        conn.execute("DELETE FROM ahorros WHERE id = ?", (id_,))


# ---------------------------------------------------------- Movimientos puntuales ----
# Entradas manuales de un gasto o ingreso de un mes concreto, sin relación con
# ningún concepto recurrente ni deuda (p.ej. una compra puntual).

def anadir_movimiento(
    cuenta_id: int | None, fecha: dt.date, concepto: str, importe: float, categoria: str,
) -> None:
    init_db()
    with _conectar() as conn:
        conn.execute(
            "INSERT INTO movimientos (cuenta_id, fecha, concepto, importe, categoria) VALUES (?, ?, ?, ?, ?)",
            (cuenta_id, fecha.isoformat(), concepto, importe, categoria),
        )


def cargar_movimientos() -> pd.DataFrame:
    init_db()
    with _conectar() as conn:
        df = pd.read_sql_query(
            """
            SELECT movimientos.*, cuentas.nombre AS cuenta
            FROM movimientos LEFT JOIN cuentas ON cuentas.id = movimientos.cuenta_id
            ORDER BY fecha DESC, movimientos.id DESC
            """,
            conn,
        )
    if not df.empty:
        df["fecha"] = pd.to_datetime(df["fecha"])
    return df


def eliminar_movimiento(id_: int) -> None:
    with _conectar() as conn:
        conn.execute("DELETE FROM movimientos WHERE id = ?", (id_,))


# ---------------------------------------------------------- Planes a largo plazo ----

def anadir_plan(
    nombre: str, descripcion: str, importe_objetivo: float,
    fecha_objetivo: dt.date | None, notas: str,
) -> None:
    init_db()
    with _conectar() as conn:
        conn.execute(
            """INSERT INTO planes (nombre, descripcion, importe_objetivo, fecha_objetivo, notas)
               VALUES (?, ?, ?, ?, ?)""",
            (nombre, descripcion, importe_objetivo,
             fecha_objetivo.isoformat() if fecha_objetivo else None, notas),
        )


def cargar_planes() -> pd.DataFrame:
    init_db()
    with _conectar() as conn:
        return pd.read_sql_query("SELECT * FROM planes ORDER BY fecha_objetivo", conn)


def actualizar_plan(
    id_: int, nombre: str, descripcion: str, importe_objetivo: float,
    fecha_objetivo: dt.date | None, notas: str,
) -> None:
    with _conectar() as conn:
        conn.execute(
            """UPDATE planes SET
                   nombre = ?, descripcion = ?, importe_objetivo = ?, fecha_objetivo = ?, notas = ?
               WHERE id = ?""",
            (nombre, descripcion, importe_objetivo,
             fecha_objetivo.isoformat() if fecha_objetivo else None, notas, id_),
        )


def eliminar_plan(id_: int) -> None:
    with _conectar() as conn:
        conn.execute("DELETE FROM planes WHERE id = ?", (id_,))


# -------------------------------------------- Valores mensuales (variable) ----
# Importe real registrado para un mes concreto de un concepto o deuda
# "variable". Si no hay valor para un mes (normalmente futuro), la proyección
# usa la media de los últimos registrados como estimación.

def registrar_valor_mensual(tipo_padre: str, padre_id: int, periodo: str, importe: float) -> None:
    init_db()
    with _conectar() as conn:
        conn.execute(
            """INSERT INTO valores_mensuales (tipo_padre, padre_id, periodo, importe)
               VALUES (?, ?, ?, ?)
               ON CONFLICT(tipo_padre, padre_id, periodo) DO UPDATE SET importe = excluded.importe""",
            (tipo_padre, padre_id, periodo, importe),
        )


def cargar_valores_mensuales(tipo_padre: str | None = None, padre_id: int | None = None) -> pd.DataFrame:
    init_db()
    query = "SELECT * FROM valores_mensuales WHERE 1=1"
    params: list = []
    if tipo_padre:
        query += " AND tipo_padre = ?"
        params.append(tipo_padre)
    if padre_id is not None:
        query += " AND padre_id = ?"
        params.append(padre_id)
    query += " ORDER BY periodo DESC"
    with _conectar() as conn:
        return pd.read_sql_query(query, conn, params=params)


def eliminar_valor_mensual(id_: int) -> None:
    with _conectar() as conn:
        conn.execute("DELETE FROM valores_mensuales WHERE id = ?", (id_,))


# ---------------------------------------------------------------- Categorías ----

def anadir_categoria(nombre: str) -> None:
    init_db()
    with _conectar() as conn:
        conn.execute(
            "INSERT INTO categorias (nombre) VALUES (?) ON CONFLICT(nombre) DO NOTHING", (nombre,)
        )


def cargar_categorias() -> list[str]:
    init_db()
    with _conectar() as conn:
        filas = conn.execute("SELECT nombre FROM categorias ORDER BY nombre").fetchall()
    return [f[0] for f in filas]


def eliminar_categoria(nombre: str) -> None:
    with _conectar() as conn:
        conn.execute("DELETE FROM categorias WHERE nombre = ?", (nombre,))


# ---------------------------------------------------------------- Logos ----

TABLAS_CON_LOGO = ("cuentas", "conceptos", "deudas", "ahorros")


def actualizar_logo(tabla: str, id_: int, ruta: str | None) -> None:
    if tabla not in TABLAS_CON_LOGO:
        raise ValueError(f"Tabla sin columna logo: {tabla}")
    with _conectar() as conn:
        conn.execute(f"UPDATE {tabla} SET logo = ? WHERE id = ?", (ruta, id_))
