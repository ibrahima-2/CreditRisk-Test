"""Génération et chargement du jeu de données SYNTHÉTIQUE.

AVERTISSEMENT : ces données sont simulées. Elles servent uniquement à tester le
système (validation, pipeline, API, non-régression). Elles ne permettent PAS de
démontrer la performance réelle d'un modèle de risque de crédit.

Mécanisme de simulation (documenté pour la traçabilité) :
- âge ~ N(38, 10) borné à [18, 70] ; ancienneté ~ Exp(5 ans) bornée à âge - 16 ;
- revenu ~ log-normale centrée sur 200 000 FCFA, borné à [30 000 ; 3 000 000] ;
- durée tirée parmi 3 à 60 mois ; montant = taux d'endettement visé x revenu x durée ;
- défaut ~ Bernoulli(sigmoïde(score)), le score augmentant avec l'endettement et la
  durée, diminuant avec l'âge, l'ancienneté et le revenu.
"""

from __future__ import annotations

import csv
from pathlib import Path

import numpy as np

GRAINE = 42
N_OBSERVATIONS = 6_000
PART_TEST = 0.25
REPERTOIRE_DONNEES = Path(__file__).resolve().parent.parent / "data"
FICHIER_TRAIN = "train.csv"
FICHIER_TEST = "test_reference.csv"

COLONNES_ENTREE = ("age", "revenu_mensuel", "montant_credit", "duree_mois", "anciennete_activite")
CIBLE = "defaut"

_DUREES = np.array([3, 6, 9, 12, 18, 24, 36, 48, 60])
_PROBA_DUREES = np.array([0.06, 0.14, 0.10, 0.25, 0.15, 0.15, 0.09, 0.04, 0.02])


def generer(n: int = N_OBSERVATIONS, graine: int = GRAINE) -> dict[str, np.ndarray]:
    """Génère ``n`` demandes synthétiques et leur cible ``defaut`` (1 = défaut)."""
    rng = np.random.default_rng(graine)
    age = np.clip(rng.normal(38, 10, n).round(), 18, 70).astype(int)
    anciennete = np.clip(np.minimum(rng.exponential(5.0, n), age - 16), 0, None).round(1)
    revenu = np.clip(np.exp(rng.normal(np.log(200_000), 0.6, n)), 30_000, 3_000_000).round(-3)
    duree = rng.choice(_DUREES, n, p=_PROBA_DUREES)
    taux_vise = np.clip(rng.lognormal(np.log(0.25), 0.45, n), 0.03, 1.2)
    montant = np.clip(taux_vise * revenu * duree, 50_000, 20_000_000).round(-4)
    taux_endettement = montant / (duree * revenu)
    score = (
        -2.3
        + 6.0 * (taux_endettement - 0.30)
        - 0.06 * (age - 38)
        - 0.15 * (anciennete - 4)
        + 0.02 * (duree - 12)
        - 0.9 * np.log(revenu / 200_000)
    )
    defaut = (rng.random(n) < 1.0 / (1.0 + np.exp(-score))).astype(int)
    return {
        "age": age,
        "revenu_mensuel": revenu,
        "montant_credit": montant,
        "duree_mois": duree,
        "anciennete_activite": anciennete,
        CIBLE: defaut,
    }


def separer(donnees: dict[str, np.ndarray], part_test: float = PART_TEST, graine: int = GRAINE):
    """Séparation stratifiée apprentissage / test, reproductible."""
    rng = np.random.default_rng(graine + 1)
    y = donnees[CIBLE]
    index_test = []
    for classe in (0, 1):
        index = np.flatnonzero(y == classe)
        rng.shuffle(index)
        index_test.extend(index[: round(len(index) * part_test)])
    masque_test = np.zeros(len(y), dtype=bool)
    masque_test[index_test] = True
    train = {k: v[~masque_test] for k, v in donnees.items()}
    test = {k: v[masque_test] for k, v in donnees.items()}
    return train, test


def ecrire_csv(donnees: dict[str, np.ndarray], chemin: Path) -> None:
    colonnes = (*COLONNES_ENTREE, CIBLE)
    with Path(chemin).open("w", newline="", encoding="utf-8") as fichier:
        ecrivain = csv.writer(fichier)
        ecrivain.writerow(colonnes)
        for ligne in zip(*(donnees[c] for c in colonnes), strict=True):
            ecrivain.writerow([_formater(v) for v in ligne])


def _formater(valeur) -> str:
    valeur = float(valeur)
    return str(int(valeur)) if valeur.is_integer() else repr(valeur)


def charger_csv(chemin: Path) -> tuple[dict[str, np.ndarray], np.ndarray]:
    """Charge un fichier CSV et renvoie (colonnes d'entrée, cible)."""
    with Path(chemin).open(encoding="utf-8") as fichier:
        lignes = list(csv.DictReader(fichier))
    colonnes = {c: np.array([float(ligne[c]) for ligne in lignes]) for c in COLONNES_ENTREE}
    cible = np.array([int(ligne[CIBLE]) for ligne in lignes])
    return colonnes, cible


def main() -> None:  # pragma: no cover - script
    REPERTOIRE_DONNEES.mkdir(exist_ok=True)
    train, test = separer(generer())
    ecrire_csv(train, REPERTOIRE_DONNEES / FICHIER_TRAIN)
    ecrire_csv(test, REPERTOIRE_DONNEES / FICHIER_TEST)
    for nom, jeu in (("train", train), ("test", test)):
        print(f"{nom}: {len(jeu[CIBLE])} lignes, taux de défaut = {jeu[CIBLE].mean():.3f}")


if __name__ == "__main__":  # pragma: no cover
    main()
