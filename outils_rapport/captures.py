"""Génère les images du rapport : extraits de code façon VS Code, terminal VS Code, pages web.

Prérequis : pygments, playwright (navigateur Chromium installé), serveur lançable depuis .venv.
Usage : python outils_rapport/captures.py . reports/preuves
Les captures de terminal sont des rendus fidèles de sorties réelles (fichiers .ansi de
reports/preuves), mis en forme comme le terminal intégré de VS Code.
"""

from __future__ import annotations

import html
import re
import subprocess
import sys
import tempfile
import time
from pathlib import Path

from playwright.sync_api import sync_playwright
from pygments import highlight
from pygments.formatters import HtmlFormatter
from pygments.lexers import JsonLexer, PythonLexer, YamlLexer

RACINE = Path(sys.argv[1]).resolve()
ANSI = Path(sys.argv[2]).resolve()
SORTIE = RACINE / "reports" / "captures"
SORTIE.mkdir(parents=True, exist_ok=True)
TRAVAIL = Path(tempfile.mkdtemp(prefix="captures_"))
TRAVAIL.mkdir(exist_ok=True)

POLICE = "Menlo, 'SF Mono', Monaco, monospace"

# ------------------------------------------------------------------ thème Dark+ (VS Code)
CSS_DARK_PLUS = """
.code .k, .code .kn, .code .ow2 { color: #c586c0; }
.code .kd, .code .kc, .code .ow, .code .si { color: #569cd6; }
.code .nf, .code .fm, .code .nd, .code .fc, .code .nbf { color: #dcdcaa; }
.code .nc, .code .ne, .code .nbt, .code .cc { color: #4ec9b0; }
.code .s, .code .s1, .code .s2, .code .sa, .code .sd, .code .se, .code .sh { color: #ce9178; }
.code .mi, .code .mf, .code .m { color: #b5cea8; }
.code .c, .code .c1, .code .cm, .code .ch { color: #6a9955; }
.code .n, .code .nv, .code .bp, .code .nn { color: #9cdcfe; }
.code .nn { color: #4ec9b0; }
.code .o, .code .p, .code .w, .code .err { color: #d4d4d4; }
.code .nt { color: #569cd6; }
.json .nt { color: #9cdcfe; }
"""

TYPES_NATIFS = {"int", "float", "str", "dict", "list", "set", "tuple", "bool", "type",
                "object", "bytes", "Exception", "MemoryError", "KeyError", "TypeError",
                "ValueError", "RuntimeError"}  # fmt: skip
MOTS_DECLARATION = {"def", "class", "lambda", "async"}


def colorer(source: str, lexer) -> list[str]:
    """Code coloré, une chaîne HTML par ligne."""
    brut = highlight(source, lexer, HtmlFormatter(nowrap=True))
    brut = re.sub(
        r'<span class="k">(\w+)</span>',
        lambda m: f'<span class="{"kd" if m.group(1) in MOTS_DECLARATION else "k"}">{m.group(1)}</span>',
        brut,
    )
    brut = re.sub(
        r'<span class="nb">(\w+)</span>',
        lambda m: f'<span class="{"nbt" if m.group(1) in TYPES_NATIFS else "nbf"}">{m.group(1)}</span>',
        brut,
    )
    # appels de fonctions / classes : nom suivi d'une parenthèse ouvrante
    brut = re.sub(
        r'<span class="n">(\w+)</span>(<span class="p">\()',
        lambda m: f'<span class="{"cc" if m.group(1)[0].isupper() else "fc"}">{m.group(1)}</span>{m.group(2)}',
        brut,
    )
    lignes = brut.split("\n")
    if lignes and lignes[-1] == "":
        lignes.pop()
    return lignes


