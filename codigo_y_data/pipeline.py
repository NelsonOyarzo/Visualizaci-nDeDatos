"""RapiMarket Q3 2026 - Pipeline de datos, auditoria A1-A6 y modelo de fuga.

Fases 1 y 2 de la guia EP3 Parte 2. Todas las rutas son relativas a este
archivo, por lo que el proyecto corre en cualquier maquina sin cambios.

Uso:  python codigo_y_data/pipeline.py
"""
from __future__ import annotations

import json
from pathlib import Path

import numpy as np
import pandas as pd

ROOT = Path(__file__).resolve().parent.parent
DATA = ROOT / "codigo_y_data" / "data"
OUT = ROOT / "codigo_y_data" / "outputs"

# ---------------------------------------------------------------- supuestos
CFG = {
    "UMBRAL_FRIO_C": -15.0,          # congelado "fuera de temperatura" si llega a mas de -15 C
    "VENTANA_RECOMPRA_DIAS": 30,
    "FECHA_CORTE_RECOMPRA": "2026-08-31",  # ultimo pedido con 30 dias de seguimiento completo
    "RESP_LIMITE_H": 24,             # reclamo "sin respuesta a tiempo" si tarda mas de 24 h
    "SEED": 42,
}
# Metas del diccionario de KPIs de la Parte 1 (hecho a mano). Editables.
METAS = {
    "clientes_activos": 61300,   # superar 61.300 clientes activos a 30 dias
    "p90_min": 60.0,             # % atrasados: p90 menor a 60 minutos
    "recompra_pct": 41.0,        # mantener el 41%
    "reclamos_100": 12.6,        # maximo 12,6 por 100 pedidos (y 0 reclamos sin respuesta en mas de 24 h)
}
TABLAS = ["clientes", "bodegas", "pedidos", "reclamos", "calificaciones", "cupones"]


# ------------------------------------------------------------------- fase 1
def load_raw(data_dir: Path = DATA) -> dict[str, pd.DataFrame]:
    raw = {t: pd.read_csv(Path(data_dir) / f"{t}.csv") for t in TABLAS}
    raw["pedidos"]["fecha"] = pd.to_datetime(raw["pedidos"]["fecha"])
    raw["clientes"]["fecha_registro"] = pd.to_datetime(raw["clientes"]["fecha_registro"])
    raw["reclamos"]["fecha"] = pd.to_datetime(raw["reclamos"]["fecha"])
    return raw


def _iqr_outliers(s: pd.Series) -> int:
    q1, q3 = s.quantile([0.25, 0.75])
    iqr = q3 - q1
    return int(((s < q1 - 3 * iqr) | (s > q3 + 3 * iqr)).sum())


def quality_report(raw: dict[str, pd.DataFrame]) -> dict:
    """Auditoria de calidad: duplicados, nulos, integridad referencial, outliers."""
    p, c, r, cal, cu, b = (raw[k] for k in ["pedidos", "clientes", "reclamos", "calificaciones", "cupones", "bodegas"])
    return {
        "filas": {k: int(len(v)) for k, v in raw.items()},
        "duplicados_pk": {
            "pedidos": int(p.pedido_id.duplicated().sum()),
            "clientes": int(c.cliente_id.duplicated().sum()),
            "reclamos": int(r.reclamo_id.duplicated().sum()),
            "calificaciones": int(cal.pedido_id.duplicated().sum()),
            "cupones": int(cu.pedido_id.duplicated().sum()),
        },
        "nulos": {k: {col: int(n) for col, n in v.isna().sum().items() if n > 0} for k, v in raw.items()},
        "huerfanos": {
            "pedidos_sin_cliente": int((~p.cliente_id.isin(c.cliente_id)).sum()),
            "pedidos_sin_bodega": int((~p.bodega.isin(b.bodega)).sum()),
            "reclamos_sin_pedido": int((~r.pedido_id.isin(p.pedido_id)).sum()),
            "calificaciones_sin_pedido": int((~cal.pedido_id.isin(p.pedido_id)).sum()),
            "cupones_sin_pedido": int((~cu.pedido_id.isin(p.pedido_id)).sum()),
        },
        "outliers_iqr3": {
            "tiempo_entrega_min": _iqr_outliers(p.tiempo_entrega_min),
            "monto_productos_clp": _iqr_outliers(p.monto_productos_clp),
            "horas_respuesta": _iqr_outliers(r.horas_respuesta),
        },
        "consistencia": {
            "atrasado_igual_tiempo_mayor_ventana": float(((p.tiempo_entrega_min > p.ventana_min) == p.atrasado).mean()),
            "temp_nula_solo_sin_congelados": bool(p.loc[p.temp_llegada_c.isna(), "con_congelados"].eq(False).all()),
            "clientes_registrados_hasta": str(c.fecha_registro.max().date()),
        },
    }


