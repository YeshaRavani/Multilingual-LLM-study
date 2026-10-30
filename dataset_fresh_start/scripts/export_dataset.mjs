import fs from 'node:fs/promises';
import path from 'node:path';
import {fileURLToPath} from 'node:url';
import assert from 'node:assert/strict';
import crypto from 'node:crypto';
import {Workbook} from '@oai/artifact-tool';

const root=path.resolve(path.dirname(fileURLToPath(import.meta.url)),'..');
const original=JSON.parse(await fs.readFile(path.join(root,'.build/originals.json'),'utf8'));
const english=JSON.parse(await fs.readFile(path.join(root,'.build/english.json'),'utf8'));
const header=['variant_id','prompt_id','category','strategy','language','prompt_text','review_status'];
const strategies=['persona_builder','emotional_stakes','task_decomposition','audience_framing'];
const languages=['English','Gujarati','Hindi','Punjabi','Kannada','Tamil','Malayalam','Marathi'];
const hash=t=>crypto.createHash('sha256').update(t,'utf8').digest('hex');
assert.equal(original.length,40);
assert.equal(english.length,160);
const base=new Map(original.map(r=>[r.prompt_id,r.original_prompt]));
const englishByKey=new Map(english.map(r=>[r.prompt_id+'|'+r.strategy,r]));
for(const row of english) {
 assert.ok(row.prompt_text.includes(base.get(row.prompt_id)),'Original question must remain verbatim');
 assert.equal(row.english_sha256,hash(row.prompt_text));
}

const csvEscape=v=>'"'+String(v??'').replaceAll('"','""')+'"';
async function authorCSV(relative,columns,records) {
 const matrix=[columns,...records.map(row=>columns.map(k=>row[k]??''))];
 const wb=Workbook.create();
 const sheet=wb.worksheets.add('Dataset');
 sheet.getRangeByIndexes(0,0,matrix.length,columns.length).values=matrix;
 wb.recalculate();
 const values=sheet.getRangeByIndexes(0,0,matrix.length,columns.length).values;
 assert.deepEqual(values,matrix);
 const output=path.join(root,relative);
 await fs.mkdir(path.dirname(output),{recursive:true});
 await fs.writeFile(output,values.map(row=>row.map(csvEscape).join(',')).join('\n')+'\n','utf8');
 const readBack=await Workbook.fromCSV(await fs.readFile(output,'utf8'),{sheetName:'Check'});
 assert.deepEqual(readBack.worksheets.getItem('Check').getUsedRange().values,matrix);
 if(relative.endsWith('english_strategy_prompts.csv')) {
  sheet.getRange('D1:F5').format.font={name:'Arial',size:10};
  sheet.getRange('D1:F1').format.fill='#F1EEE8';
  sheet.getRange('D1:F1').format.font.bold=true;
  sheet.getRange('D1:D5').format.columnWidth=25;
  sheet.getRange('E1:E5').format.columnWidth=13;
  sheet.getRange('F1:F5').format.columnWidth=100;
  sheet.getRange('D2:F5').format.wrapText=true;
  sheet.getRange('D2:F5').format.rowHeight=145;
  wb.recalculate();
  const preview=await wb.render({sheetName:'Dataset',range:'D1:F5',scale:1.5,format:'png'});
  await fs.writeFile(path.join(root,'.build/english_preview.png'),new Uint8Array(await preview.arrayBuffer()));
 }
 console.log(`Saved ${records.length} rows: ${relative}`);
}

await authorCSV('data/original/base_prompts.csv',['prompt_id','category','original_prompt'],original);
await authorCSV('data/original/english_strategy_prompts.csv',header,english);

