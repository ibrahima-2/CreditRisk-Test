"""Tests de robustesse : entrées limites, invalides et inhabituelles.

Distinction appliquée :
- entrée INVALIDE (hors contrat) : rejetée par une erreur contrôlée (4xx), jamais de 500 ;
- entrée INHABITUELLE mais VALIDE (hors domaine d'entraînement) : acceptée (200), avec
  alertes HORS_DOMAINE_* et revue humaine obligatoire.

Techniques : valeurs limites, tests de propriétés (Hypothesis), tests métamorphiques
(monotonie métier), répétabilité et accès concurrents.
"""

from __future__ import annotations

import itertools
import json
import math
from concurrent.futures import ThreadPoolExecutor

import pytest
from hypothesis import HealthCheck, given
from hypothesis import settings as reglages
from hypothesis import strategies as st

from app.preprocessing import VARIABLES_ENTREE
from app.validation import (
    AGE_MAX,
    AGE_MIN,
    AGE_MIN_DEBUT_ACTIVITE,
    ANCIENNETE_MAX,
    DUREE_MAX,
    MONTANT_MAX,
    REVENU_MAX,
)
from tests.conftest import CHAMPS_REPONSE_PREDICTION, verifier_absence_trace

CHAMPS_DECIMAUX = ["revenu_mensuel", "montant_credit", "anciennete_activite"]
CHAMPS_ENTIERS = ["age", "duree_mois"]


def poster_brut(client, texte: str):
    return client.post("/predict", content=texte, headers={"Content-Type": "application/json"})


def verifier_rejet(reponse, champ: str | None = None) -> None:
    assert reponse.status_code == 422, reponse.text
    assert reponse.json()["code"] == "DONNEES_INVALIDES"
    if champ:
        assert champ in {d["champ"] for d in reponse.json()["details"]}
    verifier_absence_trace(reponse)


# ======================================================================= valeurs manquantes
@pytest.mark.exigence("EX06", "EX11")
@pytest.mark.parametrize("champ", VARIABLES_ENTREE)
def test_valeur_nulle(client, demande_valide, champ):
    verifier_rejet(client.post("/predict", json={**demande_valide, champ: None}), champ)


@pytest.mark.exigence("EX06")
def test_toutes_les_valeurs_nulles(client):
    reponse = client.post("/predict", json=dict.fromkeys(VARIABLES_ENTREE))
    verifier_rejet(reponse)
    assert len(reponse.json()["details"]) == len(VARIABLES_ENTREE)


# =================================================================== valeurs non numériques
@pytest.mark.exigence("EX11")
@pytest.mark.parametrize("champ", VARIABLES_ENTREE)
@pytest.mark.parametrize(
    "valeur",
    ["abc", "", "35", "1e3", "٣٥", [35], {"valeur": 35}, True, False],
    ids=["texte", "vide", "nombre_texte", "notation_texte", "chiffres_arabes", "liste", "objet",
         "vrai", "faux"],
)  # fmt: skip
def test_valeur_non_numerique(client, demande_valide, champ, valeur):
    verifier_rejet(client.post("/predict", json={**demande_valide, champ: valeur}), champ)


# ================================================================ valeurs non finies (JSON brut)
@pytest.mark.exigence("EX11")
@pytest.mark.parametrize("champ", VARIABLES_ENTREE)
@pytest.mark.parametrize("jeton", ["NaN", "Infinity", "-Infinity", "1e400", "-1e400"])
def test_valeur_non_finie(client, demande_valide, champ, jeton):
    """Le module json de Python accepte NaN/Infinity (hors norme JSON) : la validation
    doit les refuser explicitement (``allow_inf_nan=False``)."""
    texte = json.dumps({**demande_valide, champ: "__X__"}).replace('"__X__"', jeton)
    verifier_rejet(poster_brut(client, texte), champ)


