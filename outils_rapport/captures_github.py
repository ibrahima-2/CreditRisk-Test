"""Captures des runs GitHub Actions (dépôt public, sans connexion).

Usage : python outils_rapport/captures_github.py <url_run> <nom_fichier_sans_extension>
Sortie : reports/captures/<nom>.png
"""

from __future__ import annotations

import sys
from pathlib import Path

from playwright.sync_api import sync_playwright

RACINE = Path(__file__).resolve().parent.parent
SORTIE = RACINE / "reports" / "captures"


def main() -> None:
    url, nom = sys.argv[1], sys.argv[2]
    with sync_playwright() as p:
        navigateur = p.chromium.launch()
        page = navigateur.new_page(viewport={"width": 1280, "height": 900}, device_scale_factor=2)
        page.goto(url, wait_until="networkidle")
        page.wait_for_timeout(1500)
        # Bandeau de cookies éventuel
        for libelle in ("Accept", "Reject"):
            bouton = page.get_by_role("button", name=libelle)
            if bouton.count():
                bouton.first.click()
                break
        page.screenshot(path=str(SORTIE / f"{nom}.png"), full_page=True)
        navigateur.close()
    print(SORTIE / f"{nom}.png")


if __name__ == "__main__":
    main()
