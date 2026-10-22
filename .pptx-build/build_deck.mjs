import fs from 'node:fs/promises';
import path from 'node:path';
import { pathToFileURL } from 'node:url';
import { Presentation, PresentationFile } from '@oai/artifact-tool';

const SKILL_DIR = '/Users/yesharavani/.codex/plugins/cache/openai-primary-runtime/presentations/26.904.11930/skills/presentations';
const workspaceDir = '/Users/yesharavani/CSS';
const TMP_DIR = path.join(workspaceDir, '.pptx-build');
const FINAL_PPTX = path.join(workspaceDir, 'output', 'multilingual_safety_fairness_proposal.pptx');
const RUNTIME_PYTHON = '/Users/yesharavani/.cache/codex-runtimes/codex-primary-runtime/dependencies/python/bin/python3';
const { finalizePresentation } = await import(pathToFileURL(path.join(SKILL_DIR, 'container_tools/artifact_tool_utils.mjs')).href);

const ppt = Presentation.create({ slideSize: { width: 1600, height: 900 } });
const C = { bg: '#F7F5F0', ink: '#2B292F', burgundy: '#842E3A', muted: '#77727B', line: '#D8D1C7', panel: '#2C2A2F', gold: '#C7983C', white: '#FFFEFC', pale: '#F1E6E5' };
const serif = 'Georgia';
const sans = 'Arial';

function rect(s, x, y, w, h, fill, radius = false, line = 'none') {
  return s.shapes.add({ geometry: radius ? 'roundRect' : 'rect', position: { left:x, top:y, width:w, height:h }, fill, line: line === 'none' ? { fill:'none', width:0 } : { fill:line, width:1.5 } });
}
function text(s, value, x, y, w, h, opts={}) {
  const sh = s.shapes.add({ geometry:'textbox', position:{ left:x, top:y, width:w, height:h }, fill:'none', line:{fill:'none',width:0} });
  sh.text = value;
  sh.text.style = { typeface: opts.font || sans, fontSize: opts.size || 24, color: opts.color || C.ink, bold: opts.bold || false, italic: opts.italic || false, autoFit:'shrinkText', breakLine: false, verticalAlignment: opts.valign || 'middle', paragraphAlignment: opts.align || 'left', marginLeft: opts.margin ?? 0, marginRight: opts.margin ?? 0, marginTop: 0, marginBottom: 0 };
  return sh;
}
function card(s, x, y, w, h, number, heading, body) {
  rect(s,x,y,w,h,C.white,true,C.line);
  text(s,number,x+32,y+26,w-64,28,{size:20,color:C.burgundy,bold:true});
  text(s,heading,x+32,y+72,w-64,62,{font:serif,size:31,bold:true});
  text(s,body,x+32,y+160,w-64,h-184,{size:20,color:C.muted,valign:'top'});
}
function footer(s, n) { text(s,'Computational Social Science  ·  Research Proposal',52,844,630,22,{size:15,color:'#B7B2AA'}); text(s,String(n).padStart(2,'0'),1510,844,38,22,{size:15,color:'#B7B2AA',align:'right'}); }

