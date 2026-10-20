import json
from pathlib import Path

CONFIG_PATH = Path(__file__).resolve().parent.parent / "config" / "categorias.json"

_DEFAULT = {
    "gasto": [
        "Vivienda", "Suministros", "Alimentación", "Transporte", "Salud",
        "Ocio", "Ropa", "Educación", "Suscripciones", "Otros gastos",
    ],
    "ingreso": [
        "Nómina", "Freelance", "Inversiones", "Regalo", "Otros ingresos",
    ],
}


def _cargar_config() -> dict:
    if CONFIG_PATH.exists():
        with open(CONFIG_PATH, "r", encoding="utf-8") as f:
            return json.load(f)
    CONFIG_PATH.parent.mkdir(parents=True, exist_ok=True)
    with open(CONFIG_PATH, "w", encoding="utf-8") as f:
        json.dump(_DEFAULT, f, ensure_ascii=False, indent=2)
    return _DEFAULT


def lista_categorias(tipo: str | None = None) -> list[str]:
    config = _cargar_config()
    if tipo in ("gasto", "ingreso"):
        return config.get(tipo, [])
    return config.get("gasto", []) + config.get("ingreso", [])
