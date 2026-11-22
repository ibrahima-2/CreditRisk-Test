| ID | Exigence | Priorité | Fonctions de test | Cas exécutés | Réussis | Échecs | Statut |
|---|---|---|---|---|---|---|---|
| EX01 | L'âge est un entier compris entre 18 et 75 ans | P1 | 7 | 45 | 45 | 0 | CONFORME |
| EX02 | Le revenu mensuel est numérique, fini, > 0 et <= 50 000 000 FCFA | P1 | 7 | 50 | 50 | 0 | CONFORME |
| EX03 | La durée est un entier compris entre 1 et 120 mois | P2 | 6 | 46 | 46 | 0 | CONFORME |
| EX04 | La prédiction retourne une probabilité valide | P1 | 7 | 35 | 35 | 0 | CONFORME |
| EX05 | Le modèle est disponible ; son indisponibilité est signalée | P1 | 8 | 17 | 17 | 0 | CONFORME |
| EX06 | Une entrée incomplète est soumise à validation | P1 | 14 | 26 | 26 | 0 | CONFORME |
| EX07 | Une nouvelle version ne dégrade pas les critères critiques | P1 | 11 | 14 | 14 | 0 | CONFORME |
| EX08 | Le montant demandé est > 0 et <= 500 000 000 FCFA | P2 | 5 | 42 | 42 | 0 | CONFORME |
| EX09 | L'ancienneté est >= 0, <= 60 ans et cohérente avec l'âge (<= âge - 14) | P2 | 7 | 39 | 39 | 0 | CONFORME |
| EX10 | Les champs non prévus par le contrat sont refusés | P2 | 4 | 8 | 8 | 0 | CONFORME |
| EX11 | Valeurs non finies, booléens et nombres sous forme de texte refusés | P1 | 9 | 103 | 103 | 0 | CONFORME |
| EX12 | Une requête mal formée reçoit une erreur contrôlée | P2 | 11 | 21 | 21 | 0 | CONFORME |
| EX13 | Aucune trace technique n'est exposée au client | P1 | 14 | 38 | 38 | 0 | CONFORME |
| EX14 | Les prédictions sont reproductibles | P1 | 13 | 13 | 13 | 0 | CONFORME |
| EX15 | Une entrée valide mais hors domaine d'entraînement est signalée | P2 | 3 | 11 | 11 | 0 | CONFORME |
| EX16 | /model-info décrit fidèlement le modèle chargé | P2 | 5 | 5 | 5 | 0 | CONFORME |
| EX17 | L'intégrité et la compatibilité de l'artefact sont vérifiées au chargement | P1 | 3 | 12 | 12 | 0 | CONFORME |
| EX18 | Les prédictions respectent la cohérence métier (monotonie) | P2 | 3 | 11 | 11 | 0 | CONFORME |
| EX19 | Les performances respectent l'objectif d'usage | P3 | 2 | 2 | 2 | 0 | CONFORME |
| EX20 | La réponse de /predict respecte son contrat | P1 | 10 | 10 | 10 | 0 | CONFORME |
| EX21 | La validation est automatisée à chaque modification | P2 | 4 | 4 | 3 | 0 | CONFORME |
| EX22 | Le prétraitement produit exactement les variables attendues par le modèle | P1 | 13 | 22 | 22 | 0 | CONFORME |

## Détail des tests par exigence

**EX01** — L'âge est un entier compris entre 18 et 75 ans
- `tests/test_api.py::test_s3_age_juste_hors_limites` : 2 réussi(s), 0 échec(s), 0 ignoré(s)
- `tests/test_api.py::test_s3_age_negatif` : 1 réussi(s), 0 échec(s), 0 ignoré(s)
- `tests/test_api.py::test_s8_valeurs_extremement_elevees` : 7 réussi(s), 0 échec(s), 0 ignoré(s)
- `tests/test_robustness.py::test_valeurs_aux_limites` : 20 réussi(s), 0 échec(s), 0 ignoré(s)
- `tests/test_validation.py::test_age_non_entier_refuse` : 5 réussi(s), 0 échec(s), 0 ignoré(s)
- `tests/test_validation.py::test_bornes_age` : 9 réussi(s), 0 échec(s), 0 ignoré(s)
- `tests/test_validation.py::test_coherence_non_evaluee_si_age_invalide` : 1 réussi(s), 0 échec(s), 0 ignoré(s)

