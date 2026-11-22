"""Module de prédiction : chargement contrôlé du modèle et orchestration du pipeline.

Pipeline d'une demande : données validées -> prétraitement -> modèle -> interprétation
(niveau de risque, alertes hors domaine, besoin de revue humaine).
"""

from __future__ import annotations

import hashlib
import json
import logging
import threading
from collections.abc import Mapping
from dataclasses import dataclass, field
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

import joblib
import numpy as np

from app import config, preprocessing

journal = logging.getLogger("creditrisk.prediction")

FAIBLE, MODERE, ELEVE = "FAIBLE", "MODERE", "ELEVE"

CLES_METADONNEES_OBLIGATOIRES = (
    "nom",
    "version",
    "variables_modele",
    "seuils",
    "domaine_entrainement",
    "sha256",
)


class ErreurChargementModele(Exception):
    """L'artefact du modèle ne peut pas être chargé ou n'est pas conforme."""


class ModeleIndisponibleError(Exception):
    """Aucun modèle valide n'est chargé : le service ne peut pas prédire."""


class ErreurPrediction(Exception):
    """Le modèle a échoué ou a produit une sortie non conforme au contrat."""


@dataclass(frozen=True)
class ResultatEvaluation:
    probabilite_defaut: float
    niveau_risque: str
    revue_humaine_requise: bool
    alertes: list[str] = field(default_factory=list)
    indicateurs: dict[str, float] = field(default_factory=dict)


def sha256_fichier(chemin: Path) -> str:
    empreinte = hashlib.sha256()
    with Path(chemin).open("rb") as fichier:
        for bloc in iter(lambda: fichier.read(65_536), b""):
            empreinte.update(bloc)
    return empreinte.hexdigest()


def classer_risque(probabilite: float, seuils: Mapping[str, float]) -> str:
    if probabilite >= seuils["risque_eleve"]:
        return ELEVE
    if probabilite >= seuils["risque_modere"]:
        return MODERE
    return FAIBLE


def detecter_alertes(
    valeurs: Mapping[str, float], domaine: Mapping[str, Mapping[str, float]]
) -> list[str]:
    """Signale les variables situées hors de l'intervalle observé à l'entraînement."""
    alertes = []
    for variable, bornes in domaine.items():
        valeur = valeurs.get(variable)
        if valeur is not None and not bornes["min"] <= valeur <= bornes["max"]:
            alertes.append(f"HORS_DOMAINE_{variable.upper()}")
    return alertes


def verifier_compatibilite(modele: Any, metadonnees: Mapping[str, Any]) -> None:
    """Refuse un modèle incompatible avec le contrat du pipeline (fail fast au chargement)."""
    manquantes = [c for c in CLES_METADONNEES_OBLIGATOIRES if c not in metadonnees]
    if manquantes:
        raise ErreurChargementModele(f"Métadonnées incomplètes : {', '.join(manquantes)}")
    if not callable(getattr(modele, "predict_proba", None)):
        raise ErreurChargementModele("L'objet chargé ne fournit pas de méthode predict_proba")
    attendu = len(preprocessing.VARIABLES_MODELE)
    n_variables = getattr(modele, "n_features_in_", None)
    if n_variables != attendu:
        raise ErreurChargementModele(
            f"Dimensions incompatibles : le modèle attend {n_variables} variables, "
            f"le prétraitement en produit {attendu}"
        )
    if list(metadonnees["variables_modele"]) != list(preprocessing.VARIABLES_MODELE):
        raise ErreurChargementModele("Ordre ou nom des variables différent du prétraitement")
    seuils = metadonnees["seuils"]
    if not 0 < seuils.get("risque_modere", -1) < seuils.get("risque_eleve", -1) < 1:
        raise ErreurChargementModele("Seuils de risque invalides")