def build_master(raw: dict[str, pd.DataFrame] | None = None) -> pd.DataFrame:
    """Une pedidos + bodegas + clientes + calificaciones + cupones + reclamos y deriva indicadores."""
    raw = raw or load_raw()
    p = raw["pedidos"].drop_duplicates("pedido_id").copy()
    # Decision de limpieza: no se eliminan outliers (son atrasos reales). Se reportan p90 y mediana.
    p = p.merge(raw["bodegas"][["bodega", "ciudad", "operador"]], on="bodega", how="left", validate="m:1")
    p = p.merge(raw["clientes"][["cliente_id", "medio_pago_valido", "fecha_registro"]], on="cliente_id", how="left", validate="m:1")
    p = p.merge(raw["calificaciones"].drop_duplicates("pedido_id"), on="pedido_id", how="left", validate="1:1")
    p = p.merge(raw["cupones"].drop_duplicates("pedido_id"), on="pedido_id", how="left", validate="1:1")
    p = p.merge(raw["reclamos"][["pedido_id", "categoria", "horas_respuesta"]].drop_duplicates("pedido_id"),
                on="pedido_id", how="left", validate="1:1")

    p["mes"] = p.fecha.dt.strftime("%Y-%m")
    p["tipo_pedido"] = np.where(p.complejo, "Complejo", "Simple")
    p["ticket_clp"] = p.monto_productos_clp + p.cargo_servicio_clp
    p["atrasado_60"] = p.tiempo_entrega_min > 60
    p["cupon"] = p.descuento_pct.notna()
    p["reclamo"] = p.categoria.notna()
    p["reclamo_tardio"] = p.reclamo & (p.horas_respuesta > CFG["RESP_LIMITE_H"])
    p["quiebre_frio"] = p.con_congelados & (p.temp_llegada_c > CFG["UMBRAL_FRIO_C"])
    p["calificado"] = p.estrellas.notna()

    p = p.sort_values(["cliente_id", "fecha", "pedido_id"]).reset_index(drop=True)
    p["n_orden"] = p.groupby("cliente_id").cumcount() + 1
    p["dias_sig"] = (p.groupby("cliente_id").fecha.shift(-1) - p.fecha).dt.days
    p["recompra30"] = p.dias_sig.le(CFG["VENTANA_RECOMPRA_DIAS"])
    p["elegible_recompra"] = p.fecha <= pd.Timestamp(CFG["FECHA_CORTE_RECOMPRA"])
    return p.sort_values("pedido_id").reset_index(drop=True)


# ----------------------------------------------------------------- indicadores
def _pct(x: float) -> float:
    return float(round(100 * x, 3))


def kpis(df: pd.DataFrame) -> dict:
    """KPIs del diccionario unificado (T5) sobre el subconjunto filtrado."""
    if df.empty:
        return {}
    ultimo = df.fecha.max()
    activos = df.loc[df.fecha > ultimo - pd.Timedelta(days=30), "cliente_id"].nunique()
    el = df[df.elegible_recompra]
    con = df[df.con_congelados]
    return {
        "pedidos": int(len(df)),
        "clientes_activos_30d": int(activos),
        "atraso_pct": _pct(df.atrasado.mean()),
        "p90_min": float(df.tiempo_entrega_min.quantile(0.9)),
        "mediana_min": float(df.tiempo_entrega_min.median()),
        "recompra_pct": _pct(el.recompra30.mean()) if len(el) else None,
        "reclamos_100": float(round(100 * df.reclamo.mean(), 2)),
        "reclamos_tardios_pct": _pct(df.loc[df.reclamo, "reclamo_tardio"].mean()) if df.reclamo.any() else 0.0,
        "quiebre_frio_pct": _pct(con.quiebre_frio.mean()) if len(con) else 0.0,
        "ticket_medio": float(round(df.ticket_clp.mean())),
    }


def estado(valor, meta, menor_es_mejor=True) -> tuple[str, str]:
    """Estado con icono + palabra (no depende solo del color, WCAG 1.4.1)."""
    if valor is None:
        return "-", "Sin datos"
    ok = valor <= meta if menor_es_mejor else valor >= meta
    if ok:
        return "●", "En meta"
    return ("▲", "Fuera de meta") if menor_es_mejor else ("▼", "Fuera de meta")