**EX02** — Le revenu mensuel est numérique, fini, > 0 et <= 50 000 000 FCFA
- `tests/test_api.py::test_s4_revenu_texte` : 3 réussi(s), 0 échec(s), 0 ignoré(s)
- `tests/test_api.py::test_s8_valeurs_extremement_elevees` : 7 réussi(s), 0 échec(s), 0 ignoré(s)
- `tests/test_preprocessing.py::test_defense_en_profondeur_valeurs_non_positives` : 6 réussi(s), 0 échec(s), 0 ignoré(s)
- `tests/test_robustness.py::test_valeurs_aux_limites` : 20 réussi(s), 0 échec(s), 0 ignoré(s)
- `tests/test_validation.py::test_bornes_revenu` : 7 réussi(s), 0 échec(s), 0 ignoré(s)
- `tests/test_validation.py::test_revenu_entier_accepte_comme_nombre` : 1 réussi(s), 0 échec(s), 0 ignoré(s)
- `tests/test_validation.py::test_revenu_non_numerique_refuse` : 6 réussi(s), 0 échec(s), 0 ignoré(s)

**EX03** — La durée est un entier compris entre 1 et 120 mois
- `tests/test_api.py::test_s6_duree_non_entiere` : 3 réussi(s), 0 échec(s), 0 ignoré(s)
- `tests/test_api.py::test_s8_valeurs_extremement_elevees` : 7 réussi(s), 0 échec(s), 0 ignoré(s)
- `tests/test_preprocessing.py::test_defense_en_profondeur_valeurs_non_positives` : 6 réussi(s), 0 échec(s), 0 ignoré(s)
- `tests/test_robustness.py::test_valeurs_aux_limites` : 20 réussi(s), 0 échec(s), 0 ignoré(s)
- `tests/test_validation.py::test_bornes_duree` : 6 réussi(s), 0 échec(s), 0 ignoré(s)
- `tests/test_validation.py::test_duree_non_entiere_rejetee` : 4 réussi(s), 0 échec(s), 0 ignoré(s)

**EX04** — La prédiction retourne une probabilité valide
- `tests/test_api.py::test_s1_exemple_de_l_enonce_sans_cycle_de_vie` : 1 réussi(s), 0 échec(s), 0 ignoré(s)
- `tests/test_api.py::test_s1_requete_valide` : 1 réussi(s), 0 échec(s), 0 ignoré(s)
- `tests/test_integration.py::test_scenario_principal_bout_en_bout` : 1 réussi(s), 0 échec(s), 0 ignoré(s)
- `tests/test_integration.py::test_sortie_du_modele_non_conforme` : 6 réussi(s), 0 échec(s), 0 ignoré(s)
- `tests/test_robustness.py::test_hors_domaine_accepte_avec_alerte` : 5 réussi(s), 0 échec(s), 0 ignoré(s)
- `tests/test_robustness.py::test_propriete_toute_demande_valide_donne_une_probabilite` : 1 réussi(s), 0 échec(s), 0 ignoré(s)
- `tests/test_robustness.py::test_valeurs_aux_limites` : 20 réussi(s), 0 échec(s), 0 ignoré(s)

**EX05** — Le modèle est disponible ; son indisponibilité est signalée
- `tests/test_api.py::test_health_nominal` : 1 réussi(s), 0 échec(s), 0 ignoré(s)
- `tests/test_api.py::test_s1_exemple_de_l_enonce_sans_cycle_de_vie` : 1 réussi(s), 0 échec(s), 0 ignoré(s)
- `tests/test_api.py::test_s9_health_signale_l_indisponibilite` : 1 réussi(s), 0 échec(s), 0 ignoré(s)
- `tests/test_api.py::test_s9_model_info_indisponible` : 1 réussi(s), 0 échec(s), 0 ignoré(s)
- `tests/test_api.py::test_s9_predict_modele_indisponible` : 1 réussi(s), 0 échec(s), 0 ignoré(s)
- `tests/test_api.py::test_s9_validation_prioritaire_sur_disponibilite` : 1 réussi(s), 0 échec(s), 0 ignoré(s)
- `tests/test_integration.py::test_modele_non_chargeable` : 10 réussi(s), 0 échec(s), 0 ignoré(s)
- `tests/test_integration.py::test_rechargement_automatique_apres_restauration` : 1 réussi(s), 0 échec(s), 0 ignoré(s)

