# Plan de test et matrice de traçabilité

Système : CreditRisk API v1.0.0, modèle `credit-risk` v1.0.0 (régression logistique).
Date : 22/11/2026.

## 1. Objet et périmètre

Vérifier que le système (validation, prétraitement, modèle, API) respecte ses exigences
fonctionnelles et techniques avant une éventuelle phase pilote.

Dans le périmètre : contrat des trois endpoints, gestion des entrées invalides et des pannes,
cohérence et reproductibilité des prédictions, non-régression du code et du modèle,
performance locale, automatisation CI.

Hors périmètre : performance réelle du modèle (données synthétiques), sécurité réseau
(authentification, TLS, limitation de débit), conformité réglementaire, interface de l'agent.

## 2. Approche

| Niveau | Fichier | Techniques |
|---|---|---|
| Unitaire | `test_validation.py`, `test_preprocessing.py`, `test_donnees.py` | partitions d'équivalence, valeurs limites, calcul manuel des variables dérivées |
| Fonctionnel (API) | `test_api.py` | 10 scénarios obligatoires, contrat de réponse, codes HTTP |
| Intégration | `test_integration.py` | espions sur le pipeline réel, injection de pannes (artefact, prétraitement, modèle) |
| Robustesse | `test_robustness.py` | valeurs limites, JSON brut (NaN, Infinity), tests de propriétés (Hypothesis), tests métamorphiques (monotonie), concurrence |
| Non-régression | `test_regression.py` | référence gelée (30 profils), tolérances versionnées, « test du test » par dégradation simulée |
| Performance | `test_performance.py`, `scripts/benchmark_performance.py`, `scripts/locustfile.py` | P95, débit, charge progressive |
| Chaîne de test | `test_tracabilite.py`, `test_echec_volontaire.py` | couverture des exigences, configuration CI, blocage sur échec |

Efficacité de la suite : deux essais de mutation (code volontairement faussé) ont été réalisés
(voir rapport 03, § 3).

## 3. Environnement

macOS 15 (Darwin 24.6), Apple M4 Pro, 12 cœurs, 24 Go ; Python 3.13.5 ; FastAPI 0.165.0 ;
Pydantic 2.14.4 ; scikit-learn 1.9.1 ; Pytest 9.2.0 ; Hypothesis 6.170.17 ; Ruff 0.17.6.
CI : runners `ubuntu-latest`, Python 3.12 et 3.13.

## 4. Critères

- Entrée : dépendances installées depuis `requirements.txt` ; artefact v1.0.0 et référence
  gelée présents ; tolérances de non-régression versionnées avant toute comparaison.
- Sortie : 0 échec sur les exigences P1 ; couverture ≥ 90 % ; Ruff sans erreur ; toute anomalie
  ouverte qualifiée (gravité, correction recommandée).

## 5. Analyse des risques et priorisation

La priorité découle de la gravité des conséquences d'une défaillance :

| Priorité | Définition | Exigences |
|---|---|---|
| P1 critique | décision erronée, fuite d'information, panne non signalée | EX01, EX02, EX04, EX05, EX06, EX07, EX11, EX13, EX14, EX17, EX20, EX22 |
| P2 majeure | donnée incohérente acceptée, perte de traçabilité | EX03, EX08, EX09, EX10, EX12, EX15, EX16, EX18, EX21 |
| P3 mineure | confort d'usage, performance hors usage nominal | EX19 |