# ------------------------------------------------------------------- fase 2
def auditoria(df: pd.DataFrame) -> dict:
    """Recalcula con los CSV las afirmaciones A1-A6 del Memo de Marketing."""
    res: dict = {}
    mes = df.groupby("mes")

    # A1 - denominador
    res["A1"] = {
        "reclamos": int(df.reclamo.sum()),
        "pedidos": int(len(df)),
        "reclamos_por_pedido_pct": _pct(df.reclamo.mean()),
        "por_mes_pct": {m: _pct(g.reclamo.mean()) for m, g in mes},
        "nota": "Las visitas a la app no vienen en los CSV: el 1,2% del memo (reclamos/visitas) no es reproducible; el denominador correcto es pedidos.",
    }

    # A2 - acumulado + ticket
    ped_mes = mes.size()
    res["A2"] = {
        "pedidos_mes": {m: int(v) for m, v in ped_mes.items()},
        "var_jul_sep_pct": _pct(ped_mes.iloc[-1] / ped_mes.iloc[0] - 1),
        "ticket_con_cargo": {m: float(round(g.ticket_clp.mean())) for m, g in mes},
        "ticket_sin_cargo": {m: float(round(g.monto_productos_clp.mean())) for m, g in mes},
        "primer_pedido_vs_recurrente": {m: {"primer_pedido": int((g.n_orden == 1).sum()), "recurrente": int((g.n_orden > 1).sum())} for m, g in mes},
    }

    # A3 - volumen vs tasa
    sant = df[df.ciudad == "Santiago"]
    por_ciudad = df.groupby("ciudad").agg(pedidos=("pedido_id", "size"), atraso=("atrasado", "mean"),
                                         p90=("tiempo_entrega_min", lambda s: s.quantile(0.9)))
    por_ciudad["pct_total"] = por_ciudad.pedidos / len(df) * 100
    res["A3"] = {
        "santiago_pct_pedidos": _pct(len(sant) / len(df)),
        "santiago_atraso_pct": _pct(sant.atrasado.mean()),
        "total_atraso_pct": _pct(df.atrasado.mean()),
        "santiago_pct_de_atrasos": _pct(sant.atrasado.sum() / df.atrasado.sum()),
        "santiago_p90": float(sant.tiempo_entrega_min.quantile(0.9)),
        "santiago_atraso_pct_ventana60": _pct(sant.atrasado_60.mean()),
        "tabla_ciudad": por_ciudad.round(3).reset_index().to_dict("records"),
    }

    # A4 - Simpson
    res["A4"] = simpson(df)

    # A5 - fidelizacion: causa real de la fuga
    el = df[df.elegible_recompra]
    cal = el[el.calificado].copy()
    cal["grupo"] = np.where(cal.estrellas <= 2, "1-2 estrellas", np.where(cal.estrellas >= 4, "4-5 estrellas", "3 estrellas"))
    rec_atr_cal = cal.groupby(["atrasado", "grupo"]).recompra30.mean().mul(100).round(1)
    res["A5"] = {
        "recompra_atrasado_pct": _pct(el[el.atrasado].recompra30.mean()),
        "recompra_a_tiempo_pct": _pct(el[~el.atrasado].recompra30.mean()),
        "recompra_por_estrellas_pct": {int(k): _pct(v) for k, v in el[el.calificado].groupby("estrellas").recompra30.mean().items()},
        "recompra_atraso_x_estrellas": {f"{'atrasado' if a else 'a tiempo'} | {g}": float(v) for (a, g), v in rec_atr_cal.items()},
        "recompra_faltantes_pct": {str(k): _pct(v) for k, v in el.groupby("faltantes").recompra30.mean().items()},
        "recompra_quiebre_frio_pct": _pct(el[el.quiebre_frio].recompra30.mean()),
        "recompra_reclamo_pct": {
            "sin reclamo": _pct(el[~el.reclamo].recompra30.mean()),
            "respuesta <= 24 h": _pct(el[el.reclamo & ~el.reclamo_tardio].recompra30.mean()),
            "respuesta > 24 h": _pct(el[el.reclamo_tardio].recompra30.mean()),
        },
        "recompra_cupon_x_atraso_pct": {f"{'atrasado' if a else 'a tiempo'} | {'con cupon' if cu else 'sin cupon'}": _pct(v)
                                        for (a, cu), v in el.groupby(["atrasado", "cupon"]).recompra30.mean().items()},
    }

    # A6 - satisfaccion
    cal_all = df[df.calificado]
    res["A6"] = {
        "tasa_respuesta_pct": _pct(df.calificado.mean()),
        "n_calificaciones": int(len(cal_all)),
        "media_estrellas": float(round(cal_all.estrellas.mean(), 2)),
        "distribucion_pct": {int(k): _pct(v) for k, v in cal_all.estrellas.value_counts(normalize=True).sort_index().items()},
        "pct_1_2": _pct((cal_all.estrellas <= 2).mean()),
        "pct_1_2_atrasado": _pct((cal_all[cal_all.atrasado].estrellas <= 2).mean()),
        "pct_1_2_a_tiempo": _pct((cal_all[~cal_all.atrasado].estrellas <= 2).mean()),
        "tasa_respuesta_por_n_orden_pct": {int(k): _pct(v) for k, v in df.groupby(df.n_orden.clip(upper=4)).calificado.mean().items()},
    }
    return res


