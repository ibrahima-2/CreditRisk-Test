"""Figures du rapport à partir des résultats mesurés (JSON versionnés dans reports/).

Usage : ``python scripts/graphiques_rapport.py`` (nécessite matplotlib, cf. requirements-perf.txt).
Sortie : ``reports/figures/*.png``.
"""

from __future__ import annotations

import json
from pathlib import Path

import matplotlib

matplotlib.use("Agg")
import matplotlib.pyplot as plt

RACINE = Path(__file__).resolve().parent.parent
PERF = RACINE / "reports" / "performance"
SORTIE = RACINE / "reports" / "figures"

SURFACE = "#fcfcfb"
ENCRE = "#0b0b0b"
ENCRE_2 = "#52514e"
GRILLE = "#e4e3df"
BLEU, ORANGE = "#2a78d6", "#eb6834"  # palette validée (CVD, contraste)

plt.rcParams.update(
    {
        "font.family": "Times New Roman",  # même police que le rapport
        "font.size": 10,
        "axes.edgecolor": GRILLE,
        "axes.labelcolor": ENCRE_2,
        "axes.titlecolor": ENCRE,
        "axes.titlesize": 11,
        "axes.titleweight": "bold",
        "axes.titlelocation": "left",
        "xtick.color": ENCRE_2,
        "ytick.color": ENCRE_2,
        "axes.spines.top": False,
        "axes.spines.right": False,
        "figure.facecolor": SURFACE,
        "axes.facecolor": SURFACE,
        "savefig.facecolor": SURFACE,
        "legend.frameon": False,
    }
)


def charger(nom: str) -> dict:
    return json.loads((PERF / nom).read_text(encoding="utf-8"))


def axes_charge(ax, titre: str, ylabel: str) -> None:
    ax.set_title(titre, pad=12)
    ax.set_xscale("log")
    ax.set_xticks([1, 2, 5, 10, 20, 50, 100], labels=["1", "2", "5", "10", "20", "50", "100"])
    ax.minorticks_off()
    ax.set_xlabel("Utilisateurs simultanés (échelle logarithmique)")
    ax.set_ylabel(ylabel)
    ax.grid(axis="y", color=GRILLE, linewidth=0.8)
    ax.set_axisbelow(True)


def courbe(ax, x, y, couleur, etiquette):
    ax.plot(x, y, color=couleur, linewidth=2, marker="o", markersize=7,
            markeredgecolor=SURFACE, markeredgewidth=2, label=etiquette)  # fmt: skip
    ax.annotate(f"{etiquette}", (x[-1], y[-1]), xytext=(8, 0), textcoords="offset points",
                va="center", color=ENCRE_2, fontsize=9)  # fmt: skip


def figure_latence_et_debit() -> None:
    resultats = charger("resultats_performance.json")["charge_progressive"]
    for cle, titre, ylabel, nom in (
        ("p95_ms", "Latence P95 de POST /predict selon la charge", "Latence P95 (ms)",
         "latence_p95_charge.png"),
        ("debit_req_s", "Débit de POST /predict selon la charge", "Requêtes par seconde",
         "debit_charge.png"),
    ):  # fmt: skip
        fig, ax = plt.subplots(figsize=(7.2, 3.8), dpi=200)
        axes_charge(ax, titre, ylabel)
        for config, couleur, libelle in (
            ("1_processus", BLEU, "1 processus"),
            ("4_processus", ORANGE, "4 processus"),
        ):
            paliers = resultats[config]
            courbe(ax, [p["utilisateurs_simultanes"] for p in paliers],
                   [p[cle] for p in paliers], couleur, libelle)  # fmt: skip
        if cle == "p95_ms":
            ax.axhline(200, color=ENCRE_2, linewidth=1, linestyle=(0, (4, 3)))
            ax.annotate("Objectif EX19 : P95 ≤ 200 ms", (1, 200), xytext=(0, 5),
                        textcoords="offset points", color=ENCRE_2, fontsize=9)  # fmt: skip
            ax.set_ylim(0, 230)
        else:
            ax.set_ylim(0, None)
        ax.set_xlim(0.8, 220)
        ax.legend(loc="upper left", bbox_to_anchor=(0, -0.22), ncol=2)
        fig.tight_layout()
        fig.savefig(SORTIE / nom)
        plt.close(fig)


