// Bundles src/main.ts into demo/bundle.js. demo/template.html references it by that name,
// and the FastAPI app serves demo/ as a static directory — no inlining needed here, since
// there's a real backend to call, unlike countersigned-actions' client-only playground.
import { build } from 'esbuild';
import { copyFileSync, mkdirSync } from 'node:fs';
import { dirname, join } from 'node:path';
import { fileURLToPath } from 'node:url';

const root = join(dirname(fileURLToPath(import.meta.url)), '..');

await build({
  entryPoints: [join(root, 'src/main.ts')],
  bundle: true, outfile: join(root, 'demo/bundle.js'), format: 'iife', target: 'es2020', legalComments: 'none',
});
mkdirSync(join(root, 'demo'), { recursive: true });
copyFileSync(join(root, 'demo/template.html'), join(root, 'demo/index.html'));
console.log('demo/bundle.js and demo/index.html built');