# =========================================================================== valeurs limites
LIMITES = [
    # (champ, valeur, acceptée ?)
    ("age", AGE_MIN - 1, False), ("age", AGE_MIN, True), ("age", AGE_MAX, True),
    ("age", AGE_MAX + 1, False),
    ("revenu_mensuel", 0, False), ("revenu_mensuel", 1e-9, True),
    ("revenu_mensuel", REVENU_MAX, True), ("revenu_mensuel", REVENU_MAX + 0.01, False),
    ("montant_credit", 0, False), ("montant_credit", 1e-9, True),
    ("montant_credit", MONTANT_MAX, True), ("montant_credit", MONTANT_MAX + 0.01, False),
    ("duree_mois", 0, False), ("duree_mois", 1, True), ("duree_mois", DUREE_MAX, True),
    ("duree_mois", DUREE_MAX + 1, False),
    ("anciennete_activite", -1e-9, False), ("anciennete_activite", 0, True),
    ("anciennete_activite", 35 - AGE_MIN_DEBUT_ACTIVITE, True),
    ("anciennete_activite", 35 - AGE_MIN_DEBUT_ACTIVITE + 1e-6, False),
]  # fmt: skip


@pytest.mark.exigence("EX01", "EX02", "EX03", "EX08", "EX09", "EX04")
@pytest.mark.parametrize(("champ", "valeur", "acceptee"), LIMITES)
def test_valeurs_aux_limites(client, demande_valide, champ, valeur, acceptee):
    reponse = client.post("/predict", json={**demande_valide, champ: valeur})
    if acceptee:
        assert reponse.status_code == 200, reponse.text
        p = reponse.json()["probabilite_defaut"]
        assert math.isfinite(p)
        assert 0.0 <= p <= 1.0
    else:
        verifier_rejet(reponse, champ)


@pytest.mark.exigence("EX09")
def test_limite_anciennete_a_75_ans(client, demande_valide):
    base = {**demande_valide, "age": AGE_MAX}
    assert client.post("/predict", json={**base, "anciennete_activite": ANCIENNETE_MAX}).is_success
    verifier_rejet(
        client.post("/predict", json={**base, "anciennete_activite": ANCIENNETE_MAX + 0.5}),
        "anciennete_activite",
    )


# ============================================== entrées valides mais hors domaine d'entraînement
HORS_DOMAINE = {
    "age_75_anciennete_60": ({"age": 75, "revenu_mensuel": 300000, "montant_credit": 1000000,
                              "duree_mois": 24, "anciennete_activite": 60},
                             {"HORS_DOMAINE_AGE", "HORS_DOMAINE_ANCIENNETE_ACTIVITE"}),
    "revenu_20_millions": ({"age": 45, "revenu_mensuel": 20000000, "montant_credit": 5000000,
                            "duree_mois": 12, "anciennete_activite": 15},
                           {"HORS_DOMAINE_REVENU_MENSUEL"}),
    "montant_400_millions": ({"age": 45, "revenu_mensuel": 2000000, "montant_credit": 400000000,
                              "duree_mois": 60, "anciennete_activite": 15},
                             {"HORS_DOMAINE_MONTANT_CREDIT"}),
    "revenu_1000_fcfa": ({"age": 30, "revenu_mensuel": 1000, "montant_credit": 50000,
                          "duree_mois": 12, "anciennete_activite": 3},
                         {"HORS_DOMAINE_REVENU_MENSUEL", "HORS_DOMAINE_TAUX_ENDETTEMENT"}),
    "duree_120_mois": ({"age": 40, "revenu_mensuel": 500000, "montant_credit": 10000000,
                        "duree_mois": 120, "anciennete_activite": 10},
                       {"HORS_DOMAINE_DUREE_MOIS"}),
}  # fmt: skip


@pytest.mark.exigence("EX15", "EX04")
@pytest.mark.parametrize("cas", list(HORS_DOMAINE))
def test_hors_domaine_accepte_avec_alerte(client, cas):
    demande, alertes_attendues = HORS_DOMAINE[cas]
    reponse = client.post("/predict", json=demande)
    assert reponse.status_code == 200
    resultat = reponse.json()
    assert alertes_attendues <= set(resultat["alertes"])
    assert resultat["revue_humaine_requise"] is True
    assert 0.0 <= resultat["probabilite_defaut"] <= 1.0