**EX06** — Une entrée incomplète est soumise à validation
- `tests/test_api.py::test_s10_corps_vide` : 1 réussi(s), 0 échec(s), 0 ignoré(s)
- `tests/test_api.py::test_s2_champ_obligatoire_absent` : 5 réussi(s), 0 échec(s), 0 ignoré(s)
- `tests/test_api.py::test_s2_corps_vide_liste_les_cinq_champs` : 1 réussi(s), 0 échec(s), 0 ignoré(s)
- `tests/test_api.py::test_s7_faute_de_frappe_detectee` : 1 réussi(s), 0 échec(s), 0 ignoré(s)
- `tests/test_api.py::test_s9_validation_prioritaire_sur_disponibilite` : 1 réussi(s), 0 échec(s), 0 ignoré(s)
- `tests/test_integration.py::test_requete_invalide_n_atteint_ni_pretraitement_ni_modele` : 1 réussi(s), 0 échec(s), 0 ignoré(s)
- `tests/test_integration.py::test_variable_absente_bloquee_par_le_pipeline_sans_validation` : 1 réussi(s), 0 échec(s), 0 ignoré(s)
- `tests/test_integration.py::test_variable_absente_bloquee_par_validation` : 1 réussi(s), 0 échec(s), 0 ignoré(s)
- `tests/test_preprocessing.py::test_variable_absente` : 1 réussi(s), 0 échec(s), 0 ignoré(s)
- `tests/test_robustness.py::test_toutes_les_valeurs_nulles` : 1 réussi(s), 0 échec(s), 0 ignoré(s)
- `tests/test_robustness.py::test_valeur_nulle` : 5 réussi(s), 0 échec(s), 0 ignoré(s)
- `tests/test_validation.py::test_champ_manquant` : 5 réussi(s), 0 échec(s), 0 ignoré(s)
- `tests/test_validation.py::test_demande_vide_liste_tous_les_champs` : 1 réussi(s), 0 échec(s), 0 ignoré(s)
- `tests/test_validation.py::test_formatage_erreurs_en_francais_sans_valeur_saisie` : 1 réussi(s), 0 échec(s), 0 ignoré(s)

**EX07** — Une nouvelle version ne dégrade pas les critères critiques
- `tests/test_donnees.py::test_reference_regenerable_a_l_identique` : 1 réussi(s), 0 échec(s), 0 ignoré(s)
- `tests/test_regression.py::test_artefact_de_reference_inchange` : 1 réussi(s), 0 échec(s), 0 ignoré(s)
- `tests/test_regression.py::test_comparaison_de_predictions_detecte_un_ecart` : 1 réussi(s), 0 échec(s), 0 ignoré(s)
- `tests/test_regression.py::test_comparaison_du_candidat_v1_1_0` : 1 réussi(s), 0 échec(s), 0 ignoré(s)
- `tests/test_regression.py::test_contrat_de_sortie_sur_les_profils_de_reference` : 1 réussi(s), 0 échec(s), 0 ignoré(s)
- `tests/test_regression.py::test_le_controle_detecte_une_degradation` : 4 réussi(s), 0 échec(s), 0 ignoré(s)
- `tests/test_regression.py::test_metriques_dans_les_tolerances` : 1 réussi(s), 0 échec(s), 0 ignoré(s)
- `tests/test_regression.py::test_modele_degrade_reel_est_rejete` : 1 réussi(s), 0 échec(s), 0 ignoré(s)
- `tests/test_regression.py::test_profils_de_reference_dans_les_tolerances` : 1 réussi(s), 0 échec(s), 0 ignoré(s)
- `tests/test_regression.py::test_taux_de_faux_negatifs_par_segment` : 1 réussi(s), 0 échec(s), 0 ignoré(s)
- `tests/test_regression.py::test_variation_dans_la_tolerance_acceptee` : 1 réussi(s), 0 échec(s), 0 ignoré(s)

