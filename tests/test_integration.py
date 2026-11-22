"""Tests d'intégration : validation -> prétraitement -> modèle -> API.

Le scénario principal instrumente le pipeline réel (espions) pour vérifier chaque étape.
Les scénarios complémentaires injectent des pannes (artefact absent ou corrompu, empreinte
non conforme, dimensions incompatibles, exceptions internes, sortie non conforme) et
vérifient que l'API répond proprement, sans exposer de trace technique.
"""

from __future__ import annotations

import json
import logging
import math
import shutil
from pathlib import Path

import joblib
import numpy as np
import pytest
from sklearn.linear_model import LogisticRegression

from app import config, preprocessing
from app.prediction import (
    ErreurChargementModele,
    ErreurPrediction,
    ServiceModele,
    sha256_fichier,
)
from tests.conftest import verifier_absence_trace

CHEMIN_MODELE = config.chemin_modele()


@pytest.fixture
def service_frais() -> ServiceModele:
    """Service indépendant de la fixture de session (peut être instrumenté sans effet de bord)."""
    service = ServiceModele.depuis_config()
    service.charger()
    return service


def ecrire_artefact(repertoire: Path, objet, metadonnees: dict, empreinte: str | None = None):
    """Écrit un artefact et ses métadonnées ; l'empreinte est recalculée sauf si imposée."""
    chemin = repertoire / "modele_test.joblib"
    joblib.dump(objet, chemin)
    meta = {**metadonnees, "sha256": empreinte or sha256_fichier(chemin)}
    chemin.with_suffix(".json").write_text(json.dumps(meta), encoding="utf-8")
    return chemin


# ======================================================================= scénario principal
@pytest.mark.exigence("EX20", "EX22", "EX04", "EX16")
def test_scenario_principal_bout_en_bout(
    service_frais, fabrique_client, monkeypatch, demande_valide
):
    journal_appels: list[tuple[str, object]] = []

    transformer_reel = preprocessing.transformer

    def espion_transformer(donnees):
        journal_appels.append(("pretraitement", dict(donnees)))
        matrice = transformer_reel(donnees)
        journal_appels.append(("variables", matrice.copy()))
        return matrice

    predire_reel = service_frais.predire_lot

    def espion_predire(matrice):
        journal_appels.append(("modele", np.array(matrice)))
        probabilites = predire_reel(matrice)
        journal_appels.append(("probabilite", float(probabilites[0])))
        return probabilites

    monkeypatch.setattr(preprocessing, "transformer", espion_transformer)
    monkeypatch.setattr(service_frais, "predire_lot", espion_predire)
    client = fabrique_client(service_frais)

    # 1. Envoi d'une requête valide
    reponse = client.post("/predict", json=demande_valide)
    assert reponse.status_code == 200
    etapes = [nom for nom, _ in journal_appels]
    assert etapes == ["pretraitement", "variables", "modele", "probabilite"]
    appels = dict(journal_appels)

    # 2. Validation : le prétraitement reçoit les données validées et typées
    assert appels["pretraitement"] == {
        **demande_valide,
        "revenu_mensuel": 250000.0,
        "montant_credit": 1000000.0,
        "anciennete_activite": 4.0,
    }
    assert isinstance(appels["pretraitement"]["age"], int)

    # 3. Transformation des variables (valeurs calculées à la main)
    attendu = np.array([[35.0, math.log(250000), 12.0, 4.0, 1.0 / 3.0]])
    np.testing.assert_allclose(appels["variables"], attendu, atol=1e-12)
    np.testing.assert_array_equal(appels["modele"], appels["variables"])

    # 4. Prédiction : la probabilité renvoyée est celle du modèle, sans altération
    modele = joblib.load(CHEMIN_MODELE)
    p_directe = float(modele.predict_proba(attendu)[0, 1])
    resultat = reponse.json()
    assert resultat["probabilite_defaut"] == pytest.approx(p_directe, abs=1e-12)
    assert appels["probabilite"] == resultat["probabilite_defaut"]

    # 5. Structure de la réponse
    assert resultat["niveau_risque"] in {"FAIBLE", "MODERE", "ELEVE"}
    assert isinstance(resultat["revue_humaine_requise"], bool)

    # 6. Cohérence des métadonnées entre endpoints et avec l'artefact sur disque
    info = client.get("/model-info").json()
    sante = client.get("/health").json()
    assert resultat["version_modele"] == info["version"] == sante["version_modele"]
    assert info["sha256"] == sha256_fichier(CHEMIN_MODELE)
    assert info["seuils"] == resultat["seuils"]
    assert modele.n_features_in_ == len(info["variables_modele"])


