from finanzas import db


def lista_categorias() -> list[str]:
    return db.cargar_categorias()