**EX08** — Le montant demandé est > 0 et <= 500 000 000 FCFA
- `tests/test_api.py::test_s5_montant_nul_ou_negatif` : 3 réussi(s), 0 échec(s), 0 ignoré(s)
- `tests/test_api.py::test_s8_valeurs_extremement_elevees` : 7 réussi(s), 0 échec(s), 0 ignoré(s)
- `tests/test_preprocessing.py::test_defense_en_profondeur_valeurs_non_positives` : 6 réussi(s), 0 échec(s), 0 ignoré(s)
- `tests/test_robustness.py::test_valeurs_aux_limites` : 20 réussi(s), 0 échec(s), 0 ignoré(s)
- `tests/test_validation.py::test_bornes_montant` : 6 réussi(s), 0 échec(s), 0 ignoré(s)

**EX09** — L'ancienneté est >= 0, <= 60 ans et cohérente avec l'âge (<= âge - 14)
- `tests/test_api.py::test_s8_valeurs_extremement_elevees` : 7 réussi(s), 0 échec(s), 0 ignoré(s)
- `tests/test_donnees.py::test_toutes_les_lignes_respectent_le_contrat_d_entree` : 1 réussi(s), 0 échec(s), 0 ignoré(s)
- `tests/test_robustness.py::test_limite_anciennete_a_75_ans` : 1 réussi(s), 0 échec(s), 0 ignoré(s)
- `tests/test_robustness.py::test_valeurs_aux_limites` : 20 réussi(s), 0 échec(s), 0 ignoré(s)
- `tests/test_validation.py::test_coherence_anciennete_age` : 8 réussi(s), 0 échec(s), 0 ignoré(s)
- `tests/test_validation.py::test_coherence_non_evaluee_si_age_invalide` : 1 réussi(s), 0 échec(s), 0 ignoré(s)
- `tests/test_validation.py::test_incoherence_anciennete_a_un_type_dedie` : 1 réussi(s), 0 échec(s), 0 ignoré(s)

**EX10** — Les champs non prévus par le contrat sont refusés
- `tests/test_api.py::test_s7_champs_supplementaires` : 1 réussi(s), 0 échec(s), 0 ignoré(s)
- `tests/test_api.py::test_s7_faute_de_frappe_detectee` : 1 réussi(s), 0 échec(s), 0 ignoré(s)
- `tests/test_robustness.py::test_schema_incorrect` : 5 réussi(s), 0 échec(s), 0 ignoré(s)
- `tests/test_validation.py::test_champ_supplementaire_refuse` : 1 réussi(s), 0 échec(s), 0 ignoré(s)

**EX11** — Valeurs non finies, booléens et nombres sous forme de texte refusés
- `tests/test_api.py::test_s4_revenu_texte` : 3 réussi(s), 0 échec(s), 0 ignoré(s)
- `tests/test_preprocessing.py::test_depassement_numerique_detecte` : 1 réussi(s), 0 échec(s), 0 ignoré(s)
- `tests/test_preprocessing.py::test_valeur_non_numerique_ou_non_finie` : 4 réussi(s), 0 échec(s), 0 ignoré(s)
- `tests/test_robustness.py::test_valeur_non_finie` : 25 réussi(s), 0 échec(s), 0 ignoré(s)
- `tests/test_robustness.py::test_valeur_non_numerique` : 45 réussi(s), 0 échec(s), 0 ignoré(s)
- `tests/test_robustness.py::test_valeur_nulle` : 5 réussi(s), 0 échec(s), 0 ignoré(s)
- `tests/test_validation.py::test_age_non_entier_refuse` : 5 réussi(s), 0 échec(s), 0 ignoré(s)
- `tests/test_validation.py::test_revenu_non_numerique_refuse` : 6 réussi(s), 0 échec(s), 0 ignoré(s)
- `tests/test_validation.py::test_valeurs_non_finies_refusees` : 9 réussi(s), 0 échec(s), 0 ignoré(s)

