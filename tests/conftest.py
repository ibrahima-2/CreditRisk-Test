"""Fixtures partagées et génération de la matrice de traçabilité exigences -> tests."""

from __future__ import annotations

import json
import os
import re
from collections import defaultdict
from pathlib import Path

import pytest
from fastapi.testclient import TestClient
from hypothesis import settings

from app.main import create_app
from app.prediction import ServiceModele
from tests.exigences import EXIGENCES

# Profils Hypothesis : « ci » est dérandomisé pour des exécutions reproductibles.
settings.register_profile("ci", max_examples=60, derandomize=True, deadline=None)
settings.register_profile("dev", max_examples=150, deadline=None)
settings.load_profile(os.environ.get("HYPOTHESIS_PROFILE", "dev"))

DEMANDE_VALIDE = {
    "age": 35,
    "revenu_mensuel": 250000,
    "montant_credit": 1000000,
    "duree_mois": 12,
    "anciennete_activite": 4,
}

CHAMPS_REPONSE_PREDICTION = {
    "probabilite_defaut",
    "niveau_risque",
    "revue_humaine_requise",
    "alertes",
    "indicateurs",
    "seuils",
    "version_modele",
    "identifiant_requete",
    "avertissement",
}

# Motifs qui ne doivent jamais apparaître dans une réponse envoyée au client.
_MOTIFS_TRACE = re.compile(
    r"Traceback|File \"|\.py\b|/Users/|/home/|site-packages|Exception|Error\(", re.IGNORECASE
)


def verifier_absence_trace(reponse) -> None:
    """Échoue si la réponse contient une trace technique (pile, chemin, nom d'exception)."""
    trouve = _MOTIFS_TRACE.search(reponse.text)
    assert trouve is None, f"Trace technique exposée : {trouve.group(0)!r} dans {reponse.text}"


@pytest.fixture
def demande_valide() -> dict:
    return dict(DEMANDE_VALIDE)


@pytest.fixture(scope="session")
def service_modele() -> ServiceModele:
    service = ServiceModele.depuis_config()
    service.charger()
    return service


@pytest.fixture(scope="session")
def metadonnees(service_modele) -> dict:
    return service_modele.metadonnees


@pytest.fixture(scope="session")
def client(service_modele):
    with TestClient(create_app(service_modele)) as c:
        yield c


@pytest.fixture
def fabrique_client():
    """Crée des clients sur des applications dont le service de modèle est injecté.

    ``raise_server_exceptions=False`` : on observe la réponse HTTP exactement comme un
    client réel la recevrait, y compris en cas d'erreur 500.
    """
    ouverts = []

    def _fabrique(service: ServiceModele) -> TestClient:
        c = TestClient(create_app(service), raise_server_exceptions=False)
        c.__enter__()
        ouverts.append(c)
        return c

    yield _fabrique
    for c in ouverts:
        c.__exit__(None, None, None)


# --------------------------------------------------------------- matrice de traçabilité
_EXIGENCES_PAR_TEST: dict[str, list[str]] = {}
_RESULTATS: dict[str, str] = {}


def pytest_configure(config):
    config.addinivalue_line("markers", "exigence(*ids): exigence(s) vérifiée(s) par le test")
    config.addinivalue_line("markers", "performance: mesure de performance légère")


def pytest_collection_modifyitems(config, items):
    for item in items:
        ids = [i for m in item.iter_markers("exigence") for i in m.args]
        inconnues = set(ids) - EXIGENCES.keys()
        if inconnues:
            raise pytest.UsageError(f"{item.nodeid} : exigence(s) inconnue(s) {inconnues}")
        _EXIGENCES_PAR_TEST[item.nodeid] = ids


def pytest_runtest_logreport(report):
    if report.when == "call" or (report.when == "setup" and report.outcome != "passed"):
        _RESULTATS[report.nodeid] = "xfailed" if hasattr(report, "wasxfail") else report.outcome


def pytest_sessionfinish(session, exitstatus):
    sortie = os.environ.get("TRACABILITE_SORTIE")
    if not sortie or not _RESULTATS:
        return
    par_exigence: dict[str, dict[str, dict[str, int]]] = defaultdict(dict)
    for nodeid, ids in _EXIGENCES_PAR_TEST.items():
        resultat = _RESULTATS.get(nodeid)
        if resultat is None:
            continue
        fonction = nodeid.split("[")[0]
        for exigence in ids:
            compte = par_exigence[exigence].setdefault(
                fonction, {"passed": 0, "failed": 0, "skipped": 0, "xfailed": 0}
            )
            compte[resultat] = compte.get(resultat, 0) + 1
    chemin = Path(sortie)
    chemin.parent.mkdir(parents=True, exist_ok=True)
    chemin.with_suffix(".json").write_text(
        json.dumps(par_exigence, indent=2, ensure_ascii=False), encoding="utf-8"
    )
    lignes = [
        "| ID | Exigence | Priorité | Fonctions de test | Cas exécutés | Réussis | Échecs "
        "| Statut |",
        "|---|---|---|---|---|---|---|---|",
    ]
    for exigence, info in EXIGENCES.items():
        tests = par_exigence.get(exigence, {})
        reussis = sum(c["passed"] for c in tests.values())
        echecs = sum(c["failed"] for c in tests.values())
        executes = sum(sum(c.values()) for c in tests.values())
        statut = "NON COUVERTE" if not tests else ("ÉCHEC" if echecs else "CONFORME")
        lignes.append(
            f"| {exigence} | {info['libelle']} | {info['priorite']} | {len(tests)} | "
            f"{executes} | {reussis} | {echecs} | {statut} |"
        )
    lignes += ["", "## Détail des tests par exigence", ""]
    for exigence in EXIGENCES:
        lignes.append(f"**{exigence}** — {EXIGENCES[exigence]['libelle']}")
        for fonction, c in sorted(par_exigence.get(exigence, {}).items()):
            lignes.append(
                f"- `{fonction}` : {c['passed']} réussi(s), {c['failed']} échec(s), "
                f"{c['skipped']} ignoré(s)"
            )
        lignes.append("")
    chemin.with_suffix(".md").write_text("\n".join(lignes), encoding="utf-8")
