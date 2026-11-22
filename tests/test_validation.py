"""Tests unitaires du module de validation (schéma d'entrée et cohérence des données).

Techniques : partitions d'équivalence et analyse des valeurs limites (min-1, min, max, max+1).
"""

from __future__ import annotations

import math

import pytest
from pydantic import ValidationError

from app.validation import (
    AGE_MAX,
    AGE_MIN,
    ANCIENNETE_MAX,
    DUREE_MAX,
    DUREE_MIN,
    MONTANT_MAX,
    REVENU_MAX,
    DemandeCredit,
    formater_erreurs,
)


def erreurs(donnees: dict) -> list[dict]:
    try:
        DemandeCredit.model_validate(donnees)
    except ValidationError as exc:
        return exc.errors()
    return []


def types_pour(donnees: dict, champ: str) -> set[str]:
    return {e["type"] for e in erreurs(donnees) if e["loc"] and e["loc"][0] == champ}


def avec(base: dict, **modifs) -> dict:
    return {**base, **modifs}


# --------------------------------------------------------------------------- partitions
@pytest.mark.exigence("EX20")
def test_demande_nominale_acceptee(demande_valide):
    demande = DemandeCredit.model_validate(demande_valide)
    assert demande.age == 35
    assert demande.revenu_mensuel == 250000.0


@pytest.mark.exigence("EX20")
def test_demande_validee_est_immuable(demande_valide):
    demande = DemandeCredit.model_validate(demande_valide)
    with pytest.raises(ValidationError):
        demande.age = 40


@pytest.mark.exigence("EX01")
@pytest.mark.parametrize(
    ("age", "valide"),
    [(-5, False), (0, False), (AGE_MIN - 1, False), (AGE_MIN, True), (AGE_MIN + 1, True),
     (AGE_MAX - 1, True), (AGE_MAX, True), (AGE_MAX + 1, False), (150, False)],
)  # fmt: skip
def test_bornes_age(demande_valide, age, valide):
    assert (erreurs(avec(demande_valide, age=age)) == []) is valide


@pytest.mark.exigence("EX02")
@pytest.mark.parametrize(
    ("revenu", "valide"),
    [(-1, False), (0, False), (0.01, True), (1, True), (250000.5, True),
     (REVENU_MAX, True), (REVENU_MAX + 1, False)],
)  # fmt: skip
def test_bornes_revenu(demande_valide, revenu, valide):
    assert (erreurs(avec(demande_valide, revenu_mensuel=revenu)) == []) is valide


@pytest.mark.exigence("EX08")
@pytest.mark.parametrize(
    ("montant", "valide"),
    [(-1_000_000, False), (-1, False), (0, False), (1, True), (MONTANT_MAX, True),
     (MONTANT_MAX + 1, False)],
)  # fmt: skip
def test_bornes_montant(demande_valide, montant, valide):
    assert (erreurs(avec(demande_valide, montant_credit=montant)) == []) is valide


@pytest.mark.exigence("EX03")
@pytest.mark.parametrize(
    ("duree", "valide"),
    [(0, False), (DUREE_MIN, True), (12, True), (DUREE_MAX, True), (DUREE_MAX + 1, False),
     (-12, False)],
)  # fmt: skip
def test_bornes_duree(demande_valide, duree, valide):
    assert (erreurs(avec(demande_valide, duree_mois=duree)) == []) is valide


@pytest.mark.exigence("EX03")
@pytest.mark.parametrize("duree", [12.5, 12.0, "12", True])
def test_duree_non_entiere_rejetee(demande_valide, duree):
    """Mode strict : aucune conversion implicite, même 12.0 ou "12"."""
    assert types_pour(avec(demande_valide, duree_mois=duree), "duree_mois") == {"int_type"}


@pytest.mark.exigence("EX09")
@pytest.mark.parametrize(
    ("age", "anciennete", "valide"),
    [(35, -0.1, False), (35, 0, True), (35, 21, True), (35, 21.1, False),
     (18, 4, True), (18, 4.5, False), (75, ANCIENNETE_MAX, True), (75, ANCIENNETE_MAX + 1, False)],
)  # fmt: skip
def test_coherence_anciennete_age(demande_valide, age, anciennete, valide):
    assert (erreurs(avec(demande_valide, age=age, anciennete_activite=anciennete)) == []) is valide