**EX12** — Une requête mal formée reçoit une erreur contrôlée
- `tests/test_api.py::test_methode_non_autorisee` : 1 réussi(s), 0 échec(s), 0 ignoré(s)
- `tests/test_api.py::test_route_inconnue` : 1 réussi(s), 0 échec(s), 0 ignoré(s)
- `tests/test_api.py::test_s10_content_type_non_json` : 1 réussi(s), 0 échec(s), 0 ignoré(s)
- `tests/test_api.py::test_s10_corps_qui_n_est_pas_un_objet` : 4 réussi(s), 0 échec(s), 0 ignoré(s)
- `tests/test_api.py::test_s10_corps_trop_volumineux` : 1 réussi(s), 0 échec(s), 0 ignoré(s)
- `tests/test_api.py::test_s10_corps_vide` : 1 réussi(s), 0 échec(s), 0 ignoré(s)
- `tests/test_api.py::test_s10_json_invalide` : 4 réussi(s), 0 échec(s), 0 ignoré(s)
- `tests/test_robustness.py::test_chaine_tres_longue` : 1 réussi(s), 0 échec(s), 0 ignoré(s)
- `tests/test_robustness.py::test_cles_dupliquees_derniere_valeur_validee` : 1 réussi(s), 0 échec(s), 0 ignoré(s)
- `tests/test_robustness.py::test_propriete_aucune_entree_ne_provoque_d_erreur_500` : 1 réussi(s), 0 échec(s), 0 ignoré(s)
- `tests/test_robustness.py::test_schema_incorrect` : 5 réussi(s), 0 échec(s), 0 ignoré(s)

**EX13** — Aucune trace technique n'est exposée au client
- `tests/test_api.py::test_identifiant_de_requete` : 4 réussi(s), 0 échec(s), 0 ignoré(s)
- `tests/test_api.py::test_route_inconnue` : 1 réussi(s), 0 échec(s), 0 ignoré(s)
- `tests/test_api.py::test_s10_json_invalide` : 4 réussi(s), 0 échec(s), 0 ignoré(s)
- `tests/test_api.py::test_s9_predict_modele_indisponible` : 1 réussi(s), 0 échec(s), 0 ignoré(s)
- `tests/test_integration.py::test_dimensions_produites_incompatibles` : 5 réussi(s), 0 échec(s), 0 ignoré(s)
- `tests/test_integration.py::test_erreur_de_pretraitement` : 1 réussi(s), 0 échec(s), 0 ignoré(s)
- `tests/test_integration.py::test_erreur_inattendue_dans_l_orchestration` : 1 réussi(s), 0 échec(s), 0 ignoré(s)
- `tests/test_integration.py::test_exception_pendant_la_prediction` : 1 réussi(s), 0 échec(s), 0 ignoré(s)
- `tests/test_integration.py::test_filet_de_securite_erreur_non_geree` : 1 réussi(s), 0 échec(s), 0 ignoré(s)
- `tests/test_integration.py::test_modele_non_chargeable` : 10 réussi(s), 0 échec(s), 0 ignoré(s)
- `tests/test_integration.py::test_sortie_du_modele_non_conforme` : 6 réussi(s), 0 échec(s), 0 ignoré(s)
- `tests/test_robustness.py::test_propriete_aucune_entree_ne_provoque_d_erreur_500` : 1 réussi(s), 0 échec(s), 0 ignoré(s)
- `tests/test_validation.py::test_formatage_erreur_inconnue_et_contexte_incomplet` : 1 réussi(s), 0 échec(s), 0 ignoré(s)
- `tests/test_validation.py::test_formatage_erreurs_en_francais_sans_valeur_saisie` : 1 réussi(s), 0 échec(s), 0 ignoré(s)

