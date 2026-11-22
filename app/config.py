"""Paramètres centralisés du service de prédiction."""

from __future__ import annotations

import os
from pathlib import Path

VERSION_API = "1.0.0"

RACINE_PROJET = Path(__file__).resolve().parent.parent
REPERTOIRE_MODELES = RACINE_PROJET / "model"
NOM_MODELE_DEFAUT = "credit_risk_v1.0.0.joblib"

# Permet de déployer une autre version du modèle sans modifier le code.
VARIABLE_ENV_MODELE = "CREDIT_MODEL_PATH"

# Une demande valide fait environ 150 octets : au-delà de 16 Kio, la requête est refusée.
TAILLE_MAX_REQUETE_OCTETS = 16_384


def chemin_modele() -> Path:
    """Chemin de l'artefact du modèle (surchargeable par variable d'environnement)."""
    return Path(os.environ.get(VARIABLE_ENV_MODELE, REPERTOIRE_MODELES / NOM_MODELE_DEFAUT))


def chemin_metadonnees(chemin_du_modele: Path) -> Path:
    """Les métadonnées sont stockées à côté de l'artefact : ``x.joblib`` -> ``x.json``."""
    return Path(chemin_du_modele).with_suffix(".json")