@pytest.mark.exigence("EX09")
def test_incoherence_anciennete_a_un_type_dedie(demande_valide):
    types = types_pour(avec(demande_valide, age=30, anciennete_activite=20), "anciennete_activite")
    assert types == {"incoherence_anciennete_age"}


@pytest.mark.exigence("EX09", "EX01")
def test_coherence_non_evaluee_si_age_invalide(demande_valide):
    """Seule l'erreur sur l'âge est signalée : pas d'erreur de cohérence en cascade."""
    liste = erreurs(avec(demande_valide, age=-5, anciennete_activite=10))
    assert [e["loc"][0] for e in liste] == ["age"]


@pytest.mark.exigence("EX06")
@pytest.mark.parametrize("champ", list(DemandeCredit.model_fields))
def test_champ_manquant(demande_valide, champ):
    del demande_valide[champ]
    assert types_pour(demande_valide, champ) == {"missing"}


@pytest.mark.exigence("EX06")
def test_demande_vide_liste_tous_les_champs():
    assert {e["loc"][0] for e in erreurs({})} == set(DemandeCredit.model_fields)


@pytest.mark.exigence("EX10")
def test_champ_supplementaire_refuse(demande_valide):
    assert types_pour(avec(demande_valide, nom="Diallo"), "nom") == {"extra_forbidden"}


# ------------------------------------------------------- types non numériques / non finis
@pytest.mark.exigence("EX11", "EX02")
@pytest.mark.parametrize("valeur", ["250000", "deux cent mille", True, None, [250000], {"v": 1}])
def test_revenu_non_numerique_refuse(demande_valide, valeur):
    assert types_pour(avec(demande_valide, revenu_mensuel=valeur), "revenu_mensuel")


@pytest.mark.exigence("EX11", "EX01")
@pytest.mark.parametrize("valeur", ["35", 35.0, 35.5, True, None])
def test_age_non_entier_refuse(demande_valide, valeur):
    assert types_pour(avec(demande_valide, age=valeur), "age")


@pytest.mark.exigence("EX11")
@pytest.mark.parametrize("champ", ["revenu_mensuel", "montant_credit", "anciennete_activite"])
@pytest.mark.parametrize("valeur", [math.nan, math.inf, -math.inf])
def test_valeurs_non_finies_refusees(demande_valide, champ, valeur):
    assert types_pour(avec(demande_valide, **{champ: valeur}), champ) == {"finite_number"}


@pytest.mark.exigence("EX02")
def test_revenu_entier_accepte_comme_nombre(demande_valide):
    """Un entier JSON est un nombre valide pour un champ décimal (pas de faux rejet)."""
    assert erreurs(avec(demande_valide, revenu_mensuel=250000)) == []


# --------------------------------------------------------------- formatage des erreurs
@pytest.mark.exigence("EX06", "EX13")
def test_formatage_erreurs_en_francais_sans_valeur_saisie(demande_valide):
    donnees = avec(demande_valide, age=-5, revenu_mensuel="secret-123")
    del donnees["duree_mois"]
    try:
        DemandeCredit.model_validate(donnees)
    except ValidationError as exc:
        details = formater_erreurs(exc.errors())
    par_champ = {d["champ"]: d for d in details}
    assert par_champ["age"]["message"] == "Doit être supérieur ou égal à 18."
    assert par_champ["duree_mois"]["message"] == "Champ obligatoire manquant."
    assert par_champ["revenu_mensuel"]["message"] == "Doit être un nombre."
    assert "secret-123" not in str(details)


@pytest.mark.exigence("EX13")
def test_formatage_erreur_inconnue_et_contexte_incomplet():
    details = formater_erreurs(
        [
            {"type": "type_inconnu", "loc": ("body", "x"), "msg": "message brut"},
            {"type": "greater_than", "loc": ("body",), "msg": "repli", "ctx": {}},
        ]
    )
    assert details[0] == {"champ": "x", "type": "type_inconnu", "message": "message brut"}
    assert details[1] == {"champ": "corps", "type": "greater_than", "message": "repli"}
