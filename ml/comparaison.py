"""Comparaison d'une version candidate du modèle à la référence gelée.

Usage : ``python -m ml.comparaison model/credit_risk_v1.1.0.joblib``
Sortie : ``reports/non_regression/comparaison_v<version>.json`` (données brutes du rapport).
"""

from __future__ import annotations

import json
import sys
import tempfile
from pathlib import Path
from typing import Any

import joblib
import numpy as np

from app import preprocessing
from app.prediction import ServiceModele
from ml import donnees
from ml.evaluation import (
    FICHIER_REFERENCE,
    FICHIER_TOLERANCES,
    calculer_metriques,
    charger_json,
    comparer_metriques,
    comparer_predictions,
    metriques_par_segment,
)

REPERTOIRE_RAPPORT = Path(__file__).resolve().parent.parent / "reports" / "non_regression"


def comparer(chemin_candidat: Path) -> dict[str, Any]:
    reference = charger_json(FICHIER_REFERENCE)
    tolerances = charger_json(FICHIER_TOLERANCES)
    service = ServiceModele(chemin_candidat)
    service.charger()
    meta = service.metadonnees

    colonnes, y = donnees.charger_csv(donnees.REPERTOIRE_DONNEES / donnees.FICHIER_TEST)
    x = preprocessing.transformer_lot(colonnes)
    p_candidat = service.predire_lot(x)
    metriques = calculer_metriques(y, p_candidat, meta["seuils"]["risque_modere"])
    controle_metriques = comparer_metriques(reference["metriques"], metriques, tolerances)

    resultats = [service.evaluer(p["entree"]) for p in reference["profils"]]
    controle_profils = comparer_predictions(
        np.array([p["probabilite_defaut"] for p in reference["profils"]]),
        np.array([r.probabilite_defaut for r in resultats]),
        [p["niveau_risque"] for p in reference["profils"]],
        [r.niveau_risque for r in resultats],
        tolerances,
    )

    service_reference = ServiceModele(Path(chemin_candidat).parent / "credit_risk_v1.0.0.joblib")
    service_reference.charger()
    p_reference = service_reference.predire_lot(x)
    ecarts_test = np.abs(p_candidat - p_reference)

    with tempfile.TemporaryDirectory() as tmp:
        copie = Path(tmp) / "copie.joblib"
        joblib.dump(joblib.load(chemin_candidat), copie)
        ecart_rechargement = float(
            np.abs(joblib.load(copie).predict_proba(x)[:, 1] - p_candidat).max()
        )

    return {
        "version_reference": reference["version_reference"],
        "version_candidate": meta["version"],
        "algorithme_candidat": meta["algorithme"],
        "seuils_reference": reference["seuils"],
        "seuils_candidat": meta["seuils"],
        "metriques_reference": reference["metriques"],
        "metriques_candidat": metriques,
        "controle_metriques": controle_metriques.en_dict(),
        "controle_profils_reference": controle_profils.en_dict(),
        "profils": [
            {
                "id": p["id"],
                "description": p["description"],
                "p_reference": p["probabilite_defaut"],
                "p_candidat": r.probabilite_defaut,
                "niveau_reference": p["niveau_risque"],
                "niveau_candidat": r.niveau_risque,
            }
            for p, r in zip(reference["profils"], resultats, strict=True)
        ],
        "ecarts_jeu_de_test": {
            "moyen": float(ecarts_test.mean()),
            "p95": float(np.percentile(ecarts_test, 95)),
            "max": float(ecarts_test.max()),
        },
        "ecart_sauvegarde_rechargement": ecart_rechargement,
        "segments_reference": metriques_par_segment(
            colonnes, y, p_reference, reference["seuils"]["risque_modere"]
        ),
        "segments_candidat": metriques_par_segment(
            colonnes, y, p_candidat, meta["seuils"]["risque_modere"]
        ),
    }


def main() -> None:  # pragma: no cover - script
    chemin = Path(sys.argv[1] if len(sys.argv) > 1 else "model/credit_risk_v1.1.0.joblib")
    resultat = comparer(chemin)
    REPERTOIRE_RAPPORT.mkdir(parents=True, exist_ok=True)
    sortie = REPERTOIRE_RAPPORT / f"comparaison_v{resultat['version_candidate']}.json"
    sortie.write_text(json.dumps(resultat, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")
    print(f"Métriques conformes : {resultat['controle_metriques']['conforme']}")
    print(f"Profils conformes   : {resultat['controle_profils_reference']['conforme']}")
    print(f"Rapport : {sortie}")


if __name__ == "__main__":  # pragma: no cover
    main()
