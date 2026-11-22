"""Contrôles de la chaîne de test elle-même : couverture des exigences et configuration CI."""

from __future__ import annotations

from pathlib import Path

import pytest

from tests.exigences import EXIGENCES

RACINE = Path(__file__).resolve().parent.parent
WORKFLOW = RACINE / ".github" / "workflows" / "tests.yml"
MODULES_DE_TEST = {p.name for p in (RACINE / "tests").glob("test_*.py")}


@pytest.mark.exigence("EX21")
def test_chaque_exigence_est_couverte_par_au_moins_un_test(request):
    modules_collectes = {Path(str(item.path)).name for item in request.session.items}
    if modules_collectes != MODULES_DE_TEST:
        pytest.skip("Vérification possible uniquement lors d'une exécution complète")
    couvertes = {
        exigence
        for item in request.session.items
        for marqueur in item.iter_markers("exigence")
        for exigence in marqueur.args
        if item.name != request.node.name
    }
    assert set(EXIGENCES) - couvertes == set()


@pytest.mark.exigence("EX21")
def test_workflow_ci_execute_lint_tests_et_couverture():
    contenu = WORKFLOW.read_text(encoding="utf-8")
    for attendu in ("pull_request", "ruff check", "ruff format --check", "pytest", "--cov",
                    "--cov-fail-under=90", "FORCER_ECHEC"):  # fmt: skip
        assert attendu in contenu, attendu


@pytest.mark.exigence("EX21")
def test_dependances_epinglees():
    """Environnement reproductible : chaque dépendance a une version exacte."""
    lignes = [
        ligne.strip()
        for ligne in (RACINE / "requirements.txt").read_text(encoding="utf-8").splitlines()
        if ligne.strip() and not ligne.startswith("#")
    ]
    assert lignes
    assert all("==" in ligne for ligne in lignes), [x for x in lignes if "==" not in x]
