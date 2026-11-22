"""Banc de performance local : latence d'inférence, latence API, P95, débit, charge progressive.

Usage : ``python scripts/benchmark_performance.py`` (depuis la racine du dépôt, macOS/Linux).
Sortie : ``reports/performance/resultats_performance.json``.

- Inférence : appel direct du modèle (sans HTTP), avec la configuration de threads par
  défaut puis limitée à 1 thread (threadpoolctl).
- API séquentielle : un client httpx, une connexion persistante.
- Charge progressive : ApacheBench (``ab``, outil C) contre un vrai serveur uvicorn.
  Un premier essai avec un client Python asynchrone (httpx) saturait avant le serveur et
  faussait les mesures : voir ``reports/05_rapport_performance.md``.
"""

from __future__ import annotations

import json
import os
import platform
import re
import shutil
import subprocess
import sys
import tempfile
import time
from pathlib import Path

import httpx
import numpy as np
import sklearn
from threadpoolctl import threadpool_limits

RACINE = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(RACINE))

from app import config, preprocessing  # noqa: E402
from app.prediction import ServiceModele  # noqa: E402
from app.validation import DemandeCredit  # noqa: E402

PORT = 8765
URL = f"http://127.0.0.1:{PORT}"
DEMANDE = {
    "age": 35,
    "revenu_mensuel": 250000,
    "montant_credit": 1000000,
    "duree_mois": 12,
    "anciennete_activite": 4,
}
PALIERS_CONCURRENCE = [1, 2, 5, 10, 20, 50, 100]
CONFIGURATIONS_SERVEUR = [1, 4]  # nombre de processus uvicorn


def statistiques(durees_s: list[float]) -> dict[str, float]:
    ms = np.array(durees_s) * 1000
    return {
        "n": int(ms.size),
        "moyenne_ms": float(ms.mean()),
        "p50_ms": float(np.percentile(ms, 50)),
        "p95_ms": float(np.percentile(ms, 95)),
        "p99_ms": float(np.percentile(ms, 99)),
        "max_ms": float(ms.max()),
    }


def mesurer(fonction, n: int, prechauffage: int = 50) -> list[float]:
    for _ in range(prechauffage):
        fonction()
    durees = []
    for _ in range(n):
        debut = time.perf_counter()
        fonction()
        durees.append(time.perf_counter() - debut)
    return durees


def inference(chemin_modele: Path, n: int = 5000) -> dict:
    service = ServiceModele(chemin_modele)
    service.charger()
    matrice = preprocessing.transformer(DEMANDE)
    resultat = {"version": service.metadonnees["version"]}
    resultat["inference_threads_defaut"] = statistiques(
        mesurer(lambda: service.predire_probabilite(matrice), n)
    )
    with threadpool_limits(limits=1):
        resultat["inference_1_thread"] = statistiques(
            mesurer(lambda: service.predire_probabilite(matrice), n)
        )
        resultat["pipeline_complet_1_thread"] = statistiques(
            mesurer(lambda: service.evaluer(DemandeCredit.model_validate(DEMANDE).model_dump()), n)
        )
    return resultat


def demarrer_serveur(processus: int) -> subprocess.Popen:
    serveur = subprocess.Popen(
        [sys.executable, "-m", "uvicorn", "app.main:app", "--port", str(PORT),
         "--workers", str(processus), "--log-level", "warning", "--no-access-log"],
        cwd=RACINE,
        env={k: v for k, v in os.environ.items() if k != config.VARIABLE_ENV_MODELE},
    )  # fmt: skip
    for _ in range(150):
        try:
            if httpx.get(f"{URL}/health", timeout=1).status_code == 200:
                time.sleep(1.0 if processus > 1 else 0.2)  # tous les processus prêts
                return serveur
        except httpx.HTTPError:
            time.sleep(0.1)
    serveur.terminate()
    raise RuntimeError("Le serveur n'a pas démarré")


def api_sequentielle(n: int = 2000) -> dict:
    with httpx.Client(base_url=URL) as client:
        durees = mesurer(lambda: client.post("/predict", json=DEMANDE).raise_for_status(), n)
    return {**statistiques(durees), "debit_req_s": n / sum(durees)}


