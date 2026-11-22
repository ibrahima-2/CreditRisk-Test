"""Test volontairement défaillant, activé à la demande pour prouver que la CI bloque.

Activation locale :  FORCER_ECHEC=1 pytest tests/test_echec_volontaire.py
Activation GitHub :  onglet Actions > « Tests » > Run workflow > cocher « forcer_echec ».
"""

from __future__ import annotations

import os

import pytest


@pytest.mark.exigence("EX21")
@pytest.mark.skipif(os.environ.get("FORCER_ECHEC") != "1", reason="activé par FORCER_ECHEC=1")
def test_echec_volontaire():
    pytest.fail("Échec volontaire : le workflow doit apparaître en rouge")
