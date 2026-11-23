"""Dashboard RapiMarket Q3 2026 (Streamlit + Plotly).

Traduce el wireframe de la Parte 1: vista estrategica (4 KPIs con meta + 3 graficos),
vista operativa (filtros, drill-down, tooltips) y vista de auditoria (A1-A6).

Ejecutar desde la raiz del proyecto:
    streamlit run dashboard/app.py
"""
import sys
from pathlib import Path

import pandas as pd
import plotly.express as px
import streamlit as st

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT / "codigo_y_data"))
import pipeline as pl  # noqa: E402

# Paleta Okabe-Ito (apta para daltonismo). Nunca se usa rojo/verde como unico codificador.
AZUL, NARANJA, VERDE, GRIS = "#0072B2", "#D55E00", "#009E73", "#595959"
BODEGAS_ORDEN = ["Centro", "Norte", "Sur", "Valparaíso", "Concepción", "La Serena", "Temuco"]
MESES_TXT = {"2026-07": "Jul", "2026-08": "Ago", "2026-09": "Sep"}

st.set_page_config(page_title="RapiMarket · Q3 2026", page_icon="🛒", layout="wide")


# ----------------------------------------------------------------- utilidades
@st.cache_data(show_spinner="Uniendo los 6 CSV y calculando indicadores...")
def cargar() -> pd.DataFrame:
    return pl.build_master()


@st.cache_data(show_spinner="Entrenando el Random Forest de fuga...")
def modelo(_df: pd.DataFrame) -> dict:
    return pl.rf_importancia(_df)


@st.cache_data
def calidad() -> dict:
    return pl.quality_report(pl.load_raw())


def n(x) -> str:
    return f"{x:,.0f}".replace(",", ".")


def d1(x) -> str:
    return f"{x:.1f}".replace(".", ",")


def estilo(fig, alto=340):
    fig.update_layout(template="plotly_white", height=alto, font=dict(size=14), margin=dict(l=10, r=10, t=40, b=10),
                      legend=dict(orientation="h", y=-0.2))
    return fig


def agrupar(df: pd.DataFrame, por) -> pd.DataFrame:
    g = df.groupby(por).agg(pedidos=("pedido_id", "size"), atrasados=("atrasado", "sum"),
                            p90=("tiempo_entrega_min", lambda s: s.quantile(0.9)), mediana=("tiempo_entrega_min", "median"),
                            reclamos=("reclamo", "sum"), congelados=("con_congelados", "sum"), quiebres=("quiebre_frio", "sum")).reset_index()
    g["atraso_pct"] = (g.atrasados / g.pedidos * 100).round(1)
    g["reclamos_100"] = (g.reclamos / g.pedidos * 100).round(1)
    g["quiebre_frio_pct"] = (g.quiebres / g.congelados.where(g.congelados > 0) * 100).round(1)
    return g


def tarjeta(col, nombre, valor, texto_valor, meta_txt, icono, estado):
    with col:
        st.metric(nombre, texto_valor, help=f"Meta propuesta: {meta_txt}" if meta_txt else None)
        st.caption(f"{icono} **{estado}**" + (f" · meta {meta_txt}" if meta_txt else ""))


# --------------------------------------------------------------------- datos
df_all = cargar()

st.sidebar.header("Filtros")
meses = st.sidebar.multiselect("Mes", sorted(df_all.mes.unique()), default=sorted(df_all.mes.unique()),
                               format_func=lambda m: MESES_TXT.get(m, m))
ciudades = st.sidebar.multiselect("Ciudad", sorted(df_all.ciudad.unique()), default=sorted(df_all.ciudad.unique()))
bod_disp = [b for b in BODEGAS_ORDEN if b in df_all[df_all.ciudad.isin(ciudades)].bodega.unique()]
bodegas = st.sidebar.multiselect("Bodega", bod_disp, default=bod_disp)
tipo = st.sidebar.radio("Tipo de pedido", ["Todos", "Simple", "Complejo"], horizontal=True)
st.sidebar.caption("Paleta apta para daltonismo (azul/naranja). El estado de cada KPI se indica con ícono y texto, no solo con color.")
st.sidebar.caption("El dataset no incluye comuna: la unidad geográfica más fina es la bodega.")

