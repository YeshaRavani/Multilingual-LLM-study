import fs from 'node:fs/promises';
import path from 'node:path';
import { pathToFileURL } from 'node:url';
import { Presentation, PresentationFile } from '@oai/artifact-tool';

const SKILL_DIR = '/Users/yesharavani/.codex/plugins/cache/openai-primary-runtime/presentations/26.904.11930/skills/presentations';
const ROOT = '/Users/yesharavani/CSS';
const BUILD = path.join(ROOT, '.pptx-build', 'submission');
const OUT = path.join(ROOT, 'output', 'multilingual_safety_fairness_submission_v2.pptx');
const PYTHON = '/Users/yesharavani/.cache/codex-runtimes/codex-primary-runtime/dependencies/python/bin/python3';
const { finalizePresentation } = await import(pathToFileURL(path.join(SKILL_DIR, 'container_tools/artifact_tool_utils.mjs')).href);

const deck = Presentation.create({ slideSize: { width: 1600, height: 900 } });
const C = {
  bg: '#F7F4EE', ink: '#29272D', burgundy: '#842F3B', darkBurgundy: '#682530',
  charcoal: '#2D2A30', gold: '#C99734', muted: '#746F78', line: '#D8D0C5',
  pale: '#F0E5E3', white: '#FFFEFB', teal: '#397888'
};
const SERIF = 'Georgia';
const SANS = 'Arial';

function rect(slide, x, y, w, h, fill, line = 'none', round = false) {
  return slide.shapes.add({
    geometry: round ? 'roundRect' : 'rect',
    position: { left: x, top: y, width: w, height: h },
    fill,
    line: line === 'none' ? { fill: 'none', width: 0 } : { fill: line, width: 1.4 },
  });
}