def page_editeur(fichier: str, debut: int, fin: int, fil: str, langage: str) -> str:
    chemin = RACINE / fichier
    toutes = chemin.read_text(encoding="utf-8").splitlines()
    extrait = "\n".join(toutes[debut - 1 : fin]) + "\n"
    lexer = {"python": PythonLexer(), "yaml": YamlLexer(), "json": JsonLexer()}[langage]
    lignes = colorer(extrait, lexer)
    numeros = "".join(f"<div>{n}</div>" for n in range(debut, debut + len(lignes)))
    code = "".join(f"<div>{l or '&nbsp;'}</div>" for l in lignes)
    nom = Path(fichier).name
    icone = {"python": ("#3c78aa", "py"), "yaml": ("#cb171e", "!"), "json": ("#cbcb41", "{}")}[langage]
    morceaux = " <span class='sep'>›</span> ".join(html.escape(p) for p in fil.split(" > "))
    langue = {"python": "Python", "yaml": "YAML", "json": "JSON"}[langage]
    return f"""<!doctype html><html><head><meta charset="utf-8"><style>
body {{ margin:0; background:#ffffff; }}
#fenetre {{ display:inline-block; min-width:980px; background:#1e1e1e; border-radius:10px; overflow:hidden;
  box-shadow: 0 8px 28px rgba(0,0,0,.35); font-family:-apple-system, 'Segoe UI', sans-serif; margin:18px; }}
.titre {{ height:34px; background:#3c3c3c; color:#cccccc; font-size:12.5px; display:flex; align-items:center; position:relative; }}
.feux {{ display:flex; gap:8px; margin-left:13px; }}
.feux span {{ width:12px; height:12px; border-radius:50%; display:inline-block; }}
.titre .nom {{ position:absolute; left:0; right:0; text-align:center; }}
.onglets {{ height:35px; background:#252526; display:flex; }}
.onglet {{ background:#1e1e1e; color:#ffffff; font-size:13px; padding:0 16px; display:flex; align-items:center; gap:7px;
  border-top:1px solid #0078d4; }}
.onglet .ic {{ color:{icone[0]}; font-weight:700; font-size:11px; font-family:{POLICE}; }}
.onglet .x {{ color:#8b8b8b; margin-left:10px; }}
.fil {{ color:#a9a9a9; font-size:12.5px; padding:5px 16px 6px; }}
.fil .sep {{ color:#6e6e6e; }}
.editeur {{ display:flex; font-family:{POLICE}; font-size:13px; line-height:19.5px; padding:4px 0 12px; }}
.num {{ color:#6e7681; text-align:right; padding:0 20px 0 16px; min-width:34px; user-select:none; }}
.code {{ color:#d4d4d4; white-space:pre; padding-right:30px; }}
.etat {{ height:22px; background:#007acc; color:#ffffff; font-size:12px; display:flex; align-items:center;
  justify-content:space-between; padding:0 12px; }}
.etat span {{ margin-left:16px; }}
{CSS_DARK_PLUS}
</style></head><body><div id="fenetre">
<div class="titre"><div class="feux"><span style="background:#ff5f57"></span><span style="background:#febc2e"></span><span style="background:#28c840"></span></div>
<div class="nom">{html.escape(nom)} — CreditRisk-Test</div></div>
<div class="onglets"><div class="onglet"><span class="ic">{icone[1]}</span>{html.escape(nom)}<span class="x">×</span></div></div>
<div class="fil">{morceaux}</div>
<div class="editeur"><div class="num">{numeros}</div><div class="code {langage}">{code}</div></div>
<div class="etat"><div><span style="margin-left:0">⎇ main</span></div><div><span>Ln {debut}, Col 1</span><span>Espaces : 4</span><span>UTF-8</span><span>LF</span><span>{langue}</span></div></div>
</div></body></html>"""


# ------------------------------------------------------------------ terminal VS Code (ANSI)
COULEURS = {30: "#000000", 31: "#cd3131", 32: "#0dbc79", 33: "#e5e510", 34: "#2472c8",
            35: "#bc3fbc", 36: "#11a8cd", 37: "#e5e5e5", 90: "#666666", 91: "#f14c4c",
            92: "#23d18b", 93: "#f5f543", 94: "#3b8eea", 95: "#d670d6", 96: "#29b8db",
            97: "#e5e5e5"}  # fmt: skip


def ansi_vers_html(texte: str) -> str:
    sortie, gras, couleur = [], False, None
    for morceau in re.split(r"(\x1b\[[0-9;]*m)", texte):
        m = re.fullmatch(r"\x1b\[([0-9;]*)m", morceau)
        if m:
            for code in [int(c) for c in (m.group(1) or "0").split(";") if c != ""] or [0]:
                if code == 0:
                    gras, couleur = False, None
                elif code == 1:
                    gras = True
                elif code == 22:
                    gras = False
                elif code == 39:
                    couleur = None
                elif code in COULEURS:
                    couleur = COULEURS[code]
            continue
        if not morceau:
            continue
        style = (f"color:{couleur};" if couleur else "") + ("font-weight:700;" if gras else "")
        texte_html = html.escape(morceau)
        sortie.append(f'<span style="{style}">{texte_html}</span>' if style else texte_html)
    return "".join(sortie)


