"""Tests de non-régression du logiciel et du modèle.

Référence : version 1.0.0 gelée dans ``model/reference/reference_v1.0.0.json`` (métriques,
empreinte de l'artefact, 30 profils de référence avec leurs sorties attendues).
Tolérances : ``model/reference/tolerances_non_regression.json``, versionnées AVANT toute
comparaison.

Deux situations sont distinguées automatiquement :
- même artefact que la référence (modification du code) : les sorties doivent être
  identiques à 1e-6 près ;
- artefact différent (nouvelle version du modèle, ex. ``CREDIT_MODEL_PATH``) : les écarts
  de probabilité et les métriques doivent rester dans les tolérances « nouveau modèle ».
"""

from __future__ import annotations

import json

import joblib
import numpy as np
import pytest
from sklearn.linear_model import LogisticRegression

from app import config, preprocessing
from app.prediction import ServiceModele, classer_risque, sha256_fichier
from ml import donnees
from ml.comparaison import comparer
from ml.entrainement import entrainer
from ml.evaluation import (
    FICHIER_REFERENCE,
    FICHIER_TOLERANCES,
    calculer_metriques,
    charger_json,
    comparer_metriques,
    comparer_predictions,
    metriques_par_segment,
)


@pytest.fixture(scope="module")
def reference() -> dict:
    return charger_json(FICHIER_REFERENCE)


@pytest.fixture(scope="module")
def tolerances() -> dict:
    return charger_json(FICHIER_TOLERANCES)


@pytest.fixture(scope="module")
def jeu_test():
    colonnes, y = donnees.charger_csv(donnees.REPERTOIRE_DONNEES / donnees.FICHIER_TEST)
    return colonnes, preprocessing.transformer_lot(colonnes), y


@pytest.fixture(scope="module")
def metriques_courantes(service_modele, jeu_test) -> dict:
    _, x, y = jeu_test
    seuil = service_modele.metadonnees["seuils"]["risque_modere"]
    return calculer_metriques(y, service_modele.predire_lot(x), seuil)


def meme_artefact(service_modele, reference) -> bool:
    return service_modele.metadonnees["sha256"] == reference["sha256_modele"]


# ========================================================= sorties du pipeline (golden set)
@pytest.mark.exigence("EX20", "EX07")
def test_contrat_de_sortie_sur_les_profils_de_reference(client, reference, metadonnees):
    for profil in reference["profils"]:
        reponse = client.post("/predict", json=profil["entree"])
        assert reponse.status_code == 200, profil["id"]
        r = reponse.json()
        assert 0.0 <= r["probabilite_defaut"] <= 1.0, profil["id"]
        assert r["niveau_risque"] == classer_risque(r["probabilite_defaut"], metadonnees["seuils"])
        assert r["revue_humaine_requise"] is (r["niveau_risque"] != "FAIBLE" or bool(r["alertes"]))
        assert r["version_modele"] == metadonnees["version"]


@pytest.mark.exigence("EX07", "EX14")
def test_profils_de_reference_dans_les_tolerances(service_modele, reference, tolerances):
    resultats = [service_modele.evaluer(p["entree"]) for p in reference["profils"]]
    p_ref = np.array([p["probabilite_defaut"] for p in reference["profils"]])
    p_cour = np.array([r.probabilite_defaut for r in resultats])

    if meme_artefact(service_modele, reference):
        tolerance = tolerances["predictions"]["meme_modele_tolerance_absolue"]
        ecarts = np.abs(p_cour - p_ref)
        fautifs = [
            p["id"] for p, e in zip(reference["profils"], ecarts, strict=True) if e > tolerance
        ]
        assert not fautifs, f"Écart max {ecarts.max():.2e} > {tolerance} sur {fautifs}"
        for profil, resultat in zip(reference["profils"], resultats, strict=True):
            assert resultat.niveau_risque == profil["niveau_risque"], profil["id"]
            assert resultat.alertes == profil["alertes"], profil["id"]
    else:
        rapport = comparer_predictions(
            p_ref,
            p_cour,
            [p["niveau_risque"] for p in reference["profils"]],
            [r.niveau_risque for r in resultats],
            tolerances,
        )
        assert rapport.conforme, f"Écarts hors tolérance : {rapport.non_conformites}"