function text(slide, value, x, y, w, h, opts = {}) {
  const shape = slide.shapes.add({
    geometry: 'textbox', position: { left: x, top: y, width: w, height: h },
    fill: 'none', line: { fill: 'none', width: 0 },
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

function rule(slide, x, y, w, color = C.burgundy, h = 4) {
  rect(slide, x, y, w, h, color);
}

function footer(slide, number) {
  text(slide, 'Computational Social Science  ·  Research Project', 58, 852, 600, 18, { size: 14, color: '#AAA49C' });
  text(slide, String(number).padStart(2, '0'), 1508, 852, 36, 18, { size: 14, color: '#AAA49C', align: 'right' });
}

function header(slide, kicker, title, subtitle, number) {
  text(slide, kicker, 58, 38, 900, 25, { size: 19, color: C.burgundy, bold: true });
  text(slide, title, 58, 87, 1440, 72, { font: SERIF, size: 52, bold: true });
  if (subtitle) text(slide, subtitle, 60, 174, 1420, 42, { size: 25, color: C.muted, italic: true });
  footer(slide, number);
}

// Slide 1: title
{
  const s = deck.slides.add();
  s.background.fill = C.bg;
  rect(s, 0, 0, 1600, 18, C.burgundy);
  text(s, 'RESEARCH PROJECT', 76, 92, 500, 26, { size: 20, color: C.burgundy, bold: true });
  text(s, 'Multilingual Safety\nFairness in LLMs', 76, 164, 1000, 180, { font: SERIF, size: 66, bold: true });
  text(s, 'A paired audit of safety decisions and helpfulness across Indian languages and communication styles', 80, 380, 1010, 74, { size: 29, color: C.muted, italic: true });
  rect(s, 1160, 92, 350, 650, C.charcoal, 'none', true);
  text(s, 'PROJECT SCOPE', 1205, 139, 240, 22, { size: 17, color: C.gold, bold: true });
  text(s, '10', 1205, 195, 180, 78, { font: SERIF, size: 65, color: C.white, bold: true });
  text(s, 'language and style\nconditions', 1208, 274, 238, 64, { size: 22, color: '#E7DFDE' });
  rule(s, 1205, 373, 238, C.gold, 3);
  text(s, '3', 1205, 409, 150, 70, { font: SERIF, size: 60, color: C.white, bold: true });
  text(s, 'LLM families', 1208, 481, 238, 34, { size: 22, color: '#E7DFDE' });
  rule(s, 1205, 551, 238, C.gold, 3);
  text(s, 'Primary outcome', 1205, 587, 210, 22, { size: 16, color: C.gold, bold: true });
  text(s, 'False-refusal\ngap', 1205, 621, 245, 76, { font: SERIF, size: 31, color: C.white, bold: true });
  rule(s, 80, 540, 900, C.burgundy, 4);
  text(s, 'Prepared by', 80, 586, 180, 22, { size: 17, color: C.burgundy, bold: true });
  text(s, 'Yesha Ravani', 80, 620, 550, 48, { font: SERIF, size: 34, bold: true });
  text(s, 'Project proposal submission', 80, 689, 520, 30, { size: 20, color: C.muted });
  footer(s, 1);
  s.speakerNotes.textFrame.setText('Title slide. Replace the displayed name if the formal submission requires a different full name or group-member list.');
}

// Slide 2: research questions
{
  const s = deck.slides.add();
  s.background.fill = C.bg;
  header(s, 'PROJECT FRAMING', 'Research questions', 'Equivalent intent is held constant while language or communication style changes.', 2);
  const rows = [
    ['01', 'Safety fairness', 'Do semantically equivalent benign requests receive different safety decisions across Indian languages and communication styles?'],
    ['02', 'Helpfulness parity', 'When a model answers, does response quality differ in correctness, completeness, actionability, tone, or language matching?'],
    ['03', 'Linguistic drivers', 'Are observed differences associated with language, script, informality, Indian English phrasing, or Hindi-English code-switching?'],
  ];
  rows.forEach((r, i) => {
    const y = 276 + i * 156;
    text(s, r[0], 74, y, 84, 55, { font: SERIF, size: 37, color: C.burgundy, bold: true });
    text(s, r[1], 184, y - 2, 440, 43, { font: SERIF, size: 29, bold: true });
    text(s, r[2], 650, y - 1, 825, 75, { size: 21, color: C.muted, valign: 'top' });
    if (i < 2) rule(s, 184, y + 110, 1290, C.line, 2);
  });
  rect(s, 58, 755, 1486, 61, C.pale, C.burgundy, true);
  text(s, 'Core comparison', 88, 771, 205, 26, { size: 18, color: C.burgundy, bold: true });
  text(s, 'Same source prompt  ×  ten language/style conditions  ×  OpenAI GPT, Gemini, and Llama', 321, 766, 1165, 36, { size: 23 });
  s.speakerNotes.textFrame.setText('Research questions finalized during project development.');
}

// Slide 3: literature
{
  const s = deck.slides.add();
  s.background.fill = C.bg;
  header(s, 'LITERATURE REVIEW', 'Relevant literature covered so far', 'Four studies define the over-refusal, multilingual-safety, and code-switching context.', 3);
  const papers = [
    ['Röttger et al. · NAACL 2024', 'XSTest', 'Introduces safe prompts that resemble unsafe requests and shows how models can display exaggerated safety behavior.'],
    ['Cui et al. · 2024', 'OR-Bench', 'Scales over-refusal measurement with seemingly toxic but benign prompts, plus harmful contrast prompts.'],
    ['Shen et al. · ACL Findings 2024', 'The Language Barrier', 'Finds that safety behavior changes across languages, especially between higher-resource and lower-resource languages.'],
    ['Yoo et al. · ACL 2025', 'Code-Switching Red-Teaming', 'Shows that code-switching can weaken safeguards and connects multilingual understanding with safety evaluation.'],
  ];
  papers.forEach((p, i) => {
    const y = 268 + i * 132;
    text(s, String(i + 1).padStart(2, '0'), 74, y, 75, 42, { font: SERIF, size: 30, color: C.burgundy, bold: true });
    text(s, p[0], 176, y, 365, 25, { size: 17, color: C.burgundy, bold: true });
    text(s, p[1], 176, y + 32, 365, 38, { font: SERIF, size: 27, bold: true });
    text(s, p[2], 570, y + 2, 888, 72, { size: 20, color: C.muted, valign: 'top' });
    if (i < 3) rule(s, 176, y + 104, 1282, C.line, 2);
  });
  text(s, 'Sources: Röttger et al. (2024), Cui et al. (2024), Shen et al. (2024), Yoo et al. (2025)', 60, 803, 1410, 25, { size: 16, color: C.muted, italic: true });
  s.speakerNotes.textFrame.setText([
    'Sources:',
    'XSTest: https://aclanthology.org/2024.naacl-long.301/',
    'OR-Bench: https://arxiv.org/abs/2405.20947',
    'The Language Barrier: https://aclanthology.org/2024.findings-acl.156/',
    'Code-Switching Red-Teaming: https://aclanthology.org/2025.acl-long.657/',
  ].join('\n'));
}

// Slide 4: gaps
{
  const s = deck.slides.add();
  s.background.fill = C.bg;
  header(s, 'RESEARCH GAP', 'What the current literature leaves open', 'The proposed study shifts attention from attack success to equal access for ordinary multilingual users.', 4);
  text(s, 'Established evidence', 72, 274, 530, 38, { font: SERIF, size: 30, bold: true });
  rule(s, 72, 326, 580, C.burgundy);
  const left = [
    'English benchmarks identify false refusals on benign prompts.',
    'Multilingual studies find uneven safety behavior across languages.',
    'Code-switching research mainly examines adversarial or jailbreak settings.',
  ];
  left.forEach((v, i) => {
    text(s, String(i + 1).padStart(2, '0'), 76, 365 + i * 114, 58, 35, { font: SERIF, size: 26, color: C.burgundy, bold: true });
    text(s, v, 149, 359 + i * 114, 482, 72, { size: 21, color: C.muted, valign: 'top' });
  });
  rect(s, 706, 270, 838, 473, C.charcoal, 'none', true);
  text(s, 'OPEN QUESTIONS', 751, 311, 260, 22, { size: 17, color: C.gold, bold: true });
  text(s, 'A paired Indian-language\nfalse-refusal audit', 751, 353, 700, 90, { font: SERIF, size: 39, color: C.white, bold: true });
  rule(s, 751, 469, 690, C.gold, 3);
  const gaps = [
    'Limited matched evaluation of benign prompts across several Indian languages and everyday styles',
    'Language and communication style often remain mixed together rather than measured separately',
    'Refusal rate alone misses answer quality, tone, language matching, and clarification behavior',
    'Few public datasets pair human-validated variants with responses from both closed and open model families',
  ];
  gaps.forEach((g, i) => {
    text(s, String(i + 1), 757, 501 + i * 55, 35, 30, { font: SERIF, size: 21, color: C.gold, bold: true });
    text(s, g, 807, 496 + i * 55, 620, 45, { size: 18, color: '#E9E1E0', valign: 'top' });
  });
  text(s, 'Proposed contribution: a human-validated dataset of semantically equivalent prompts and model responses across ten conditions.', 72, 770, 1430, 50, { size: 23, color: C.burgundy, bold: true });
  s.speakerNotes.textFrame.setText([
    'Gap synthesis based on:',
    'https://aclanthology.org/2024.naacl-long.301/',
    'https://arxiv.org/abs/2405.20947',
    'https://aclanthology.org/2024.findings-acl.156/',
    'https://aclanthology.org/2025.acl-long.657/',
    'The gap statements are scoped claims from this initial literature review, not claims that no related work exists.',
  ].join('\n'));
}

// Slide 5: current work
{
  const s = deck.slides.add();
  s.background.fill = C.bg;
  header(s, 'CURRENT WORK', 'Pilot dataset and evaluation pipeline', 'The current phase builds the paired dataset and prepares controlled API collection.', 5);
  const stages = [
    ['01', 'Source set', 'Six canonical English prompts\nFour benign, safety-adjacent requests\nTwo prompts that should be refused'],
    ['02', 'Ten conditions', 'Standard, Indian, and informal English\nHindi and Hinglish\nGujarati, Punjabi, Bengali, Marathi, Kannada'],
    ['03', 'Translation', 'Google Translate API for six languages\nHuman writing or review for Indian English, informal English, and Hinglish'],
    ['04', 'Model responses', 'OpenAI GPT, Gemini, and Llama\nExact model versions will be fixed before collection'],
  ];
  stages.forEach((a, i) => {
    const x = 58 + i * 378;
    const dark = i === 3;
    rect(s, x, 270, 330, 335, dark ? C.charcoal : C.white, dark ? 'none' : C.line, true);
    text(s, a[0], x + 30, 302, 70, 30, { font: SERIF, size: 26, color: dark ? C.gold : C.burgundy, bold: true });
    text(s, a[1], x + 30, 354, 270, 48, { font: SERIF, size: 28, color: dark ? C.white : C.ink, bold: true });
    text(s, a[2], x + 30, 438, 270, 126, { size: 18, color: dark ? '#E9E1E0' : C.muted, valign: 'top' });
  });
  text(s, 'Work completed', 60, 660, 260, 28, { font: SERIF, size: 27, bold: true });
  text(s, 'Source CSV with six prompts  ·  translation script  ·  API response collector  ·  annotation-ready output structure', 60, 699, 1420, 36, { size: 20, color: C.muted });
  rect(s, 58, 760, 1486, 63, C.burgundy, 'none', true);
  text(s, 'Next milestone', 88, 777, 190, 25, { size: 18, color: '#F8ECEB', bold: true });
  text(s, 'Finalize model versions, validate all 60 prompt variants, then collect 180 responses in the first run', 303, 771, 1175, 37, { size: 23, color: C.white });
  s.speakerNotes.textFrame.setText('Current status reflects files implemented in the workspace. One run yields 6 prompts × 10 conditions × 3 model families = 180 responses.');
}

await fs.mkdir(path.dirname(OUT), { recursive: true });
const candidate = path.join(BUILD, 'candidate_submission.pptx');
await (await PresentationFile.exportPptx(deck)).save(candidate);

const result = await finalizePresentation({
  explicitTotalSlideCount: 5,
  requiredNativeTableOwnerSlides: [],
  workspaceDir: ROOT,
  candidatePath: candidate,
  finalPath: OUT,
  pythonExecutable: PYTHON,
  integrityValidatorPath: path.join(SKILL_DIR, 'container_tools/inspect_presentation_package_integrity.py'),
  layoutValidatorPath: path.join(SKILL_DIR, 'container_tools/inspect_presentation_layout_geometry.py'),
  layoutArgs: ['--expected-slide-size-emu', '15240000,8572500', '--validate-bullet-geometry', '--validate-heading-fit'],
  fontPolicy: { basis: 'design', families: [SERIF, SANS] },
  verifyArtifactToolImport: true,
  receiptPath: path.join(BUILD, 'submission_v2.validation.json'),
});
console.log(JSON.stringify(result, null, 2));