@pytest.mark.exigence("EX06", "EX20")
def test_requete_invalide_n_atteint_ni_pretraitement_ni_modele(
    service_frais, fabrique_client, monkeypatch, demande_valide
):
    appels = []
    monkeypatch.setattr(preprocessing, "transformer", lambda d: appels.append("p"))
    monkeypatch.setattr(service_frais, "predire_lot", lambda m: appels.append("m"))
    client = fabrique_client(service_frais)
    del demande_valide["age"]
    assert client.post("/predict", json=demande_valide).status_code == 422
    assert appels == []


# ============================================================== modèle non chargeable
def _cas_artefact_absent(rep: Path, meta: dict) -> Path:
    return rep / "absent.joblib"


def _cas_artefact_corrompu(rep: Path, meta: dict) -> Path:
    chemin = rep / "corrompu.joblib"
    chemin.write_bytes(b"ceci n'est pas un modele" * 10)
    meta = {**meta, "sha256": sha256_fichier(chemin)}
    chemin.with_suffix(".json").write_text(json.dumps(meta), encoding="utf-8")
    return chemin


def _cas_empreinte_non_conforme(rep: Path, meta: dict) -> Path:
    return ecrire_artefact(rep, joblib.load(CHEMIN_MODELE), meta, empreinte="0" * 64)


def _cas_metadonnees_absentes(rep: Path, meta: dict) -> Path:
    chemin = rep / "sans_meta.joblib"
    shutil.copy(CHEMIN_MODELE, chemin)
    return chemin


def _cas_metadonnees_illisibles(rep: Path, meta: dict) -> Path:
    chemin = rep / "meta_illisible.joblib"
    shutil.copy(CHEMIN_MODELE, chemin)
    chemin.with_suffix(".json").write_text("{pas du json", encoding="utf-8")
    return chemin


def _cas_objet_sans_predict_proba(rep: Path, meta: dict) -> Path:
    return ecrire_artefact(rep, {"poids": [1, 2, 3]}, meta)


def _cas_dimensions_incompatibles(rep: Path, meta: dict) -> Path:
    """Modèle entraîné sur 4 variables alors que le prétraitement en produit 5."""
    rng = np.random.default_rng(0)
    modele = LogisticRegression().fit(rng.normal(size=(50, 4)), rng.integers(0, 2, 50))
    return ecrire_artefact(rep, modele, meta)


def _cas_metadonnees_incompletes(rep: Path, meta: dict) -> Path:
    return ecrire_artefact(rep, joblib.load(CHEMIN_MODELE), {k: v for k, v in meta.items()
                                                             if k != "seuils"})  # fmt: skip


def _cas_ordre_variables_different(rep: Path, meta: dict) -> Path:
    variables = list(reversed(meta["variables_modele"]))
    return ecrire_artefact(rep, joblib.load(CHEMIN_MODELE), {**meta, "variables_modele": variables})


def _cas_seuils_invalides(rep: Path, meta: dict) -> Path:
    seuils = {"risque_modere": 0.6, "risque_eleve": 0.3}
    return ecrire_artefact(rep, joblib.load(CHEMIN_MODELE), {**meta, "seuils": seuils})


