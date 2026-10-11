# ACADEMY IMPLEMENTATION

## Arquitectura de Subarashii Duel Academy V1.0

### Decisión Arquitectónica: Perfil "GLOBAL"
Tras la auditoría de la base de datos `ygo_data.db`, se determinó que la tabla `academy_profiles` actualmente posee una clave única compuesta por `(player_id, store_id, format_name)`. 

Para implementar el sistema ELO, XP y Niveles como un ecosistema centralizado (sin romper la capacidad actual del software de llevar estadísticas por formato), se ha tomado la decisión de utilizar el identificador **`format_name="GLOBAL"`** para alojar el perfil oficial de la academia.

**Reglas de la Identidad GLOBAL:**
1. **Unicidad:** Solo puede existir un perfil con `format_name="GLOBAL"` por cada jugador y tienda.
2. **Independencia Histórica:** Los torneos seguirán guardándose con sus formatos originales (Ej. GOAT, Edison), pero al procesar la Academia, el motor acumulará ELO, XP y Logros sobre el perfil `GLOBAL`.
3. **Preservación:** Los perfiles existentes de formatos individuales (Ej. `format_name="GOAT"`) no serán eliminados ni modificados por la Academia. Coexistirán como datos estadísticos de formato.

### Modelo de Datos
La V1.0 introduce las siguientes estructuras:
- `academy_missions` y `mission_catalog`
- `academy_seasons` y `academy_season_players`
- `player_rewards` y `reward_catalog`
- `academy_publications` y `academy_public_snapshots`
- `academy_preseason_players` (para idempotencia de pretemporada)

Adicionalmente, se extienden:
- `players`: Nueva columna `slug` única para la URL pública (Ej. `nmardones`).
- `academy_profiles`: Nuevas columnas `xp` y `level`.

### Flujo "Finalizar Torneo"
El nuevo ciclo de vida de un torneo en YGO Tools será:
1. **Backup:** Snapshots automáticos de SQLite.
2. **Validación:** Comprobación de integridad de rondas y resultados.
3. **Cierre Local:** Registro de resultados.
4. **Academy Engine:** Cálculo y persistencia de ELO, XP, Logros y Misiones sobre el perfil GLOBAL.
5. **Ranking y Temporada:** Actualización de Snapshot temporal.
6. **Publicación Segura:** Generación de archivos JSON estáticos en un directorio versionado (`publication_XX`) y subida remota verificada con Checksum.

### Estrategia de Recuperación
En caso de falla de conectividad, el torneo se marca como `PENDING_PUBLICATION`. Las operaciones de base de datos están envueltas en transacciones SQL (`BEGIN`, `COMMIT`, `ROLLBACK`) para evitar corrupciones de escritura parciales.