def page_terminal(texte: str, largeur: int = 1100) -> str:
    return f"""<!doctype html><html><head><meta charset="utf-8"><style>
body {{ margin:0; background:#ffffff; }}
#fenetre {{ display:inline-block; width:{largeur}px; background:#1e1e1e; border-radius:10px; overflow:hidden;
  box-shadow: 0 8px 28px rgba(0,0,0,.35); margin:18px; font-family:-apple-system, 'Segoe UI', sans-serif; }}
.entete {{ height:35px; display:flex; align-items:center; justify-content:space-between; padding:0 14px;
  border-top:1px solid #2b2b2b; background:#1e1e1e; }}
.entete .tabs span {{ color:#9d9d9d; font-size:11px; letter-spacing:.4px; margin-right:22px; padding:9px 0 7px; }}
.entete .tabs span.actif {{ color:#e7e7e7; border-bottom:1px solid #e7e7e7; }}
.entete .droite {{ color:#9d9d9d; font-size:12px; }}
pre {{ margin:0; padding:8px 18px 16px; color:#cccccc; font-family:{POLICE}; font-size:12px; line-height:17px;
  white-space:pre-wrap; word-break:break-all; }}
</style></head><body><div id="fenetre">
<div class="entete"><div class="tabs"><span>PROBLÈMES</span><span>SORTIE</span><span>CONSOLE DE DÉBOGAGE</span><span class="actif">TERMINAL</span><span>PORTS</span></div>
<div class="droite">zsh — CreditRisk-Test</div></div>
<pre>{ansi_vers_html(texte)}</pre></div></body></html>"""


def invite(commande: str) -> str:
    return f"\x1b[1;32m(.venv) CreditRisk-Test %\x1b[0m {commande}\n"


# ------------------------------------------------------------------------- inventaire
EXTRAITS = [
    # (nom, fichier, marqueur de début, marqueur de fin, décalage de fin, fil d'Ariane, langage)
    ("code_validation_schema", "app/validation.py", "class DemandeCredit", "        return valeur", 0,
     "app > validation.py > DemandeCredit", "python"),
    ("code_prediction_contrat", "app/prediction.py", "    def predire_lot",
     "        return float(self.predire_lot(matrice)[0])", 0,
     "app > prediction.py > ServiceModele > predire_lot", "python"),
    ("code_main_gestion_erreurs", "app/main.py", "    @app.exception_handler(ModeleIndisponibleError)",
     "    @app.exception_handler(Exception)", 3, "app > main.py > create_app", "python"),
    ("code_test_api_s1", "tests/test_api.py", "@pytest.mark.exigence(\"EX04\", \"EX20\")\ndef test_s1_requete_valide",
     "    assert float(reponse.headers[\"X-Temps-Traitement-ms\"])", 0,
     "tests > test_api.py > test_s1_requete_valide", "python"),
    ("code_test_integration_pannes", "tests/test_integration.py", "CAS_CHARGEMENT = {",
     "    assert client.get(\"/health\").status_code == 503", 0,
     "tests > test_integration.py > test_modele_non_chargeable", "python"),
    ("code_test_robustesse_proprietes", "tests/test_robustness.py", "VALEURS_ARBITRAIRES = st.one_of(",
     "def test_propriete_aucune_entree_ne_provoque_d_erreur_500", 3,
     "tests > test_robustness.py > test_propriete_aucune_entree_ne_provoque_d_erreur_500", "python"),
    ("code_test_robustesse_monotonie", "tests/test_robustness.py",
     "@pytest.mark.exigence(\"EX18\")\n@pytest.mark.parametrize(\"base\"",
     "    assert all(e >= -1e-12 for e in ecarts)", 0,
     "tests > test_robustness.py > test_monotonie_metier", "python"),
    ("code_test_regression_metriques", "tests/test_regression.py",
     "@pytest.mark.exigence(\"EX07\")\ndef test_metriques_dans_les_tolerances",
     "    assert critere_attendu in rapport.non_conformites", 0,
     "tests > test_regression.py > test_metriques_dans_les_tolerances", "python"),
    ("code_tolerances_json", "model/reference/tolerances_non_regression.json", "  \"metriques\": {",
     "  \"segments\": {", -1, "model > reference > tolerances_non_regression.json", "json"),
    ("code_workflow_ci", ".github/workflows/tests.yml", "  tests:",
     "          --junitxml=reports/ci/junit.xml", 0, ".github > workflows > tests.yml > jobs > tests", "yaml"),
]  # fmt: skip


def bornes(fichier: str, debut: str, fin: str, decalage: int) -> tuple[int, int]:
    texte = (RACINE / fichier).read_text(encoding="utf-8")
    i = texte.index(debut)
    j = texte.index(fin, i)
    return texte.count("\n", 0, i) + 1, texte.count("\n", 0, j) + 1 + decalage


def capturer_html(page, contenu: str, nom: str) -> None:
    fichier = TRAVAIL / f"{nom}.html"
    fichier.write_text(contenu, encoding="utf-8")
    page.goto(fichier.as_uri())
    page.wait_for_timeout(150)
    page.locator("#fenetre").screenshot(path=str(SORTIE / f"{nom}.png"))


