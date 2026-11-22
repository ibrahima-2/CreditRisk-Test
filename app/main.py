"""API de prédiction du risque de défaut (FastAPI).

Endpoints :
- GET  /health     : disponibilité du service et du modèle ;
- POST /predict    : estimation du risque de défaut d'une demande ;
- GET  /model-info : métadonnées de la version du modèle chargée.

Principe de sécurité : aucune trace technique (pile d'appels, chemin de fichier, message
d'exception) n'est renvoyée au client. Les détails sont journalisés côté serveur et
corrélés par l'identifiant de requête (en-tête ``X-Request-ID``).
"""

from __future__ import annotations

import logging
import re
import time
import uuid
from contextlib import asynccontextmanager

from fastapi import FastAPI, Request
from fastapi.exceptions import RequestValidationError
from fastapi.responses import JSONResponse
from starlette.exceptions import HTTPException as StarletteHTTPException

from app import config
from app.prediction import (
    ErreurChargementModele,
    ErreurPrediction,
    ModeleIndisponibleError,
    ServiceModele,
)
from app.preprocessing import VARIABLES_ENTREE, ErreurPretraitement
from app.schemas import InfoModele, ReponseErreur, ReponsePrediction, ReponseSante
from app.validation import DemandeCredit, formater_erreurs

journal = logging.getLogger("creditrisk.api")

_IDENTIFIANT_VALIDE = re.compile(r"^[A-Za-z0-9-]{1,64}$")

_REPONSES_ERREUR = {
    400: {"model": ReponseErreur, "description": "Requête mal formée"},
    422: {"model": ReponseErreur, "description": "Données invalides"},
    500: {"model": ReponseErreur, "description": "Erreur interne"},
    503: {"model": ReponseErreur, "description": "Modèle indisponible"},
}


class ErreurInterne(Exception):
    """Erreur inattendue pendant le traitement d'une demande."""


def reponse_erreur(
    request: Request,
    statut: int,
    code: str,
    message: str,
    details: list[dict[str, str]] | None = None,
    entetes: dict[str, str] | None = None,
) -> JSONResponse:
    corps = ReponseErreur(
        code=code,
        message=message,
        details=details or [],
        identifiant_requete=getattr(request.state, "identifiant_requete", None),
    )
    return JSONResponse(status_code=statut, content=corps.model_dump(), headers=entetes)


