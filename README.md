# Finanzas

Herramienta personal de control de finanzas: ingresos, gastos, deudas, ahorros
y planes a largo plazo, con un dashboard con gráficos. Entrada manual, sin
integración bancaria. 100 % gratuita (Python + SQLite + Streamlit).

## Arrancar en local

```bash
python -m venv .venv && source .venv/bin/activate   # Windows: .venv\Scripts\activate
pip install -r requirements.txt
streamlit run app.py
```

## Usar desde el móvil (gratis)

1. Crea una cuenta gratuita en [Streamlit Community Cloud](https://streamlit.io/cloud)
   con tu usuario de GitHub.
2. "New app" → elige este repositorio, rama `main`, archivo principal `app.py`.
3. Deploy. Te da una URL pública (`https://<algo>.streamlit.app`).
4. Abre esa URL en el navegador del móvil y usa "Añadir a pantalla de inicio"
   para tenerla como si fuera una app.

Como el repo es privado, en el panel de la app activa el acceso para tu
cuenta de GitHub (Streamlit Cloud lee repos privados autorizando la app
sobre tu cuenta).

## Estructura

- `app.py`: interfaz (menú lateral + páginas: Inicio, Movimientos, Deudas, Ahorros, Planes)
- `finanzas/db.py`: SQLite en `data/finanzas.db` (movimientos, deudas, ahorros, planes)
- `finanzas/categorias.py`: lista de categorías (`config/categorias.json`)

## Privacidad

`data/*.db` y los `*.csv` están en `.gitignore`. No subas datos reales al repositorio.
Si despliegas en Streamlit Community Cloud, la base de datos vive en el propio
servidor de la app (no en GitHub), pero ten en cuenta que el almacenamiento del
plan gratuito no es persistente de forma garantizada ante reinicios: exporta
tus datos de vez en cuando si quieres respaldo.