def main() -> None:
    with sync_playwright() as p:
        navigateur = p.chromium.launch()
        page = navigateur.new_page(viewport={"width": 1300, "height": 900}, device_scale_factor=2)

        for nom, fichier, debut, fin, decalage, fil, langage in EXTRAITS:
            a, b = bornes(fichier, debut, fin, decalage)
            capturer_html(page, page_editeur(fichier, a, b, fil, langage), nom)
            print(f"{nom}: {fichier} L{a}-{b}")

        terminaux = {
            "terminal_pytest_complet": (invite(
                "HYPOTHESIS_PROFILE=ci pytest --cov=app --cov=ml --cov-branch --cov-report=term-missing "
                "--cov-report=html:reports/preuves/htmlcov --cov-fail-under=90 --junitxml=reports/preuves/junit.xml")
                + (RACINE / "reports/preuves/pytest_complet.ansi").read_text(encoding="utf-8"), 1180),
            "terminal_ruff": ((ANSI / "ruff.ansi").read_text(encoding="utf-8"), 760),
            "terminal_echec_volontaire": (invite("FORCER_ECHEC=1 pytest tests/test_echec_volontaire.py; echo \"Code de sortie : $?\"")
                + (RACINE / "reports/preuves/echec_volontaire.ansi").read_text(encoding="utf-8"), 1000),
        }  # fmt: skip
        for nom in ("api_nominal", "api_erreurs", "api_503", "pytest_candidat_v1.1.0_execution3",
                    "mutation_m2", "mutation_m1"):  # fmt: skip
            fichier = ANSI / f"{nom}.ansi"
            if fichier.exists():
                cle = "candidat_v1_1_0" if nom.startswith("pytest_candidat") else nom
                terminaux[f"terminal_{cle}"] = (fichier.read_text(encoding="utf-8"), 1180)
        for nom, (texte, largeur) in terminaux.items():
            capturer_html(page, page_terminal(texte, largeur), nom)
            print(nom)

        # ------------------------------------------------------------ pages web réelles
        page_cov = navigateur.new_page(viewport={"width": 1100, "height": 300}, device_scale_factor=2)
        page_cov.goto((RACINE / "reports/preuves/htmlcov/index.html").as_uri())
        page_cov.wait_for_timeout(300)
        page_cov.screenshot(path=str(SORTIE / "web_couverture_index.png"), full_page=True)
        page_web = navigateur.new_page(viewport={"width": 1280, "height": 860}, device_scale_factor=2)
        print("web_couverture_index")

        locust = RACINE / "reports/performance/locust.html"
        if locust.exists():
            page_web.goto(locust.as_uri())
            page_web.wait_for_timeout(2500)
            page_web.screenshot(path=str(SORTIE / "web_locust.png"))
            print("web_locust")

        serveur = subprocess.Popen(
            [str(RACINE / ".venv/bin/python"), "-m", "uvicorn", "app.main:app", "--host", "127.0.0.1",
             "--port", "8012", "--log-level", "warning"], cwd=RACINE)  # fmt: skip
        try:
            time.sleep(3)
            page_web.goto("http://127.0.0.1:8012/docs")
            page_web.wait_for_selector(".opblock", timeout=20000)
            page_web.wait_for_timeout(800)
            page_web.screenshot(path=str(SORTIE / "web_swagger_endpoints.png"))
            print("web_swagger_endpoints")
            bloc = page_web.locator("#operations-default-predire_predict_post")
            bloc.locator(".opblock-summary").click()
            page_web.wait_for_timeout(500)
            bloc.locator("button.try-out__btn").click()
            page_web.wait_for_timeout(300)
            zone = bloc.locator("textarea.body-param__text")
            zone.fill('{\n  "age": 35,\n  "revenu_mensuel": 250000,\n  "montant_credit": 1000000,\n'
                      '  "duree_mois": 12,\n  "anciennete_activite": 4\n}')  # fmt: skip
            bloc.locator("button.execute").click()
            page_web.wait_for_selector("#operations-default-predire_predict_post .live-responses-table",
                                       timeout=10000)  # fmt: skip
            page_web.wait_for_timeout(600)
            reponse = bloc.locator(".responses-wrapper .live-responses-table").first
            reponse.scroll_into_view_if_needed()
            reponse.screenshot(path=str(SORTIE / "web_swagger_predict_reponse.png"))
            print("web_swagger_predict_reponse")
        finally:
            serveur.terminate()
            serveur.wait()
        navigateur.close()


if __name__ == "__main__":
    main()
