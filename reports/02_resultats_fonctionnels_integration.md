# Résultats des tests fonctionnels et d'intégration

Exécution du 22/11/2026, modèle v1.0.0. Sortie brute : `reports/preuves/pytest_complet.txt`,
JUnit : `reports/preuves/junit.xml`.

| Fichier | Cas | Réussis | Échecs | Durée |
|---|---|---|---|---|
| `tests/test_api.py` | 53 | 53 | 0 | 0,15 s |
| `tests/test_integration.py` | 31 | 31 | 0 | 0,32 s |

## 1. Scénarios fonctionnels obligatoires (`tests/test_api.py`)

| N° | Scénario | Donnée testée | HTTP attendu | Contenu attendu | Comportement de l'application | Observé |
|---|---|---|---|---|---|---|
| S1 | Requête valide | D0 | 200 | `probabilite_defaut` ∈ [0, 1] (0,1094), `niveau_risque` MODERE, 9 champs | prédiction, en-têtes `X-Request-ID` et `X-Temps-Traitement-ms` | Conforme |
| S2 | Champ obligatoire absent | chacun des 5 champs ; `{}` | 422 | `DONNEES_INVALIDES`, `details[].type = missing` par champ | aucune prédiction, prétraitement non appelé | Conforme |
| S3 | Âge négatif | `age: -5` ; 17 ; 76 | 422 | `greater_than_equal`, « Doit être supérieur ou égal à 18. » | rejet avant le modèle | Conforme |
| S4 | Revenu en texte | `"250000"`, `"deux cent cinquante mille"`, `""` | 422 | `float_type` ; la valeur saisie n'est pas renvoyée | pas de conversion implicite (mode strict) | Conforme |
| S5 | Montant nul ou négatif | 0, -1, -1 000 000 | 422 | `greater_than` | rejet | Conforme |
| S6 | Durée non entière | 12.5, 12.0, `"12"` | 422 | `int_type` | 12.0 est aussi refusé : le contrat impose un entier JSON | Conforme |
| S7 | Champs supplémentaires | `nom`, `score_interne` ; `revenu` au lieu de `revenu_mensuel` | 422 | `extra_forbidden` sur chaque champ ; `missing` sur `revenu_mensuel` | aucune ignorance silencieuse | Conforme |
| S8 | Valeurs extrêmes | âge 10⁶ et 10³⁰, revenu 10¹² et 1e308, montant 10¹⁵, durée 10⁹, ancienneté 10⁶ | 422 | `less_than_equal` sur le champ | rejet sans dépassement numérique | Conforme |
| S9 | Modèle indisponible | artefact absent | 503 | `MODELE_INDISPONIBLE`, en-tête `Retry-After: 30` ; `/health` : `{"statut": "degrade", "modele_charge": false}` | démarrage en mode dégradé, nom du fichier non exposé ; une requête invalide reste en 422 | Conforme |
| S10 | Requête mal formée | JSON tronqué, guillemets simples, clés non citées | 400 | `REQUETE_MAL_FORMEE` |  | Conforme |
| S10 | Corps non objet | `[1,2,3]`, `"texte"`, `42`, `null` | 422 | `model_attributes_type` / `missing` |  | Conforme |
| S10 | Corps vide | `""` | 422 | `missing` sur `corps` | comportement retenu : corps vide = corps absent | Conforme |
| S10 | Corps > 16 Kio | champ de 16 385 caractères | 413 | `REQUETE_TROP_VOLUMINEUSE` | rejet avant lecture du corps | Conforme |
| S10 | Content-Type `text/plain` | `age=35&...` | 422 (415 serait plus précis) | `model_attributes_type` | écart consigné : anomalie AN-07 | Conforme au comportement documenté |

Autres contrôles : `/health` nominal (200), `/model-info` (version, variables, seuils, empreinte
égaux aux métadonnées), route inconnue (404 `RESSOURCE_INTROUVABLE`), `GET /predict`
(405 `METHODE_NON_AUTORISEE`, en-tête `Allow: POST`), propagation ou remplacement de
`X-Request-ID` (identifiant entrant accepté s'il respecte `[A-Za-z0-9-]{1,64}`).

Le test d'exemple de l'énoncé est repris à l'identique (`test_s1_exemple_de_l_enonce_sans_cycle_de_vie`).
Il crée `TestClient(app)` sans bloc `with`, donc sans événement de démarrage : le service charge
le modèle à la première requête.

## 2. Tests d'intégration (`tests/test_integration.py`)

### Scénario principal

Le pipeline réel est instrumenté par des espions sur `preprocessing.transformer` et
`ServiceModele.predire_lot`.

| Étape | Vérification | Observé |
|---|---|---|
| Ordre des appels | prétraitement → variables → modèle → probabilité | Conforme |
| Validation | le prétraitement reçoit les données typées (`age` entier, montants décimaux) | Conforme |
| Transformation | matrice = `[35, ln 250000, 12, 4, 1/3]` à 1e-12 près | Conforme |
| Prédiction | probabilité de l'API = `predict_proba` direct du modèle (écart ≤ 1e-12) | Conforme |
| Structure | niveau de risque, booléen de revue humaine | Conforme |
| Métadonnées | même version dans `/predict`, `/model-info`, `/health` ; empreinte = SHA-256 du fichier ; `n_features_in_` = 5 | Conforme |

Une requête invalide n'appelle ni le prétraitement ni le modèle.

### Scénarios complémentaires

| Scénario | Injection | Réponse attendue | Observé |
|---|---|---|---|
| Modèle non chargeable | 10 cas : artefact absent, corrompu, empreinte SHA-256 fausse, métadonnées absentes / illisibles / incomplètes, objet sans `predict_proba`, modèle à 4 variables, ordre des variables inversé, seuils incohérents | 503 `MODELE_INDISPONIBLE` ; `/health` 503 ; cause journalisée côté serveur, absente de la réponse | Conforme (10/10) |
| Restauration de l'artefact | fichier copié pendant que le service tourne | 503 puis 200, sans redémarrage | Conforme |
| Variable absente | `duree_mois` retiré | API : 422 ; appel interne sans validation : `ErreurPretraitement` explicite | Conforme |
| Erreur de prétraitement | exception contenant un chemin interne | 500 `ERREUR_PRETRAITEMENT` ; chemin absent de la réponse ; identifiant de requête présent dans les journaux | Conforme |
| Dimensions incompatibles | matrices (1,4), (1,6), (2,5), (5,), (0,5) | 500 `ERREUR_PREDICTION` | Conforme après correction de AN-01 |
| Erreur pendant la prédiction | `MemoryError` levée par le modèle | 500 `ERREUR_PREDICTION`, type d'exception journalisé | Conforme |
| Sortie du modèle non conforme | NaN, infini, hors [0,1], somme ≠ 1, 3 classes, tableau 1D | 500 ; aucune probabilité renvoyée | Conforme |
| Erreur inattendue (orchestration) | `KeyError` | 500 `ERREUR_INTERNE` | Conforme |
| Filet de sécurité global | métadonnées altérées après chargement | 500 `ERREUR_INTERNE` via le gestionnaire global | Conforme |

Toutes les réponses d'erreur sont contrôlées par `verifier_absence_trace` (motifs refusés :
`Traceback`, `File "`, `.py`, `/Users/`, `/home/`, `site-packages`, `Exception`, `Error(`).

### Défaut trouvé par ces tests

AN-01 : avec une matrice (2, 5) produite pour une demande unique, le service renvoyait la
prédiction de la première ligne avec un code 200. Correction : `predire_probabilite` exige une
matrice (1, n). Le test passe depuis la correction.
