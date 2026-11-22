"""Entraînement reproductible des versions du modèle et écriture des métadonnées.

Usage : ``python -m ml.entrainement 1.0.0`` (référence) ou ``1.1.0`` (candidat).
"""

from __future__ import annotations

import json
import platform
import sys
from collections.abc import Callable
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

import joblib
import numpy as np
import sklearn
from sklearn.ensemble import HistGradientBoostingClassifier
from sklearn.linear_model import LogisticRegression
from sklearn.metrics import fbeta_score
from sklearn.model_selection import StratifiedKFold, cross_val_predict
from sklearn.pipeline import Pipeline
from sklearn.preprocessing import StandardScaler

from app import preprocessing
from app.prediction import sha256_fichier
from ml import donnees
from ml.evaluation import calculer_metriques

REPERTOIRE_MODELES = Path(__file__).resolve().parent.parent / "model"
GRILLE_SEUILS = np.round(np.arange(0.05, 0.71, 0.01), 2)


def modele_v1_0() -> Pipeline:
    """Référence : régression logistique (interprétable, rapide, déterministe)."""
    return Pipeline(
        [
            ("normalisation", StandardScaler()),
            ("classifieur", LogisticRegression(C=1.0, max_iter=1_000)),
        ]
    )


def modele_v1_1() -> HistGradientBoostingClassifier:
    """Candidat : gradient boosting avec contraintes de monotonie métier.

    Ordre des variables : age, log_revenu, duree, anciennete, taux_endettement.
    -1 : le risque ne peut que baisser quand la variable augmente ; +1 : l'inverse.
    """
    return HistGradientBoostingClassifier(
        max_iter=150,
        learning_rate=0.05,
        max_leaf_nodes=15,
        min_samples_leaf=40,
        monotonic_cst=[-1, -1, 0, -1, 1],
        random_state=donnees.GRAINE,
    )


VERSIONS: dict[str, tuple[Callable[[], Any], str]] = {
    "1.0.0": (modele_v1_0, "StandardScaler + LogisticRegression"),
    "1.1.0": (modele_v1_1, "HistGradientBoostingClassifier (contraintes de monotonie)"),
}


def choisir_seuils(fabrique: Callable[[], Any], x: np.ndarray, y: np.ndarray) -> dict[str, float]:
    """Seuils de risque estimés par validation croisée sur le jeu d'apprentissage seul.

    - ``risque_modere`` (seuil de signalement) : maximise le F2, qui pondère le rappel
      deux fois plus que la précision. Au-delà, la demande est signalée pour revue
      humaine : un défaut non signalé (faux négatif) coûte plus cher qu'un examen inutile.
    - ``risque_eleve`` : maximise le F1 (compromis précision/rappel), strictement
      au-dessus du seuil de signalement.
    """
    cv = StratifiedKFold(n_splits=5, shuffle=True, random_state=donnees.GRAINE)
    proba = cross_val_predict(fabrique(), x, y, cv=cv, method="predict_proba")[:, 1]
    f2 = [fbeta_score(y, proba >= s, beta=2) for s in GRILLE_SEUILS]
    modere = float(GRILLE_SEUILS[int(np.argmax(f2))])
    candidats = GRILLE_SEUILS[modere < GRILLE_SEUILS]
    f1 = [fbeta_score(y, proba >= s, beta=1) for s in candidats]
    return {"risque_modere": modere, "risque_eleve": float(candidats[int(np.argmax(f1))])}


def domaine(colonnes: dict[str, np.ndarray], x: np.ndarray) -> dict[str, dict[str, float]]:
    """Intervalle observé à l'entraînement pour chaque variable (détection hors domaine)."""
    bornes = {c: (float(v.min()), float(v.max())) for c, v in colonnes.items()}
    taux = x[:, preprocessing.VARIABLES_MODELE.index("taux_endettement")]
    bornes["taux_endettement"] = (float(taux.min()), float(taux.max()))
    return {c: {"min": a, "max": b} for c, (a, b) in bornes.items()}


def entrainer(
    version: str,
    repertoire_donnees: Path = donnees.REPERTOIRE_DONNEES,
    repertoire_sortie: Path = REPERTOIRE_MODELES,
) -> dict[str, Any]:
    fabrique, algorithme = VERSIONS[version]
    colonnes_train, y_train = donnees.charger_csv(repertoire_donnees / donnees.FICHIER_TRAIN)
    colonnes_test, y_test = donnees.charger_csv(repertoire_donnees / donnees.FICHIER_TEST)
    x_train = preprocessing.transformer_lot(colonnes_train)
    x_test = preprocessing.transformer_lot(colonnes_test)

    seuils = choisir_seuils(fabrique, x_train, y_train)
    modele = fabrique().fit(x_train, y_train)
    # Les métriques sont calculées au seuil de signalement : un faux négatif est un
    # défaut classé FAIBLE, donc non soumis à revue humaine.
    metriques = calculer_metriques(
        y_test, modele.predict_proba(x_test)[:, 1], seuils["risque_modere"]
    )

    repertoire_sortie.mkdir(parents=True, exist_ok=True)
    chemin_modele = repertoire_sortie / f"credit_risk_v{version}.joblib"
    joblib.dump(modele, chemin_modele)
    metadonnees = {
        "nom": "credit-risk",
        "version": version,
        "algorithme": algorithme,
        "date_entrainement": datetime.now(UTC).isoformat(timespec="seconds"),
        "variables_modele": list(preprocessing.VARIABLES_MODELE),
        "seuils": seuils,
        "domaine_entrainement": domaine(colonnes_train, x_train),
        "metriques_test": metriques,
        "jeu_donnees": {
            "type": "synthetique",
            "graine": donnees.GRAINE,
            "effectif_apprentissage": len(y_train),
            "effectif_test": len(y_test),
            "avertissement": (
                "Données simulées : elles servent à tester le système et ne démontrent "
                "pas la performance réelle d'un modèle de crédit."
            ),
        },
        "sha256": sha256_fichier(chemin_modele),
        "versions_logicielles": {
            "python": platform.python_version(),
            "scikit-learn": sklearn.__version__,
            "numpy": np.__version__,
            "joblib": joblib.__version__,
        },
    }
    chemin_modele.with_suffix(".json").write_text(
        json.dumps(metadonnees, indent=2, ensure_ascii=False) + "\n", encoding="utf-8"
    )
    return metadonnees


def main() -> None:  # pragma: no cover - script
    version = sys.argv[1] if len(sys.argv) > 1 else "1.0.0"
    metadonnees = entrainer(version)
    print(json.dumps({k: metadonnees[k] for k in ("version", "seuils")}, indent=2))
    print(json.dumps(metadonnees["metriques_test"], indent=2))


if __name__ == "__main__":  # pragma: no cover
    main()