def figure_biais_mesure() -> None:
    ab = charger("resultats_performance.json")["charge_progressive"]["1_processus"]
    httpx = charger("biais_client_httpx_1_worker.json")["charge_progressive"]
    fig, ax = plt.subplots(figsize=(7.2, 3.8), dpi=200)
    axes_charge(ax, "Même serveur (1 processus), deux générateurs de charge", "Latence P95 (ms)")
    ax.set_yscale("log")
    ax.set_ylabel("Latence P95 (ms, échelle log.)")
    ax.set_yticks([1, 10, 100, 1000], labels=["1", "10", "100", "1 000"])
    courbe(ax, [p["utilisateurs_simultanes"] for p in ab], [max(p["p95_ms"], 1) for p in ab],
           BLEU, "ApacheBench (C)")  # fmt: skip
    courbe(ax, [p["utilisateurs_simultanes"] for p in httpx], [p["p95_ms"] for p in httpx],
           ORANGE, "Client httpx asynchrone (Python)")  # fmt: skip
    ax.set_xlim(0.8, 400)
    ax.legend(loc="upper left", bbox_to_anchor=(0, -0.22), ncol=2)
    fig.tight_layout()
    fig.savefig(SORTIE / "biais_generateur_de_charge.png")
    plt.close(fig)


def figure_faux_negatifs() -> None:
    comparaison = json.loads(
        (RACINE / "reports" / "non_regression" / "comparaison_v1.1.0.json").read_text("utf-8")
    )
    segments = comparaison["segments_reference"]
    seuil = json.loads(
        (RACINE / "model" / "reference" / "tolerances_non_regression.json").read_text("utf-8")
    )["segments"]
    libelles = {
        "age_18_25": "18-25 ans", "age_26_40": "26-40 ans", "age_41_55": "41-55 ans",
        "age_56_plus": "56 ans et +", "revenu_tercile_1": "Revenu, tercile 1 (bas)",
        "revenu_tercile_2": "Revenu, tercile 2", "revenu_tercile_3": "Revenu, tercile 3 (haut)",
    }  # fmt: skip
    noms = list(libelles)[::-1]
    valeurs = [segments[n]["taux_faux_negatifs"] * 100 for n in noms]
    suffisant = [segments[n]["defauts"] >= seuil["effectif_defauts_min"] for n in noms]
    fig, ax = plt.subplots(figsize=(7.2, 3.9), dpi=200)
    barres = ax.barh(
        [libelles[n] for n in noms], valeurs, height=0.6,
        color=[BLEU if s else SURFACE for s in suffisant], edgecolor=BLEU, linewidth=1.2,
        hatch=[None if s else "////" for s in suffisant],
    )  # fmt: skip
    for barre, nom, valeur in zip(barres, noms, valeurs, strict=True):
        m = segments[nom]
        ax.annotate(
            f"{valeur:.1f} %  ({m['faux_negatifs']}/{m['defauts']} défauts)",
            (barre.get_width(), barre.get_y() + barre.get_height() / 2),
            xytext=(6, 0), textcoords="offset points", va="center", color=ENCRE, fontsize=9,
        )  # fmt: skip
    limite = seuil["taux_faux_negatifs_max"] * 100
    ax.axvline(limite, color=ENCRE_2, linewidth=1, linestyle=(0, (4, 3)))
    ax.annotate(f"Tolérance {limite:.0f} %", (limite, len(noms) - 0.4), xytext=(4, 0),
                textcoords="offset points", color=ENCRE_2, fontsize=9)  # fmt: skip
    ax.set_xlim(0, 100)
    ax.set_xlabel("Taux de faux négatifs au seuil de signalement (%)")
    fig.suptitle(
        "Défauts non signalés par segment, modèle v1.0.0 (jeu de test)",
        x=0.015, ha="left", fontsize=11, fontweight="bold", color=ENCRE,
    )  # fmt: skip
    ax.grid(axis="x", color=GRILLE, linewidth=0.8)
    ax.set_axisbelow(True)
    ax.tick_params(axis="y", length=0)
    ax.annotate("Hachuré : moins de 15 défauts dans le segment, estimation non fiable",
                (0, -0.27), xycoords="axes fraction", color=ENCRE_2, fontsize=8.5)  # fmt: skip
    fig.tight_layout()
    fig.savefig(SORTIE / "faux_negatifs_segments.png")
    plt.close(fig)


def main() -> None:
    SORTIE.mkdir(parents=True, exist_ok=True)
    figure_latence_et_debit()
    figure_biais_mesure()
    figure_faux_negatifs()
    print(f"Figures écrites dans {SORTIE}")


if __name__ == "__main__":
    main()