def create_app(service: ServiceModele | None = None) -> FastAPI:
    """Fabrique de l'application (permet d'injecter un service de modèle dans les tests)."""
    service = service or ServiceModele.depuis_config()

    @asynccontextmanager
    async def cycle_de_vie(_: FastAPI):
        if not service.est_charge:
            try:
                service.charger()
            except ErreurChargementModele:
                journal.error("Démarrage en mode dégradé : modèle indisponible")
        yield

    app = FastAPI(
        title="CreditRisk API",
        description="Estimation du risque de défaut de remboursement (prototype de test).",
        version=config.VERSION_API,
        lifespan=cycle_de_vie,
    )
    app.state.service_modele = service

    @app.middleware("http")
    async def contexte_requete(request: Request, call_next):
        entrant = request.headers.get("x-request-id", "")
        identifiant = entrant if _IDENTIFIANT_VALIDE.match(entrant) else uuid.uuid4().hex
        request.state.identifiant_requete = identifiant
        debut = time.perf_counter()
        taille = request.headers.get("content-length")
        if taille is not None and (
            not taille.isdigit() or int(taille) > config.TAILLE_MAX_REQUETE_OCTETS
        ):
            reponse = reponse_erreur(
                request,
                413,
                "REQUETE_TROP_VOLUMINEUSE",
                f"Le corps de la requête dépasse {config.TAILLE_MAX_REQUETE_OCTETS} octets.",
            )
        else:
            reponse = await call_next(request)
        reponse.headers["X-Request-ID"] = identifiant
        reponse.headers["X-Temps-Traitement-ms"] = f"{(time.perf_counter() - debut) * 1000:.3f}"
        return reponse

    # ------------------------------------------------------------------ gestion des erreurs
    @app.exception_handler(RequestValidationError)
    async def erreur_validation(request: Request, exc: RequestValidationError):
        erreurs = list(exc.errors())
        if any(e.get("type") == "json_invalid" for e in erreurs):
            return reponse_erreur(
                request,
                400,
                "REQUETE_MAL_FORMEE",
                "Le corps de la requête n'est pas un JSON valide.",
            )
        return reponse_erreur(
            request,
            422,
            "DONNEES_INVALIDES",
            "Les données de la demande ne respectent pas le contrat d'entrée.",
            formater_erreurs(erreurs),
        )

    @app.exception_handler(ModeleIndisponibleError)
    async def erreur_modele_indisponible(request: Request, exc: ModeleIndisponibleError):
        journal.error("[%s] Modèle indisponible : %s", request.state.identifiant_requete, exc)
        return reponse_erreur(
            request,
            503,
            "MODELE_INDISPONIBLE",
            "Le modèle de prédiction est momentanément indisponible. Réessayez plus tard.",
            entetes={"Retry-After": "30"},
        )

    @app.exception_handler(ErreurPretraitement)
    async def erreur_pretraitement(request: Request, exc: ErreurPretraitement):
        journal.error(
            "[%s] Erreur de prétraitement", request.state.identifiant_requete, exc_info=exc
        )
        return reponse_erreur(
            request,
            500,
            "ERREUR_PRETRAITEMENT",
            "La demande n'a pas pu être préparée pour le modèle.",
        )

    @app.exception_handler(ErreurPrediction)
    async def erreur_prediction(request: Request, exc: ErreurPrediction):
        journal.error("[%s] Erreur de prédiction", request.state.identifiant_requete, exc_info=exc)
        return reponse_erreur(
            request,
            500,
            "ERREUR_PREDICTION",
            "Le modèle n'a pas pu produire une estimation valide.",
        )

    @app.exception_handler(ErreurInterne)
    async def erreur_interne(request: Request, exc: ErreurInterne):
        journal.error("[%s] Erreur interne", request.state.identifiant_requete, exc_info=exc)
        return reponse_erreur(request, 500, "ERREUR_INTERNE", "Une erreur interne est survenue.")

    @app.exception_handler(Exception)
    async def erreur_inattendue(request: Request, exc: Exception):
        journal.critical("Erreur non gérée", exc_info=exc)
        return reponse_erreur(request, 500, "ERREUR_INTERNE", "Une erreur interne est survenue.")

    @app.exception_handler(StarletteHTTPException)
    async def erreur_http(request: Request, exc: StarletteHTTPException):
        connus = {
            404: ("RESSOURCE_INTROUVABLE", "Ressource introuvable."),
            405: ("METHODE_NON_AUTORISEE", "Méthode HTTP non autorisée pour cette ressource."),
        }
        code, message = connus.get(exc.status_code, ("ERREUR_HTTP", str(exc.detail)))
        return reponse_erreur(
            request, exc.status_code, code, message, entetes=getattr(exc, "headers", None)
        )

    # ------------------------------------------------------------------------ endpoints
    @app.get("/health", response_model=ReponseSante, responses={503: {"model": ReponseSante}})
    def sante():
        try:
            service.assurer_charge()
        except ModeleIndisponibleError:
            corps = ReponseSante(
                statut="degrade",
                modele_charge=False,
                version_modele=None,
                version_api=config.VERSION_API,
            )
            return JSONResponse(status_code=503, content=corps.model_dump())
        return ReponseSante(
            statut="ok",
            modele_charge=True,
            version_modele=service.metadonnees["version"],
            version_api=config.VERSION_API,
        )

    @app.post("/predict", response_model=ReponsePrediction, responses=_REPONSES_ERREUR)
    def predire(demande: DemandeCredit, request: Request):
        donnees = demande.model_dump()
        try:
            resultat = service.evaluer(donnees)
            metadonnees = service.metadonnees
        except (ModeleIndisponibleError, ErreurPretraitement, ErreurPrediction):
            raise
        except Exception as exc:
            raise ErreurInterne() from exc
        journal.info(
            "[%s] prédiction p=%.4f niveau=%s alertes=%d",
            request.state.identifiant_requete,
            resultat.probabilite_defaut,
            resultat.niveau_risque,
            len(resultat.alertes),
        )
        return ReponsePrediction(
            probabilite_defaut=resultat.probabilite_defaut,
            niveau_risque=resultat.niveau_risque,
            revue_humaine_requise=resultat.revue_humaine_requise,
            alertes=resultat.alertes,
            indicateurs=resultat.indicateurs,
            seuils=metadonnees["seuils"],
            version_modele=metadonnees["version"],
            identifiant_requete=request.state.identifiant_requete,
        )

    @app.get("/model-info", response_model=InfoModele, responses={503: _REPONSES_ERREUR[503]})
    def info_modele():
        metadonnees = service.metadonnees
        champs = set(InfoModele.model_fields) - {"variables_entree", "version_api"}
        return InfoModele(
            **{k: metadonnees[k] for k in champs if k in metadonnees},
            variables_entree=list(VARIABLES_ENTREE),
            version_api=config.VERSION_API,
        )

    return app


app = create_app()