class ServiceModele:
    """Encapsule l'artefact du modèle, ses métadonnées et le contrat de sortie."""

    def __init__(self, chemin_modele: Path, chemin_metadonnees: Path | None = None) -> None:
        self.chemin_modele = Path(chemin_modele)
        self.chemin_metadonnees = Path(
            chemin_metadonnees or config.chemin_metadonnees(self.chemin_modele)
        )
        self._modele: Any = None
        self._metadonnees: dict[str, Any] | None = None
        self._verrou = threading.Lock()
        self.derniere_erreur: str | None = None
        self.charge_le: datetime | None = None

    @classmethod
    def depuis_config(cls) -> ServiceModele:
        return cls(config.chemin_modele())

    @classmethod
    def depuis_objets(cls, modele: Any, metadonnees: Mapping[str, Any]) -> ServiceModele:
        """Construit un service à partir d'objets en mémoire (tests, injection)."""
        service = cls(Path("<memoire>"))
        service._installer(modele, dict(metadonnees))
        return service

    @property
    def est_charge(self) -> bool:
        return self._modele is not None

    @property
    def metadonnees(self) -> dict[str, Any]:
        self.assurer_charge()
        return dict(self._metadonnees or {})

    def charger(self) -> None:
        """Charge l'artefact après vérification de son intégrité (SHA-256) et du contrat."""
        with self._verrou:
            try:
                metadonnees = json.loads(self.chemin_metadonnees.read_text(encoding="utf-8"))
                if sha256_fichier(self.chemin_modele) != metadonnees.get("sha256"):
                    raise ErreurChargementModele(
                        "Empreinte SHA-256 de l'artefact différente de celle des métadonnées"
                    )
                modele = joblib.load(self.chemin_modele)
                self._installer(modele, metadonnees)
            except ErreurChargementModele as exc:
                self._echec(str(exc))
                raise
            except Exception as exc:  # fichier absent, JSON invalide, pickle corrompu...
                self._echec(f"{type(exc).__name__} lors du chargement de l'artefact")
                raise ErreurChargementModele(self.derniere_erreur) from exc
        journal.info(
            "Modèle %s v%s chargé",
            self._metadonnees["nom"],
            self._metadonnees["version"],
        )

    def _echec(self, raison: str) -> None:
        self._modele, self._metadonnees = None, None
        self.derniere_erreur = raison
        journal.error("Chargement du modèle impossible : %s", raison)

    def _installer(self, modele: Any, metadonnees: dict[str, Any]) -> None:
        verifier_compatibilite(modele, metadonnees)
        self._modele, self._metadonnees = modele, metadonnees
        self.derniere_erreur = None
        self.charge_le = datetime.now(UTC)

    def assurer_charge(self) -> None:
        """Charge le modèle à la demande ; lève ``ModeleIndisponibleError`` en cas d'échec."""
        if self.est_charge:
            return
        try:
            self.charger()
        except ErreurChargementModele as exc:
            raise ModeleIndisponibleError(str(exc)) from exc

    def predire_lot(self, matrice: np.ndarray) -> np.ndarray:
        """Probabilités de défaut pour une matrice (n, 5), avec contrôle du contrat de sortie."""
        self.assurer_charge()
        modele = self._modele
        matrice = np.asarray(matrice, dtype=np.float64)
        attendu = len(preprocessing.VARIABLES_MODELE)
        if matrice.ndim != 2 or matrice.shape[1] != attendu or matrice.shape[0] == 0:
            raise ErreurPrediction(
                f"Dimensions des données {matrice.shape} incompatibles avec le modèle "
                f"(attendu : (n, {attendu}))"
            )
        try:
            probabilites = np.asarray(modele.predict_proba(matrice), dtype=np.float64)
        except Exception as exc:
            raise ErreurPrediction(f"Échec du modèle : {type(exc).__name__}") from exc
        if (
            probabilites.shape != (matrice.shape[0], 2)
            or not np.all(np.isfinite(probabilites))
            or np.any(probabilites < 0)
            or np.any(probabilites > 1)
            or not np.allclose(probabilites.sum(axis=1), 1.0, atol=1e-6)
        ):
            raise ErreurPrediction("Sortie du modèle non conforme au contrat de probabilité")
        return probabilites[:, 1]

    def predire_probabilite(self, matrice: np.ndarray) -> float:
        """Probabilité pour UNE demande : une matrice de plusieurs lignes est refusée
        (correction de l'anomalie AN-01 : la première ligne était renvoyée silencieusement)."""
        if np.ndim(matrice) != 2 or np.shape(matrice)[0] != 1:
            raise ErreurPrediction(
                f"Une demande unique doit produire une matrice (1, n), reçu {np.shape(matrice)}"
            )
        return float(self.predire_lot(matrice)[0])

    def evaluer(self, donnees: Mapping[str, float]) -> ResultatEvaluation:
        """Exécute le pipeline complet pour une demande déjà validée."""
        self.assurer_charge()
        metadonnees = self._metadonnees
        matrice = preprocessing.transformer(donnees)
        probabilite = self.predire_probabilite(matrice)
        indicateurs = preprocessing.indicateurs(donnees)
        niveau = classer_risque(probabilite, metadonnees["seuils"])
        alertes = detecter_alertes({**donnees, **indicateurs}, metadonnees["domaine_entrainement"])
        return ResultatEvaluation(
            probabilite_defaut=probabilite,
            niveau_risque=niveau,
            revue_humaine_requise=niveau != FAIBLE or bool(alertes),
            alertes=alertes,
            indicateurs=indicateurs,
        )
