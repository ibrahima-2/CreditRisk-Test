# CreditRisk-Test

Stratégie de test d'un prototype d'estimation du risque de défaut de remboursement
(microfinance) : API FastAPI, modèle scikit-learn, tests Pytest, intégration continue
GitHub Actions.

> **Données synthétiques.** Le jeu de données est simulé (`ml/donnees.py`, graine 42). Il
> sert à tester le système ; il ne démontre pas la performance réelle d'un modèle de crédit.

## Résultats en bref

| Indicateur | Valeur |
|---|---|
| Tests exécutés | 334 (333 réussis, 1 ignoré volontairement) |
| Couverture (lignes + branches) | 99,86 % (`app/` : 100 %) |
| Exigences couvertes | 22 / 22 (matrice générée : `reports/preuves/tracabilite.md`) |
| Anomalies détectées | 9 (4 corrigées, 5 ouvertes) : `reports/03_robustesse_registre_anomalies.md` |
| Inférence v1.0.0 | P95 = 0,11 ms |
| API, 10 utilisateurs simultanés | P95 = 7 ms ; débit max ≈ 1 900 req/s (1 processus) |

Le rapport de qualification (Word) est remis séparément et n'est pas versionné ici. Les
rapports par partie sont dans `reports/` (01 à 05).

## Architecture

```
requête JSON ─► validation.py ─► preprocessing.py ─► modèle (joblib) ─► prediction.py ─► réponse
                (schéma strict)   (variables dérivées)  (contrôle SHA-256,   (niveau de risque,
                                                         dimensions, sortie)   alertes, revue humaine)
```

| Module | Rôle |
|---|---|
| `app/validation.py` | Schéma Pydantic strict : bornes, types sans conversion implicite, champs inconnus refusés, NaN/Infinity refusés, cohérence âge/ancienneté |
| `app/preprocessing.py` | Variables du modèle (`log_revenu_mensuel`, `taux_endettement`, …), même code à l'entraînement et en production |
| `app/prediction.py` | Chargement contrôlé (empreinte SHA-256, dimensions, ordre des variables, seuils), contrat de sortie, orchestration |
| `app/main.py` | Endpoints, gestion des erreurs sans trace technique, identifiant de requête |
| `ml/` | Génération des données, entraînement reproductible, métriques, gel de la référence, comparaison de versions |

## Contrat de l'API

`POST /predict`

```json
{"age": 35, "revenu_mensuel": 250000, "montant_credit": 1000000, "duree_mois": 12, "anciennete_activite": 4}
```

Réponse 200 (extrait) : `probabilite_defaut` (0–1), `niveau_risque` (`FAIBLE` / `MODERE` / `ELEVE`),
`revue_humaine_requise`, `alertes` (`HORS_DOMAINE_*`), `indicateurs`, `seuils`, `version_modele`,
`identifiant_requete`.

| Situation | HTTP | `code` |
|---|---|---|
| Données hors contrat (manquantes, type, bornes, champ inconnu, NaN) | 422 | `DONNEES_INVALIDES` |
| JSON syntaxiquement invalide | 400 | `REQUETE_MAL_FORMEE` |
| Corps > 16 Kio | 413 | `REQUETE_TROP_VOLUMINEUSE` |
| Modèle absent, corrompu ou incompatible | 503 | `MODELE_INDISPONIBLE` |
| Échec du prétraitement / du modèle / erreur inattendue | 500 | `ERREUR_PRETRAITEMENT` / `ERREUR_PREDICTION` / `ERREUR_INTERNE` |

`GET /health` : 200 si le modèle est chargé, 503 sinon. `GET /model-info` : version, variables,
seuils, domaine d'entraînement, métriques, empreinte. Documentation interactive : `/docs`.

## Commandes

Prérequis : Python 3.12 ou 3.13.

