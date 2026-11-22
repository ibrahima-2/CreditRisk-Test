"""Tests unitaires du module de prétraitement (variables dérivées et contrat de dimension)."""

from __future__ import annotations

import math

import numpy as np
import pytest

from app.preprocessing import (
    VARIABLES_ENTREE,
    VARIABLES_MODELE,
    ErreurPretraitement,
    indicateurs,
    transformer,
    transformer_lot,
)
from ml import donnees


@pytest.mark.exigence("EX22")
def test_transformation_valeurs_attendues(demande_valide):
    """Calcul manuel : taux = 1 000 000 / (12 x 250 000) = 1/3 ; log(250 000) ≈ 12,4292."""
    matrice = transformer(demande_valide)
    attendu = np.array([[35.0, math.log(250000), 12.0, 4.0, 1.0 / 3.0]])
    assert matrice.shape == (1, len(VARIABLES_MODELE))
    assert matrice.dtype == np.float64
    np.testing.assert_allclose(matrice, attendu, rtol=0, atol=1e-12)


@pytest.mark.exigence("EX22")
@pytest.mark.parametrize(
    ("montant", "duree", "revenu", "taux_attendu"),
    [(1_200_000, 24, 100_000, 0.5), (300_000, 6, 200_000, 0.25), (90_000, 1, 300_000, 0.3)],
)
def test_taux_endettement_pour_des_durees_differentes_de_12(montant, duree, revenu, taux_attendu):
    """Ajouté après l'essai de mutation M2 : avec une durée de 12 mois, une formule erronée
    (montant / (12 x revenu)) donnait le même résultat que la formule correcte."""
    demande = {"age": 40, "revenu_mensuel": revenu, "montant_credit": montant,
               "duree_mois": duree, "anciennete_activite": 5}  # fmt: skip
    taux = transformer(demande)[0, VARIABLES_MODELE.index("taux_endettement")]
    assert taux == pytest.approx(taux_attendu, abs=1e-12)


@pytest.mark.exigence("EX22")
def test_ordre_des_variables_fait_partie_du_contrat():
    assert VARIABLES_MODELE == (
        "age",
        "log_revenu_mensuel",
        "duree_mois",
        "anciennete_activite",
        "taux_endettement",
    )


@pytest.mark.exigence("EX22", "EX14")
def test_meme_transformation_entrainement_et_production():
    """La transformation par lot (entraînement) et unitaire (API) donnent le même résultat."""
    colonnes, _ = donnees.charger_csv(donnees.REPERTOIRE_DONNEES / donnees.FICHIER_TEST)
    lot = transformer_lot(colonnes)
    for i in range(0, len(lot), 97):
        ligne = transformer({c: colonnes[c][i] for c in VARIABLES_ENTREE})
        np.testing.assert_array_equal(ligne[0], lot[i])


@pytest.mark.exigence("EX06", "EX22")
def test_variable_absente(demande_valide):
    del demande_valide["anciennete_activite"]
    with pytest.raises(ErreurPretraitement, match="anciennete_activite"):
        transformer(demande_valide)


@pytest.mark.exigence("EX11", "EX22")
@pytest.mark.parametrize("valeur", ["abc", None, math.nan, math.inf])
def test_valeur_non_numerique_ou_non_finie(demande_valide, valeur):
    demande_valide["revenu_mensuel"] = valeur
    with pytest.raises(ErreurPretraitement):
        transformer(demande_valide)


@pytest.mark.exigence("EX02", "EX03", "EX08")
@pytest.mark.parametrize("champ", ["revenu_mensuel", "montant_credit", "duree_mois"])
@pytest.mark.parametrize("valeur", [0, -1])
def test_defense_en_profondeur_valeurs_non_positives(demande_valide, champ, valeur):
    """Même si la validation était contournée, aucune division par zéro ni log négatif."""
    demande_valide[champ] = valeur
    with pytest.raises(ErreurPretraitement, match=champ):
        transformer(demande_valide)


@pytest.mark.exigence("EX11", "EX22")
def test_depassement_numerique_detecte():
    with pytest.raises(ErreurPretraitement, match="non finies"):
        transformer(
            {
                "age": 35,
                "revenu_mensuel": 1e-308,
                "montant_credit": 1e308,
                "duree_mois": 1,
                "anciennete_activite": 4,
            }
        )


@pytest.mark.exigence("EX22")
def test_colonnes_de_longueurs_differentes():
    colonnes = {c: [1.0, 2.0] for c in VARIABLES_ENTREE}
    colonnes["age"] = [30.0]
    with pytest.raises(ErreurPretraitement, match="même nombre"):
        transformer_lot(colonnes)


@pytest.mark.exigence("EX20")
def test_indicateurs_pour_l_agent(demande_valide):
    assert indicateurs(demande_valide) == {
        "mensualite_estimee": 83333.33,
        "taux_endettement": pytest.approx(1 / 3),
    }