df = df_all[df_all.mes.isin(meses) & df_all.ciudad.isin(ciudades) & df_all.bodega.isin(bodegas)]
if tipo != "Todos":
    df = df[df.tipo_pedido == tipo]
if df.empty:
    st.warning("No hay pedidos con esos filtros. Amplía la selección en el panel izquierdo.")
    st.stop()

k = pl.kpis(df)
M = pl.METAS

# --------------------------------------------------------------- encabezado
st.title("RapiMarket · Q3 2026")
por_ciudad = agrupar(df, "ciudad")
top = por_ciudad.sort_values("atrasados", ascending=False).iloc[0]
titular = (f"{top.ciudad} concentra {d1(top.atrasados / por_ciudad.atrasados.sum() * 100)}% de los atrasos "
           f"con {d1(top.pedidos / por_ciudad.pedidos.sum() * 100)}% de los pedidos")
st.subheader(titular)

tab1, tab2, tab3 = st.tabs(["Vista estratégica", "Vista operativa", "Auditoría del memo (A1–A6)"])

# ------------------------------------------------------ vista estrategica
with tab1:
    c1, c2, c3, c4 = st.columns(4)
    ic, tx = pl.estado(k["clientes_activos_30d"], M["clientes_activos"], menor_es_mejor=False)
    tarjeta(c1, "Clientes activos (30 días)", k["clientes_activos_30d"], n(k["clientes_activos_30d"]), f"> {n(M['clientes_activos'])}", ic, tx)
    ic, tx = pl.estado(k["p90_min"], M["p90_min"])
    tarjeta(c2, "% de pedidos atrasados", k["atraso_pct"], f"{d1(k['atraso_pct'])}%", f"p90 < {n(M['p90_min'])} min (hoy {n(k['p90_min'])})", ic, tx)
    ic, tx = pl.estado(k["recompra_pct"], M["recompra_pct"], menor_es_mejor=False)
    tarjeta(c3, "Recompra a 30 días", k["recompra_pct"], "s/d" if k["recompra_pct"] is None else f"{d1(k['recompra_pct'])}%",
            f"mantener {d1(M['recompra_pct'])}%", ic, tx)
    ic, tx = pl.estado(k["reclamos_100"], M["reclamos_100"])
    tarjeta(c4, "Reclamos por 100 pedidos", k["reclamos_100"], d1(k["reclamos_100"]), f"máx. {d1(M['reclamos_100'])}", ic, tx)
    st.caption("Metas tomadas del diccionario de KPIs de la Parte 1 (papel), basado en el anexo. Los CSV tienen otra escala "
               "(78.000 clientes), por lo que la comparación de clientes activos con la meta de 61.300 es solo referencial.")
    if k["recompra_pct"] is None:
        st.caption("Recompra a 30 días: sin dato porque septiembre no tiene 30 días de seguimiento completos.")

    g1, g2 = st.columns(2)
    with g1:
        pm = df.groupby("mes").size().reset_index(name="pedidos")
        pm["mes_txt"] = pm.mes.map(MESES_TXT)
        fig = px.bar(pm, x="mes_txt", y="pedidos", text="pedidos", title="A · Pedidos por mes", color_discrete_sequence=[AZUL])
        fig.update_traces(texttemplate="%{text:,}", hovertemplate="%{x}: %{y:,} pedidos<extra></extra>")
        fig.update_yaxes(rangemode="tozero", title=None)
        fig.update_xaxes(title=None)
        st.plotly_chart(estilo(fig), use_container_width=True)
        st.caption("Barras por mes con eje desde 0 (no acumulado).")
    with g2:
        rec = df[df.elegible_recompra].groupby("mes").recompra30.mean().mul(100)
        rcl = df.groupby("mes").reclamo.mean().mul(100)
        tm = pd.DataFrame({"Recompra a 30 días (%)": rec, "Reclamos por 100 pedidos": rcl}).reset_index()
        tm["mes"] = tm.mes.map(MESES_TXT)
        largo = tm.melt("mes", var_name="indicador", value_name="valor")
        fig = px.line(largo, x="mes", y="valor", color="indicador", line_dash="indicador", markers=True,
                      title="B · Recompra y reclamos", color_discrete_map={"Recompra a 30 días (%)": AZUL, "Reclamos por 100 pedidos": NARANJA})
        fig.update_traces(hovertemplate="%{x}: %{y:.1f}<extra>%{fullData.name}</extra>")
        fig.update_yaxes(rangemode="tozero", title="%  /  por 100 pedidos")
        fig.update_xaxes(title=None)
        st.plotly_chart(estilo(fig), use_container_width=True)
        st.caption("Dos líneas distintas por color y trazo (continua vs punteada).")

    sim = agrupar(df, ["bodega", "tipo_pedido"])
    fig = px.bar(sim, x="bodega", y="atraso_pct", color="tipo_pedido", barmode="group", text="atraso_pct",
                 pattern_shape="tipo_pedido", category_orders={"bodega": BODEGAS_ORDEN},
                 color_discrete_map={"Simple": AZUL, "Complejo": NARANJA}, pattern_shape_map={"Simple": "", "Complejo": "/"},
                 title="C · % de atraso por bodega y tipo de pedido (Paradoja de Simpson)",
                 hover_data={"pedidos": ":,", "p90": ":.0f"})
    fig.update_traces(texttemplate="%{text:.1f}%")
    fig.update_yaxes(rangemode="tozero", title="% de pedidos atrasados")
    fig.update_xaxes(title=None)
    st.plotly_chart(estilo(fig, 380), use_container_width=True)
    st.caption("Centro parece peor que Norte en el total, pero es mejor en ambos tipos de pedido: tiene más pedidos complejos. "
               "La bodega Sur (operador externo) es la peor en ambos tipos.")

