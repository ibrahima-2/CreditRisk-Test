"""Gel de la version de référence : métriques, empreinte et profils de référence (golden set).

Usage : ``python -m ml.reference`` (à n'exécuter qu'une fois par version de référence).
"""

from __future__ import annotations

import json
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

from app import config
from app.prediction import ServiceModele
from ml import donnees
from ml.evaluation import FICHIER_REFERENCE

N_PROFILS_TEST = 18

PROFILS_TYPES: list[dict[str, Any]] = [
    {"id": "G01", "description": "Profil nominal (exemple de l'énoncé)",
     "entree": {"age": 35, "revenu_mensuel": 250000, "montant_credit": 1000000, "duree_mois": 12, "anciennete_activite": 4}},
    {"id": "G02", "description": "Profil a priori peu risqué",
     "entree": {"age": 50, "revenu_mensuel": 800000, "montant_credit": 1000000, "duree_mois": 12, "anciennete_activite": 20}},
    {"id": "G03", "description": "Jeune, faible revenu, endettement très élevé",
     "entree": {"age": 22, "revenu_mensuel": 60000, "montant_credit": 1500000, "duree_mois": 12, "anciennete_activite": 1}},
    {"id": "G04", "description": "Borne basse : 18 ans, ancienneté nulle",
     "entree": {"age": 18, "revenu_mensuel": 100000, "montant_credit": 300000, "duree_mois": 6, "anciennete_activite": 0}},
    {"id": "G05", "description": "Borne haute : 75 ans, ancienneté 60 ans (hors domaine)",
     "entree": {"age": 75, "revenu_mensuel": 300000, "montant_credit": 1000000, "duree_mois": 24, "anciennete_activite": 60}},
    {"id": "G06", "description": "Durée minimale (1 mois)",
     "entree": {"age": 40, "revenu_mensuel": 200000, "montant_credit": 100000, "duree_mois": 1, "anciennete_activite": 5}},
    {"id": "G07", "description": "Durée maximale (120 mois, hors domaine)",
     "entree": {"age": 40, "revenu_mensuel": 500000, "montant_credit": 10000000, "duree_mois": 120, "anciennete_activite": 10}},
    {"id": "G08", "description": "Revenu très élevé mais valide (hors domaine)",
     "entree": {"age": 45, "revenu_mensuel": 20000000, "montant_credit": 5000000, "duree_mois": 12, "anciennete_activite": 15}},
    {"id": "G09", "description": "Montant très élevé mais valide (hors domaine)",
     "entree": {"age": 45, "revenu_mensuel": 2000000, "montant_credit": 400000000, "duree_mois": 60, "anciennete_activite": 15}},
    {"id": "G10", "description": "Revenu très faible (hors domaine)",
     "entree": {"age": 30, "revenu_mensuel": 1000, "montant_credit": 50000, "duree_mois": 12, "anciennete_activite": 3}},
    {"id": "G11", "description": "Mensualité égale au revenu (endettement 100 %)",
     "entree": {"age": 30, "revenu_mensuel": 100000, "montant_credit": 1200000, "duree_mois": 12, "anciennete_activite": 3}},
    {"id": "G12", "description": "Artisan expérimenté, demande modérée",
     "entree": {"age": 42, "revenu_mensuel": 150000, "montant_credit": 600000, "duree_mois": 18, "anciennete_activite": 8}},
]  # fmt: skip


def profils_reference() -> list[dict[str, Any]]:
    """Profils types + premières lignes du jeu de test versionné."""
    colonnes, _ = donnees.charger_csv(donnees.REPERTOIRE_DONNEES / donnees.FICHIER_TEST)
    profils = list(PROFILS_TYPES)
    for i in range(N_PROFILS_TEST):
        entree = {c: colonnes[c][i].item() for c in donnees.COLONNES_ENTREE}
        entree["age"], entree["duree_mois"] = int(entree["age"]), int(entree["duree_mois"])
        profils.append({"id": f"T{i + 1:02d}", "description": f"Ligne {i + 1} du jeu de test",
                        "entree": entree})  # fmt: skip
    return profils


def construire_reference(chemin_modele: Path) -> dict[str, Any]:
    service = ServiceModele(chemin_modele)
    service.charger()
    metadonnees = service.metadonnees
    profils = []
    for profil in profils_reference():
        resultat = service.evaluer(profil["entree"])
        profils.append(
            {
                **profil,
                "probabilite_defaut": resultat.probabilite_defaut,
                "niveau_risque": resultat.niveau_risque,
                "alertes": resultat.alertes,
            }
        )
    return {
        "version_reference": metadonnees["version"],
        "sha256_modele": metadonnees["sha256"],
        "date_gel": datetime.now(UTC).isoformat(timespec="seconds"),
        "seuils": metadonnees["seuils"],
        "metriques": metadonnees["metriques_test"],
        "profils": profils,
    }


def main() -> None:  # pragma: no cover - script
    reference = construire_reference(config.REPERTOIRE_MODELES / config.NOM_MODELE_DEFAUT)
    Path(FICHIER_REFERENCE).write_text(
        json.dumps(reference, indent=2, ensure_ascii=False) + "\n", encoding="utf-8"
    )
    print(
        f"Référence v{reference['version_reference']} gelée : {len(reference['profils'])} profils"
    )


if __name__ == "__main__":  # pragma: no cover
    main()
