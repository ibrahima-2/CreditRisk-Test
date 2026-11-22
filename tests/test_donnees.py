"""Reproductibilité et conformité du jeu de données synthétique et de la référence gelée."""

from __future__ import annotations

import numpy as np
import pytest

from app import config
from app.validation import DemandeCredit
from ml import donnees
from ml.evaluation import FICHIER_REFERENCE, charger_json
from ml.reference import construire_reference


@pytest.mark.exigence("EX14")
def test_generation_deterministe():
    a, b = donnees.generer(500, graine=7), donnees.generer(500, graine=7)
    for colonne in a:
        np.testing.assert_array_equal(a[colonne], b[colonne])


@pytest.mark.exigence("EX14")
def test_donnees_versionnees_regenerables(tmp_path):
    """Les CSV versionnés sont exactement ceux produits par la génération documentée."""
    train, test = donnees.separer(donnees.generer())
    for jeu, fichier in ((train, donnees.FICHIER_TRAIN), (test, donnees.FICHIER_TEST)):
        donnees.ecrire_csv(jeu, tmp_path / fichier)
        regenere, y_regenere = donnees.charger_csv(tmp_path / fichier)
        versionne, y_versionne = donnees.charger_csv(donnees.REPERTOIRE_DONNEES / fichier)
        np.testing.assert_array_equal(y_regenere, y_versionne)
        for colonne in donnees.COLONNES_ENTREE:
            np.testing.assert_allclose(regenere[colonne], versionne[colonne], rtol=1e-12)


@pytest.mark.exigence("EX14")
def test_separation_stratifiee():
    train, test = donnees.separer(donnees.generer())
    assert len(test[donnees.CIBLE]) == pytest.approx(0.25 * donnees.N_OBSERVATIONS, abs=1)
    assert test[donnees.CIBLE].mean() == pytest.approx(train[donnees.CIBLE].mean(), abs=0.005)


@pytest.mark.exigence("EX20", "EX09")
def test_toutes_les_lignes_respectent_le_contrat_d_entree():
    colonnes, y = donnees.charger_csv(donnees.REPERTOIRE_DONNEES / donnees.FICHIER_TRAIN)
    for i in range(len(y)):
        ligne = {c: colonnes[c][i].item() for c in donnees.COLONNES_ENTREE}
        ligne["age"], ligne["duree_mois"] = int(ligne["age"]), int(ligne["duree_mois"])
        DemandeCredit.model_validate(ligne)
    assert set(np.unique(y)) == {0, 1}


@pytest.mark.exigence("EX14", "EX07")
def test_reference_regenerable_a_l_identique():
    """Recalculer la référence à partir de l'artefact v1.0.0 redonne les valeurs gelées."""
    gelee = charger_json(FICHIER_REFERENCE)
    recalculee = construire_reference(config.REPERTOIRE_MODELES / config.NOM_MODELE_DEFAUT)
    assert recalculee["sha256_modele"] == gelee["sha256_modele"]
    assert recalculee["seuils"] == gelee["seuils"]
    for a, b in zip(recalculee["profils"], gelee["profils"], strict=True):
        assert a["entree"] == b["entree"]
        assert a["probabilite_defaut"] == pytest.approx(b["probabilite_defaut"], abs=1e-12)
        assert a["niveau_risque"] == b["niveau_risque"]
