import fs from 'node:fs';
import path from 'node:path';
import { fileURLToPath } from 'node:url';
const bridge = await import('@microsoft/powerbi-desktop-bridge-cli').catch(() => import(new URL('../../../tmp/pbi-authoring-tools/node_modules/@microsoft/powerbi-desktop-bridge-cli/dist/index.js', import.meta.url)));
const { connectToBridge, requireMethod } = bridge;

const pid = process.argv[2];
if (!pid || !/^\d+$/.test(pid)) throw new Error('Provide the verified Criteo Desktop PID');
const project = path.resolve(path.dirname(fileURLToPath(import.meta.url)), '..');
const output = path.join(project, 'reports', 'figures', 'powerbi');
fs.mkdirSync(output, { recursive: true });
const connection = await connectToBridge({ pid, waitMs: 10000 });
try {
  requireMethod(connection.manifest, 'report.snapshot.capture/v2');
  const pages = JSON.parse(fs.readFileSync(path.join(project, 'powerbi', 'Criteo.Report', 'definition', 'pages', 'pages.json'), 'utf8')).pageOrder;
  for (const pageId of pages) {
    const result = await connection.client.sendBridgeMethod('report.snapshot.capture/v2', { pageId, scale: 2, region: { x: 0, y: 0, width: 1600, height: 900 } });
    if (result.mimeType !== 'image/png' || !result.payload) throw new Error('No PNG returned for '+pageId);
    const bytes = Buffer.from(result.payload, result.encoding || 'base64');
    const file = path.join(output, 'report_'+pageId+'.png');
    fs.writeFileSync(file, bytes);
    console.log(JSON.stringify({ pageId, file, bytes: bytes.length }));
  }
} finally { connection.client.dispose(); }
