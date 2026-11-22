"""Tests fonctionnels de l'API : contrat des endpoints /health, /predict et /model-info.

Scénarios obligatoires (énoncé, partie II) et réponse attendue :

| N° | Scénario                              | HTTP | Code d'erreur / contenu                 |
|----|---------------------------------------|------|-----------------------------------------|
| S1 | Requête valide                        | 200  | probabilite_defaut dans [0, 1]          |
| S2 | Champ obligatoire absent              | 422  | DONNEES_INVALIDES, type missing         |
| S3 | Âge négatif                           | 422  | DONNEES_INVALIDES, greater_than_equal   |
| S4 | Revenu sous forme de texte            | 422  | DONNEES_INVALIDES, float_type           |
| S5 | Montant nul ou négatif                | 422  | DONNEES_INVALIDES, greater_than         |
| S6 | Durée non entière                     | 422  | DONNEES_INVALIDES, int_type             |
| S7 | Champs supplémentaires                | 422  | DONNEES_INVALIDES, extra_forbidden      |
| S8 | Valeurs extrêmement élevées           | 422  | DONNEES_INVALIDES, less_than_equal      |
| S9 | Modèle indisponible                   | 503  | MODELE_INDISPONIBLE + Retry-After       |
| S10| Requête mal formée                    | 400  | REQUETE_MAL_FORMEE                      |
"""

from __future__ import annotations

import math
from pathlib import Path

import pytest
from fastapi.testclient import TestClient

from app import config
from app.main import app
from app.prediction import ServiceModele, classer_risque
from app.preprocessing import VARIABLES_ENTREE
from tests.conftest import CHAMPS_REPONSE_PREDICTION, verifier_absence_trace

CHAMPS = list(VARIABLES_ENTREE)


def poster(client, corps: dict):
    return client.post("/predict", json=corps)


def details(reponse) -> dict[str, str]:
    """{champ: type d'erreur} extrait d'une réponse 422."""
    return {d["champ"]: d["type"] for d in reponse.json()["details"]}


def verifier_erreur(reponse, statut: int, code: str) -> dict:
    assert reponse.status_code == statut, reponse.text
    corps = reponse.json()
    assert corps["code"] == code
    assert corps["message"]
    assert corps["identifiant_requete"] == reponse.headers["X-Request-ID"]
    verifier_absence_trace(reponse)
    return corps


# ---------------------------------------------------------------------- S1 : nominal
@pytest.mark.exigence("EX04", "EX20")
def test_s1_requete_valide(client, demande_valide, metadonnees):
    reponse = poster(client, demande_valide)

    assert reponse.status_code == 200
    resultat = reponse.json()
    assert set(resultat) == CHAMPS_REPONSE_PREDICTION
    probabilite = resultat["probabilite_defaut"]
    assert isinstance(probabilite, float)
    assert math.isfinite(probabilite)
    assert 0.0 <= probabilite <= 1.0
    assert resultat["niveau_risque"] == classer_risque(probabilite, metadonnees["seuils"])
    assert resultat["version_modele"] == metadonnees["version"]
    assert resultat["seuils"] == metadonnees["seuils"]
    assert resultat["indicateurs"]["mensualite_estimee"] == pytest.approx(83333.33)
    assert resultat["identifiant_requete"] == reponse.headers["X-Request-ID"]
    assert float(reponse.headers["X-Temps-Traitement-ms"]) >= 0


@pytest.mark.exigence("EX04", "EX05")
def test_s1_exemple_de_l_enonce_sans_cycle_de_vie():
    """Test fourni par l'énoncé, à l'identique : client créé sans ``with`` (donc sans
    événement de démarrage). Le modèle doit être chargé à la première requête."""
    client = TestClient(app)
    response = client.post(
        "/predict",
        json={
            "age": 35,
            "revenu_mensuel": 250000,
            "montant_credit": 1000000,
            "duree_mois": 12,
            "anciennete_activite": 4,
        },
    )
    assert response.status_code == 200
    resultat = response.json()
    assert 0 <= resultat["probabilite_defaut"] <= 1


@pytest.mark.exigence("EX15", "EX20")
def test_s1_profil_dans_le_domaine_sans_alerte(client, demande_valide):
    resultat = poster(client, demande_valide).json()
    assert resultat["alertes"] == []
    assert resultat["revue_humaine_requise"] is (resultat["niveau_risque"] != "FAIBLE")


# ------------------------------------------------------------ S2 : champ obligatoire
@pytest.mark.exigence("EX06")
@pytest.mark.parametrize("champ", CHAMPS)
def test_s2_champ_obligatoire_absent(client, demande_valide, champ):
    del demande_valide[champ]
    reponse = poster(client, demande_valide)
    verifier_erreur(reponse, 422, "DONNEES_INVALIDES")
    assert details(reponse) == {champ: "missing"}


@pytest.mark.exigence("EX06")
def test_s2_corps_vide_liste_les_cinq_champs(client):
    reponse = poster(client, {})
    verifier_erreur(reponse, 422, "DONNEES_INVALIDES")
    assert set(details(reponse)) == set(CHAMPS)