@pytest.mark.exigence("EX15")
@pytest.mark.parametrize("cas", list(HORS_DOMAINE))
def test_probabilite_saturee_toujours_signalee(client, cas):
    """Anomalie AN-02 : hors domaine, la régression logistique extrapole et peut renvoyer
    exactement 0,0 ou 1,0. Exigence minimale vérifiée : un score saturé n'est jamais
    renvoyé sans alerte ni revue humaine."""
    resultat = client.post("/predict", json=HORS_DOMAINE[cas][0]).json()
    if resultat["probabilite_defaut"] in (0.0, 1.0):
        assert resultat["alertes"]
        assert resultat["revue_humaine_requise"]


# ======================================================================== schéma incorrect
@pytest.mark.exigence("EX10", "EX12")
@pytest.mark.parametrize(
    "corps",
    [
        [{"age": 35}],
        {"demande": {"age": 35, "revenu_mensuel": 250000, "montant_credit": 1000000,
                     "duree_mois": 12, "anciennete_activite": 4}},
        {"Age": 35, "Revenu_Mensuel": 250000, "Montant_Credit": 1000000, "Duree_Mois": 12,
         "Anciennete_Activite": 4},
        "age=35",
        12345,
    ],
    ids=["liste", "objet_imbrique", "casse_differente", "chaine", "nombre"],
)  # fmt: skip
def test_schema_incorrect(client, corps):
    verifier_rejet(client.post("/predict", json=corps))


@pytest.mark.exigence("EX12")
def test_cles_dupliquees_derniere_valeur_validee(client, demande_valide):
    """JSON avec clé dupliquée : la dernière occurrence est retenue puis validée."""
    texte = json.dumps(demande_valide)[:-1] + ', "age": -1}'
    verifier_rejet(poster_brut(client, texte), "age")


@pytest.mark.exigence("EX12")
def test_chaine_tres_longue(client, demande_valide):
    reponse = client.post("/predict", json={**demande_valide, "revenu_mensuel": "9" * 10_000})
    verifier_rejet(reponse, "revenu_mensuel")


# ================================================================ propriétés (Hypothesis)
@st.composite
def demandes_valides(draw):
    age = draw(st.integers(AGE_MIN, AGE_MAX))
    return {
        "age": age,
        "revenu_mensuel": draw(st.floats(1.0, REVENU_MAX, allow_nan=False)),
        "montant_credit": draw(st.floats(1.0, MONTANT_MAX, allow_nan=False)),
        "duree_mois": draw(st.integers(1, DUREE_MAX)),
        "anciennete_activite": draw(
            st.floats(0, min(ANCIENNETE_MAX, age - AGE_MIN_DEBUT_ACTIVITE), allow_nan=False)
        ),
    }


@pytest.mark.exigence("EX04", "EX20")
@reglages(suppress_health_check=[HealthCheck.function_scoped_fixture])
@given(demande=demandes_valides())
def test_propriete_toute_demande_valide_donne_une_probabilite(client, demande):
    reponse = client.post("/predict", json=demande)
    assert reponse.status_code == 200, reponse.text
    resultat = reponse.json()
    assert set(resultat) == CHAMPS_REPONSE_PREDICTION
    assert math.isfinite(resultat["probabilite_defaut"])
    assert 0.0 <= resultat["probabilite_defaut"] <= 1.0


VALEURS_ARBITRAIRES = st.one_of(
    st.none(), st.booleans(), st.integers(-(10**20), 10**20),
    st.floats(allow_nan=False, allow_infinity=False), st.text(max_size=20),
    st.lists(st.integers(), max_size=3),
)  # fmt: skip