Les tests P1 sont exécutés à chaque PR (comme l'ensemble de la suite : 4,5 s).

## 6. Matrice de traçabilité

Les 7 premières exigences sont celles de l'énoncé ; EX08 à EX22 sont ajoutées. Les colonnes
« cas exécutés » et « statut » sont produites automatiquement par `tests/conftest.py` à partir
des marqueurs `@pytest.mark.exigence` (fichier source : `reports/preuves/tracabilite.md`).

| ID | Exigence | Résultat attendu | Risque visé | Prio. | Cas de test | Cas exécutés | Statut |
|---|---|---|---|---|---|---|---|
| EX01 | Âge entier dans [18, 75] | Hors limites rejeté (422) | Évaluation d'un mineur ou d'un profil impossible | P1 | CT-01, CT-11, CT-21 | 45 | Conforme |
| EX02 | Revenu numérique, fini, > 0, ≤ 50 M FCFA | Erreur contrôlée (422) | Division par zéro, log négatif, 500 | P1 | CT-02, CT-12, CT-21 | 50 | Conforme |
| EX03 | Durée entière dans [1, 120] | 12.5, 0, 121, "12" rejetés | Mensualité faussée | P2 | CT-03, CT-14 | 46 | Conforme |
| EX04 | Probabilité valide | Finie, dans [0, 1] | Décision sur score aberrant | P1 | CT-10, CT-24, CT-30 | 35 | Conforme |
| EX05 | Modèle disponible, indisponibilité signalée | 503 + `/health` dégradé | Erreur opaque, réponse fausse | P1 | CT-17, CT-25, CT-26 | 17 | Conforme |
| EX06 | Entrée incomplète validée | 422 listant chaque champ manquant | Prédiction sur données partielles | P1 | CT-04, CT-11, CT-20 | 26 | Conforme |
| EX07 | Nouvelle version sans dégradation critique | Métriques et profils dans les tolérances | Hausse des défauts non détectés | P1 | CT-33 à CT-37 | 14 | Conforme |
| EX08 | Montant > 0 et ≤ 500 M FCFA | Rejet 422 | Endettement nul ou absurde | P2 | CT-05, CT-13 | 42 | Conforme |
| EX09 | Ancienneté ≥ 0, ≤ 60, ≤ âge − 14 | Rejet 422 `incoherence_anciennete_age` | Données contradictoires | P2 | CT-06 | 39 | Conforme |
| EX10 | Champs non prévus refusés | 422 `extra_forbidden` | Faute de frappe masquée | P2 | CT-07, CT-15 | 8 | Conforme |
| EX11 | NaN, Infinity, booléens, nombres en texte refusés | 422 | NaN propagé jusqu'à la probabilité | P1 | CT-08, CT-22 | 103 | Conforme |
| EX12 | Requête mal formée contrôlée | 400 / 422 / 413 | 500, déni de service | P2 | CT-18, CT-31 | 21 | Conforme |
| EX13 | Aucune trace technique exposée | 500 générique + identifiant | Fuite d'information | P1 | CT-27, CT-28, CT-31 | 38 | Conforme |
| EX14 | Reproductibilité | Mêmes sorties : répétition, sauvegarde/rechargement, ré-entraînement | Décisions non auditables | P1 | CT-32, CT-38, CT-39 | 13 | Conforme |
| EX15 | Hors domaine valide signalé | 200 + `HORS_DOMAINE_*` + revue humaine | Extrapolation silencieuse | P2 | CT-23 | 11 | Conforme |
| EX16 | `/model-info` fidèle à l'artefact | Version, seuils, métriques, empreinte cohérents | Audit impossible | P2 | CT-19, CT-35 | 5 | Conforme |
| EX17 | Intégrité et compatibilité de l'artefact | SHA-256, dimensions, variables vérifiés | Modèle corrompu ou substitué | P1 | CT-25 | 12 | Conforme |
| EX18 | Monotonie métier | Montant ↑ ⇒ p ↑ ; revenu ou ancienneté ↑ ⇒ p ↓ | Modèle incohérent | P2 | CT-29 | 11 | Conforme |
| EX19 | Performance | Inférence P95 ≤ 10 ms ; API P95 ≤ 200 ms à 10 utilisateurs | Attente au guichet | P3 | CT-40 | 2 | Conforme |
| EX20 | Contrat de réponse `/predict` | Champs, types, niveau cohérent avec seuils | Rupture d'intégration | P1 | CT-10, CT-24, CT-34 | 10 | Conforme |
| EX21 | Automatisation | Ruff + Pytest + couverture ≥ 90 % par PR ; échec bloquant | Régression livrée | P2 | CT-41, CT-42 | 4 (1 ignoré) | Conforme |
| EX22 | Prétraitement conforme au modèle | Ordre, dimension (n, 5), valeurs identiques entraînement/production | Écart entraînement/production | P1 | CT-09, CT-27 | 22 | Conforme |

## 7. Cas de test

Précondition commune : API démarrée avec le modèle v1.0.0 (sauf mention).
Demande nominale `D0` = `{age: 35, revenu_mensuel: 250000, montant_credit: 1000000, duree_mois: 12, anciennete_activite: 4}`.

| ID | Exigence | Précondition | Données d'entrée | Résultat attendu | Fonction Pytest |
|---|---|---|---|---|---|
| CT-01 | EX01 |  | âge -5, 0, 17, 18, 19, 74, 75, 76, 150 | valides : 18 à 75 | `test_validation::test_bornes_age` |
| CT-02 | EX02 |  | revenu -1, 0, 0,01, 1, 50 M, 50 M + 1 | valides : ]0 ; 50 M] | `test_validation::test_bornes_revenu` |
| CT-03 | EX03 |  | durée 12.5, 12.0, "12", true | `int_type` | `test_validation::test_duree_non_entiere_rejetee` |
| CT-04 | EX06 |  | D0 privé d'un champ (×5) ; `{}` | `missing` sur le champ ; 5 erreurs | `test_validation::test_champ_manquant`, `test_demande_vide_liste_tous_les_champs` |
| CT-05 | EX08 |  | montant -1 M, -1, 0, 1, 500 M, 500 M + 1 | valides : ]0 ; 500 M] | `test_validation::test_bornes_montant` |
| CT-06 | EX09 |  | (35, 21) valide ; (35, 21,1) ; (18, 4,5) ; (75, 61) rejetés | `incoherence_anciennete_age` | `test_validation::test_coherence_anciennete_age` |
| CT-07 | EX10 |  | D0 + `nom` | `extra_forbidden` | `test_validation::test_champ_supplementaire_refuse` |
| CT-08 | EX11 |  | NaN, +inf, -inf sur les champs décimaux | `finite_number` | `test_validation::test_valeurs_non_finies_refusees` |
| CT-09 | EX22 |  | D0 ; durées 24, 6, 1 | matrice `[35, ln 250000, 12, 4, 1/3]` ; taux = montant / (durée × revenu) | `test_preprocessing::test_transformation_valeurs_attendues`, `test_taux_endettement_pour_des_durees_differentes_de_12` |
| CT-10 | EX04, EX20 |  | POST D0 | 200, 9 champs, p ∈ [0, 1], niveau cohérent avec les seuils | `test_api::test_s1_requete_valide` |
| CT-11 | EX06, EX01 |  | S2 : champ absent ; S3 : âge -5 | 422 `missing` ; 422 `greater_than_equal` | `test_api::test_s2_*`, `test_s3_*` |
| CT-12 | EX02 |  | S4 : revenu "250000", texte, "" | 422 `float_type` | `test_api::test_s4_revenu_texte` |
| CT-13 | EX08 |  | S5 : montant 0, -1, -1 M | 422 `greater_than` | `test_api::test_s5_montant_nul_ou_negatif` |
| CT-14 | EX03 |  | S6 : durée 12.5, 12.0, "12" | 422 `int_type` | `test_api::test_s6_duree_non_entiere` |
| CT-15 | EX10 |  | S7 : D0 + `nom`, `score_interne` ; `revenu` au lieu de `revenu_mensuel` | 422 sur chaque champ | `test_api::test_s7_*` |
| CT-16 | EX01-03, 08 |  | S8 : âge 10³⁰, revenu 1e308, durée 10⁹… | 422 `less_than_equal` | `test_api::test_s8_valeurs_extremement_elevees` |
| CT-17 | EX05 | modèle absent | S9 : POST D0, GET /health, /model-info | 503 `MODELE_INDISPONIBLE`, `Retry-After: 30` | `test_api::test_s9_*` |
| CT-18 | EX12 |  | S10 : JSON tronqué, guillemets simples, corps vide, liste, > 16 Kio, text/plain | 400 / 422 / 413 | `test_api::test_s10_*` |
| CT-19 | EX16 |  | GET /model-info | version, variables, seuils, empreinte = métadonnées | `test_api::test_model_info` |
| CT-20 | EX06 |  | null sur chaque champ | 422 | `test_robustness::test_valeur_nulle` |
| CT-21 | EX01-09 |  | 20 valeurs limites (min-ε, min, max, max+ε) | 200 ou 422 selon la borne | `test_robustness::test_valeurs_aux_limites` |
| CT-22 | EX11 |  | NaN, Infinity, -Infinity, 1e400 en JSON brut (×5 champs) ; 9 types non numériques (×5) | 422 | `test_robustness::test_valeur_non_finie`, `test_valeur_non_numerique` |
| CT-23 | EX15 |  | 5 profils valides hors domaine | 200 + alertes + revue humaine | `test_robustness::test_hors_domaine_accepte_avec_alerte` |
| CT-24 | EX04, EX20 |  | demandes valides générées (Hypothesis) | 200, p finie dans [0, 1] | `test_robustness::test_propriete_toute_demande_valide_donne_une_probabilite` |
| CT-25 | EX05, EX17 | artefact altéré (10 cas) | absent, corrompu, empreinte fausse, métadonnées absentes / illisibles / incomplètes, objet sans `predict_proba`, 4 variables, ordre inversé, seuils invalides | 503, détail journalisé côté serveur uniquement | `test_integration::test_modele_non_chargeable` |
| CT-26 | EX05 | artefact absent puis restauré | POST D0 avant / après restauration | 503 puis 200 sans redémarrage | `test_integration::test_rechargement_automatique_apres_restauration` |
| CT-27 | EX22, EX13 | prétraitement remplacé | matrices (1,4), (1,6), (2,5), (5,), (0,5) | 500 `ERREUR_PREDICTION` | `test_integration::test_dimensions_produites_incompatibles` |
| CT-28 | EX13 | modèle factice | `MemoryError`, `KeyError`, ErreurPretraitement avec chemin interne | 500 générique ; chemin absent de la réponse, présent dans les journaux | `test_integration::test_exception_pendant_la_prediction`, `test_erreur_de_pretraitement`, `test_erreur_inattendue_dans_l_orchestration` |
| CT-29 | EX18 |  | 3 profils × montant, revenu, ancienneté croissants | variation monotone de p | `test_robustness::test_monotonie_metier` |
| CT-30 | EX04, EX13 | modèle factice | sorties NaN, infinie, hors [0,1], somme ≠ 1, 3 classes, 1D | 500, aucune probabilité renvoyée | `test_integration::test_sortie_du_modele_non_conforme` |
| CT-31 | EX12, EX13 |  | dictionnaires arbitraires (Hypothesis) | jamais de 500, aucune trace | `test_robustness::test_propriete_aucune_entree_ne_provoque_d_erreur_500` |
| CT-32 | EX14 |  | D0 ×25 ; 300 appels sur 16 threads | sorties identiques | `test_robustness::test_meme_entree_meme_sortie`, `test_predictions_concurrentes_identiques` |
| CT-33 | EX07 | référence v1.0.0 gelée | 30 profils de référence | même artefact : écart ≤ 1e-6 ; autre artefact : tolérances « nouveau modèle » | `test_regression::test_profils_de_reference_dans_les_tolerances` |
| CT-34 | EX20 |  | 30 profils via l'API | contrat respecté | `test_regression::test_contrat_de_sortie_sur_les_profils_de_reference` |
| CT-35 | EX07, EX16 | jeu de test versionné | métriques recalculées | dans les tolérances ; égales aux métadonnées | `test_regression::test_metriques_dans_les_tolerances`, `test_metriques_recalculees_egales_aux_metadonnees` |
| CT-36 | EX07 |  | rappel −0,10, F1 −0,05, AUC −0,03, Brier +0,02 ; modèle sur étiquettes permutées | non-conformité signalée | `test_regression::test_le_controle_detecte_une_degradation`, `test_modele_degrade_reel_est_rejete` |
| CT-37 | EX07 |  | taux de faux négatifs par segment | ≤ 35 % pour tout segment ≥ 15 défauts | `test_regression::test_taux_de_faux_negatifs_par_segment` |
| CT-38 | EX14 |  | dump/load joblib ; rechargement par le service | écart ≤ 1e-12 | `test_regression::test_coherence_apres_sauvegarde_et_rechargement` |
| CT-39 | EX14 |  | ré-entraînement v1.0.0, même graine | mêmes seuils, écart ≤ 1e-9 | `test_regression::test_reentrainement_reproductible` |
| CT-40 | EX19 |  | 500 inférences ; 200 requêtes API | P95 ≤ 10 ms ; P95 ≤ 200 ms | `test_performance::*` |
| CT-41 | EX21 | suite complète | marqueurs `exigence` | 22 exigences couvertes | `test_tracabilite::test_chaque_exigence_est_couverte_par_au_moins_un_test` |
| CT-42 | EX21 | `FORCER_ECHEC=1` | test volontairement défaillant | code de sortie 1, workflow en échec | `test_echec_volontaire::test_echec_volontaire` |