# ---------------------------------------------------------------------- S3 : âge négatif
@pytest.mark.exigence("EX01")
def test_s3_age_negatif(client, demande_valide):
    reponse = poster(client, {**demande_valide, "age": -5})
    corps = verifier_erreur(reponse, 422, "DONNEES_INVALIDES")
    assert details(reponse) == {"age": "greater_than_equal"}
    assert corps["details"][0]["message"] == "Doit être supérieur ou égal à 18."


@pytest.mark.exigence("EX01")
@pytest.mark.parametrize("age", [17, 76])
def test_s3_age_juste_hors_limites(client, demande_valide, age):
    reponse = poster(client, {**demande_valide, "age": age})
    verifier_erreur(reponse, 422, "DONNEES_INVALIDES")
    assert "age" in details(reponse)


# --------------------------------------------------------------- S4 : revenu en texte
@pytest.mark.exigence("EX02", "EX11")
@pytest.mark.parametrize("revenu", ["250000", "deux cent cinquante mille", ""])
def test_s4_revenu_texte(client, demande_valide, revenu):
    reponse = poster(client, {**demande_valide, "revenu_mensuel": revenu})
    verifier_erreur(reponse, 422, "DONNEES_INVALIDES")
    assert details(reponse) == {"revenu_mensuel": "float_type"}
    assert set(reponse.json()["details"][0]) == {"champ", "type", "message"}  # pas d'écho


# ------------------------------------------------------------ S5 : montant nul/négatif
@pytest.mark.exigence("EX08")
@pytest.mark.parametrize("montant", [0, -1, -1_000_000])
def test_s5_montant_nul_ou_negatif(client, demande_valide, montant):
    reponse = poster(client, {**demande_valide, "montant_credit": montant})
    verifier_erreur(reponse, 422, "DONNEES_INVALIDES")
    assert details(reponse) == {"montant_credit": "greater_than"}


# -------------------------------------------------------------- S6 : durée non entière
@pytest.mark.exigence("EX03")
@pytest.mark.parametrize("duree", [12.5, 12.0, "12"])
def test_s6_duree_non_entiere(client, demande_valide, duree):
    reponse = poster(client, {**demande_valide, "duree_mois": duree})
    verifier_erreur(reponse, 422, "DONNEES_INVALIDES")
    assert details(reponse) == {"duree_mois": "int_type"}


# --------------------------------------------------------- S7 : champs supplémentaires
@pytest.mark.exigence("EX10")
def test_s7_champs_supplementaires(client, demande_valide):
    reponse = poster(client, {**demande_valide, "nom": "Diallo", "score_interne": 900})
    verifier_erreur(reponse, 422, "DONNEES_INVALIDES")
    assert details(reponse) == {"nom": "extra_forbidden", "score_interne": "extra_forbidden"}


@pytest.mark.exigence("EX10", "EX06")
def test_s7_faute_de_frappe_detectee(client, demande_valide):
    """« revenu » au lieu de « revenu_mensuel » : deux erreurs, aucune ignorance silencieuse."""
    demande_valide["revenu"] = demande_valide.pop("revenu_mensuel")
    reponse = poster(client, demande_valide)
    assert details(reponse) == {"revenu_mensuel": "missing", "revenu": "extra_forbidden"}


# ---------------------------------------------------------- S8 : valeurs extrêmes
@pytest.mark.exigence("EX01", "EX02", "EX03", "EX08", "EX09")
@pytest.mark.parametrize(
    ("champ", "valeur"),
    [("age", 10**6), ("age", 10**30), ("revenu_mensuel", 1e12), ("revenu_mensuel", 1e308),
     ("montant_credit", 1e15), ("duree_mois", 10**9), ("anciennete_activite", 1e6)],
)  # fmt: skip
def test_s8_valeurs_extremement_elevees(client, demande_valide, champ, valeur):
    reponse = poster(client, {**demande_valide, champ: valeur})
    verifier_erreur(reponse, 422, "DONNEES_INVALIDES")
    assert champ in details(reponse)


# ------------------------------------------------------------ S9 : modèle indisponible
@pytest.fixture
def client_sans_modele(fabrique_client, tmp_path: Path):
    return fabrique_client(ServiceModele(tmp_path / "absent.joblib"))


@pytest.mark.exigence("EX05", "EX13")
def test_s9_predict_modele_indisponible(client_sans_modele, demande_valide):
    reponse = poster(client_sans_modele, demande_valide)
    verifier_erreur(reponse, 503, "MODELE_INDISPONIBLE")
    assert reponse.headers["Retry-After"] == "30"
    assert "absent.joblib" not in reponse.text


@pytest.mark.exigence("EX05")
def test_s9_health_signale_l_indisponibilite(client_sans_modele):
    reponse = client_sans_modele.get("/health")
    assert reponse.status_code == 503
    assert reponse.json() == {
        "statut": "degrade",
        "modele_charge": False,
        "version_modele": None,
        "version_api": config.VERSION_API,
    }


