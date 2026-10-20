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
            CREATE TABLE IF NOT EXISTS movimientos (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                fecha TEXT NOT NULL,
                concepto TEXT NOT NULL,
                importe REAL NOT NULL,
                categoria TEXT NOT NULL
            )
            """
        )
        conn.execute(
            """
            CREATE TABLE IF NOT EXISTS deudas (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                nombre TEXT NOT NULL,
                importe_total REAL NOT NULL,
                importe_pendiente REAL NOT NULL,
                cuota_mensual REAL NOT NULL,
                fecha_inicio TEXT NOT NULL
            )
            """
        )
        conn.execute(
            """
            CREATE TABLE IF NOT EXISTS ahorros (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                nombre TEXT NOT NULL,
                objetivo REAL NOT NULL,
                actual REAL NOT NULL DEFAULT 0,
                fecha_objetivo TEXT
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


# ---------- Movimientos (ingresos / gastos) ----------

def anadir(fecha: dt.date, concepto: str, importe: float, categoria: str) -> None:
    init_db()
    with _conectar() as conn:
        conn.execute(
            "INSERT INTO movimientos (fecha, concepto, importe, categoria) VALUES (?, ?, ?, ?)",
            (fecha.isoformat(), concepto, importe, categoria),
        )


def cargar() -> pd.DataFrame:
    init_db()
    with _conectar() as conn:
        df = pd.read_sql_query(
            "SELECT * FROM movimientos ORDER BY fecha DESC, id DESC", conn
        )
    if not df.empty:
        df["fecha"] = pd.to_datetime(df["fecha"])
    return df


def eliminar_movimiento(id_: int) -> None:
    with _conectar() as conn:
        conn.execute("DELETE FROM movimientos WHERE id = ?", (id_,))


# ---------- Deudas ----------

def anadir_deuda(
    nombre: str, importe_total: float, importe_pendiente: float,
    cuota_mensual: float, fecha_inicio: dt.date,
) -> None:
    init_db()
    with _conectar() as conn:
        conn.execute(
            """INSERT INTO deudas
               (nombre, importe_total, importe_pendiente, cuota_mensual, fecha_inicio)
               VALUES (?, ?, ?, ?, ?)""",
            (nombre, importe_total, importe_pendiente, cuota_mensual, fecha_inicio.isoformat()),
        )


def cargar_deudas() -> pd.DataFrame:
    init_db()
    with _conectar() as conn:
        return pd.read_sql_query("SELECT * FROM deudas ORDER BY fecha_inicio", conn)


def actualizar_deuda_pendiente(id_: int, nuevo_pendiente: float) -> None:
    with _conectar() as conn:
        conn.execute(
            "UPDATE deudas SET importe_pendiente = ? WHERE id = ?", (nuevo_pendiente, id_)
        )


def eliminar_deuda(id_: int) -> None:
    with _conectar() as conn:
        conn.execute("DELETE FROM deudas WHERE id = ?", (id_,))


# ---------- Ahorros ----------

def anadir_ahorro(nombre: str, objetivo: float, actual: float, fecha_objetivo: dt.date | None) -> None:
    init_db()
    with _conectar() as conn:
        conn.execute(
            "INSERT INTO ahorros (nombre, objetivo, actual, fecha_objetivo) VALUES (?, ?, ?, ?)",
            (nombre, objetivo, actual, fecha_objetivo.isoformat() if fecha_objetivo else None),
        )


def cargar_ahorros() -> pd.DataFrame:
    init_db()
    with _conectar() as conn:
        return pd.read_sql_query("SELECT * FROM ahorros ORDER BY id", conn)


def actualizar_ahorro_actual(id_: int, nuevo_actual: float) -> None:
    with _conectar() as conn:
        conn.execute("UPDATE ahorros SET actual = ? WHERE id = ?", (nuevo_actual, id_))


def eliminar_ahorro(id_: int) -> None:
    with _conectar() as conn:
        conn.execute("DELETE FROM ahorros WHERE id = ?", (id_,))


# ---------- Planes a largo plazo ----------

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


def eliminar_plan(id_: int) -> None:
    with _conectar() as conn:
        conn.execute("DELETE FROM planes WHERE id = ?", (id_,))