@pytest.mark.exigence("EX17", "EX07")
def test_artefact_de_reference_inchange(service_modele, reference):
    if not meme_artefact(service_modele, reference):
        pytest.skip("Version candidate déployée : comparaison par tolérances « nouveau modèle »")
    assert sha256_fichier(config.chemin_modele()) == reference["sha256_modele"]


# ================================================================= métriques vs référence
@pytest.mark.exigence("EX07")
def test_metriques_dans_les_tolerances(metriques_courantes, reference, tolerances):
    rapport = comparer_metriques(reference["metriques"], metriques_courantes, tolerances)
    detail = {c.critere: (round(c.candidat, 4), round(c.limite, 4)) for c in rapport.controles
              if not c.conforme}  # fmt: skip
    assert rapport.conforme, f"Régression détectée (valeur, limite) : {detail}"


@pytest.mark.exigence("EX16", "EX14")
def test_metriques_recalculees_egales_aux_metadonnees(metriques_courantes, metadonnees):
    """Les métriques publiées par /model-info correspondent bien à l'artefact chargé."""
    publiees = metadonnees["metriques_test"]
    for cle in ("roc_auc", "rappel", "precision", "f1", "brier"):
        assert metriques_courantes[cle] == pytest.approx(publiees[cle], abs=1e-9), cle
    assert metriques_courantes["matrice_confusion"] == publiees["matrice_confusion"]


@pytest.mark.exigence("EX07")
@pytest.mark.parametrize(
    ("metrique", "variation", "critere_attendu"),
    [("rappel", -0.10, "rappel_baisse"), ("f1", -0.05, "f1_baisse"),
     ("roc_auc", -0.03, "roc_auc_baisse"), ("brier", +0.02, "brier_hausse")],
)  # fmt: skip
def test_le_controle_detecte_une_degradation(reference, tolerances, metrique, variation,
                                             critere_attendu):  # fmt: skip
    """Test du test : une dégradation au-delà de la tolérance doit être signalée."""
    candidat = {**reference["metriques"]}
    candidat[metrique] = candidat[metrique] + variation
    rapport = comparer_metriques(reference["metriques"], candidat, tolerances)
    assert not rapport.conforme
    assert critere_attendu in rapport.non_conformites


@pytest.mark.exigence("EX07")
def test_variation_dans_la_tolerance_acceptee(reference, tolerances):
    candidat = {**reference["metriques"]}
    candidat["rappel"] -= 0.02  # < 0,03 toléré
    candidat["f1"] += 0.01
    assert comparer_metriques(reference["metriques"], candidat, tolerances).conforme


@pytest.mark.exigence("EX07")
def test_modele_degrade_reel_est_rejete(reference, tolerances, jeu_test):
    """Modèle réellement dégradé (entraîné sur des étiquettes permutées) : rejet attendu."""
    colonnes_train, y_train = donnees.charger_csv(
        donnees.REPERTOIRE_DONNEES / donnees.FICHIER_TRAIN
    )
    x_train = preprocessing.transformer_lot(colonnes_train)
    y_permute = np.random.default_rng(0).permutation(y_train)
    modele = LogisticRegression(max_iter=1000).fit(x_train, y_permute)
    _, x, y = jeu_test
    seuil = reference["seuils"]["risque_modere"]
    metriques = calculer_metriques(y, modele.predict_proba(x)[:, 1], seuil)
    rapport = comparer_metriques(reference["metriques"], metriques, tolerances)
    assert not rapport.conforme
    assert "roc_auc_baisse" in rapport.non_conformites


@pytest.mark.exigence("EX07")
def test_comparaison_de_predictions_detecte_un_ecart(reference, tolerances):
    p_ref = np.array([p["probabilite_defaut"] for p in reference["profils"]])
    niveaux = [p["niveau_risque"] for p in reference["profils"]]
    decale = np.clip(p_ref + 0.3, 0, 1)
    rapport = comparer_predictions(p_ref, decale, niveaux, ["ELEVE"] * len(niveaux), tolerances)
    assert set(rapport.non_conformites) >= {"ecart_moyen_probabilite", "ecart_max_probabilite"}


