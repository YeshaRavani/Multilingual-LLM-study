import fs from 'node:fs/promises';
import path from 'node:path';
import crypto from 'node:crypto';
import { pathToFileURL } from 'node:url';
import { FileBlob, PresentationFile } from '@oai/artifact-tool';

const SKILL_DIR = '/Users/yesharavani/.codex/plugins/cache/openai-primary-runtime/presentations/26.1011.11113/skills/presentations';
const ROOT = '/Users/yesharavani/CSS';
const BUILD = path.join(ROOT, '.pptx-build', 'submission', 'budget');
const SOURCE = path.join(ROOT, 'output', 'multilingual_safety_fairness_submission_v2.pptx');
const FINAL = path.join(ROOT, 'output', 'multilingual_safety_fairness_submission_with_budget.pptx');
const PYTHON = '/Users/yesharavani/.cache/codex-runtimes/codex-primary-runtime/dependencies/python/bin/python3';

const { finalizePresentation } = await import(
  pathToFileURL(path.join(SKILL_DIR, 'container_tools', 'artifact_tool_utils.mjs')).href
);

const C = {
  bg: '#F7F4EE', ink: '#29272D', burgundy: '#842F3B', charcoal: '#2D2A30',
  gold: '#C99734', muted: '#746F78', line: '#D8D0C5', pale: '#F0E5E3', white: '#FFFEFB',
};
const SERIF = 'Georgia';
const SANS = 'Arial';

function rect(slide, x, y, w, h, fill, line = 'none', round = false) {
  return slide.shapes.add({
    geometry: round ? 'roundRect' : 'rect',
    position: { left: x, top: y, width: w, height: h },
    fill,
    line: line === 'none' ? { fill: 'none', width: 0 } : { fill: line, width: 1.2 },
  });
}

function text(slide, value, x, y, w, h, opts = {}) {
  const shape = slide.shapes.add({
    geometry: 'textbox',
    position: { left: x, top: y, width: w, height: h },
    fill: 'none',
    line: { fill: 'none', width: 0 },
  });
  shape.text = value;
  shape.text.style = {
    typeface: opts.font || SANS,
    fontSize: opts.size || 22,
    color: opts.color || C.ink,
    bold: opts.bold || false,
    italic: opts.italic || false,
    autoFit: 'shrinkText',
    paragraphAlignment: opts.align || 'left',
    verticalAlignment: opts.valign || 'middle',
    marginLeft: opts.margin ?? 0,
    marginRight: opts.margin ?? 0,
    marginTop: 0,
    marginBottom: 0,
  };
  return shape;
}

function footer(slide, number) {
  text(slide, 'Computational Social Science  ·  Research Project', 58, 852, 600, 18, { size: 14, color: '#AAA49C' });
  text(slide, String(number).padStart(2, '0'), 1508, 852, 36, 18, { size: 14, color: '#AAA49C', align: 'right' });
}

await fs.mkdir(BUILD, { recursive: true });
const deck = await PresentationFile.importPptx(await FileBlob.load(SOURCE));
const slide = deck.slides.add();
slide.background.fill = C.bg;

text(slide, 'IMPLEMENTATION BUDGET', 58, 38, 900, 25, { size: 19, color: C.burgundy, bold: true });
text(slide, 'API budget for one full research run', 58, 87, 1440, 72, { font: SERIF, size: 52, bold: true });
text(slide, '60 source prompts produce 600 language and style variants and 1,800 model responses.', 60, 174, 1420, 42, { size: 25, color: C.muted, italic: true });
footer(slide, 6);

const values = [
  ['API', 'Purpose', 'Planned volume', 'Published rate or free tier', 'Estimated run cost'],
  ['Google Cloud Translation', 'Six native-language versions', '360 translations\n≈54K characters', 'First 500K characters/month free\nThen $20 per 1M characters', '$0 free\n$1.08 paid'],
  ['OpenAI GPT-6 Luna', 'OpenAI response collection', '600 responses\n72K input + ≤240K output tokens', '$0.10 per 1M input\n$0.50 per 1M output', '≤$0.13'],
  ['Gemini 3.1 Flash-Lite', 'Gemini response collection', '600 responses\nSame token ceiling', 'Free tier available\nPaid: $0.25 input / $1.50 output', '$0 free\n≤$0.38 paid'],
  ['Groq GPT-OSS 20B', 'Free open-weight comparison', '600 responses\nRun across at least two days', 'Free: 1K requests/day, 200K tokens/day\nPaid: $0.075 input / $0.30 output', '$0 free\n≤$0.08 paid'],
];

const table = slide.tables.add({
  rows: values.length,
  columns: values[0].length,
  left: 58,
  top: 248,
  width: 1486,
  height: 390,
  columnWidths: [250, 300, 300, 410, 226],
  values,
});
table.styleOptions = { headerRow: true, bandedRows: false };
table.borders.assign({ style: 'solid', fill: C.line, width: 1 });
table.rows[0].height = 54;
for (let r = 1; r < values.length; r += 1) table.rows[r].height = 84;

table.cells.block({ row: 0, column: 0, rowCount: 1, columnCount: 5 }).assign({
  fill: C.charcoal,
  textStyle: { typeface: SANS, fontSize: 16, bold: true, color: C.white },
  margins: { left: 14, right: 12, top: 8, bottom: 8 },
  anchor: 'middle',
});