# ------------------------------------------------------- vista operativa
with tab2:
    nivel = st.radio("Nivel de detalle (drill-down)", ["Ciudad", "Bodega", "Bodega y tipo de pedido", "Mes"], horizontal=True)
    claves = {"Ciudad": ["ciudad"], "Bodega": ["bodega"], "Bodega y tipo de pedido": ["bodega", "tipo_pedido"], "Mes": ["mes"]}[nivel]
    det = agrupar(df, claves)
    if "bodega" in det:
        det["bodega"] = det.bodega.where(det.bodega != "Sur", "Sur (externa)")
    etiqueta = det[claves].astype(str).agg(" · ".join, axis=1)
    det["unidad"] = etiqueta.map(lambda t: MESES_TXT.get(t, t))
    det = det.sort_values("atraso_pct", ascending=False)
    fig = px.bar(det, x="atraso_pct", y="unidad", orientation="h", text="atraso_pct", color_discrete_sequence=[AZUL],
                 title=f"% de atraso por {nivel.lower()}", hover_data={"pedidos": ":,", "p90": ":.0f", "mediana": ":.0f", "unidad": False})
    fig.update_traces(texttemplate="%{text:.1f}%")
    fig.update_yaxes(autorange="reversed", title=None)
    fig.update_xaxes(rangemode="tozero", title="% de pedidos atrasados")
    st.plotly_chart(estilo(fig, max(300, 38 * len(det) + 90)), use_container_width=True)

    tabla = det[["unidad", "pedidos", "atraso_pct", "p90", "mediana", "reclamos_100", "quiebre_frio_pct"]].rename(columns={
        "unidad": nivel, "pedidos": "Pedidos", "atraso_pct": "% atraso", "p90": "p90 (min)", "mediana": "Mediana (min)",
        "reclamos_100": "Reclamos /100", "quiebre_frio_pct": "% quiebre de frío"})
    st.dataframe(tabla, hide_index=True, use_container_width=True)
    st.caption("Meta de entrega: p90 < 60 min. Quiebre de frío = congelado que llega a más de −15 °C.")

    o1, o2 = st.columns(2)
    with o1:
        sem = df.assign(semana=df.fecha.dt.to_period("W").dt.start_time).groupby(["semana", "ciudad"]).atrasado.mean().mul(100).reset_index()
        fig = px.line(sem, x="semana", y="atrasado", color="ciudad", title="% de atraso por semana",
                      color_discrete_sequence=[NARANJA, AZUL, VERDE, GRIS, "#E69F00"])
        fig.update_traces(hovertemplate="%{x|%d-%m}: %{y:.1f}%<extra>%{fullData.name}</extra>")
        fig.update_yaxes(rangemode="tozero", title="%")
        fig.update_xaxes(title=None)
        st.plotly_chart(estilo(fig), use_container_width=True)
    with o2:
        rc = df[df.reclamo].groupby("categoria").agg(reclamos=("pedido_id", "size"), tardios=("reclamo_tardio", "mean")).reset_index()
        rc["tardios"] = (rc.tardios * 100).round(1)
        fig = px.bar(rc.sort_values("reclamos"), x="reclamos", y="categoria", orientation="h", text="reclamos",
                     color_discrete_sequence=[NARANJA], title="Reclamos por categoría", hover_data={"tardios": ":.1f"})
        fig.update_traces(texttemplate="%{text:,}")
        fig.update_xaxes(title=None)
        fig.update_yaxes(title=None)
        st.plotly_chart(estilo(fig), use_container_width=True)
        st.caption(f"{d1(k['reclamos_tardios_pct'])}% de los reclamos se respondió después de 24 h.")

