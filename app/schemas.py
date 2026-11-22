"""Schémas des réponses de l'API (contrat de sortie documenté dans OpenAPI)."""

from __future__ import annotations

from typing import Any, Literal

from pydantic import BaseModel, Field

AVERTISSEMENT = (
    "Estimation statistique d'aide à la décision : elle ne constitue pas une décision "
    "de crédit et doit être interprétée par un agent habilité."
)


class Seuils(BaseModel):
    risque_modere: float
    risque_eleve: float


class Indicateurs(BaseModel):
    mensualite_estimee: float = Field(description="Montant / durée, hors intérêts (FCFA)")
    taux_endettement: float = Field(description="Mensualité estimée / revenu mensuel")


class ReponsePrediction(BaseModel):
    probabilite_defaut: float = Field(ge=0.0, le=1.0, allow_inf_nan=False)
    niveau_risque: Literal["FAIBLE", "MODERE", "ELEVE"]
    revue_humaine_requise: bool
    alertes: list[str]
    indicateurs: Indicateurs
    seuils: Seuils
    version_modele: str
    identifiant_requete: str
    avertissement: str = AVERTISSEMENT


class DetailErreur(BaseModel):
    champ: str
    type: str
    message: str


class ReponseErreur(BaseModel):
    code: str
    message: str
    details: list[DetailErreur] = []
    identifiant_requete: str | None = None


class ReponseSante(BaseModel):
    statut: Literal["ok", "degrade"]
    modele_charge: bool
    version_modele: str | None
    version_api: str


class InfoModele(BaseModel):
    nom: str
    version: str
    algorithme: str
    date_entrainement: str
    variables_entree: list[str]
    variables_modele: list[str]
    seuils: Seuils
    domaine_entrainement: dict[str, dict[str, float]]
    metriques_test: dict[str, Any]
    jeu_donnees: dict[str, Any]
    sha256: str
    versions_logicielles: dict[str, str]
    version_api: str