table.cells.block({ row: 1, column: 0, rowCount: 4, columnCount: 5 }).assign({
  fill: C.white,
  textStyle: { typeface: SANS, fontSize: 15, color: C.ink },
  margins: { left: 14, right: 12, top: 8, bottom: 8 },
  anchor: 'middle',
});

for (let r = 1; r < values.length; r += 1) {
  table.getCell(r, 0).text.style = { typeface: SERIF, fontSize: 16, bold: true, color: C.ink };
  table.getCell(r, 4).fill = C.pale;
  table.getCell(r, 4).text.style = { typeface: SANS, fontSize: 16, bold: true, color: C.burgundy };
}

rect(slide, 58, 682, 1486, 122, C.burgundy, 'none', true);
text(slide, 'RECOMMENDED AUTHORIZATION', 88, 704, 325, 22, { size: 16, color: '#F4D9D7', bold: true });
text(slide, '₹1,000', 88, 731, 275, 55, { font: SERIF, size: 42, color: C.white, bold: true });
rect(slide, 408, 709, 2, 67, '#B96570');
text(slide, 'One full run', 448, 705, 220, 22, { size: 16, color: '#F4D9D7', bold: true });
text(slide, '≤$0.13 with free tiers', 448, 735, 340, 38, { size: 24, color: C.white, bold: true });
rect(slide, 820, 709, 2, 67, '#B96570');
text(slide, 'Conservative paid equivalent', 860, 705, 330, 22, { size: 16, color: '#F4D9D7', bold: true });
text(slide, '≤$1.67 per run', 860, 735, 300, 38, { size: 24, color: C.white, bold: true });
text(slide, 'Covers the $5 OpenAI minimum credit purchase, taxes, retries, and several full reruns.', 1180, 706, 320, 70, { size: 17, color: C.white, valign: 'top' });

text(slide, 'Pricing checked 13 Oct 2026. Assumes ≤120 input tokens and a 400-token output cap per response; ₹96 per US$1.', 60, 817, 1170, 22, { size: 13, color: C.muted, italic: true });
text(slide, 'Groq’s free generative option is GPT-OSS 20B, not Llama; a paid Llama endpoint needs a revised estimate.', 1050, 813, 440, 30, { size: 12, color: C.burgundy, bold: true, align: 'right' });

slide.speakerNotes.textFrame.setText([
  'Budget calculation and sources, checked 13 October 2026:',
  'Dataset scale: 60 source prompts × 10 conditions = 600 variants; 600 variants × 3 models = 1,800 model responses.',
  'Translation assumption: 60 prompts × 6 machine-translated languages × 150 source characters = 54,000 billable characters.',
  'Model assumption per provider: 600 responses × 120 input tokens = 72,000 input tokens; 600 × 400-token cap = 240,000 maximum output tokens.',
  'Google Translation paid equivalent: 0.054M × $20 = $1.08. Monthly credit makes the expected cost $0.',
  'OpenAI: 0.072M × $0.10 + 0.240M × $0.50 = $0.1272.',
  'Gemini paid equivalent: 0.072M × $0.25 + 0.240M × $1.50 = $0.378.',
  'Groq paid equivalent: 0.072M × $0.075 + 0.240M × $0.30 = $0.0774. Free-tier token volume requires collection across at least two days.',
  'All-paid equivalent total: $1.6626. Expected usage with Translation, Gemini, and Groq free tiers: $0.1272.',
  'OpenAI prepaid billing requires a minimum initial purchase of $5. The recommended authorization is ₹1,000, approximately $10.40 at ₹96 per US dollar.',
  'Sources:',
  'Google Cloud Translation: https://cloud.google.com/products/translate/pricing',
  'OpenAI GPT-6 Luna: https://developers.openai.com/api/docs/models/gpt-6-luna',
  'OpenAI prepaid billing: https://help.openai.com/en/articles/8264644-how-can-i-set-up-prepaid-billing',
  'Gemini pricing: https://ai.google.dev/gemini-api/docs/pricing',
  'Groq free rate limits: https://console.groq.com/docs/rate-limits',
  'Groq GPT-OSS 20B: https://console.groq.com/docs/model/openai/gpt-oss-20b',
  'USD/INR reference: https://www.investing.com/currencies/usd-inr-historical-data',
].join('\n'));

const candidate = path.join(BUILD, 'candidate_with_budget.pptx');
await (await PresentationFile.exportPptx(deck)).save(candidate);

const sourceBytes = await fs.readFile(SOURCE);
const sourceSha256 = crypto.createHash('sha256').update(sourceBytes).digest('hex');
const result = await finalizePresentation({
  explicitTotalSlideCount: 6,
  requiredNativeTableOwnerSlides: [6],
  workspaceDir: ROOT,
  candidatePath: candidate,
  finalPath: FINAL,
  pythonExecutable: PYTHON,
  integrityValidatorPath: path.join(SKILL_DIR, 'container_tools', 'inspect_presentation_package_integrity.py'),
  layoutValidatorPath: path.join(SKILL_DIR, 'container_tools', 'inspect_presentation_layout_geometry.py'),
  layoutArgs: [
    '--expected-slide-size-emu', '15240000,8572500',
    '--validate-bullet-geometry', '--validate-heading-fit',
    '--require-native-table-slide', '6',
  ],
  fontPolicy: {
    basis: 'reference',
    families: [SERIF, SANS],
    referencePath: SOURCE,
    referenceSha256: sourceSha256,
  },
  verifyArtifactToolImport: true,
  receiptPath: path.join(BUILD, 'submission_with_budget.validation.json'),
});

console.log(JSON.stringify(result, null, 2));