# ============================================================ sauvegarde et rechargement
@pytest.mark.exigence("EX14", "EX17")
def test_coherence_apres_sauvegarde_et_rechargement(service_modele, jeu_test, tolerances,
                                                    metadonnees, tmp_path):  # fmt: skip
    _, x, _ = jeu_test
    modele = joblib.load(config.chemin_modele())
    chemin = tmp_path / "copie.joblib"
    joblib.dump(modele, chemin)
    recharge = joblib.load(chemin)

    ecart = np.abs(recharge.predict_proba(x)[:, 1] - service_modele.predire_lot(x)).max()
    assert ecart <= tolerances["predictions"]["sauvegarde_rechargement_tolerance_absolue"]

    # Rechargement par le service complet (contrôle d'empreinte compris)
    meta = {**metadonnees, "sha256": sha256_fichier(chemin)}
    chemin.with_suffix(".json").write_text(json.dumps(meta), encoding="utf-8")
    service = ServiceModele(chemin)
    service.charger()
    np.testing.assert_array_equal(service.predire_lot(x), service_modele.predire_lot(x))


@pytest.mark.exigence("EX14")
def test_reentrainement_reproductible(service_modele, reference, jeu_test, tmp_path):
    """Ré-entraîner la version de référence avec la même graine redonne le même modèle."""
    if not meme_artefact(service_modele, reference):
        pytest.skip("Le modèle déployé n'est pas la version de référence")
    meta = entrainer(reference["version_reference"], repertoire_sortie=tmp_path)
    assert meta["seuils"] == reference["seuils"]
    _, x, _ = jeu_test
    nouveau = joblib.load(tmp_path / f"credit_risk_v{reference['version_reference']}.joblib")
    ecart = np.abs(nouveau.predict_proba(x)[:, 1] - service_modele.predire_lot(x)).max()
    assert ecart <= 1e-9
    for cle in ("roc_auc", "rappel", "f1"):
        assert meta["metriques_test"][cle] == pytest.approx(reference["metriques"][cle], abs=1e-9)


# ===================================================== contrôle complémentaire par segment
@pytest.mark.exigence("EX07")
def test_taux_de_faux_negatifs_par_segment(service_modele, jeu_test, tolerances):
    """Aucun segment suffisamment représenté ne dépasse le taux de faux négatifs maximal.

    Ce contrôle ne remplace pas une analyse d'équité : voir le rapport de qualification."""
    colonnes, x, y = jeu_test
    seuil = service_modele.metadonnees["seuils"]["risque_modere"]
    regles = tolerances["segments"]
    par_segment = metriques_par_segment(colonnes, y, service_modele.predire_lot(x), seuil)
    hors_limite = {
        nom: round(m["taux_faux_negatifs"], 3)
        for nom, m in par_segment.items()
        if m["defauts"] >= regles["effectif_defauts_min"]
        and m["taux_faux_negatifs"] > regles["taux_faux_negatifs_max"]
    }
    assert not hors_limite, (
        f"Segments au-delà de {regles['taux_faux_negatifs_max']} : {hors_limite}"
    )


# ================================================== comparaison d'une version candidate
@pytest.mark.exigence("EX07")
def test_comparaison_du_candidat_v1_1_0():
    """Le comparateur produit un rapport complet ; v1.1.0 est signalé sur les profils de
    référence (écarts hors tolérance) bien que ses métriques restent dans les tolérances."""
    resultat = comparer(config.REPERTOIRE_MODELES / "credit_risk_v1.1.0.joblib")
    assert resultat["version_candidate"] == "1.1.0"
    assert resultat["controle_metriques"]["conforme"] is True
    assert resultat["controle_profils_reference"]["conforme"] is False
    assert resultat["ecart_sauvegarde_rechargement"] == 0.0
    assert set(resultat["segments_candidat"]) == set(resultat["segments_reference"])