```bash
python3 -m venv .venv && source .venv/bin/activate
pip install -r requirements.txt

uvicorn app.main:app --reload                       # API sur http://127.0.0.1:8000/docs

pytest                                              # suite complète
pytest --cov=app --cov=ml --cov-branch --cov-report=term-missing --cov-report=html --cov-fail-under=90
ruff check . && ruff format --check .               # qualité du code
TRACABILITE_SORTIE=reports/preuves/tracabilite pytest   # régénère la matrice de traçabilité
FORCER_ECHEC=1 pytest tests/test_echec_volontaire.py    # échec volontaire (code de sortie 1)
CREDIT_MODEL_PATH=model/credit_risk_v1.1.0.joblib pytest  # suite contre le modèle candidat
```

Reproduire les artefacts (déjà versionnés) :

```bash
python -m ml.donnees                  # data/train.csv, data/test_reference.csv
python -m ml.entrainement 1.0.0       # model/credit_risk_v1.0.0.{joblib,json}
python -m ml.entrainement 1.1.0       # modèle candidat
python -m ml.reference                # gèle la référence (à ne faire qu'une fois par référence)
python -m ml.comparaison model/credit_risk_v1.1.0.joblib   # rapport de non-régression (JSON)
```

Performance (outils optionnels : `pip install -r requirements-perf.txt`, ApacheBench `ab`) :

```bash
python scripts/benchmark_performance.py         # reports/performance/resultats_performance.json
uvicorn app.main:app --port 8000 &
locust -f scripts/locustfile.py --host http://127.0.0.1:8000 --headless \
       --csv reports/performance/locust --html reports/performance/locust.html
python scripts/graphiques_rapport.py            # reports/figures/*.png
```

## Intégration continue

`.github/workflows/tests.yml`, déclenché à chaque pull request, push sur `main` et à la demande :

- job **Qualité** : `ruff check` et `ruff format --check` ;
- job **Pytest** (Python 3.12 et 3.13) : tests, couverture minimale de 90 %, rapports JUnit,
  XML et HTML archivés, résumé dans l'onglet du run ;
- démonstration du blocage : *Actions › Tests › Run workflow* en cochant `forcer_echec`
  (active `tests/test_echec_volontaire.py`) ; le run doit apparaître en échec.

Les tests s'appuient sur le modèle versionné `model/credit_risk_v1.0.0.joblib` ; aucun
ré-entraînement complet n'est nécessaire à chaque modification.

Runs de référence (https://github.com/ibrahima-2/CreditRisk-Test/actions) :

| Run | Déclenchement | Ruff | Pytest 3.12 | Pytest 3.13 | Résultat |
|---|---|---|---|---|---|
| n° 1 | push sur `main` | réussi | réussi | réussi | 333 réussis, 1 ignoré, couverture 99,86 % |
| n° 2 | manuel, `forcer_echec` coché | réussi | échec | échec | `test_echec_volontaire` en échec, code de sortie 1 |

Extraits des journaux : `reports/preuves/ci_github_journaux.txt`.

## Organisation du dépôt

```
app/                 service (validation, prétraitement, prédiction, API)
ml/                  données, entraînement, évaluation, référence, comparaison
model/               artefacts versionnés + reference/ (référence gelée, tolérances)
data/                jeu synthétique versionné
tests/               test_validation, test_preprocessing, test_api, test_integration,
                     test_robustness, test_regression, test_performance, test_donnees,
                     test_tracabilite, test_echec_volontaire, exigences.py (catalogue)
scripts/             banc de performance, locustfile, figures
reports/             plan de test, rapports, preuves, captures, figures
outils_rapport/      génération des captures (Playwright) et du rapport Word (docx, non versionné)
.github/workflows/   tests.yml
```

Les captures de terminal du rapport sont des rendus des sorties réelles enregistrées dans
`reports/preuves/*.ansi`, mis en forme comme le terminal intégré de VS Code ; les captures
web (Swagger, couverture, Locust) sont prises dans un navigateur headless.

## Limites

Données synthétiques ; mesures de performance sur un poste local (Apple M4 Pro), client et
serveur sur la même machine ; pas d'authentification ni de limitation de débit (hors
périmètre du prototype).