# ----------------------------------------------------------- auditoria
with tab3:
    st.markdown("Recálculo con los CSV **completos** (no depende de los filtros). El detalle de cada afirmación está en el informe ejecutivo.")
    a = pl.auditoria(df_all)
    filas = [
        ("A1 Calidad de servicio", "1,2% de reclamos (25.200 / 2,1 M de visitas)",
         f"{d1(a['A1']['reclamos_por_pedido_pct'])}% de los pedidos tiene reclamo ({n(a['A1']['reclamos'])} / {n(a['A1']['pedidos'])}); "
         f"sube de {d1(a['A1']['por_mes_pct']['2026-07'])}% a {d1(a['A1']['por_mes_pct']['2026-09'])}%", "Error de denominador"),
        ("A2 Crecimiento", "Pedidos acumulados 3,34 M; ticket en fuerte alza",
         f"Pedidos por mes {n(a['A2']['pedidos_mes']['2026-07'])} → {n(a['A2']['pedidos_mes']['2026-09'])} ({d1(a['A2']['var_jul_sep_pct'])}%). "
         f"Ticket sin cargo de $1.990: {n(a['A2']['ticket_sin_cargo']['2026-07'])} → {n(a['A2']['ticket_sin_cargo']['2026-09'])}", "Acumulado y cargo fijo"),
        ("A3 Concentración", "Santiago es 55%, no requiere inversión",
         f"Santiago: {d1(a['A3']['santiago_pct_pedidos'])}% de pedidos, {d1(a['A3']['santiago_atraso_pct'])}% de atraso "
         f"(total {d1(a['A3']['total_atraso_pct'])}%), {d1(a['A3']['santiago_pct_de_atrasos'])}% de todos los atrasos", "Volumen vs tasa"),
        ("A4 Bodegas", "Centro es la peor (22,0% vs 15,6%); cerrar",
         "Centro gana a Norte en ambos tipos de pedido; Sur es la peor", "Paradoja de Simpson"),
        ("A5 Fidelización", "El problema es la calidad del producto",
         f"Recompra: {d1(a['A5']['recompra_a_tiempo_pct'])}% a tiempo vs {d1(a['A5']['recompra_atrasado_pct'])}% con atraso; "
         "la calificación casi no la cambia", "Causa equivocada (confusión)"),
        ("A6 Satisfacción", "4,6 de 5",
         f"Promedio {str(a['A6']['media_estrellas']).replace('.', ',')} sobre {n(a['A6']['n_calificaciones'])} calificaciones; "
         f"{d1(a['A6']['pct_1_2'])}% da 1-2 estrellas", "Sesgo de supervivencia (no reproducible)"),
    ]
    st.dataframe(pd.DataFrame(filas, columns=["Afirmación", "El memo dice", "Los datos CSV muestran", "Tipo de error"]),
                 hide_index=True, use_container_width=True)

    m = modelo(df_all)
    imp = pd.DataFrame(m["importancias"]).rename(columns={"variable": "Variable", "importancia_gini_pct": "Importancia Gini (%)",
                                                          "importancia_permutacion_pct": "Importancia por permutación (%)"})
    st.markdown(f"**Random Forest de fuga** (no recompra a 30 días, n = {n(m['n'])}): AUC = {str(m['auc']).replace('.', ',')} "
                "(la guía menciona 0,81; con las variables disponibles en los CSV no se reproduce).")
    st.dataframe(imp, hide_index=True, use_container_width=True)

    with st.expander("Calidad de los datos"):
        q = calidad()
        st.json(q)
