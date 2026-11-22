# Rapport de performance

## 1. Objectif et justification

Usage : un agent de crédit saisit une demande dans un formulaire et attend le résultat.

Hypothèse de dimensionnement (à confirmer par l'institution) : 50 agences × 5 agents, au plus
une demande par agent et par minute en pointe, soit environ 4 req/s. Avec un temps de traitement
de quelques millisecondes, la loi de Little donne une concurrence moyenne très inférieure à 1 ;
10 requêtes simultanées représentent donc une pointe exceptionnelle.

| Exigence EX19 | Objectif | Raison |
|---|---|---|
| Inférence du modèle | P95 ≤ 10 ms | laisser l'essentiel du budget au réseau et à l'interface |
| API `POST /predict` | P95 ≤ 200 ms à 10 utilisateurs simultanés | sous 0,1 s une réponse paraît immédiate, sous 1 s le travail n'est pas interrompu ; 200 ms laisse une marge pour le réseau d'agence |
| Débit | ≥ 50 req/s | 10 fois la pointe estimée |

## 2. Configuration

| Élément | Valeur |
|---|---|
| Machine | Apple M4 Pro, 12 cœurs logiques, 24 Go, macOS (Darwin 24.6.0, arm64) |
| Logiciel | Python 3.13.5, scikit-learn 1.9.1, numpy 2.5.5, FastAPI 0.165.0, uvicorn 0.54.0 |
| Serveur | uvicorn, endpoint synchrone exécuté dans le pool de threads ; 1 puis 4 processus |
| Générateur de charge | ApacheBench (`ab -k`, connexions persistantes) ; Locust 2.47.0 pour le scénario réaliste |
| Réseau | boucle locale (127.0.0.1) : aucune latence réseau |
| Scripts | `scripts/benchmark_performance.py`, `scripts/locustfile.py` ; résultats bruts dans `reports/performance/` |

## 3. Mesures

### Latence d'inférence (appel direct du modèle, 5 000 appels après 50 de préchauffage)

| Mesure | v1.0.0 | v1.1.0 (threads par défaut) | v1.1.0 (1 thread) |
|---|---|---|---|
| Inférence seule, P50 | 0,103 ms | 3,90 ms | 0,392 ms |
| Inférence seule, P95 | 0,114 ms | 11,23 ms | 0,408 ms |
| Inférence seule, P99 | 0,219 ms | 16,04 ms | 0,461 ms |
| Pipeline complet (validation + prétraitement + modèle), P95 | 0,149 ms |  | 0,449 ms |

### API, requêtes séquentielles (2 000 requêtes, une connexion)

P50 0,98 ms ; P95 1,18 ms ; P99 1,42 ms ; débit 977 req/s.

### Charge progressive (ApacheBench, au moins 4 000 requêtes par palier, 0 échec)

| Utilisateurs simultanés | 1 processus : P95 | 1 processus : débit | 4 processus : P95 | 4 processus : débit |
|---|---|---|---|---|
| 1 | 1 ms | 839 req/s | 2 ms | 741 req/s |
| 2 | 2 ms | 1 256 req/s | 2 ms | 1 229 req/s |
| 5 | 4 ms | 1 511 req/s | 2 ms | 3 108 req/s |
| 10 | 7 ms | 1 658 req/s | 4 ms | 3 889 req/s |
| 20 | 14 ms | 1 790 req/s | 6 ms | 4 800 req/s |
| 50 | 34 ms | 1 900 req/s | 13 ms | 5 381 req/s |
| 100 | 69 ms | 1 904 req/s | 25 ms | 5 618 req/s |

Résolution de `ab` : 1 ms.

Figures : `reports/figures/latence_p95_charge.png`, `debit_charge.png`.

### Scénario réaliste (Locust)

Paliers de 30 s à 1, 5, 10, 25 et 50 agents ; chaque agent attend 0,5 à 1,5 s entre deux
actions ; 80 % de demandes valides, 10 % invalides, 10 % `/health`.

| Requête | Nombre | Échecs | P50 | P95 | P99 | Max |
|---|---|---|---|---|---|---|
| POST /predict (valide) | 2 168 | 0 | 4 ms | 10 ms | 19 ms | 61 ms |
| POST /predict (invalide, 422 attendu) | 285 | 0 | 3 ms | 9 ms | 17 ms | 31 ms |
| GET /health | 296 | 0 | 3 ms | 8 ms | 19 ms | 19 ms |
| Total | 2 749 | 0 | 4 ms | 10 ms | 18 ms | 61 ms |

## 4. Interprétation

- Objectifs tenus avec v1.0.0 : inférence P95 = 0,11 ms (objectif 10 ms) ; API P95 = 7 ms à
  10 utilisateurs (objectif 200 ms) ; débit plafond ≈ 1 900 req/s avec 1 processus (objectif 50).
- Le modèle n'est pas le facteur limitant : 0,11 ms sur environ 1 ms de temps de réponse.
  Au-delà de 20 utilisateurs, le débit plafonne et la latence croît avec la file d'attente
  (P95 69 ms à 100). Avec 4 processus, le débit est multiplié par 3 et le P95 divisé par 2,8.
- v1.1.0 dépasse l'objectif d'inférence (P95 11,2 ms) à cause du coût de démarrage des
  threads OpenMP pour une seule ligne ; limité à 1 thread, il passe à 0,41 ms (AN-05).
- Biais de mesure identifié et corrigé (AN-09). Le premier essai utilisait un client
  httpx asynchrone dans un seul processus Python. Il mesurait un P95 de 166 ms à 20
  utilisateurs et un débit en baisse au-delà de 5. Trois vérifications ont montré que le
  client saturait avant le serveur :
  1. `/health`, qui n'appelle pas le modèle, se dégradait de la même façon ;
  2. passer à 4 processus serveur ne changeait rien ;
  3. ApacheBench, sur le même serveur, mesurait un P95 de 14 ms.

  Figure : `reports/figures/biais_generateur_de_charge.png`.

## 5. Limites

Client et serveur partagent la même machine (ils se disputent le CPU) ; pas de latence réseau ;
poste de développement plus rapide qu'un serveur d'entrée de gamme ou qu'un runner CI ; une
seule demande type (le temps d'inférence d'une régression logistique ne dépend pas des
valeurs). Les contrôles de `tests/test_performance.py` exécutés en CI sont volontairement larges
(10 ms et 200 ms) pour détecter une dégradation grossière sans échouer au hasard.
