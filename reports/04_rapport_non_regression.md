# Rapport de non-régression

## 1. Référence et stratégie

**Version de référence** : modèle v1.0.0 (régression logistique), gelé le 22/11/2026 dans
`model/reference/reference_v1.0.0.json` : empreinte SHA-256 de l'artefact, seuils, métriques
sur le jeu de test versionné (1 500 demandes, 200 défauts) et sorties attendues pour 30 profils
de référence (12 profils types dont 7 aux limites ou hors domaine, 18 lignes du jeu de test).

**Tolérances** : `model/reference/tolerances_non_regression.json`, écrites et versionnées
avant la première comparaison.

| Contrôle | Règle |
|---|---|
| Rappel | baisse ≤ 0,03 et plancher 0,75 |
| F1 | baisse ≤ 0,03 et plancher 0,30 |
| ROC AUC | baisse ≤ 0,02 et plancher 0,70 |
| Brier | hausse ≤ 0,01 |
| Même artefact (modification du code) | écart de probabilité ≤ 1e-6 sur chaque profil, niveau et alertes identiques |
| Sauvegarde / rechargement | écart ≤ 1e-12 |
| Nouvel artefact (modification du modèle) | écart moyen ≤ 0,05 ; écart max ≤ 0,20 ; changements de niveau ≤ 20 % des profils |
| Segments (âge, terciles de revenu) | taux de faux négatifs ≤ 35 % si le segment compte ≥ 15 défauts |

Justification du seuil de 0,03 sur le rappel : sur 200 défauts, il correspond à 6 défauts
manqués de plus. En deçà, l'écart reste dans l'ordre du bruit d'échantillonnage ; au-delà, il
doit être expliqué.

Les métriques sont calculées au **seuil de signalement** (`risque_modere`) : un faux négatif est
un défaut classé FAIBLE, donc non soumis à revue humaine.

La suite distingue automatiquement les deux situations (comparaison de l'empreinte de l'artefact
chargé avec celle de la référence).

## 2. Modification du code, artefact inchangé

Modifications intervenues après le gel : correction AN-01 (`predire_probabilite`), messages
404/405 (AN-08), ajout de tests.

| Contrôle | Résultat |
|---|---|
| Suite complète | 333 réussis, 1 ignoré (échec volontaire), 0 échec |
| Écart max sur les 30 profils | 0,0 (tolérance 1e-6) |
| Niveaux et alertes | identiques sur 30/30 |
| Métriques recalculées = métadonnées publiées | égalité à 1e-9 près, matrice de confusion identique |
| Sauvegarde / rechargement joblib | écart 0,0 sur les 1 500 demandes |
| Ré-entraînement v1.0.0 (même graine) | mêmes seuils (0,09 / 0,21), écart ≤ 1e-9 ; artefact identique octet par octet sur la machine de développement |

## 3. Modification du modèle : v1.0.0 → v1.1.0