**EX14** — Les prédictions sont reproductibles
- `tests/test_donnees.py::test_donnees_versionnees_regenerables` : 1 réussi(s), 0 échec(s), 0 ignoré(s)
- `tests/test_donnees.py::test_generation_deterministe` : 1 réussi(s), 0 échec(s), 0 ignoré(s)
- `tests/test_donnees.py::test_reference_regenerable_a_l_identique` : 1 réussi(s), 0 échec(s), 0 ignoré(s)
- `tests/test_donnees.py::test_separation_stratifiee` : 1 réussi(s), 0 échec(s), 0 ignoré(s)
- `tests/test_preprocessing.py::test_meme_transformation_entrainement_et_production` : 1 réussi(s), 0 échec(s), 0 ignoré(s)
- `tests/test_regression.py::test_coherence_apres_sauvegarde_et_rechargement` : 1 réussi(s), 0 échec(s), 0 ignoré(s)
- `tests/test_regression.py::test_metriques_recalculees_egales_aux_metadonnees` : 1 réussi(s), 0 échec(s), 0 ignoré(s)
- `tests/test_regression.py::test_profils_de_reference_dans_les_tolerances` : 1 réussi(s), 0 échec(s), 0 ignoré(s)
- `tests/test_regression.py::test_reentrainement_reproductible` : 1 réussi(s), 0 échec(s), 0 ignoré(s)
- `tests/test_robustness.py::test_entier_et_decimal_equivalents` : 1 réussi(s), 0 échec(s), 0 ignoré(s)
- `tests/test_robustness.py::test_invariance_a_l_ordre_des_champs` : 1 réussi(s), 0 échec(s), 0 ignoré(s)
- `tests/test_robustness.py::test_meme_entree_meme_sortie` : 1 réussi(s), 0 échec(s), 0 ignoré(s)
- `tests/test_robustness.py::test_predictions_concurrentes_identiques` : 1 réussi(s), 0 échec(s), 0 ignoré(s)

**EX15** — Une entrée valide mais hors domaine d'entraînement est signalée
- `tests/test_api.py::test_s1_profil_dans_le_domaine_sans_alerte` : 1 réussi(s), 0 échec(s), 0 ignoré(s)
- `tests/test_robustness.py::test_hors_domaine_accepte_avec_alerte` : 5 réussi(s), 0 échec(s), 0 ignoré(s)
- `tests/test_robustness.py::test_probabilite_saturee_toujours_signalee` : 5 réussi(s), 0 échec(s), 0 ignoré(s)

**EX16** — /model-info décrit fidèlement le modèle chargé
- `tests/test_api.py::test_model_info` : 1 réussi(s), 0 échec(s), 0 ignoré(s)
- `tests/test_api.py::test_s9_model_info_indisponible` : 1 réussi(s), 0 échec(s), 0 ignoré(s)
- `tests/test_integration.py::test_filet_de_securite_erreur_non_geree` : 1 réussi(s), 0 échec(s), 0 ignoré(s)
- `tests/test_integration.py::test_scenario_principal_bout_en_bout` : 1 réussi(s), 0 échec(s), 0 ignoré(s)
- `tests/test_regression.py::test_metriques_recalculees_egales_aux_metadonnees` : 1 réussi(s), 0 échec(s), 0 ignoré(s)

**EX17** — L'intégrité et la compatibilité de l'artefact sont vérifiées au chargement
- `tests/test_integration.py::test_modele_non_chargeable` : 10 réussi(s), 0 échec(s), 0 ignoré(s)
- `tests/test_regression.py::test_artefact_de_reference_inchange` : 1 réussi(s), 0 échec(s), 0 ignoré(s)
- `tests/test_regression.py::test_coherence_apres_sauvegarde_et_rechargement` : 1 réussi(s), 0 échec(s), 0 ignoré(s)

**EX18** — Les prédictions respectent la cohérence métier (monotonie)
- `tests/test_robustness.py::test_entier_et_decimal_equivalents` : 1 réussi(s), 0 échec(s), 0 ignoré(s)
- `tests/test_robustness.py::test_invariance_a_l_ordre_des_champs` : 1 réussi(s), 0 échec(s), 0 ignoré(s)
- `tests/test_robustness.py::test_monotonie_metier` : 9 réussi(s), 0 échec(s), 0 ignoré(s)

**EX19** — Les performances respectent l'objectif d'usage
- `tests/test_performance.py::test_latence_api_p95_sequentielle` : 1 réussi(s), 0 échec(s), 0 ignoré(s)
- `tests/test_performance.py::test_latence_inference_p95` : 1 réussi(s), 0 échec(s), 0 ignoré(s)