@pytest.mark.exigence("EX05", "EX16")
def test_s9_model_info_indisponible(client_sans_modele):
    verifier_erreur(client_sans_modele.get("/model-info"), 503, "MODELE_INDISPONIBLE")


@pytest.mark.exigence("EX05", "EX06")
def test_s9_validation_prioritaire_sur_disponibilite(client_sans_modele):
    """Une demande invalide est rejetée en 422 même si le modèle est absent."""
    verifier_erreur(poster(client_sans_modele, {}), 422, "DONNEES_INVALIDES")


# ----------------------------------------------------------- S10 : requête mal formée
@pytest.mark.exigence("EX12", "EX13")
@pytest.mark.parametrize("corps", ['{"age": 35,', "pas du json", "{'age': 35}", "{age: 35}"])
def test_s10_json_invalide(client, corps):
    reponse = client.post("/predict", content=corps, headers={"Content-Type": "application/json"})
    verifier_erreur(reponse, 400, "REQUETE_MAL_FORMEE")


@pytest.mark.exigence("EX12")
@pytest.mark.parametrize("corps", ["[1, 2, 3]", '"texte"', "42", "null"])
def test_s10_corps_qui_n_est_pas_un_objet(client, corps):
    reponse = client.post("/predict", content=corps, headers={"Content-Type": "application/json"})
    verifier_erreur(reponse, 422, "DONNEES_INVALIDES")


@pytest.mark.exigence("EX12", "EX06")
def test_s10_corps_vide(client):
    """Comportement observé et retenu : un corps vide est un corps absent (422), pas un JSON
    syntaxiquement invalide (400)."""
    reponse = client.post("/predict", content="", headers={"Content-Type": "application/json"})
    verifier_erreur(reponse, 422, "DONNEES_INVALIDES")
    assert details(reponse) == {"corps": "missing"}


@pytest.mark.exigence("EX12")
def test_s10_corps_trop_volumineux(client, demande_valide):
    demande_valide["commentaire"] = "x" * (config.TAILLE_MAX_REQUETE_OCTETS + 1)
    verifier_erreur(poster(client, demande_valide), 413, "REQUETE_TROP_VOLUMINEUSE")


@pytest.mark.exigence("EX12")
def test_s10_content_type_non_json(client):
    """Comportement observé : 422 (corps non interprété comme objet). Un 415 serait plus
    précis : écart consigné comme anomalie mineure AN-07."""
    reponse = client.post(
        "/predict", content="age=35&revenu_mensuel=250000", headers={"Content-Type": "text/plain"}
    )
    verifier_erreur(reponse, 422, "DONNEES_INVALIDES")
    assert details(reponse) == {"corps": "model_attributes_type"}


# -------------------------------------------------------------- /health et /model-info
@pytest.mark.exigence("EX05")
def test_health_nominal(client, metadonnees):
    reponse = client.get("/health")
    assert reponse.status_code == 200
    assert reponse.json() == {
        "statut": "ok",
        "modele_charge": True,
        "version_modele": metadonnees["version"],
        "version_api": config.VERSION_API,
    }


@pytest.mark.exigence("EX16")
def test_model_info(client, metadonnees):
    reponse = client.get("/model-info")
    assert reponse.status_code == 200
    info = reponse.json()
    assert info["version"] == metadonnees["version"]
    assert info["variables_entree"] == CHAMPS
    assert info["variables_modele"] == metadonnees["variables_modele"]
    assert info["seuils"] == metadonnees["seuils"]
    assert info["sha256"] == metadonnees["sha256"]
    assert info["jeu_donnees"]["type"] == "synthetique"
    assert set(info["metriques_test"]) >= {"rappel", "f1", "roc_auc"}


# --------------------------------------------------------------- routes et en-têtes
@pytest.mark.exigence("EX12", "EX13")
def test_route_inconnue(client):
    verifier_erreur(client.get("/admin"), 404, "RESSOURCE_INTROUVABLE")


@pytest.mark.exigence("EX12")
def test_methode_non_autorisee(client):
    reponse = client.get("/predict")
    corps = verifier_erreur(reponse, 405, "METHODE_NON_AUTORISEE")
    assert corps["message"] == "Méthode HTTP non autorisée pour cette ressource."
    assert "POST" in reponse.headers["Allow"]


@pytest.mark.exigence("EX13")
@pytest.mark.parametrize(
    ("entrant", "conserve"),
    [("agence-12-req-0001", True), ("x" * 65, False), ("id avec espaces", False),
     ("<script>", False)],
)  # fmt: skip
def test_identifiant_de_requete(client, demande_valide, entrant, conserve):
    reponse = client.post("/predict", json=demande_valide, headers={"X-Request-ID": entrant})
    assert (reponse.headers["X-Request-ID"] == entrant) is conserve
    assert reponse.json()["identifiant_requete"] == reponse.headers["X-Request-ID"]