CAS_CHARGEMENT = {
    "artefact_absent": (_cas_artefact_absent, "FileNotFoundError"),
    "artefact_corrompu": (_cas_artefact_corrompu, "lors du chargement"),
    "empreinte_non_conforme": (_cas_empreinte_non_conforme, "SHA-256"),
    "metadonnees_absentes": (_cas_metadonnees_absentes, "FileNotFoundError"),
    "metadonnees_illisibles": (_cas_metadonnees_illisibles, "JSONDecodeError"),
    "objet_sans_predict_proba": (_cas_objet_sans_predict_proba, "predict_proba"),
    "dimensions_incompatibles": (_cas_dimensions_incompatibles, "Dimensions incompatibles"),
    "metadonnees_incompletes": (_cas_metadonnees_incompletes, "seuils"),
    "ordre_variables_different": (_cas_ordre_variables_different, "Ordre ou nom"),
    "seuils_invalides": (_cas_seuils_invalides, "Seuils"),
}


@pytest.mark.exigence("EX05", "EX17", "EX13")
@pytest.mark.parametrize("cas", list(CAS_CHARGEMENT))
def test_modele_non_chargeable(cas, tmp_path, metadonnees, fabrique_client, demande_valide, caplog):
    preparer, raison_attendue = CAS_CHARGEMENT[cas]
    service = ServiceModele(preparer(tmp_path, metadonnees))

    with pytest.raises(ErreurChargementModele):
        service.charger()
    assert raison_attendue in service.derniere_erreur
    assert not service.est_charge

    client = fabrique_client(service)
    with caplog.at_level(logging.ERROR, logger="creditrisk"):
        reponse = client.post("/predict", json=demande_valide)
    assert reponse.status_code == 503
    assert reponse.json()["code"] == "MODELE_INDISPONIBLE"
    verifier_absence_trace(reponse)
    assert str(tmp_path) not in reponse.text
    assert raison_attendue in caplog.text  # le détail reste dans les journaux serveur
    assert client.get("/health").status_code == 503


@pytest.mark.exigence("EX05")
def test_rechargement_automatique_apres_restauration(tmp_path, fabrique_client, demande_valide):
    """Le service se rétablit dès que l'artefact redevient disponible, sans redémarrage."""
    chemin = tmp_path / "credit_risk.joblib"
    client = fabrique_client(ServiceModele(chemin))
    assert client.post("/predict", json=demande_valide).status_code == 503

    shutil.copy(CHEMIN_MODELE, chemin)
    shutil.copy(config.chemin_metadonnees(CHEMIN_MODELE), chemin.with_suffix(".json"))
    assert client.get("/health").json()["statut"] == "ok"
    assert client.post("/predict", json=demande_valide).status_code == 200


# ================================================================ variable absente
@pytest.mark.exigence("EX06", "EX22")
def test_variable_absente_bloquee_par_validation(client, demande_valide):
    del demande_valide["duree_mois"]
    reponse = client.post("/predict", json=demande_valide)
    assert reponse.status_code == 422
    assert reponse.json()["details"][0]["champ"] == "duree_mois"


@pytest.mark.exigence("EX06", "EX22")
def test_variable_absente_bloquee_par_le_pipeline_sans_validation(service_frais, demande_valide):
    """Défense en profondeur : un appel interne qui contournerait la validation échoue
    explicitement au prétraitement au lieu de produire une prédiction."""
    del demande_valide["duree_mois"]
    with pytest.raises(preprocessing.ErreurPretraitement, match="duree_mois"):
        service_frais.evaluer(demande_valide)


# ================================================================== erreurs internes
@pytest.mark.exigence("EX13")
def test_erreur_de_pretraitement(
    service_frais, fabrique_client, monkeypatch, demande_valide, caplog
):
    def defaillant(donnees):
        raise preprocessing.ErreurPretraitement("détail interne /srv/secret/config.yaml")

    monkeypatch.setattr(preprocessing, "transformer", defaillant)
    client = fabrique_client(service_frais)
    with caplog.at_level(logging.ERROR, logger="creditrisk"):
        reponse = client.post("/predict", json=demande_valide)

    assert reponse.status_code == 500
    corps = reponse.json()
    assert corps["code"] == "ERREUR_PRETRAITEMENT"
    assert "secret" not in reponse.text
    verifier_absence_trace(reponse)
    assert corps["identifiant_requete"] in caplog.text  # corrélation client / journaux
    assert "secret" in caplog.text


