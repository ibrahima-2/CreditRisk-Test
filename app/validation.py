"""Module de validation : format et cohérence des données d'un demandeur.

Le schéma est volontairement strict :
- aucun champ supplémentaire n'est accepté (``extra="forbid"``) ;
- aucune conversion implicite (``strict=True``) : ``"250000"`` (texte), ``true`` (booléen)
  ou ``12.5`` pour un entier sont rejetés au lieu d'être convertis silencieusement ;
- les valeurs non finies (NaN, ±Infinity) sont refusées (``allow_inf_nan=False``).
"""

from __future__ import annotations

from typing import Any

from pydantic import BaseModel, ConfigDict, Field, ValidationInfo, field_validator
from pydantic_core import PydanticCustomError

# Limites « dures » : au-delà, la saisie est considérée comme invalide et rejetée.
AGE_MIN, AGE_MAX = 18, 75
REVENU_MAX = 50_000_000  # FCFA par mois
MONTANT_MAX = 500_000_000  # FCFA
DUREE_MIN, DUREE_MAX = 1, 120  # mois
ANCIENNETE_MAX = 60  # années
AGE_MIN_DEBUT_ACTIVITE = 14  # ancienneté maximale = âge - 14 ans

EXEMPLE_DEMANDE: dict[str, Any] = {
    "age": 35,
    "revenu_mensuel": 250000,
    "montant_credit": 1000000,
    "duree_mois": 12,
    "anciennete_activite": 4,
}


class DemandeCredit(BaseModel):
    """Données d'entrée d'une demande de crédit."""

    model_config = ConfigDict(
        extra="forbid",
        strict=True,
        allow_inf_nan=False,
        frozen=True,
        json_schema_extra={"examples": [EXEMPLE_DEMANDE]},
    )

    age: int = Field(ge=AGE_MIN, le=AGE_MAX, description="Âge du demandeur (années)")
    revenu_mensuel: float = Field(gt=0, le=REVENU_MAX, description="Revenu mensuel (FCFA)")
    montant_credit: float = Field(gt=0, le=MONTANT_MAX, description="Montant demandé (FCFA)")
    duree_mois: int = Field(ge=DUREE_MIN, le=DUREE_MAX, description="Durée du crédit (mois)")
    anciennete_activite: float = Field(
        ge=0, le=ANCIENNETE_MAX, description="Ancienneté de l'activité (années)"
    )

    @field_validator("anciennete_activite")
    @classmethod
    def verifier_coherence_avec_age(cls, valeur: float, info: ValidationInfo) -> float:
        age = info.data.get("age")  # absent si l'âge est lui-même invalide
        if age is not None and valeur > age - AGE_MIN_DEBUT_ACTIVITE:
            raise PydanticCustomError(
                "incoherence_anciennete_age",
                "L'ancienneté d'activité ({anciennete} ans) est incompatible avec l'âge "
                "({age} ans) : elle ne peut dépasser l'âge moins {ecart} ans.",
                {"anciennete": valeur, "age": age, "ecart": AGE_MIN_DEBUT_ACTIVITE},
            )
        return valeur


# Messages en français pour les types d'erreurs les plus fréquents.
_MESSAGES: dict[str, str] = {
    "missing": "Champ obligatoire manquant.",
    "extra_forbidden": "Champ non autorisé.",
    "int_type": "Doit être un nombre entier.",
    "float_type": "Doit être un nombre.",
    "finite_number": "Doit être un nombre fini (NaN et infini refusés).",
    "greater_than": "Doit être strictement supérieur à {gt}.",
    "greater_than_equal": "Doit être supérieur ou égal à {ge}.",
    "less_than": "Doit être strictement inférieur à {lt}.",
    "less_than_equal": "Doit être inférieur ou égal à {le}.",
    "model_attributes_type": "Le corps de la requête doit être un objet JSON.",
    "dict_type": "Le corps de la requête doit être un objet JSON.",
    "model_type": "Le corps de la requête doit être un objet JSON.",
}


def formater_erreurs(erreurs: list[dict[str, Any]]) -> list[dict[str, str]]:
    """Convertit les erreurs Pydantic en détails lisibles, sans renvoyer la valeur saisie."""
    details = []
    for erreur in erreurs:
        localisation = [str(p) for p in erreur.get("loc", ()) if p != "body"]
        modele = _MESSAGES.get(erreur.get("type", ""))
        try:
            message = modele.format(**erreur.get("ctx", {})) if modele else erreur["msg"]
        except (KeyError, IndexError):
            message = erreur.get("msg", "Valeur invalide.")
        details.append(
            {
                "champ": ".".join(localisation) or "corps",
                "type": erreur.get("type", "inconnu"),
                "message": message,
            }
        )
    return details
