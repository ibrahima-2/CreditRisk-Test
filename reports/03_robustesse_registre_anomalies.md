# Tests de robustesse et registre des anomalies

`tests/test_robustness.py` : 129 cas, 129 réussis (profil Hypothesis `ci` : 60 exemples par
propriété, dérandomisé).

## 1. Entrées invalides et entrées inhabituelles

Règle appliquée :

- entrée **invalide** (hors contrat) : rejet contrôlé 4xx, jamais de 500 ;
- entrée **inhabituelle mais valide** (dans les bornes du contrat, hors de l'intervalle observé
  à l'entraînement) : réponse 200, alertes `HORS_DOMAINE_*`, `revue_humaine_requise = true`.

Domaine d'entraînement (v1.0.0) : âge 18–70 ; revenu 30 000–1 364 000 FCFA ; montant
50 000–19 800 000 FCFA ; durée 3–60 mois ; ancienneté 0–41 ans ; taux d'endettement 0,05–1,13.

## 2. Analyse par test

| Test | Risque visé | Comportement attendu | Résultat observé | Gravité | Correction recommandée |
|---|---|---|---|---|---|
| Valeurs manquantes : `null` sur chaque champ, tous à `null` | prédiction sur donnée imputée implicitement | 422, un détail par champ | 6/6 conformes |  |  |
| Valeurs non numériques : texte, `""`, `"35"`, `"1e3"`, chiffres arabes-indiens, liste, objet, `true`, `false` (×5 champs) | conversion implicite (`"35"` → 35, `true` → 1) | 422 | 45/45 conformes |  |  |
| Valeurs non finies en JSON brut : `NaN`, `Infinity`, `-Infinity`, `1e400`, `-1e400` (×5 champs) | le module `json` de Python accepte ces jetons hors norme ; NaN propagé jusqu'à la probabilité | 422 `finite_number` (décimaux) ou `int_type` (entiers) | 25/25 conformes |  | conserver `allow_inf_nan=False` (voir § 3, M1) |
| Valeurs aux limites (20 cas : min−ε, min, max, max+ε par champ) | erreur d'un sur les bornes | 200 sur la borne, 422 au-delà | 20/20 conformes |  |  |
| Ancienneté limite à 75 ans (60 / 60,5) | incohérence âge/ancienneté | 200 / 422 | conforme |  |  |
| Hors domaine valide (75 ans et 60 ans d'ancienneté ; revenu 20 M ; montant 400 M ; revenu 1 000 FCFA ; 120 mois) | extrapolation silencieuse | 200 + alertes + revue humaine | 5/5 conformes |  |  |
| Probabilité saturée hors domaine | score « certain » (0,0 ou 1,0) sur un profil jamais vu | jamais sans alerte | conforme, mais saturation observée (AN-02) | Majeure | voir AN-02 |
| Schéma incorrect : liste, objet imbriqué, clés en casse différente, chaîne, nombre | mauvaise intégration client | 422 | 5/5 conformes |  |  |
| Clé dupliquée (`"age"` répété) | ambiguïté de parsing | dernière valeur retenue puis validée | conforme (`age: -1` rejeté) |  |  |
| Chaîne de 10 000 caractères | consommation mémoire, 500 | 422 | conforme |  |  |
| Propriété : toute demande valide générée → 200 et p ∈ [0, 1] | cas non anticipés | aucune exception | conforme |  |  |
| Propriété : tout dictionnaire arbitraire → 200 ou 422, jamais 500 | erreur non gérée | aucune trace | conforme |  |  |
| Monotonie : montant ↑, revenu ↑, ancienneté ↑ (3 profils) | modèle incohérent avec le métier | p non décroissante / non croissante | 9/9 conformes |  | revalider à chaque nouvelle version (le candidat v1.1.0 impose ces contraintes par construction) |
| Invariance : ordre des champs, 250000 vs 250000.0 | dépendance à la forme | même probabilité | conforme |  |  |
| Répétition (25 appels) et concurrence (300 appels, 16 threads) | état partagé, non-déterminisme | sorties identiques | conforme |  |  |

## 3. Efficacité de la suite : essais de mutation

Pour vérifier que la suite détecte réellement des défauts, deux versions volontairement
faussées du code ont été testées dans une copie du projet (sorties :
`reports/preuves/mutation_m1.ansi`, `mutation_m2.ansi`).

| Mutation | Modification | Tests en échec | Ce qui serait passé sans ces tests |
|---|---|---|---|
| M1 | schéma Pydantic en configuration par défaut (sans `extra="forbid"`, `strict=True`, `allow_inf_nan=False`) et contrôle âge/ancienneté désactivé | 43 / 256 (API, robustesse, validation) | `"250000"`, `12.0`, `"12"` et un champ inconnu acceptés (200) ; ancienneté de 30 ans à 35 ans acceptée avec p = 0,004 (profil très favorable fondé sur une donnée impossible) ; NaN rejeté seulement par effet de bord de la borne max, avec un message trompeur (« Doit être inférieur ou égal à 50000000 ») |
| M2 | taux d'endettement calculé `montant / (12 × revenu)` au lieu de `montant / (durée × revenu)` | 9 / 334 après correction de la suite (5 avant) | AUC 0,705 (< 0,756), F1 0,315 (< 0,325), Brier 0,172 ; le rappel restait dans la tolérance |

M2 a révélé une faiblesse de la suite (AN-06) : le seul exemple de test unitaire du prétraitement
avait une durée de 12 mois, valeur pour laquelle la formule fausse et la formule juste
coïncident. Trois cas à 24, 6 et 1 mois ont été ajoutés ; ils détectent désormais la mutation.

## 4. Registre des anomalies

Gravité : **Critique** (décision erronée sans signalement, fuite de données), **Majeure**
(résultat faux ou non fiable dans des cas identifiables), **Mineure** (écart au contrat sans
effet sur la décision).

| ID | Composant | Description | Détection | Gravité | Statut | Correction |
|---|---|---|---|---|---|---|
| AN-01 | Prédiction | Une matrice (2, 5) produite pour une demande unique renvoyait la prédiction de la 1ʳᵉ ligne avec un code 200 | `test_dimensions_produites_incompatibles[forme2]` | Majeure | Corrigée | `predire_probabilite` exige une matrice (1, n) ; re-test conforme |
| AN-02 | Modèle | Hors domaine, la régression logistique extrapole et renvoie exactement 0,0 ou 1,0 (G03 : 1,0 ; G05 : 0,0 ; G09 : 1,0 ; G10 : 1,0) | profils de référence, `test_probabilite_saturee_toujours_signalee` | Majeure | Ouverte, atténuée (alertes + revue humaine systématiques) | Plafonner le taux d'endettement au domaine observé avant le modèle, ou refuser au-delà d'un domaine élargi ; afficher « hors domaine » à la place du score |
| AN-03 | Modèle (équité) | Taux de faux négatifs très inégal selon l'âge : 2,3 % (18–25 ans) ; 15,4 % (26–40) ; 32,7 % (41–55) ; 66,7 % (56+, 2 défauts sur 3, non significatif). Même tendance par revenu : 9,8 % (tercile bas) à 30,6 % (tercile haut) | `metriques_par_segment` ; `test_taux_de_faux_negatifs_par_segment` passe (32,7 % < 35 %) | Majeure ; bloquante pour une mise en production | Ouverte | Faire définir par le métier et la conformité un écart maximal entre segments ; recalibrer ou fixer des seuils par segment ; réévaluer sur données réelles |
| AN-04 | Non-régression | Candidat v1.1.0 hors tolérance sur les profils de référence : écart moyen 0,060 (> 0,05), écart max 0,760 sur G09 (> 0,20) ; G07 (120 mois) passe de MODÉRÉ à FAIBLE | `test_profils_de_reference_dans_les_tolerances` avec `CREDIT_MODEL_PATH=v1.1.0` | Majeure | Ouverte : candidat rejeté | Ne pas déployer v1.1.0 ; le gradient boosting reste constant hors domaine, ce qui sous-estime le risque des profils extrêmes |
| AN-05 | Performance | v1.1.0 : inférence P95 11,2 ms (objectif 10 ms) avec les threads OpenMP par défaut, 0,41 ms limité à 1 thread ; contrôle CI instable (échec à 2 exécutions sur 3) | banc de performance, `test_latence_inference_p95` | Mineure | Ouverte (candidat non déployé) | Limiter OpenMP à 1 thread en service (`OMP_NUM_THREADS=1` ou `threadpoolctl`) |
| AN-06 | Suite de tests | Mutation M2 non détectée par les tests unitaires du prétraitement | essai de mutation | Majeure (faiblesse du test) | Corrigée | 3 cas avec durée ≠ 12 mois |
| AN-07 | API | Content-Type `text/plain` : 422 au lieu de 415 | `test_s10_content_type_non_json` | Mineure | Ouverte | Vérifier le Content-Type et renvoyer 415 |
| AN-08 | API | Messages 404 et 405 en anglais (« Method Not Allowed »), seuls messages non traduits | observation pendant les captures `curl` | Mineure | Corrigée | Messages français + assertion dans `test_methode_non_autorisee` |
| AN-09 | Protocole de test | Le premier générateur de charge (client httpx asynchrone, un processus Python) saturait avant le serveur : P95 de 166 ms à 20 utilisateurs contre 14 ms mesurés avec ApacheBench | comparaison `/health` vs `/predict`, 1 vs 4 processus, httpx vs `ab` | Sans objet (anomalie de mesure, pas du produit) | Corrigée | ApacheBench retenu comme référence ; mesures biaisées conservées dans `reports/performance/biais_*.json` |
