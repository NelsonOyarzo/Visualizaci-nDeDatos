# RapiMarket Q3 2026: carpeta profesional (ADY1104 · EP3 Parte 2)

Grupo 06 · Integrantes: Nelson Oyarzo y Matias Caileo

## Qué contiene

| Carpeta | Contenido |
|---|---|
| `informes/` | Informe ejecutivo PDF (4 págs.): diagnóstico, recálculo A1–A6, Paradoja de Simpson y propuesta Minto |
| `dashboard/` | `app.py`: dashboard interactivo en Streamlit + Plotly (vista estratégica, operativa y auditoría) |
| `presentacion/` | Resumen ejecutivo de 8 láminas (PPTX y PDF) con la Pirámide de Minto |
| `guion_y_papel/` | Digitalización de las hojas a mano de la Parte 1: guión detallado (T6), wireframe y demás tareas (JPG y un PDF único) |
| `codigo_y_data/` | `pipeline.py` (integración, calidad, A1–A6, modelo), `generar_figuras.py`, `data/` (6 CSV) y `outputs/` |

## Cómo ejecutar (sin rutas absolutas)

```bash
python -m venv .venv
source .venv/bin/activate          # Windows: .venv\Scripts\activate
pip install -r requirements.txt

python codigo_y_data/pipeline.py          # genera codigo_y_data/outputs/metricas.json
python codigo_y_data/generar_figuras.py   # genera codigo_y_data/outputs/figuras/*.png
streamlit run dashboard/app.py            # abre el dashboard en el navegador
```

Todas las rutas se calculan respecto a cada archivo (`Path(__file__)`), así que la carpeta funciona desde cualquier ubicación.

## Arquitectura

```
CSV (6) → pipeline.load_raw → quality_report → build_master (joins + indicadores)
                                   ├→ kpis / auditoria (A1–A6) / rf_importancia → metricas.json → informe y presentación
                                   └→ dashboard/app.py (filtros → KPIs, gráficos, drill-down)
```

Joins: `pedidos` ← `bodegas` (bodega), `clientes` (cliente_id), `calificaciones`, `cupones` y `reclamos` (pedido_id). Todas las relaciones se validan (`validate=`) y no hay huérfanos ni duplicados.

## Supuestos y diferencias con la guía

- **Columnas reales.** La guía describe columnas que no existen en los CSV entregados (`plan`, `comuna`, `tiempo_min`, `costo_usd`, `canjeado`, etc.). Se usaron las columnas reales. No hay comuna: el detalle geográfico llega hasta la bodega.
- **Atraso** = tiempo de entrega mayor a la ventana de 45 min del dataset (campo `atrasado`). Con más de 60 min (como dice la guía) Santiago da 14,5% en vez de 23,0%; la guía menciona 24,0%.
- **Congelado fuera de temperatura** = llega a más de −15 °C (supuesto del equipo; da 11,1%, equivalente a 1 de cada 9 del anexo).
- **Recompra a 30 días**: solo pedidos hasta el 31-08-2026 (los únicos con 30 días de seguimiento).
- **Metas de los KPIs** (`METAS` en `pipeline.py`) son las del diccionario de KPIs de la Parte 1 hecho a mano (activos > 61.300, p90 < 60 min, recompra 41%, reclamos máx. 12,6 por 100). Las metas del piloto de 90 días (atrasos ≤ 12%, frío ≤ 5%) y la distribución de los USD 3 M son propuestas nuevas del equipo.
- **Modelo de fuga**: el Random Forest sobre las variables disponibles da AUC = 0,64, no 0,81; el orden de importancia sí coincide (el atraso lidera).
- **A6 (4,6 de 5)** no se reproduce: el promedio en los CSV es 3,06.
- **Limitación de datos**: ningún cliente se registró después de junio de 2026 (cohorte cerrada).
- **Distribución de los USD 3 M** (45/30/15/10%) es una hipótesis del equipo a validar con el piloto.
- **Conciliación Parte 1 vs Parte 2.** El papel usa el anexo oficial (pedidos 63.000 → 58.000, recompra 41% → 33%, Santiago 24% de atraso). Los CSV tienen otra escala (pedidos 98.822 → 37.818, 78.000 clientes). Las conclusiones coinciden (el atraso explica la fuga, Santiago y Sur concentran el problema, cupones pesan poco), pero las cifras absolutas no. El guión y el wireframe a mano citan las cifras del anexo; el dashboard, el informe y las láminas, las de los CSV.

## Estado de verificación

- `pipeline.py`, `generar_figuras.py`, el informe y la presentación se ejecutaron y revisaron.
- El dashboard se desarrolló en un entorno sin Streamlit ni Plotly, por lo que **no se ha visto corriendo**. Su lógica de datos se probó con datos reales; antes de entregar, ejecútenlo (`streamlit run dashboard/app.py`), revisen cada pestaña y ajusten lo que haga falta.

## Declaración ética de uso de IA

> Completar y ajustar para que refleje el uso real del grupo.

- **Herramienta:** Claude (Anthropic), usada como asistente en esta Parte 2, que se desarrolló en casa.
- **Para qué se usó:** análisis exploratorio y recálculo de A1–A6 sobre los CSV, redacción del código del pipeline, el dashboard y las figuras, y borradores del informe, la presentación y este README.
- **Cómo se verificó:** las cifras se generan con scripts reproducibles a partir de los CSV y quedan en `outputs/metricas.json`; el informe y las láminas leen esas cifras. El grupo revisó los resultados y [describir qué verificó cada integrante].
- **Qué NO se hizo con IA:** el trabajo en papel de la Parte 1 (auditoría, wireframe y guión), elaborado a mano en la sesión presencial sin dispositivos ni asistentes.
- **Responsabilidad:** el equipo entiende y puede explicar cada resultado, supuesto y limitación descritos en este documento.

Integrantes: [nombre 1] · [nombre 2] · [nombre 3]