if(!process.argv.includes('--english-only')) {
 const checkpoint=(await fs.readFile(path.join(root,'.build/translations_aligned.jsonl'),'utf8')).split('\n').filter(Boolean).map(JSON.parse);
 const translated=new Map(checkpoint.map(r=>[r.variant_id,r]));
 assert.equal(translated.size,1120,'Do not export a partial multilingual dataset as complete');
 for(const row of translated.values()) {
  const source=englishByKey.get(row.prompt_id+'|'+row.strategy);
  assert.ok(source);
  assert.equal(row.english_sha256,source.english_sha256,'Translation belongs to stale English text');
  assert.equal(row.translation_truncated,false);
  assert.ok(row.prompt_text.trim());
  assert.notEqual(row.prompt_text,source.prompt_text);
 }
 const edits=JSON.parse(await fs.readFile(path.join(root,'scripts/translation_edits.json'),'utf8'));
 const editAudit=[];
 for(const [id,raw] of translated) {
  const row={...raw};
  const reasons=[];
  for(const rule of edits.rules) {
   if(rule.variant_id && rule.variant_id!==id) continue;
   if(rule.prompt_id && rule.prompt_id!==row.prompt_id) continue;
   if(rule.language && rule.language!==row.language) continue;
   const before=row.prompt_text;
   for(const [from,to] of rule.replacements??[]) row.prompt_text=row.prompt_text.replaceAll(from,to);
   if(rule.append_if_missing && !row.prompt_text.includes(rule.append_if_missing)) row.prompt_text+=' '+rule.append_if_missing;
   if(before!==row.prompt_text) reasons.push(rule.reason);
  }
  if(row.prompt_text!==raw.prompt_text) {
   editAudit.push({variant_id:id,raw_sha256:hash(raw.prompt_text),edited_sha256:hash(row.prompt_text),reasons,
                  reviewer:'Codex assistant targeted correction; not bilingual-expert validation'});
   translated.set(id,row);
  }
 }
 const records=[...english,...translated.values()].sort((a,b)=>
   a.prompt_id.localeCompare(b.prompt_id)||strategies.indexOf(a.strategy)-strategies.indexOf(b.strategy)||languages.indexOf(a.language)-languages.indexOf(b.language));
 assert.equal(records.length,1280);
 assert.equal(new Set(records.map(r=>r.variant_id)).size,1280);
 assert.equal(new Set(records.map(r=>r.prompt_text)).size,1280,'Duplicate text needs investigation');
 const coverage={};
 for(const row of records) {
  assert.ok(languages.includes(row.language));
  assert.ok(strategies.includes(row.strategy));
  const key=row.prompt_id+'|'+row.strategy;
  (coverage[key]??=[]).push(row.language);
 }
 assert.equal(Object.keys(coverage).length,160);
 for(const group of Object.values(coverage)) assert.deepEqual([...group].sort(),[...languages].sort());
 await authorCSV('data/translations/multilingual_prompts.csv',header,records);
 const validation={rows:1280,original_prompts:40,strategies:4,languages:8,unique_ids:1280,missing_rows:0,duplicate_texts:0,
   language_counts:Object.fromEntries(languages.map(l=>[l,records.filter(r=>r.language===l).length])),
   strategy_counts:Object.fromEntries(strategies.map(s=>[s,records.filter(r=>r.strategy===s).length])),
   original_english_retained_verbatim:true,translation_status:'model_assisted_with_documented_overrides_needs_bilingual_review',
   english_authoring_method:'Codex-assistant-authored deterministic wrappers and prompt-specific decomposition',
   source_file:'data/source_prompts_research_v1.csv',source_file_sha256:hash(await fs.readFile(path.join(root,'../data/source_prompts_research_v1.csv'))),
   translated_input:'aligned framing, original question, and numbered parts; shared questions translated once per language',translation_model:'facebook/nllb-200-distilled-600M',
   assistant_supplied_terminology_units:JSON.parse(await fs.readFile(path.join(root,'scripts/chunk_overrides.json'),'utf8')).units.reduce((n,u)=>n+Object.keys(u.translations).length,0),
   targeted_translation_edits:editAudit.length,model_response_collection_performed:false};
 await fs.writeFile(path.join(root,'outputs/dataset_validation.json'),JSON.stringify(validation,null,2)+'\n');
 await fs.writeFile(path.join(root,'outputs/translation_edit_audit.json'),JSON.stringify(editAudit,null,2)+'\n');
 console.log('PASS: complete 40 × 4 × 8 coverage, exact English questions, no empty or duplicate prompts.');
}
