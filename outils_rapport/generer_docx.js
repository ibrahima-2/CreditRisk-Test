// Génère le rapport Word à partir de reports/06_rapport_qualification.md (source unique).
// Prérequis : npm install docx (dans outils_rapport/)
// Usage : node outils_rapport/generer_docx.js . reports/Rapport_qualification_CreditRisk.docx
const fs = require("fs");
const path = require("path");
const {
  Document, Packer, Paragraph, TextRun, ImageRun, Table, TableRow, TableCell, WidthType,
  BorderStyle, ShadingType, AlignmentType, HeadingLevel, LevelFormat, Footer, PageNumber,
  TableOfContents, PageBreak, TabStopType,
} = require("docx");

const RACINE = process.argv[2];
const SORTIE = process.argv[3];
const RAPPORTS = path.join(RACINE, "reports");
const source = fs.readFileSync(path.join(RAPPORTS, "06_rapport_qualification.md"), "utf8");

const LARGEUR = 9638; // A4 (11906) - 2 x 1134 (2 cm)
const POLICE = "Times New Roman";
const MONO = "Consolas";
const ENCRE = "000000";
const NOIR = "000000";
const VERT = "A9D08E"; // en-têtes de tableaux
const GRIS = "595959";

// ---------------------------------------------------------------- texte en ligne
function runs(texte, base = {}) {
  const morceaux = texte.split(/(\*\*[^*]+\*\*|`[^`]+`|\*[^*\s][^*]*\*)/g).filter((m) => m !== "");
  return morceaux.map((m) => {
    if (m.startsWith("**")) return new TextRun({ ...base, text: m.slice(2, -2), bold: true });
    if (m.startsWith("`"))
      return new TextRun({
        ...base, text: m.slice(1, -1), font: MONO, size: Math.round((base.size || 22) * 0.86),
        shading: { type: ShadingType.CLEAR, fill: "F0F0F0", color: "auto" },
      });
    if (m.startsWith("*") && m.endsWith("*") && m.length > 2)
      return new TextRun({ ...base, text: m.slice(1, -1), italics: true });
    return new TextRun({ ...base, text: m });
  });
}

// ---------------------------------------------------------------- images
function dimensionsPng(fichier) {
  const b = fs.readFileSync(fichier);
  return { largeur: b.readUInt32BE(16), hauteur: b.readUInt32BE(20) };
}

function image(chemin, legende) {
  const fichier = path.join(RAPPORTS, chemin);
  const { largeur, hauteur } = dimensionsPng(fichier);
  const maxL = 640, maxH = 760; // pixels à 96 ppp
  let l = largeur / 2, h = hauteur / 2; // captures en 2x
  const echelle = Math.min(maxL / l, maxH / h, 1);
  l = Math.round(l * echelle); h = Math.round(h * echelle);
  return [
    new Paragraph({
      alignment: AlignmentType.CENTER, keepNext: true, spacing: { before: 160, after: 60 },
      children: [new ImageRun({ type: "png", data: fs.readFileSync(fichier), transformation: { width: l, height: h },
        altText: { title: legende, description: legende, name: path.basename(chemin) } })],
    }),
    new Paragraph({
      alignment: AlignmentType.CENTER, spacing: { after: 220 },
      children: runs(legende, { italics: true, size: 18, color: GRIS }),
    }),
  ];
}

// ---------------------------------------------------------------- tableaux
const bordure = { style: BorderStyle.SINGLE, size: 4, color: "BFBFBF" };
const bordures = { top: bordure, bottom: bordure, left: bordure, right: bordure };