// Slide 1
{
  const s = ppt.slides.add(); s.background.fill = C.bg;
  text(s,'RESEARCH PROPOSAL  ·  MULTILINGUAL LLM AUDIT',52,42,900,28,{size:20,color:C.burgundy,bold:true});
  text(s,'Multilingual Safety Fairness in LLMs',52,95,1420,84,{font:serif,size:62,bold:true});
  text(s,'Do equivalent benign requests receive equal assistance when users write in different Indian languages and communication styles?',54,194,1410,58,{size:30,color:C.muted,italic:true});
  rect(s,52,294,1496,100,C.panel,true);
  text(s,'Research focus',86,321,184,34,{size:21,color:C.gold,bold:true});
  text(s,'Compare the safety decision and helpfulness of each model response while holding the user’s underlying intent constant.',284,317,1210,44,{size:27,color:C.white});
  card(s,52,454,460,270,'01','Ten language and style conditions','Standard English\nIndian English\nInformal English\nHindi and Hinglish');
  card(s,570,454,460,270,'02','Indian-language coverage','Gujarati\nPunjabi\nBengali\nMarathi and Kannada');
  card(s,1088,454,460,270,'03','Models under study','OpenAI GPT\nGemini\nLlama\n\nIndividual model versions to be selected later');
  rect(s,52,760,1496,56,C.pale,true,C.burgundy);
  text(s,'Primary question',86,775,218,25,{size:20,color:C.burgundy,bold:true});
  text(s,'Does language or communication style change the likelihood of a refusal or the usefulness of an answer?',350,770,1130,33,{size:24,color:C.ink});
  footer(s,1);
  s.speakerNotes.textFrame.setText('Project framing based on the user-provided proposal and research discussion.');
}

// Slide 2
{
  const s = ppt.slides.add(); s.background.fill = C.bg;
  text(s,'RESEARCH PROPOSAL  ·  DATASET & EVALUATION PLAN',52,42,1000,28,{size:20,color:C.burgundy,bold:true});
  text(s,'Paired Multilingual Prompt Dataset',52,95,1420,84,{font:serif,size:62,bold:true});
  text(s,'Every source prompt has one canonical English version and ten matched language or style variants.',52,197,1420,42,{size:29,color:C.muted});
  card(s,52,304,460,345,'01  SOURCE PROMPTS','Canonical English corpus','Write safety-adjacent, benign prompts plus clearly disallowed prompts.\n\nKeep a stable prompt ID and the expected outcome for each item.');
  card(s,570,304,460,345,'02  MULTILINGUAL EXPANSION','Ten matched variants','Use Google Translate API for native-language translations.\n\nManually write or review Indian English, informal English, and Hinglish because these are communication styles.');
  card(s,1088,304,460,345,'03  MODEL RESPONSE AUDIT','Three model families','Send every variant through OpenAI GPT, Gemini, and Llama APIs.\n\nStore the exact model ID, settings, prompt text, and full raw response.');
  rect(s,52,699,1496,104,C.burgundy,true);
  text(s,'Response dataset',86,724,220,25,{size:20,color:'#F8EDEB',bold:true});
  text(s,'Per original prompt: 10 versions × 3 LLM families = 30 recorded responses',86,757,1360,37,{size:31,color:C.white});
  text(s,'Annotate each response: answer, refusal, warning, clarification, unsafe compliance, response language, and helpfulness.',52,822,1440,22,{size:19,color:C.muted,italic:true});
  footer(s,2);
  s.speakerNotes.textFrame.setText('Dataset construction plan based on the user-provided research design.');
}

await fs.mkdir(path.dirname(FINAL_PPTX), { recursive:true });
const candidatePath = path.join(TMP_DIR, 'candidate_multilingual_safety.pptx');
await (await PresentationFile.exportPptx(ppt)).save(candidatePath);

const result = await finalizePresentation({
  explicitTotalSlideCount: 2,
  requiredNativeTableOwnerSlides: [],
  workspaceDir,
  candidatePath,
  finalPath: FINAL_PPTX,
  pythonExecutable: RUNTIME_PYTHON,
  integrityValidatorPath: path.join(SKILL_DIR, 'container_tools/inspect_presentation_package_integrity.py'),
  layoutValidatorPath: path.join(SKILL_DIR, 'container_tools/inspect_presentation_layout_geometry.py'),
  layoutArgs: ['--expected-slide-size-emu','15240000,8572500','--validate-bullet-geometry','--validate-heading-fit'],
  fontPolicy: { basis:'design', families:[serif,sans] },
  verifyArtifactToolImport: true,
  receiptPath: path.join(TMP_DIR, 'multilingual_safety.validation.json'),
});
console.log(JSON.stringify({finalPath:FINAL_PPTX, result}, null, 2));
