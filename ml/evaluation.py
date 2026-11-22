"""Métriques du modèle et comparaison à une version de référence (non-régression)."""

from __future__ import annotations

import json
from dataclasses import asdict, dataclass
from pathlib import Path
from typing import Any

import numpy as np
from sklearn.metrics import (
    accuracy_score,
    brier_score_loss,
    confusion_matrix,
    f1_score,
    precision_score,
    recall_score,
    roc_auc_score,
)

REPERTOIRE_REFERENCE = Path(__file__).resolve().parent.parent / "model" / "reference"
FICHIER_TOLERANCES = REPERTOIRE_REFERENCE / "tolerances_non_regression.json"
FICHIER_REFERENCE = REPERTOIRE_REFERENCE / "reference_v1.0.0.json"


def calculer_metriques(y_vrai: np.ndarray, probabilites: np.ndarray, seuil: float) -> dict:
    """Métriques de classification au seuil de décision « risque élevé »."""
    y_vrai = np.asarray(y_vrai).astype(int)
    y_pred = (np.asarray(probabilites) >= seuil).astype(int)
    vn, fp, fn, vp = confusion_matrix(y_vrai, y_pred, labels=[0, 1]).ravel()
    return {
        "roc_auc": float(roc_auc_score(y_vrai, probabilites)),
        "rappel": float(recall_score(y_vrai, y_pred, zero_division=0)),
        "precision": float(precision_score(y_vrai, y_pred, zero_division=0)),
        "f1": float(f1_score(y_vrai, y_pred, zero_division=0)),
        "exactitude": float(accuracy_score(y_vrai, y_pred)),
        "brier": float(brier_score_loss(y_vrai, probabilites)),
        "taux_faux_negatifs": float(fn / (fn + vp)) if (fn + vp) else 0.0,
        "seuil": float(seuil),
        "effectif": len(y_vrai),
        "taux_defaut": float(y_vrai.mean()),
        "matrice_confusion": {"vn": int(vn), "fp": int(fp), "fn": int(fn), "vp": int(vp)},
    }


def charger_json(chemin: Path) -> dict[str, Any]:
    return json.loads(Path(chemin).read_text(encoding="utf-8"))


@dataclass(frozen=True)
class Controle:
    critere: str
    reference: float | None
    candidat: float
    limite: float
    conforme: bool
    regle: str


@dataclass(frozen=True)
class RapportComparaison:
    controles: list[Controle]

    @property
    def conforme(self) -> bool:
        return all(c.conforme for c in self.controles)

    @property
    def non_conformites(self) -> list[str]:
        return [c.critere for c in self.controles if not c.conforme]

    def en_dict(self) -> dict[str, Any]:
        return {"conforme": self.conforme, "controles": [asdict(c) for c in self.controles]}


def comparer_metriques(reference: dict, candidat: dict, tolerances: dict) -> RapportComparaison:
    """Compare les métriques d'une version candidate à la référence.

    Pour chaque métrique : baisse (ou hausse pour le Brier) maximale tolérée par rapport à
    la référence ET, le cas échéant, plancher absolu imposé par le métier.
    """
    controles: list[Controle] = []
    for metrique, regle in tolerances["metriques"].items():
        ref, cand = reference[metrique], candidat[metrique]
        if "baisse_max_absolue" in regle:
            limite = ref - regle["baisse_max_absolue"]
            controles.append(
                Controle(
                    f"{metrique}_baisse",
                    ref,
                    cand,
                    limite,
                    cand >= limite - 1e-12,
                    f">= référence - {regle['baisse_max_absolue']}",
                )
            )
        if "hausse_max_absolue" in regle:
            limite = ref + regle["hausse_max_absolue"]
            controles.append(
                Controle(
                    f"{metrique}_hausse",
                    ref,
                    cand,
                    limite,
                    cand <= limite + 1e-12,
                    f"<= référence + {regle['hausse_max_absolue']}",
                )
            )
        if "plancher" in regle:
            controles.append(
                Controle(
                    f"{metrique}_plancher",
                    None,
                    cand,
                    regle["plancher"],
                    cand >= regle["plancher"],
                    f">= {regle['plancher']} (plancher métier)",
                )
            )
    return RapportComparaison(controles)


def comparer_predictions(
    p_reference: np.ndarray,
    p_candidat: np.ndarray,
    niveaux_reference: list[str],
    niveaux_candidat: list[str],
    tolerances: dict,
) -> RapportComparaison:
    """Compare les sorties de deux versions sur le jeu de profils de référence (golden set)."""
    ecarts = np.abs(np.asarray(p_candidat) - np.asarray(p_reference))
    changements = float(
        np.mean([a != b for a, b in zip(niveaux_reference, niveaux_candidat, strict=True)])
    )
    regles = tolerances["predictions"]["nouveau_modele"]
    return RapportComparaison(
        [
            Controle(
                "ecart_moyen_probabilite",
                None,
                float(ecarts.mean()),
                regles["ecart_moyen_max"],
                float(ecarts.mean()) <= regles["ecart_moyen_max"],
                f"<= {regles['ecart_moyen_max']}",
            ),
            Controle(
                "ecart_max_probabilite",
                None,
                float(ecarts.max()),
                regles["ecart_max"],
                float(ecarts.max()) <= regles["ecart_max"],
                f"<= {regles['ecart_max']}",
            ),
            Controle(
                "taux_changement_niveau_risque",
                None,
                changements,
                regles["taux_changement_niveau_max"],
                changements <= regles["taux_changement_niveau_max"],
                f"<= {regles['taux_changement_niveau_max']}",
            ),
        ]
    )


def segments(colonnes: dict[str, np.ndarray]) -> dict[str, np.ndarray]:
    """Segments de contrôle : tranches d'âge et terciles de revenu (calculés sur ``colonnes``)."""
    age, revenu = colonnes["age"], colonnes["revenu_mensuel"]
    t1, t2 = np.quantile(revenu, [1 / 3, 2 / 3])
    return {
        "age_18_25": age <= 25,
        "age_26_40": (age > 25) & (age <= 40),
        "age_41_55": (age > 40) & (age <= 55),
        "age_56_plus": age > 55,
        "revenu_tercile_1": revenu <= t1,
        "revenu_tercile_2": (revenu > t1) & (revenu <= t2),
        "revenu_tercile_3": revenu > t2,
    }


def metriques_par_segment(
    colonnes: dict[str, np.ndarray], y_vrai: np.ndarray, probabilites: np.ndarray, seuil: float
) -> dict[str, dict[str, float]]:
    """Taux de faux négatifs et taux de signalement par segment de demandeurs."""
    y_vrai = np.asarray(y_vrai).astype(int)
    signales = np.asarray(probabilites) >= seuil
    resultats = {}
    for nom, masque in segments(colonnes).items():
        defauts = int(y_vrai[masque].sum())
        faux_negatifs = int(((y_vrai == 1) & ~signales & masque).sum())
        resultats[nom] = {
            "effectif": int(masque.sum()),
            "defauts": defauts,
            "faux_negatifs": faux_negatifs,
            "taux_faux_negatifs": faux_negatifs / defauts if defauts else 0.0,
            "taux_signalement": float(signales[masque].mean()) if masque.any() else 0.0,
        }
    return resultats