Candidat : `HistGradientBoostingClassifier` avec contraintes de monotonie (âge −, revenu −,
ancienneté −, taux d'endettement +). Seuils recalculés sur l'apprentissage : 0,08 / 0,16.
Commande : `python -m ml.comparaison model/credit_risk_v1.1.0.joblib` puis
`CREDIT_MODEL_PATH=model/credit_risk_v1.1.0.joblib pytest`.

### Métriques (jeu de test)

| Métrique | v1.0.0 | v1.1.0 | Écart | Limite | Conforme |
|---|---|---|---|---|---|
| Rappel | 0,825 | 0,805 | −0,020 | ≥ 0,795 et ≥ 0,75 | oui |
| F1 | 0,355 | 0,338 | −0,017 | ≥ 0,325 et ≥ 0,30 | oui |
| ROC AUC | 0,776 | 0,766 | −0,010 | ≥ 0,756 et ≥ 0,70 | oui |
| Brier | 0,0993 | 0,1010 | +0,0017 | ≤ 0,1093 | oui |
| Précision | 0,226 | 0,214 | −0,012 |  |  |
| Faux négatifs / défauts | 35 / 200 | 39 / 200 | +4 |  |  |

Toutes les métriques restent dans les tolérances, mais toutes se dégradent : aucun gain ne
justifie le remplacement.

### Sorties sur les profils de référence

| Contrôle | Valeur | Limite | Conforme |
|---|---|---|---|
| Écart moyen de probabilité | 0,060 | ≤ 0,05 | **non** |
| Écart maximal | 0,760 (G09) | ≤ 0,20 | **non** |
| Profils changeant de niveau | 5 / 30 (16,7 %) | ≤ 20 % | oui |

| Profil | v1.0.0 | v1.1.0 | Commentaire |
|---|---|---|---|
| G09 montant 400 M (hors domaine) | 1,000 ÉLEVÉ | 0,240 ÉLEVÉ | v1.0.0 sature, v1.1.0 reste constant au-delà du domaine |
| G07 durée 120 mois (hors domaine) | 0,109 MODÉRÉ | 0,008 FAIBLE | risque fortement sous-estimé ; la revue humaine reste déclenchée par l'alerte hors domaine |
| G04 18 ans, ancienneté nulle | 0,693 | 0,892 | même niveau |
| T07, T14, T18 | MODÉRÉ | ÉLEVÉ | seuil « élevé » abaissé (0,21 → 0,16) |
| T12 | FAIBLE (0,066) | MODÉRÉ (0,081) | seuil de signalement abaissé (0,09 → 0,08) |

Sur les 1 500 demandes du jeu de test : écart moyen 0,030, P95 0,114, max 0,374.

### Faux négatifs par segment

| Segment | Défauts | v1.0.0 | v1.1.0 |
|---|---|---|---|
| 18–25 ans | 44 | 2,3 % | 4,5 % |
| 26–40 ans | 104 | 15,4 % | 18,3 % |
| 41–55 ans | 49 | 32,7 % | 32,7 % |
| 56 ans et + | 3 | 66,7 % | 66,7 % |
| Revenu tercile 1 | 92 | 9,8 % | 12,0 % |
| Revenu tercile 2 | 59 | 18,6 % | 20,3 % |
| Revenu tercile 3 | 49 | 30,6 % | 32,7 % |

### Exécution de la suite avec v1.1.0

| Exécution | Résultat | Échecs |
|---|---|---|
| 1 (`reports/preuves/pytest_candidat_v1.1.0.txt`) | 2 échecs, 328 réussis, 3 ignorés | profils de référence ; latence d'inférence P95 14,7 ms |
| 2 | 2 échecs | profils de référence ; latence P95 14,8 ms |
| 3 (`reports/preuves/pytest_candidat_v1.1.0_execution3.ansi`) | 1 échec, 330 réussis, 3 ignorés | profils de référence |

L'échec sur les profils de référence est stable. Le contrôle de latence est instable avec ce
modèle (threads OpenMP, voir AN-05). Deux tests sont ignorés par conception quand l'artefact
n'est pas la référence (empreinte, ré-entraînement).

### Décision

**v1.1.0 rejeté.** Écarts hors tolérance sur les profils de référence (investigation
obligatoire selon la politique), sous-estimation du risque des profils extrêmes (G07),
métriques légèrement inférieures et latence supérieure à l'objectif. v1.0.0 reste la version
de référence.

## 4. Régression simulée sur le code (mutation M2)

Taux d'endettement calculé sans la durée. Contrôles déclenchés : AUC 0,705 (limite 0,756),
F1 0,315 (limite 0,325), Brier 0,172 (limite 0,109), profils de référence hors tolérance,
métriques publiées incohérentes avec l'artefact. Le rappel restait dans la tolérance : seul,
il n'aurait pas suffi. Détail : rapport 03, § 3.
