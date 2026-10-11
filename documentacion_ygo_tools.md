# Documentación de Funcionalidades: YGO Tools by Sholshy

Este documento describe en detalle las características y funcionalidades principales de la aplicación de escritorio **YGO Tools by Sholshy**. 

La aplicación es un completo sistema de gestión para organizadores de torneos (TOs) y tiendas de Yu-Gi-Oh!, así como una herramienta gráfica para generar imágenes de decklists de jugadores. Está desarrollada en Python, utilizando `customtkinter` para una interfaz moderna y oscura, y emplea una base de datos local SQLite para el almacenamiento de la información.

---

## 1. Menú Principal e Interfaz
- **Estilo Moderno:** Interfaz gráfica basada en `customtkinter`, con un tema oscuro y acentos azules, proporcionando una experiencia visual agradable y moderna.
- **Entretenimiento Integrado:** Incluye un reproductor de música de fondo (reproduce `keygen.wav` en bucle) que se puede silenciar con un botón en la esquina inferior izquierda. Además, presenta un GIF animado (Yugi bailando) como detalle estético en el menú principal.

## 2. Gestor de Tiendas (Store Manager)
Esta funcionalidad permite a los organizadores gestionar los distintos locales o tiendas donde se realizan los eventos.
- **Registro de Tiendas:** Permite añadir nuevas tiendas al sistema. Las tiendas son la entidad base; los torneos y ligas están vinculados a una tienda específica.
- **Estado Activo/Inactivo:** Se puede marcar una tienda como activa o inactiva para filtrar su visibilidad en el sistema y mantener organizados los eventos actuales.
- **Gestión de Base de Datos:** Todas las tiendas se guardan en la tabla `stores` de la base de datos local SQLite.

## 3. Gestor de Torneos (Tournament Manager)
El módulo de torneos permite llevar el control de eventos individuales.
- **Creación de Torneos:** Los torneos se registran vinculados a una tienda, especificando el formato de juego (Ej: Edison, GOAT, TCG, Speed Duel, Genesys), la fecha y la modalidad de juego.
- **Registro de Resultados:** Permite vincular a los jugadores al torneo y registrar sus puntos de partida (Match Points) y puntos por posición (Placement Points).
- **Asistencia y Misiones:** Se puede marcar la asistencia de un jugador e incluso registrar datos adicionales como grillas de "Bingo" o misiones especiales cumplidas durante el evento.
- **Control Financiero:** Incluye la capacidad de rastrear las ganancias (profit) generadas por el torneo específico.

## 4. Gestor de Ligas (League Manager)
Diseñado para organizar competencias a largo plazo que abarcan múltiples torneos.
- **Perfiles de Liga:** Cada jugador puede tener un "Perfil de Liga" que lo asocia a una tienda específica y a un formato concreto. En su perfil se registra el mazo que está utilizando y su "carta insignia" (signature card).
- **Control de Jugadores Globales:** Permite registrar jugadores en el sistema global utilizando su nombre, información de contacto (teléfono, email) e identificador oficial (Konami ID).
- **Seguimiento de Puntos:** Al vincularse con el Gestor de Torneos, la liga acumula automáticamente los puntos de cada jugador en los diferentes eventos, facilitando la creación de tablas de posiciones (Standings) a lo largo de la temporada.

## 5. Calculadora de Premios (Prize Calculator)
Una herramienta rápida y eficaz para la logística de los eventos.
- **Distribución Proporcional:** Permite calcular automáticamente cómo deben repartirse los premios (como sobres o crédito en tienda) basándose en la cantidad total de jugadores inscritos en el torneo.
- **Actualización Dinámica:** Ajusta las proporciones y la cantidad de premios destinados al Top 4, Top 8, etc., agilizando el proceso administrativo al finalizar un evento.

## 6. YGO Deck Post Generator (Generador de Imágenes de Decks)
Una de las herramientas más potentes y visuales del programa, orientada a la creación de contenido para redes sociales.
- **Parseo de Decklists:** El usuario puede pegar una lista de cartas en formato texto (Main, Extra y Side Deck). El programa la lee inteligentemente y separa las secciones.
- **Integración con YGOPRODeck API:** Descarga automáticamente las imágenes de las cartas faltantes utilizando la API pública de YGOPRODeck, guardándolas en una carpeta de caché (`cache/`) para acelerar futuros usos.
- **Revisión de Banlists Automática:** Dependiendo del formato seleccionado (TCG, OCG, GOAT, Edison, Speed Duel, Genesys, o Sin Banlist), el programa carga la lista de cartas prohibidas/limitadas correspondiente.
    - Para formatos oficiales (TCG/OCG), descarga la banlist de la API.
    - Para formatos retro/alternativos, utiliza archivos JSON locales (ej. `edison_banlist.json`, `genesys_banlist.json`).
    - Coloca iconos visuales sobre las cartas indicando si están Prohibidas (0), Limitadas (1) o Semi-Limitadas (2).
    - Incluye reglas especiales, como el límite de 100 puntos y la restricción de monstruos Link/Pendulum en el formato *Genesys*, así como límites de tamaño de mazo para *Speed Duel*.
- **Generación Visual (Renderizado):** Ensambla todas las cartas sobre un fondo (que puede ser el arte de una carta específica desenfocada), añade sombras, distribuye el Extra Deck y Side Deck proporcionalmente, e incluye el nombre del campeón, el torneo y la fecha.
- **Exportación:** Permite exportar el póster final en alta resolución como una imagen PNG lista para ser compartida.

## 7. Arquitectura de Datos y Sistema
- **Base de Datos SQLite (`ygo_data.db`):** Toda la información estructurada de tiendas, ligas, jugadores y resultados se guarda localmente sin necesidad de conexión a internet o de configurar un servidor SQL complejo. Las relaciones usan claves foráneas para asegurar la integridad de los datos en borrados en cascada.
- **Gestión de Archivos Locales:** Se apoya en directorios locales como `data/` para la base de datos y `cache/` para almacenar eficientemente las miniaturas de las cartas de Yu-Gi-Oh! descargadas.
