"""Test de charge Locust (optionnel, non exécuté en CI).

Lancement (serveur démarré au préalable sur le port 8000) :
    pip install -r requirements-perf.txt
    uvicorn app.main:app --port 8000 &
    locust -f scripts/locustfile.py --host http://127.0.0.1:8000 --headless \
        --csv reports/performance/locust --html reports/performance/locust.html

La forme de charge ``ChargeProgressive`` monte par paliers de 1 à 50 utilisateurs.
"""

from __future__ import annotations

from locust import HttpUser, LoadTestShape, between, task

DEMANDE = {
    "age": 35,
    "revenu_mensuel": 250000,
    "montant_credit": 1000000,
    "duree_mois": 12,
    "anciennete_activite": 4,
}


class AgentDeCredit(HttpUser):
    """Un agent saisit une demande toutes les 0,5 à 1,5 s (hypothèse volontairement haute)."""

    wait_time = between(0.5, 1.5)

    @task(8)
    def demande_valide(self):
        self.client.post("/predict", json=DEMANDE, name="POST /predict (valide)")

    @task(1)
    def demande_invalide(self):
        with self.client.post(
            "/predict", json={**DEMANDE, "age": -5}, name="POST /predict (invalide)",
            catch_response=True,
        ) as reponse:  # fmt: skip
            if reponse.status_code == 422:
                reponse.success()

    @task(1)
    def sante(self):
        self.client.get("/health", name="GET /health")


class ChargeProgressive(LoadTestShape):
    """Paliers de 30 s : 1, 5, 10, 25, 50 utilisateurs."""

    paliers = ((30, 1), (60, 5), (90, 10), (120, 25), (150, 50))

    def tick(self):
        temps = self.get_run_time()
        for fin, utilisateurs in self.paliers:
            if temps < fin:
                return utilisateurs, max(utilisateurs, 1)
        return None