def simpson(df: pd.DataFrame) -> dict:
    g = df.groupby(["bodega", "tipo_pedido"]).agg(pedidos=("pedido_id", "size"), atrasados=("atrasado", "sum")).reset_index()
    g["atraso_pct"] = (g.atrasados / g.pedidos * 100).round(1)
    tot = df.groupby("bodega").agg(pedidos=("pedido_id", "size"), atraso_pct=("atrasado", lambda s: round(100 * s.mean(), 1)))
    mezcla = df.groupby("bodega").complejo.mean().mul(100).round(1)
    return {
        "por_bodega_tipo": g.to_dict("records"),
        "total_bodega": {b: {"pedidos": int(r.pedidos), "atraso_pct": float(r.atraso_pct), "pct_complejos": float(mezcla[b])} for b, r in tot.iterrows()},
    }


def rf_importancia(df: pd.DataFrame) -> dict:
    """Verifica la matriz de importancia (Tabla E). Objetivo: no recompra a 30 dias."""
    from sklearn.ensemble import RandomForestClassifier
    from sklearn.inspection import permutation_importance
    from sklearn.metrics import roc_auc_score
    from sklearn.model_selection import train_test_split

    el = df[df.elegible_recompra].copy()
    y = (~el.recompra30).astype(int)
    X = pd.DataFrame({
        "Pedido atrasado": el.atrasado.astype(int),
        "Productos faltantes o sustituidos": el.faltantes.astype(int),
        "Congelados fuera de temperatura": el.quiebre_frio.astype(int),
        "Reclamo sin respuesta > 24 h": el.reclamo_tardio.astype(int),
        "Uso de cupón": el.cupon.astype(int),
        "Calificación del pedido (0 = sin)": el.estrellas.fillna(0),
        "Ciudad de origen": el.ciudad.astype("category").cat.codes,
    })
    Xtr, Xte, ytr, yte = train_test_split(X, y, test_size=0.3, random_state=CFG["SEED"], stratify=y)
    rf = RandomForestClassifier(n_estimators=200, min_samples_leaf=50, random_state=CFG["SEED"], n_jobs=-1).fit(Xtr, ytr)
    auc = float(roc_auc_score(yte, rf.predict_proba(Xte)[:, 1]))
    gini = pd.Series(rf.feature_importances_, index=X.columns) * 100
    sub = Xte.sample(min(15000, len(Xte)), random_state=CFG["SEED"])
    perm = permutation_importance(rf, sub, yte.loc[sub.index], scoring="roc_auc", n_repeats=5, random_state=CFG["SEED"], n_jobs=-1)
    perm_s = pd.Series(perm.importances_mean, index=X.columns).clip(lower=0)
    perm_s = perm_s / perm_s.sum() * 100
    out = pd.DataFrame({"importancia_gini_pct": gini.round(1), "importancia_permutacion_pct": perm_s.round(1)}).sort_values("importancia_gini_pct", ascending=False)
    return {"auc": round(auc, 3), "tasa_fuga_pct": _pct(y.mean()), "n": int(len(el)), "importancias": out.reset_index(names="variable").to_dict("records")}


# --------------------------------------------------------------------- main
def main() -> None:
    OUT.mkdir(parents=True, exist_ok=True)
    raw = load_raw()
    calidad = quality_report(raw)
    df = build_master(raw)
    resultado = {
        "calidad": calidad,
        "kpis_q3": kpis(df),
        "kpis_por_mes": {m: kpis(g) for m, g in df.groupby("mes")},
        "auditoria": auditoria(df),
        "modelo_fuga": rf_importancia(df),
        "supuestos": CFG,
        "metas_kpi_parte1": METAS,
    }
    (OUT / "metricas.json").write_text(json.dumps(resultado, ensure_ascii=False, indent=2, default=str), encoding="utf-8")
    print(f"OK -> {OUT / 'metricas.json'}")
    print("Pedidos:", resultado["kpis_q3"]["pedidos"], "| AUC:", resultado["modelo_fuga"]["auc"])


if __name__ == "__main__":
    main()
