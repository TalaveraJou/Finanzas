# Finanzas

Herramienta personal de control de finanzas. Entrada manual, sin integración bancaria. 100 % gratuita (Python + SQLite + Streamlit).

## Arrancar

```bash
python -m venv .venv && source .venv/bin/activate   # Windows: .venv\Scripts\activate
pip install -r requirements.txt
streamlit run app.py
```

## Estructura

- `app.py`: interfaz (menú lateral + páginas)
- `finanzas/db.py`: SQLite en `data/finanzas.db`
- `finanzas/categorias.py`: lista de categorías (`config/categorias.json`)

## Privacidad

`data/*.db` y los `*.csv` están en `.gitignore`. No subas datos reales al repositorio.
