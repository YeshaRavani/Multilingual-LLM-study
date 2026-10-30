import fs from 'node:fs/promises';
import path from 'node:path';
import { FileBlob, PresentationFile } from '@oai/artifact-tool';

const root = '/Users/yesharavani/CSS';
const source = path.join(root, 'output', 'multilingual_safety_fairness_submission_with_budget_and_scoring.pptx');
const output = path.join(root, '.pptx-build', 'submission', 'scoring', 'final-rendered');

await fs.mkdir(output, { recursive: true });
const deck = await PresentationFile.importPptx(await FileBlob.load(source));
for (const [index, slide] of deck.slides.items.entries()) {
  const blob = await slide.export({ format: 'png', scale: 1 });
  const filename = `slide-${String(index + 1).padStart(2, '0')}.png`;
  await fs.writeFile(path.join(output, filename), new Uint8Array(await blob.arrayBuffer()));
}
const montage = await deck.export({ format: 'webp', montage: true });
await fs.writeFile(path.join(output, 'montage.webp'), new Uint8Array(await montage.arrayBuffer()));
console.log(JSON.stringify({ slideCount: deck.slides.items.length, output }, null, 2));