@pytest.mark.exigence("EX22", "EX13")
@pytest.mark.parametrize("forme", [(1, 4), (1, 6), (2, 5), (5,), (0, 5)])
def test_dimensions_produites_incompatibles(service_frais, fabrique_client, monkeypatch,
                                           demande_valide, forme):  # fmt: skip
    """Le prétraitement renvoie une matrice de mauvaise forme : refus avant le modèle."""
    monkeypatch.setattr(preprocessing, "transformer", lambda d: np.zeros(forme))
    reponse = fabrique_client(service_frais).post("/predict", json=demande_valide)
    assert reponse.status_code == 500
    assert reponse.json()["code"] == "ERREUR_PREDICTION"
    verifier_absence_trace(reponse)


class ModeleDefaillant:
    """Modèle factice respectant l'interface mais dont predict_proba échoue ou ment."""

    n_features_in_ = 5

    def __init__(self, sortie=None, exception: Exception | None = None):
        self.sortie, self.exception = sortie, exception

    def predict_proba(self, x):
        if self.exception:
            raise self.exception
        return np.asarray(self.sortie, dtype=float)


@pytest.mark.exigence("EX13")
def test_exception_pendant_la_prediction(metadonnees, fabrique_client, demande_valide, caplog):
    modele = ModeleDefaillant(exception=MemoryError("/opt/modeles/credit.bin : mémoire épuisée"))
    client = fabrique_client(ServiceModele.depuis_objets(modele, metadonnees))
    with caplog.at_level(logging.ERROR, logger="creditrisk"):
        reponse = client.post("/predict", json=demande_valide)
    assert reponse.status_code == 500
    assert reponse.json()["code"] == "ERREUR_PREDICTION"
    assert "/opt/modeles" not in reponse.text
    verifier_absence_trace(reponse)
    assert "MemoryError" in caplog.text


@pytest.mark.exigence("EX04", "EX13")
@pytest.mark.parametrize(
    "sortie",
    [[[np.nan, np.nan]], [[0.5, np.inf]], [[-0.2, 1.2]], [[0.3, 0.3]], [[0.2, 0.3, 0.5]], [0.7]],
    ids=["nan", "infini", "hors_0_1", "somme_differente_de_1", "trois_classes", "forme_1d"],
)
def test_sortie_du_modele_non_conforme(metadonnees, fabrique_client, demande_valide, sortie):
    """Le contrat de sortie est vérifié : une probabilité invalide n'est jamais renvoyée."""
    client = fabrique_client(ServiceModele.depuis_objets(ModeleDefaillant(sortie), metadonnees))
    reponse = client.post("/predict", json=demande_valide)
    assert reponse.status_code == 500
    assert reponse.json()["code"] == "ERREUR_PREDICTION"
    assert "probabilite_defaut" not in reponse.json()


@pytest.mark.exigence("EX13")
def test_erreur_inattendue_dans_l_orchestration(service_frais, fabrique_client, monkeypatch,
                                                demande_valide):  # fmt: skip
    def defaillant(donnees):
        raise KeyError("cle_interne_seuils")

    monkeypatch.setattr(service_frais, "evaluer", defaillant)
    reponse = fabrique_client(service_frais).post("/predict", json=demande_valide)
    assert reponse.status_code == 500
    assert reponse.json()["code"] == "ERREUR_INTERNE"
    assert "cle_interne" not in reponse.text
    verifier_absence_trace(reponse)


@pytest.mark.exigence("EX13", "EX16")
def test_filet_de_securite_erreur_non_geree(metadonnees, fabrique_client):
    """Métadonnées altérées après chargement : /model-info échoue hors des cas prévus ;
    le gestionnaire global renvoie un 500 générique."""
    service = ServiceModele.depuis_objets(joblib.load(CHEMIN_MODELE), metadonnees)
    service._metadonnees = {**metadonnees, "algorithme": None}
    reponse = fabrique_client(service).get("/model-info")
    assert reponse.status_code == 500
    assert reponse.json()["code"] == "ERREUR_INTERNE"
    verifier_absence_trace(reponse)


@pytest.mark.exigence("EX22")
def test_predire_lot_refuse_une_matrice_vide(service_frais):
    with pytest.raises(ErreurPrediction, match="Dimensions"):
        service_frais.predire_lot(np.empty((0, 5)))