@pytest.mark.exigence("EX12", "EX13")
@reglages(suppress_health_check=[HealthCheck.function_scoped_fixture])
@given(
    corps=st.dictionaries(
        st.sampled_from([*VARIABLES_ENTREE, "extra", ""]), VALEURS_ARBITRAIRES, max_size=7
    )
)
def test_propriete_aucune_entree_ne_provoque_d_erreur_500(client, corps):
    reponse = client.post("/predict", json=corps)
    assert reponse.status_code in {200, 422}, reponse.text
    verifier_absence_trace(reponse)


# ================================================================= tests métamorphiques
PROFILS_BASE = [
    {"age": 35, "revenu_mensuel": 250000, "montant_credit": 1000000, "duree_mois": 12,
     "anciennete_activite": 4},
    {"age": 50, "revenu_mensuel": 800000, "montant_credit": 3000000, "duree_mois": 24,
     "anciennete_activite": 20},
    {"age": 24, "revenu_mensuel": 90000, "montant_credit": 400000, "duree_mois": 6,
     "anciennete_activite": 1},
]  # fmt: skip


def probabilite(service, demande) -> float:
    return service.evaluer(demande).probabilite_defaut


@pytest.mark.exigence("EX18")
@pytest.mark.parametrize("base", PROFILS_BASE)
@pytest.mark.parametrize(
    ("champ", "facteurs", "sens"),
    [("montant_credit", [1.0, 1.25, 1.5, 2.0, 3.0], +1),
     ("revenu_mensuel", [1.0, 1.25, 1.5, 2.0, 3.0], -1),
     ("anciennete_activite", [0.0, 0.25, 0.5, 0.75, 1.0], -1)],
    ids=["montant_croissant", "revenu_croissant", "anciennete_croissante"],
)  # fmt: skip
def test_monotonie_metier(service_modele, base, champ, facteurs, sens):
    """Toutes choses égales par ailleurs : plus de montant ne diminue pas le risque ; plus de
    revenu ou d'ancienneté ne l'augmente pas."""
    if champ == "anciennete_activite":
        maximum = base["age"] - AGE_MIN_DEBUT_ACTIVITE
        valeurs = [f * maximum for f in facteurs]
    else:
        valeurs = [f * base[champ] for f in facteurs]
    probas = [probabilite(service_modele, {**base, champ: v}) for v in valeurs]
    ecarts = [sens * (b - a) for a, b in itertools.pairwise(probas)]
    assert all(e >= -1e-12 for e in ecarts), f"{champ} : {probas}"


@pytest.mark.exigence("EX18", "EX14")
def test_invariance_a_l_ordre_des_champs(client, demande_valide):
    inverse = dict(reversed(list(demande_valide.items())))
    p1 = client.post("/predict", json=demande_valide).json()["probabilite_defaut"]
    p2 = client.post("/predict", json=inverse).json()["probabilite_defaut"]
    assert p1 == p2


@pytest.mark.exigence("EX18", "EX14")
def test_entier_et_decimal_equivalents(client, demande_valide):
    """250000 et 250000.0 désignent le même revenu : même probabilité."""
    p1 = client.post("/predict", json=demande_valide).json()["probabilite_defaut"]
    decimal = {**demande_valide, "revenu_mensuel": 250000.0, "montant_credit": 1000000.0}
    assert client.post("/predict", json=decimal).json()["probabilite_defaut"] == p1


# ======================================================== répétabilité et accès concurrents
@pytest.mark.exigence("EX14")
def test_meme_entree_meme_sortie(client, demande_valide):
    sorties = {
        client.post("/predict", json=demande_valide).json()["probabilite_defaut"] for _ in range(25)
    }
    assert len(sorties) == 1


@pytest.mark.exigence("EX14")
def test_predictions_concurrentes_identiques(service_modele):
    demandes = [PROFILS_BASE[i % 3] for i in range(300)]
    attendu = [probabilite(service_modele, d) for d in PROFILS_BASE]
    with ThreadPoolExecutor(max_workers=16) as pool:
        resultats = list(pool.map(lambda d: probabilite(service_modele, d), demandes))
    assert resultats == [attendu[i % 3] for i in range(300)]
