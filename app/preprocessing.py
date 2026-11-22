"""Module de prétraitement : construction des variables attendues par le modèle.

Une seule implémentation (vectorisée) est utilisée à l'entraînement ET en production,
afin d'éliminer tout écart entre les deux chaînes (« training/serving skew »).
La normalisation (StandardScaler) fait partie du pipeline scikit-learn sauvegardé.
"""

from __future__ import annotations

from collections.abc import Mapping, Sequence

import numpy as np

VARIABLES_ENTREE: tuple[str, ...] = (
    "age",
    "revenu_mensuel",
    "montant_credit",
    "duree_mois",
    "anciennete_activite",
)

# Ordre des colonnes de la matrice transmise au modèle (fait partie du contrat).
VARIABLES_MODELE: tuple[str, ...] = (
    "age",
    "log_revenu_mensuel",
    "duree_mois",
    "anciennete_activite",
    "taux_endettement",
)


class ErreurPretraitement(Exception):
    """Les données ne peuvent pas être transformées en variables du modèle."""


def _colonnes_numeriques(colonnes: Mapping[str, Sequence[float]]) -> dict[str, np.ndarray]:
    manquantes = [nom for nom in VARIABLES_ENTREE if nom not in colonnes]
    if manquantes:
        raise ErreurPretraitement(f"Variables manquantes : {', '.join(manquantes)}")
    try:
        valeurs = {
            nom: np.asarray(colonnes[nom], dtype=np.float64).reshape(-1) for nom in VARIABLES_ENTREE
        }
    except (TypeError, ValueError) as exc:
        raise ErreurPretraitement("Variables non numériques") from exc
    if len({v.size for v in valeurs.values()}) != 1:
        raise ErreurPretraitement("Les variables n'ont pas toutes le même nombre de lignes")
    if not all(np.all(np.isfinite(v)) for v in valeurs.values()):
        raise ErreurPretraitement("Valeurs non finies dans les variables d'entrée")
    for nom in ("revenu_mensuel", "montant_credit", "duree_mois"):
        if np.any(valeurs[nom] <= 0):
            raise ErreurPretraitement(f"La variable {nom} doit être strictement positive")
    return valeurs


def transformer_lot(colonnes: Mapping[str, Sequence[float]]) -> np.ndarray:
    """Transforme des colonnes brutes en matrice (n, 5) ordonnée selon ``VARIABLES_MODELE``."""
    v = _colonnes_numeriques(colonnes)
    with np.errstate(over="ignore", divide="ignore", invalid="ignore"):
        taux_endettement = v["montant_credit"] / (v["duree_mois"] * v["revenu_mensuel"])
        matrice = np.column_stack(
            [
                v["age"],
                np.log(v["revenu_mensuel"]),
                v["duree_mois"],
                v["anciennete_activite"],
                taux_endettement,
            ]
        )
    if not np.all(np.isfinite(matrice)):
        raise ErreurPretraitement("Variables dérivées non finies (dépassement numérique)")
    return matrice


def transformer(donnees: Mapping[str, float]) -> np.ndarray:
    """Transforme une demande unique en matrice (1, 5)."""
    return transformer_lot({nom: [donnees[nom]] for nom in VARIABLES_ENTREE if nom in donnees})


def indicateurs(donnees: Mapping[str, float]) -> dict[str, float]:
    """Indicateurs lisibles par l'agent de crédit (mensualité hors intérêts, endettement)."""
    mensualite = float(donnees["montant_credit"]) / float(donnees["duree_mois"])
    return {
        "mensualite_estimee": round(mensualite, 2),
        "taux_endettement": mensualite / float(donnees["revenu_mensuel"]),
    }
