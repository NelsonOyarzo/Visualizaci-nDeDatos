"""Genera las figuras estaticas (PNG) usadas en el informe y la presentacion.

Uso:  python codigo_y_data/generar_figuras.py
Requiere haber ejecutado antes pipeline.py (usa outputs/metricas.json).
"""
import json
from pathlib import Path

import matplotlib

matplotlib.use("Agg")
import matplotlib.pyplot as plt  # noqa: E402

ROOT = Path(__file__).resolve().parent.parent
OUT = ROOT / "codigo_y_data" / "outputs"
FIG = OUT / "figuras"
FIG.mkdir(parents=True, exist_ok=True)

AZUL, NARANJA, GRIS, VERDE = "#0072B2", "#D55E00", "#595959", "#009E73"  # Okabe-Ito
plt.rcParams.update({"font.size": 11, "axes.spines.top": False, "axes.spines.right": False, "axes.titleweight": "bold",
                     "axes.titlesize": 12, "figure.dpi": 100})
M = json.loads((OUT / "metricas.json").read_text(encoding="utf-8"))
A = M["auditoria"]


def guardar(fig, nombre):
    fig.tight_layout()
    fig.savefig(FIG / nombre, dpi=200)
    plt.close(fig)


def fmt(x, d=1):
    return f"{x:.{d}f}".replace(".", ",")


# 1. Pedidos y reclamos por mes ------------------------------------------------
def fig_mes():
    meses = ["Jul", "Ago", "Sep"]
    ped = list(A["A2"]["pedidos_mes"].values())
    rec = list(A["A1"]["por_mes_pct"].values())
    fig, ax = plt.subplots(1, 2, figsize=(8.4, 3.2))
    b = ax[0].bar(meses, ped, color=AZUL)
    ax[0].set_title("Pedidos por mes")
    ax[0].set_ylim(0, max(ped) * 1.15)
    for r, v in zip(b, ped):
        ax[0].text(r.get_x() + r.get_width() / 2, v + max(ped) * 0.02, f"{v:,}".replace(",", "."), ha="center", fontsize=10)
    ax[0].set_yticks([])
    ax[0].spines["left"].set_visible(False)
    ax[1].plot(meses, rec, color=NARANJA, marker="o", linewidth=2.5, linestyle="--")
    ax[1].set_title("Reclamos por 100 pedidos")
    ax[1].set_ylim(0, 20)
    for m, v in zip(meses, rec):
        ax[1].text(m, v + 1.2, fmt(v), ha="center", fontsize=10)
    guardar(fig, "fig_mes.png")


# 2. Paradoja de Simpson -------------------------------------------------------
def fig_simpson():
    orden = ["Centro", "Norte", "Sur"]
    d = {(r["bodega"], r["tipo_pedido"]): r["atraso_pct"] for r in A["A4"]["por_bodega_tipo"]}
    tot = {b: A["A4"]["total_bodega"][b]["atraso_pct"] for b in orden}
    mezcla = {b: A["A4"]["total_bodega"][b]["pct_complejos"] for b in orden}
    fig, ax = plt.subplots(figsize=(8.4, 3.6))
    w = 0.26
    xs = range(len(orden))
    series = [("Simple", AZUL, "", [d[(b, "Simple")] for b in orden], -w),
              ("Complejo", NARANJA, "//", [d[(b, "Complejo")] for b in orden], 0),
              ("Total bodega", GRIS, "..", [tot[b] for b in orden], w)]
    for nombre, col, hatch, vals, off in series:
        bars = ax.bar([x + off for x in xs], vals, w * 0.95, label=nombre, color=col, hatch=hatch, edgecolor="white")
        for r, v in zip(bars, vals):
            ax.text(r.get_x() + r.get_width() / 2, v + 1, fmt(v) + "%", ha="center", fontsize=9)
    ax.set_xticks(list(xs))
    ax.set_xticklabels([f"{b}\n({fmt(mezcla[b], 0)}% complejos)" if b != "Sur" else f"Sur (externa)\n({fmt(mezcla[b], 0)}% complejos)" for b in orden])
    ax.set_ylabel("% de pedidos atrasados")
    ax.set_ylim(0, 55)
    ax.legend(frameon=False, ncol=3, loc="upper left")
    ax.set_title("Centro parece peor que Norte, pero gana en ambos tipos de pedido")
    guardar(fig, "fig_simpson.png")