def palier_ab(concurrence: int, fichier_corps: Path) -> dict:
    total = max(4000, 400 * concurrence)
    sortie = subprocess.run(
        ["ab", "-q", "-k", "-n", str(total), "-c", str(concurrence), "-p", str(fichier_corps),
         "-T", "application/json", f"{URL}/predict"],
        capture_output=True, text=True, check=True,
    ).stdout  # fmt: skip

    def valeur(motif: str) -> float:
        trouve = re.search(motif, sortie)
        return float(trouve.group(1)) if trouve else 0.0

    return {
        "utilisateurs_simultanes": concurrence,
        "requetes": total,
        "debit_req_s": valeur(r"Requests per second:\s+([\d.]+)"),
        "moyenne_ms": valeur(r"Time per request:\s+([\d.]+) \[ms\] \(mean\)"),
        "p50_ms": valeur(r"\n\s+50%\s+(\d+)"),
        "p95_ms": valeur(r"\n\s+95%\s+(\d+)"),
        "p99_ms": valeur(r"\n\s+99%\s+(\d+)"),
        "max_ms": valeur(r"\n\s+100%\s+(\d+)"),
        "echecs": int(valeur(r"Failed requests:\s+(\d+)") + valeur(r"Non-2xx responses:\s+(\d+)")),
    }


def configuration() -> dict:
    def sysctl(cle: str) -> str:
        try:
            return subprocess.check_output(["sysctl", "-n", cle], text=True).strip()
        except (OSError, subprocess.CalledProcessError):
            return ""

    memoire = sysctl("hw.memsize")
    return {
        "systeme": f"{platform.system()} {platform.release()} ({platform.machine()})",
        "processeur": sysctl("machdep.cpu.brand_string") or platform.processor(),
        "coeurs_logiques": os.cpu_count(),
        "memoire_go": round(int(memoire) / 1024**3, 1) if memoire.isdigit() else None,
        "python": platform.python_version(),
        "scikit-learn": sklearn.__version__,
        "numpy": np.__version__,
        "serveur": "uvicorn, endpoint synchrone exécuté dans le pool de threads",
        "generateur_de_charge": "ApacheBench (ab), connexions persistantes, même machine",
    }


def main() -> None:
    if shutil.which("ab") is None:
        sys.exit("ApacheBench (ab) est requis pour la charge progressive.")
    resultats = {"date": time.strftime("%Y-%m-%d %H:%M:%S"), "configuration": configuration()}

    print("Inférence…")
    modeles = sorted(config.REPERTOIRE_MODELES.glob("credit_risk_v*.joblib"))
    resultats["inference"] = [inference(m) for m in modeles]
    for r in resultats["inference"]:
        print(
            f"  v{r['version']} : P95 {r['inference_threads_defaut']['p95_ms']:.3f} ms "
            f"(threads par défaut), {r['inference_1_thread']['p95_ms']:.3f} ms (1 thread)"
        )

    with tempfile.TemporaryDirectory() as tmp:
        corps = Path(tmp) / "demande.json"
        corps.write_text(json.dumps(DEMANDE), encoding="utf-8")
        resultats["charge_progressive"] = {}
        for processus in CONFIGURATIONS_SERVEUR:
            serveur = demarrer_serveur(processus)
            try:
                if processus == 1:
                    resultats["api_sequentielle"] = api_sequentielle()
                    print(
                        f"API séquentielle : P95 {resultats['api_sequentielle']['p95_ms']:.2f} ms"
                    )
                paliers = []
                for concurrence in PALIERS_CONCURRENCE:
                    mesure = palier_ab(concurrence, corps)
                    paliers.append(mesure)
                    print(
                        f"  {processus} processus, {concurrence:>3} utilisateurs : "
                        f"P95 {mesure['p95_ms']:.0f} ms, {mesure['debit_req_s']:.0f} req/s, "
                        f"échecs {mesure['echecs']}"
                    )
                resultats["charge_progressive"][f"{processus}_processus"] = paliers
            finally:
                serveur.terminate()
                serveur.wait(timeout=15)

    sortie = RACINE / "reports" / "performance" / "resultats_performance.json"
    sortie.parent.mkdir(parents=True, exist_ok=True)
    sortie.write_text(json.dumps(resultats, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")
    print(f"Résultats : {sortie}")


if __name__ == "__main__":
    main()
