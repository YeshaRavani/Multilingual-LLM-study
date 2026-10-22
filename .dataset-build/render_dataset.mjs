import fs from 'node:fs/promises';
import path from 'node:path';
import { FileBlob, SpreadsheetFile } from '@oai/artifact-tool';

const input = '/Users/yesharavani/CSS/outputs/dataset_v1/multilingual_safety_prompt_dataset_v1.xlsx';
const outDir = '/Users/yesharavani/CSS/.dataset-build/rendered';
await fs.mkdir(outDir, { recursive: true });
const wb = await SpreadsheetFile.importXlsx(await FileBlob.load(input));
for (const sheetName of ['Prompt Dataset', 'Category Summary', 'Codebook and Sources']) {
  const preview = await wb.render({ sheetName, autoCrop: 'all', scale: 1, format: 'png' });
  const safe = sheetName.toLowerCase().replaceAll(' ', '-');
  await fs.writeFile(path.join(outDir, `${safe}.png`), new Uint8Array(await preview.arrayBuffer()));
}
console.log(outDir);