# 3. Que explica la fuga ----------------------------------------------------------
def fig_fuga():
    a5 = A["A5"]
    fig, ax = plt.subplots(1, 2, figsize=(8.4, 3.4))
    grupos = ["1-2 estrellas", "3 estrellas", "4-5 estrellas"]
    for i, (nombre, col, hatch) in enumerate([("a tiempo", AZUL, ""), ("atrasado", NARANJA, "//")]):
        vals = [a5["recompra_atraso_x_estrellas"][f"{nombre} | {g}"] for g in grupos]
        bars = ax[0].bar([x + (i - 0.5) * 0.38 for x in range(3)], vals, 0.36, label="Pedido " + nombre, color=col, hatch=hatch, edgecolor="white")
        for r, v in zip(bars, vals):
            ax[0].text(r.get_x() + r.get_width() / 2, v + 1.5, fmt(v, 0) + "%", ha="center", fontsize=9)
    ax[0].set_xticks(range(3))
    ax[0].set_xticklabels(["1-2 ★", "3 ★", "4-5 ★"])
    ax[0].set_ylim(0, 100)
    ax[0].set_title("Recompra a 30 días según calificación")
    ax[0].legend(frameon=False, loc="upper center", ncol=2, fontsize=9)
    c = a5["recompra_cupon_x_atraso_pct"]
    etiquetas = ["a tiempo | sin cupon", "a tiempo | con cupon", "atrasado | sin cupon", "atrasado | con cupon"]
    vals = [c[e] for e in etiquetas]
    cols = [AZUL, AZUL, NARANJA, NARANJA]
    bars = ax[1].bar(range(4), vals, color=cols, edgecolor="white")
    for r, h in zip(bars, ["", "..", "//", "//.."]):
        r.set_hatch(h)
    for r, v in zip(bars, vals):
        ax[1].text(r.get_x() + r.get_width() / 2, v + 1.5, fmt(v, 0) + "%", ha="center", fontsize=9)
    ax[1].set_xticks(range(4))
    ax[1].set_xticklabels(["A tiempo\nsin cupón", "A tiempo\ncon cupón", "Atrasado\nsin cupón", "Atrasado\ncon cupón"], fontsize=9)
    ax[1].set_ylim(0, 100)
    ax[1].set_title("Un cupón no compensa un atraso")
    guardar(fig, "fig_fuga.png")


# 4. Importancia del modelo --------------------------------------------------------
def fig_modelo():
    imp = M["modelo_fuga"]["importancias"][::-1]
    fig, ax = plt.subplots(figsize=(8.4, 3.2))
    nombres = [i["variable"] for i in imp]
    ax.barh(nombres, [i["importancia_gini_pct"] for i in imp], color=AZUL, height=0.6)
    for y, i in enumerate(imp):
        ax.text(i["importancia_gini_pct"] + 0.8, y, fmt(i["importancia_gini_pct"]) + "%", va="center", fontsize=9)
    ax.set_xlim(0, 65)
    ax.set_xlabel("Importancia relativa (Gini, %)")
    ax.set_title(f"Random Forest de fuga (AUC = {fmt(M['modelo_fuga']['auc'], 2)})")
    guardar(fig, "fig_modelo.png")


if __name__ == "__main__":
    fig_mes()
    fig_simpson()
    fig_fuga()
    fig_modelo()
    print("Figuras en", FIG)