**EX20** — La réponse de /predict respecte son contrat
- `tests/test_api.py::test_s1_profil_dans_le_domaine_sans_alerte` : 1 réussi(s), 0 échec(s), 0 ignoré(s)
- `tests/test_api.py::test_s1_requete_valide` : 1 réussi(s), 0 échec(s), 0 ignoré(s)
- `tests/test_donnees.py::test_toutes_les_lignes_respectent_le_contrat_d_entree` : 1 réussi(s), 0 échec(s), 0 ignoré(s)
- `tests/test_integration.py::test_requete_invalide_n_atteint_ni_pretraitement_ni_modele` : 1 réussi(s), 0 échec(s), 0 ignoré(s)
- `tests/test_integration.py::test_scenario_principal_bout_en_bout` : 1 réussi(s), 0 échec(s), 0 ignoré(s)
- `tests/test_preprocessing.py::test_indicateurs_pour_l_agent` : 1 réussi(s), 0 échec(s), 0 ignoré(s)
- `tests/test_regression.py::test_contrat_de_sortie_sur_les_profils_de_reference` : 1 réussi(s), 0 échec(s), 0 ignoré(s)
- `tests/test_robustness.py::test_propriete_toute_demande_valide_donne_une_probabilite` : 1 réussi(s), 0 échec(s), 0 ignoré(s)
- `tests/test_validation.py::test_demande_nominale_acceptee` : 1 réussi(s), 0 échec(s), 0 ignoré(s)
- `tests/test_validation.py::test_demande_validee_est_immuable` : 1 réussi(s), 0 échec(s), 0 ignoré(s)

**EX21** — La validation est automatisée à chaque modification
- `tests/test_echec_volontaire.py::test_echec_volontaire` : 0 réussi(s), 0 échec(s), 1 ignoré(s)
- `tests/test_tracabilite.py::test_chaque_exigence_est_couverte_par_au_moins_un_test` : 1 réussi(s), 0 échec(s), 0 ignoré(s)
- `tests/test_tracabilite.py::test_dependances_epinglees` : 1 réussi(s), 0 échec(s), 0 ignoré(s)
- `tests/test_tracabilite.py::test_workflow_ci_execute_lint_tests_et_couverture` : 1 réussi(s), 0 échec(s), 0 ignoré(s)

**EX22** — Le prétraitement produit exactement les variables attendues par le modèle
- `tests/test_integration.py::test_dimensions_produites_incompatibles` : 5 réussi(s), 0 échec(s), 0 ignoré(s)
- `tests/test_integration.py::test_predire_lot_refuse_une_matrice_vide` : 1 réussi(s), 0 échec(s), 0 ignoré(s)
- `tests/test_integration.py::test_scenario_principal_bout_en_bout` : 1 réussi(s), 0 échec(s), 0 ignoré(s)
- `tests/test_integration.py::test_variable_absente_bloquee_par_le_pipeline_sans_validation` : 1 réussi(s), 0 échec(s), 0 ignoré(s)
- `tests/test_integration.py::test_variable_absente_bloquee_par_validation` : 1 réussi(s), 0 échec(s), 0 ignoré(s)
- `tests/test_preprocessing.py::test_colonnes_de_longueurs_differentes` : 1 réussi(s), 0 échec(s), 0 ignoré(s)
- `tests/test_preprocessing.py::test_depassement_numerique_detecte` : 1 réussi(s), 0 échec(s), 0 ignoré(s)
- `tests/test_preprocessing.py::test_meme_transformation_entrainement_et_production` : 1 réussi(s), 0 échec(s), 0 ignoré(s)
- `tests/test_preprocessing.py::test_ordre_des_variables_fait_partie_du_contrat` : 1 réussi(s), 0 échec(s), 0 ignoré(s)
- `tests/test_preprocessing.py::test_taux_endettement_pour_des_durees_differentes_de_12` : 3 réussi(s), 0 échec(s), 0 ignoré(s)
- `tests/test_preprocessing.py::test_transformation_valeurs_attendues` : 1 réussi(s), 0 échec(s), 0 ignoré(s)
- `tests/test_preprocessing.py::test_valeur_non_numerique_ou_non_finie` : 4 réussi(s), 0 échec(s), 0 ignoré(s)
- `tests/test_preprocessing.py::test_variable_absente` : 1 réussi(s), 0 échec(s), 0 ignoré(s)
