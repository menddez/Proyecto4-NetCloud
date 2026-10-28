// Convierte un archivo Markdown a Word (.docx) legible (titulos, tablas, listas, comandos, negritas).
// Uso: node md_a_docx.js <entrada.md> <salida.docx>
const fs = require('fs');
const d = require('docx');
const {
  Document, Packer, Paragraph, TextRun, HeadingLevel, AlignmentType,
  Table, TableRow, TableCell, WidthType, ShadingType, BorderStyle, LevelFormat, PageNumber, Header
} = d;

const [, , ENTRADA, SALIDA] = process.argv;
const SANS = 'Calibri', MONO = 'Consolas', AZUL = '1F4E79', GRIS = 'EDEFF4', CODEBG = 'F2F2F2';
const md = fs.readFileSync(ENTRADA, 'utf8').replace(/\r\n/g, '\n').split('\n');

// --- inline: **negrita**, `codigo`, resto texto plano ---
function inline(text, base = {}) {
  const runs = [];
  const re = /(\*\*[^*]+\*\*|`[^`]+`)/g;
  let i = 0, m;
  const push = (t, o) => { if (t) runs.push(new TextRun({ text: t, font: SANS, size: 21, ...base, ...o })); };
  while ((m = re.exec(text))) {
    push(text.slice(i, m.index));
    const tok = m[0];
    if (tok.startsWith('**')) push(tok.slice(2, -2), { bold: true });
    else runs.push(new TextRun({ text: tok.slice(1, -1), font: MONO, size: 20, shading: { type: ShadingType.CLEAR, fill: CODEBG }, ...base }));
    i = re.lastIndex;
  }
  push(text.slice(i));
  return runs.length ? runs : [new TextRun({ text: '', font: SANS, size: 21 })];
}

const out = [];
const H = (t, lvl) => new Paragraph({ heading: lvl, spacing: { before: lvl === HeadingLevel.HEADING_1 ? 240 : 160, after: 80 },
  children: [new TextRun({ text: t, font: SANS, bold: true, color: lvl === HeadingLevel.HEADING_1 ? '000000' : AZUL,
    size: lvl === HeadingLevel.HEADING_1 ? 30 : lvl === HeadingLevel.HEADING_2 ? 26 : 23 })] });

function tabla(filas) {
  const headers = filas[0], n = headers.length, rows = filas.slice(1).map((r) => {
    while (r.length < n) r.push('');
    return r.slice(0, n);
  });
  const total = 9360, cw = headers.map(() => Math.floor(total / n));
  const celda = (txt, ri, ci) => new TableCell({ width: { size: cw[ci], type: WidthType.DXA },
    shading: ri < 0 ? { type: ShadingType.CLEAR, fill: AZUL } : (ri % 2 === 1 ? { type: ShadingType.CLEAR, fill: GRIS } : undefined),
    margins: { top: 30, bottom: 30, left: 70, right: 70 },
    children: [new Paragraph({ spacing: { line: 240 },
      children: inline(txt, ri < 0 ? { bold: true, color: 'FFFFFF', size: 20 } : { size: 20 }) })] });
  const tr = (cells, ri) => new TableRow({ tableHeader: ri < 0, children: cells.map((c, ci) => celda(c, ri, ci)) });
  return new Table({ columnWidths: cw, width: { size: total, type: WidthType.DXA },
    rows: [tr(headers, -1), ...rows.map((r, i) => tr(r, i))] });
}
const splitRow = (ln) => ln.trim().replace(/^\|/, '').replace(/\|$/, '')
  .split(/(?<!\\)\|/).map((s) => s.trim().replace(/\\\|/g, '|'));

let i = 0;
while (i < md.length) {
  let ln = md[i];
  if (ln.startsWith('```')) {                      // bloque de codigo
    i++;
    const code = [];
    while (i < md.length && !md[i].startsWith('```')) { code.push(md[i]); i++; }
    i++;
    code.forEach((c, k) => out.push(new Paragraph({ spacing: { line: 240, before: k === 0 ? 60 : 0, after: k === code.length - 1 ? 60 : 0 },
      shading: { type: ShadingType.CLEAR, fill: CODEBG }, border: { left: { style: BorderStyle.SINGLE, size: 18, color: AZUL, space: 6 } },
      children: [new TextRun({ text: c || ' ', font: MONO, size: 19 })] })));
    continue;
  }
  if (ln.startsWith('|') && md[i + 1] && /^\|[\s:|-]+\|$/.test(md[i + 1].trim())) {  // tabla
    const filas = [splitRow(ln)];
    i += 2;
    while (i < md.length && md[i].trim().startsWith('|')) { filas.push(splitRow(md[i])); i++; }
    out.push(tabla(filas));
    out.push(new Paragraph({ children: [new TextRun({ text: '', size: 8 })], spacing: { after: 60 } }));
    continue;
  }
  if (/^#{1,3}\s/.test(ln)) {
    const lvl = ln.startsWith('### ') ? HeadingLevel.HEADING_3 : ln.startsWith('## ') ? HeadingLevel.HEADING_2 : HeadingLevel.HEADING_1;
    out.push(H(ln.replace(/^#+\s/, ''), lvl));
  } else if (/^[-*]\s/.test(ln)) {
    out.push(new Paragraph({ numbering: { reference: 'vinetas', level: 0 }, spacing: { after: 0, line: 276 }, children: inline(ln.replace(/^[-*]\s/, '')) }));
  } else if (/^\d+\.\s/.test(ln)) {
    out.push(new Paragraph({ numbering: { reference: 'numeros', level: 0 }, spacing: { after: 0, line: 276 }, children: inline(ln.replace(/^\d+\.\s/, '')) }));
  } else if (ln.startsWith('> ')) {
    out.push(new Paragraph({ spacing: { line: 276, before: 40, after: 40 }, indent: { left: 360 },
      border: { left: { style: BorderStyle.SINGLE, size: 18, color: 'B0B8C4', space: 8 } },
      children: inline(ln.slice(2), { italics: true, color: '555555' }) }));
  } else if (ln.trim() === '---') {
    out.push(new Paragraph({ border: { bottom: { style: BorderStyle.SINGLE, size: 6, color: 'C0C4CC' } }, spacing: { after: 80 }, children: [new TextRun({ text: '' })] }));
  } else if (ln.trim() === '') {
    out.push(new Paragraph({ children: [new TextRun({ text: '', size: 10 })], spacing: { after: 40 } }));
  } else {
    out.push(new Paragraph({ spacing: { line: 276, after: 40 }, children: inline(ln) }));
  }
  i++;
}

const doc = new Document({
  styles: { default: { document: { run: { font: SANS, size: 21 } } } },
  numbering: { config: [
    { reference: 'vinetas', levels: [{ level: 0, format: LevelFormat.BULLET, text: '•', alignment: AlignmentType.LEFT, style: { paragraph: { indent: { left: 420, hanging: 240 } } } }] },
    { reference: 'numeros', levels: [{ level: 0, format: LevelFormat.DECIMAL, text: '%1.', alignment: AlignmentType.LEFT, style: { paragraph: { indent: { left: 420, hanging: 240 } } } }] }
  ] },
  sections: [{
    properties: { page: { size: { width: 12240, height: 15840 }, margin: { top: 1080, bottom: 1080, left: 1080, right: 1080 } } },
    headers: { default: new Header({ children: [new Paragraph({ alignment: AlignmentType.RIGHT, children: [new TextRun({ font: SANS, size: 16, color: '888888', children: ['NetCloud-Secure · ', PageNumber.CURRENT] })] })] }) },
    children: out
  }]
});
Packer.toBuffer(doc).then((b) => { fs.writeFileSync(SALIDA, b); console.log('OK:', SALIDA, (b.length / 1024).toFixed(0), 'KB'); });
