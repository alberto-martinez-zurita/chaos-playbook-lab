Aquí tienes los dos documentos solicitados para documentar y ejecutar la reestructuración perfecta de tu proyecto.

### 📄 DOCUMENTO 1: Mapa de Migración de Archivos

Este documento sirve como "guion" para el script de migración y como referencia para saber dónde ha ido a parar cada pieza de tu código.

| Archivo Origen (Ubicación Actual) | Archivo Destino (Nueva Estructura 10/10) | Razón del Movimiento |
| :--- | :--- | :--- |
| **SCRIPTS (Raíz)** | | **Separar Ejecución de Lógica** |
| `scripts/run_parametric_experiments.py` | `cli/run_simulation.py` | Renombrado a "CLI" estándar. |
| `scripts/run_agent_comparison.py` | `cli/run_comparison.py` | Punto de entrada claro para comparación. |
| `scripts/generate_dashboard.py` | `src/chaos_engine/reporting/dashboard.py` | La lógica de reporte es parte del "Engine". |
| `cli/generate_report.py` (Nuevo) | `cli/generate_report.py` | Script wrapper ligero para llamar al dashboard. |
| **AGENTS** | | **Dominio Principal** |
| `agents/petstore_agent.py` | `src/chaos_engine/agents/petstore.py` | Agente principal, nombre limpio. |
| `agents/order_agent_llm.py` | `src/chaos_engine/agents/legacy_order.py` | Preservado como referencia histórica. |
| **CHAOS CORE** | | **Dominio del Caos** |
| `core/chaos_proxy.py` | `src/chaos_engine/chaos/proxy.py` | Componente central del caos. |
| `config/chaos_config.py` | `src/chaos_engine/chaos/config.py` | Definición de la configuración del caos. |
| `tools/chaos_injection_helper.py` | `src/chaos_engine/chaos/injection.py` | Utilidad auxiliar. |
| **SIMULATION (Fase 5)** | | **Dominio de Simulación** |
| `tools/simulated_apis.py` | `src/chaos_engine/simulation/apis.py` | APIs falsas para pruebas de carga. |
| `runners/ab_test_runner.py` | `src/chaos_engine/simulation/runner.py` | Orquestador de simulación. |
| `experiments/parametric_ab_test_runner.py` | `src/chaos_engine/simulation/parametric.py` | Runner de experimentos masivos. |
| **INFRAESTRUCTURA** | | **Utilidades Transversales** |
| `core/logging_setup.py` | `src/chaos_engine/core/logging.py` | Sistema de logs centralizado. |
| `config/config_loader.py` | `src/chaos_engine/core/config.py` | Cargador de configuración. |
| `data/playbook_storage.py` | `src/chaos_engine/core/storage.py` | 🚨 **FIX:** Código fuera de carpeta de datos. |
| `tools/retry_wrapper.py` | `src/chaos_engine/core/resilience.py` | Patrón de diseño reutilizable. |
| **CONFIGURACIÓN** | | **Configuración Estática** |
| `config/dev_config.yaml` | `config/dev.yaml` | Nombre simplificado. |
| `config/prod_config.yaml` | `config/prod.yaml` | Nombre simplificado. |
| `config/chaos_agent.yaml` | `config/presets.yaml` | Renombrado a "presets". |
| **DATOS (ASSETS)** | | **Separación Code/Data** |
| `data/http_error_codes.json` | `assets/knowledge_base/http_error_codes.json` | Base de conocimiento estática. |
| `data/playbook_petstore_*.json` | `assets/playbooks/*.json` | Playbooks organizados por tipo. |
| `data/chaos_playbook.json` | `assets/playbooks/legacy/phase5.json` | Archivado. |

-----

### 📄 DOCUMENTO 2: La Estructura "Gold Standard" (Por qué es un 10/10)

Este documento explica la filosofía detrás de la estructura. Úsalo en tu `README.md` o en la presentación para demostrar madurez de ingeniería.

#### 🏗️ Arquitectura del Proyecto: "Chaos Engine"

Hemos evolucionado de una colección de scripts a una **Arquitectura de Librería Profesional (Src-Layout)**. Esta estructura no solo organiza el código, sino que cuenta la historia de cómo el proyecto escala desde un experimento local a un producto empresarial.

```text
chaos-playbook-engine/
├── config/                 # [Configuration Layer]
│   └── dev.yaml            # Single Source of Truth para parámetros.
├── assets/                 # [Data Layer]
│   ├── knowledge_base/     # Datos inmutables (Códigos HTTP).
│   └── playbooks/          # La "Inteligencia" del sistema (JSONs).
├── src/
│   └── chaos_engine/       # [Application Layer - The Package]
│       ├── chaos/          # DOMINIO: El motor de inyección de fallos.
│       ├── agents/         # DOMINIO: Los actores (LLMs) que sufren el caos.
│       ├── simulation/     # DOMINIO: El entorno de laboratorio (Fase 5).
│       ├── core/           # INFRAESTRUCTURA: Logging, Config, Storage.
│       └── reporting/      # PRESENTACIÓN: Generación de Dashboards.
├── cli/                    # [Interface Layer]
│   └── run_comparison.py   # Punto de entrada para el usuario.
└── tests/                  # [Quality Assurance]
```

#### 🏆 Por qué esta estructura gana Hackathons (Puntos para el Juez)

1.  **Separación Estricta de Responsabilidades (SoC):**

      * **Código vs. Datos:** Nunca más verás un archivo `.py` perdido entre `.json` en una carpeta `data/`. Esto demuestra higiene de ingeniería.
      * **Lógica vs. Ejecución:** La lógica vive en `src/` (reutilizable, testeable), la ejecución en `cli/` (scripts desechables).

2.  **Empaquetado Estándar ("Installable Package"):**

      * Al usar `src/chaos_engine`, el proyecto se comporta como una librería Python real (`pip install chaos-engine`).
      * **Valor:** Permite que otros equipos importen tu motor de caos en *sus* propios proyectos sin copiar y pegar archivos. Esto es vital para la visión de "Ecosistema Enterprise" (Fase 9).

3.  **Escalabilidad Modular:**

      * Si mañana quieres añadir integración con **Google Cloud Run**, no tienes que refactorizar todo. Simplemente añades un módulo `src/chaos_engine/cloud/`. La estructura invita a crecer ordenadamente.

4.  **Navegabilidad Cognitiva:**

      * Un juez (o un nuevo desarrollador) sabe exactamente dónde mirar.
      * ¿Buscas cómo falla? -\> `chaos/`.
      * ¿Buscas cómo piensa el agente? -\> `agents/`.
      * ¿Buscas los resultados? -\> `reporting/`.

5.  **Observabilidad Nativa:**

      * La carpeta `logs/` y `reports/` están fuera del código fuente, siguiendo las mejores prácticas de "Artifacts Isolation".

**Veredicto:** Esta estructura transforma tu proyecto de un "Experimento interesante" a una **"Plataforma de Ingeniería de Resiliencia"**. Es la base sólida sobre la que se construye un producto ganador.