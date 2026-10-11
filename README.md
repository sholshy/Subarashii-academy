# Subarashii YGO Tools

Proyecto para la gestión de torneos, liga, y utilidades para la comunidad de Yu-Gi-Oh! de **Subarashii**.

## Instalación

1. Clona el repositorio.
2. Crea un entorno virtual: `python -m venv .venv`
3. Activa el entorno virtual:
   - Windows: `.venv\Scripts\activate`
   - Linux/Mac: `source .venv/bin/activate`
4. Instala las dependencias: `pip install -r requirements.txt`
5. Configura tu `.env` (si usas la interfaz web, debes definir `FLASK_SECRET_KEY`).

## Ejecución

- **Aplicación Desktop (Tkinter)**: `python app.py` o `python main.py`
- **Servidor Web (Flask)**: `python web_app.py`

## Arquitectura

- **Base de Datos**: `data/ygo_data.db` (SQLite).
  - Almacena tiendas, jugadores, perfiles de liga, resultados globales por torneo, y el registro individual de cada partida (`tournament_matches`).
- **Históricos**: `data/history/` guarda el respaldo JSON de los torneos exportados.
- **Autosave**: `data/tournament_autosave.json` mantiene el estado temporal de un torneo en curso en la UI de escritorio para evitar pérdidas ante un cierre accidental. Al exportarse, se respalda en el historial y luego se inserta automáticamente en la base de datos (vía `migrate_history.py`).

## Roadmap — Subarashii Duel Academy

El sistema actual está preparado para integrarse con **Subarashii Duel Academy**, un sistema de gamificación basado en ELO/Rating y progresión de los jugadores, inspirado en el anime.

Las siguientes estructuras ya están inicializadas en la base de datos, pendientes de implementación de lógica de negocio:
- `academy_profiles` (Rating y Dormitorio)
- `academy_rating_history` (Tracking de la evolución del ELO por cada match)
- `academy_achievements` (Logros y misiones desbloqueadas)

**Pendiente para Academia V1.0:**
1. Fórmula matemática de ELO/Rating adaptada al formato local.
2. Interfaz web o UI para mostrar perfiles públicos de Academia, ranking y dormitorios (Slifer/Ra/Obelisk).
3. Sistema de ascensos basado en temporadas.
4. Simulación histórica inicial para pre-calcular los Ratings base partiendo de los datos heredados.

## Advertencias de Seguridad

- Nunca expondremos el archivo `.env` o la base de datos `data/ygo_data.db` (si contiene datos sensibles) en el control de versiones. 
- La ruta `/register` del panel Web ahora requiere autorización explícita (vía `ALLOW_REGISTRATION=1` en el entorno) para evitar la creación indiscriminada de usuarios.


## Web Preview Local (Duelorapido.cl)
Para visualizar la web pública de la academia utilizando los datos sincronizados, ejecuta el siguiente comando en la raíz del proyecto:

`ash
python public_web.py
`

Luego, abre tu navegador en http://localhost:8000/. Esta web es **READ ONLY** y sirve los datos estáticos extraídos por el Cloud Sync en la carpeta mock_server.
