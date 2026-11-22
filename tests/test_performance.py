"""Contrôles de performance légers, exécutés à chaque intégration continue.

Ils détectent une dégradation grossière (ex. modèle 100 fois plus lent). La mesure
détaillée (P95, débit, charge progressive) est faite par ``scripts/benchmark_performance.py``
et documentée dans ``reports/05_rapport_performance.md``.
"""

from __future__ import annotations

import time

import numpy as np
import pytest

from app import preprocessing

OBJECTIF_INFERENCE_P95_MS = 10.0
OBJECTIF_API_P95_MS = 200.0


def p95(durees_s: list[float]) -> float:
    return float(np.percentile(np.array(durees_s) * 1000, 95))


@pytest.mark.performance
@pytest.mark.exigence("EX19")
def test_latence_inference_p95(service_modele, demande_valide):
    matrice = preprocessing.transformer(demande_valide)
    for _ in range(20):  # préchauffage
        service_modele.predire_probabilite(matrice)
    durees = []
    for _ in range(500):
        debut = time.perf_counter()
        service_modele.predire_probabilite(matrice)
        durees.append(time.perf_counter() - debut)
    assert p95(durees) <= OBJECTIF_INFERENCE_P95_MS


@pytest.mark.performance
@pytest.mark.exigence("EX19")
def test_latence_api_p95_sequentielle(client, demande_valide):
    for _ in range(10):
        client.post("/predict", json=demande_valide)
    durees = []
    for _ in range(200):
        debut = time.perf_counter()
        reponse = client.post("/predict", json=demande_valide)
        durees.append(time.perf_counter() - debut)
        assert reponse.status_code == 200
    assert p95(durees) <= OBJECTIF_API_P95_MS