function largeursColonnes(lignes) {
  const n = lignes[0].length;
  const nettoyer = (t) => (t || "").replace(/[*`]/g, "");
  const poids = Array.from({ length: n }, (_, j) => {
    const max = Math.max(...lignes.map((l) => nettoyer(l[j]).length));
    return Math.min(Math.max(max, 6), 60);
  });
  // largeur minimale : le mot le plus long de la colonne tient sur une ligne
  const minima = Array.from({ length: n }, (_, j) => {
    const mot = Math.max(...lignes.map((l) => Math.max(...nettoyer(l[j]).split(/[\s/]+/).map((m) => m.length))));
    return Math.min(Math.max(mot * 115 + 240, 800), 3200);
  });
  const total = poids.reduce((a, b) => a + b, 0);
  const brutes = poids.map((p, j) => Math.max(Math.round((p / total) * LARGEUR), minima[j]));
  const somme = brutes.reduce((a, b) => a + b, 0);
  const ajustees = brutes.map((b) => Math.floor((b * LARGEUR) / somme));
  ajustees[ajustees.length - 1] += LARGEUR - ajustees.reduce((a, b) => a + b, 0);
  return ajustees;
}

function tableau(lignes) {
  const largeurs = largeursColonnes(lignes);
  const rangs = lignes.map((cellules, i) =>
    new TableRow({
      tableHeader: i === 0,
      cantSplit: true,
      children: cellules.map((texte, j) =>
        new TableCell({
          borders: bordures,
          width: { size: largeurs[j], type: WidthType.DXA },
          shading: i === 0 ? { fill: VERT, type: ShadingType.CLEAR, color: "auto" } : undefined,
          margins: { top: 50, bottom: 50, left: 90, right: 90 },
          children: [new Paragraph({ children: runs(texte, { size: 17, bold: i === 0 }) })],
        })
      ),
    })
  );
  return [
    new Table({ width: { size: LARGEUR, type: WidthType.DXA }, columnWidths: largeurs, rows: rangs }),
    new Paragraph({ spacing: { after: 120 }, children: [] }),
  ];
}

// ---------------------------------------------------------------- analyse du Markdown
function cellules(ligne) {
  return ligne.trim().replace(/^\|/, "").replace(/\|$/, "").split("|").map((c) => c.trim());
}

const corps = [];
let titre = "";
let instanceListe = 0;
const lignes = source.split("\n");
let i = 0;
let premierH2 = true;
while (i < lignes.length) {
  const ligne = lignes[i];
  if (ligne.startsWith("# ")) { titre = ligne.slice(2).trim(); i++; continue; }
  if (ligne.startsWith("## ")) {
    corps.push(new Paragraph({ heading: HeadingLevel.HEADING_1, pageBreakBefore: true,
      children: runs(ligne.slice(3).trim()) }));
    premierH2 = false; i++; continue;
  }
  if (ligne.startsWith("### ")) {
    corps.push(new Paragraph({ heading: HeadingLevel.HEADING_2, children: runs(ligne.slice(4).trim()) }));
    i++; continue;
  }
  if (ligne.startsWith("```")) {
    i++;
    const bloc = [];
    while (i < lignes.length && !lignes[i].startsWith("```")) { bloc.push(lignes[i]); i++; }
    i++;
    bloc.forEach((b, k) => corps.push(new Paragraph({
      spacing: { before: k === 0 ? 80 : 0, after: k === bloc.length - 1 ? 160 : 0 },
      shading: { type: ShadingType.CLEAR, fill: "F3F3F3", color: "auto" },
      children: [new TextRun({ text: b || " ", font: MONO, size: 16 })],
    })));
    continue;
  }
  const img = ligne.match(/^!\[(.+)\]\((.+)\)\s*$/);
  if (img) { corps.push(...image(img[2], img[1])); i++; continue; }
  if (ligne.trim().startsWith("|")) {
    const bloc = [];
    while (i < lignes.length && lignes[i].trim().startsWith("|")) { bloc.push(lignes[i]); i++; }
    const donnees = bloc.filter((l) => !/^\s*\|[\s:|-]+\|\s*$/.test(l)).map(cellules);
    corps.push(...tableau(donnees));
    continue;
  }
  if (/^\s*- /.test(ligne)) {
    while (i < lignes.length && /^\s*- /.test(lignes[i])) {
      let texte = lignes[i].replace(/^\s*- /, "");
      i++;
      while (i < lignes.length && /^\s{2,}\S/.test(lignes[i]) && !/^\s*- /.test(lignes[i])) {
        texte += " " + lignes[i].trim(); i++;
      }
      corps.push(new Paragraph({ numbering: { reference: "puces", level: 0 }, spacing: { after: 60 },
        children: runs(texte) }));
    }
    continue;
  }
  if (/^\d+\. /.test(ligne)) {
    instanceListe++;
    while (i < lignes.length && /^\d+\. /.test(lignes[i])) {
      let texte = lignes[i].replace(/^\d+\. /, "");
      i++;
      while (i < lignes.length && /^\s{2,}\S/.test(lignes[i])) { texte += " " + lignes[i].trim(); i++; }
      corps.push(new Paragraph({ numbering: { reference: "numeros", level: 0, instance: instanceListe },
        spacing: { after: 60 }, children: runs(texte) }));
    }
    continue;
  }
  if (ligne.trim() === "") { i++; continue; }
  if (premierH2) { i++; continue; } // sous-titre du Markdown : déjà sur la page de garde
  // paragraphe : lignes consécutives non vides
  let texte = ligne.trim();
  i++;
  while (i < lignes.length && lignes[i].trim() !== "" && !/^(#|\||!\[|```|\s*- |\d+\. )/.test(lignes[i])) {
    texte += " " + lignes[i].trim(); i++;
  }
  corps.push(new Paragraph({ spacing: { after: 120 }, alignment: AlignmentType.JUSTIFIED, children: runs(texte) }));
}

// ---------------------------------------------------------------- page de garde
function ligneInfo(cle, valeur) {
  return new TableRow({ children: [
    new TableCell({ borders: bordures, width: { size: 3000, type: WidthType.DXA },
      shading: { fill: VERT, type: ShadingType.CLEAR, color: "auto" },
      margins: { top: 80, bottom: 80, left: 120, right: 120 },
      children: [new Paragraph({ children: [new TextRun({ text: cle, bold: true, size: 20 })] })] }),
    new TableCell({ borders: bordures, width: { size: 6638, type: WidthType.DXA },
      margins: { top: 80, bottom: 80, left: 120, right: 120 },
      children: [new Paragraph({ children: runs(valeur, { size: 20 }) })] }),
  ] });
}

const garde = [
  new Paragraph({ spacing: { before: 2400, after: 120 }, children: [
    new TextRun({ text: "Rapport de qualification", font: POLICE, size: 52, bold: true, color: NOIR })] }),
  new Paragraph({ spacing: { after: 480 }, border: { bottom: { style: BorderStyle.SINGLE, size: 12, color: NOIR, space: 8 } },
    children: [new TextRun({ text: "Système d'estimation du risque de défaut de remboursement (CreditRisk API)",
      size: 28, color: GRIS })] }),
  new Paragraph({ spacing: { after: 240 }, children: [new TextRun({
    text: "Tests fonctionnels, d'intégration, de robustesse, de non-régression et de performance ; automatisation GitHub Actions.",
    size: 22 })] }),
  new Table({ width: { size: LARGEUR, type: WidthType.DXA }, columnWidths: [3000, 6638], rows: [
    ligneInfo("Module", "Test logiciel, Master 2"),
    ligneInfo("Étudiant(e)", "à compléter"),
    ligneInfo("Version évaluée", "API 1.0.0, modèle credit-risk v1.0.0 (régression logistique)"),
    ligneInfo("Date", "22 novembre 2026"),
    ligneInfo("Dépôt", process.env.URL_DEPOT || "CreditRisk-Test (URL GitHub à compléter)"),
    ligneInfo("Résultat", "334 tests : 333 réussis, 1 ignoré ; couverture 99,86 % ; 22 exigences conformes ; 10 anomalies (5 corrigées)"),
  ] }),
  new Paragraph({ spacing: { before: 480 }, children: [new TextRun({
    text: "Données synthétiques : elles servent à tester le système et ne démontrent pas la performance réelle d'un modèle de crédit.",
    italics: true, size: 19, color: GRIS })] }),
  new Paragraph({ children: [new PageBreak()] }),
  new Paragraph({ spacing: { after: 200 }, children: [new TextRun({ text: "Sommaire", bold: true, size: 32, color: NOIR })] }),
  new TableOfContents("Sommaire", { hyperlink: true, headingStyleRange: "1-2" }),
];

const doc = new Document({
  creator: "CreditRisk-Test",
  title: titre,
  description: "Rapport de qualification du prototype CreditRisk",
  features: { updateFields: true },
  styles: {
    default: { document: { run: { font: POLICE, size: 22, color: ENCRE } } },
    paragraphStyles: [
      { id: "Heading1", name: "Heading 1", basedOn: "Normal", next: "Normal", quickFormat: true,
        run: { font: POLICE, size: 32, bold: true, color: NOIR },
        paragraph: { spacing: { before: 120, after: 200 }, keepNext: true, outlineLevel: 0 } },
      { id: "Heading2", name: "Heading 2", basedOn: "Normal", next: "Normal", quickFormat: true,
        run: { font: POLICE, size: 26, bold: true, color: NOIR },
        paragraph: { spacing: { before: 280, after: 120 }, keepNext: true, outlineLevel: 1 } },
    ],
  },
  numbering: { config: [
    { reference: "puces", levels: [{ level: 0, format: LevelFormat.BULLET, text: "•", alignment: AlignmentType.LEFT,
      style: { paragraph: { indent: { left: 540, hanging: 270 } } } }] },
    { reference: "numeros", levels: [{ level: 0, format: LevelFormat.DECIMAL, text: "%1.", alignment: AlignmentType.LEFT,
      style: { paragraph: { indent: { left: 540, hanging: 300 } } } }] },
  ] },
  sections: [{
    properties: { page: { size: { width: 11906, height: 16838 },
      margin: { top: 1134, bottom: 1134, left: 1134, right: 1134 } } },
    footers: { default: new Footer({ children: [new Paragraph({
      tabStops: [{ type: TabStopType.RIGHT, position: LARGEUR }],
      border: { top: { style: BorderStyle.SINGLE, size: 4, color: "BFBFBF", space: 4 } },
      children: [
        new TextRun({ text: "CreditRisk API : rapport de qualification", size: 16, color: GRIS }),
        new TextRun({ children: ["\tPage ", PageNumber.CURRENT, " / ", PageNumber.TOTAL_PAGES], size: 16, color: GRIS }),
      ] })] }) },
    children: [...garde, ...corps],
  }],
});

Packer.toBuffer(doc).then((tampon) => {
  fs.writeFileSync(SORTIE, tampon);
  console.log(`Écrit : ${SORTIE} (${(tampon.length / 1024 / 1024).toFixed(1)} Mo)`);
});
