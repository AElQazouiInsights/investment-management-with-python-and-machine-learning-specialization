import { createHash } from 'node:crypto';
import { mkdir, readFile, rename, writeFile } from 'node:fs/promises';
import { dirname, join } from 'node:path';
import { fileURLToPath } from 'node:url';
import { createRequire } from 'node:module';

const root = fileURLToPath(new URL('../', import.meta.url));
const require = createRequire(import.meta.url);
const runtimeDir = dirname(require.resolve('pyodide/package.json'));
const configText = await readFile(join(root, 'runtime/config.json'), 'utf8');
const config = JSON.parse(configText);
const digest = data => createHash('sha256').update(data).digest('hex');
const configSha256 = digest(configText);
const installed = JSON.parse(await readFile(join(runtimeDir, 'package.json'), 'utf8'));
if (installed.version !== config.version) {
  throw new Error(`Pyodide ${installed.version} does not match runtime/config.json (${config.version}). Run pnpm install after updating both pins.`);
}
const upstream = JSON.parse(await readFile(join(runtimeDir, 'pyodide-lock.json'), 'utf8'));
const lockPath = join(root, 'runtime/pyodide-lock.json');
const cdn = `https://cdn.jsdelivr.net/pyodide/v${config.version}/full/`;

async function download(url) {
  const response = await fetch(url, { signal: AbortSignal.timeout(120000) });
  if (!response.ok) throw new Error(`Download failed: ${url} (HTTP ${response.status})`);
  return Buffer.from(await response.arrayBuffer());
}

if (process.argv.includes('--update-lock')) {
  const available = { ...upstream.packages };
  for (const [name, { version, depends }] of Object.entries(config.wheels)) {
    const metadata = JSON.parse(await download(`https://pypi.org/pypi/${name}/${version}/json`));
    const wheel = metadata.urls.find(file => file.filename.endsWith('-py3-none-any.whl'));
    if (!wheel) throw new Error(`No universal Python 3 wheel for ${name}==${version}`);
    available[name] = {
      name, version, depends, file_name: wheel.filename,
      sha256: wheel.digests.sha256, source: wheel.url,
      imports: [name.replaceAll('-', '_')], install_dir: 'site', package_type: 'package'
    };
  }
  const packages = {};
  function include(name) {
    name = name.toLowerCase().replaceAll(/[-_.]+/g, '-');
    if (packages[name]) return;
    const pkg = available[name];
    if (!pkg) throw new Error(`Missing dependency in Pyodide distribution: ${name}`);
    packages[name] = { ...pkg, depends: pkg.depends.map(dependency => dependency.toLowerCase().replaceAll(/[-_.]+/g, '-')) };
    pkg.depends.forEach(include);
  }
  config.packages.forEach(include);
  const manifest = { configSha256, info: upstream.info, packages };
  await writeFile(lockPath, JSON.stringify({ revision: digest(JSON.stringify(manifest)), ...manifest }, null, 2) + '\n');
}

const { revision, ...lock } = JSON.parse(await readFile(lockPath, 'utf8'));
if (revision !== digest(JSON.stringify(lock))) {
  throw new Error('Runtime lockfile checksum is invalid. Run pnpm runtime:update to regenerate it.');
}
if (lock.configSha256 !== configSha256) {
  throw new Error('Runtime pins changed. Run pnpm runtime:update and review runtime/pyodide-lock.json.');
}
const destination = join(root, 'docs/public/pyodide', config.version, revision.slice(0, 12));
await mkdir(destination, { recursive: true });

async function saveVerified(filename, sha256, load) {
  const target = join(destination, filename);
  const cached = await readFile(target).catch(error => {
    if (error.code !== 'ENOENT') throw error;
  });
  if (cached && digest(cached) === sha256) return;
  const data = await load();
  if (digest(data) !== sha256) throw new Error(`SHA-256 mismatch: ${filename}`);
  await writeFile(`${target}.tmp`, data);
  await rename(`${target}.tmp`, target);
}

for (const filename of ['pyodide.asm.mjs', 'pyodide.asm.wasm', 'python_stdlib.zip']) {
  const data = await readFile(join(runtimeDir, filename));
  await saveVerified(filename, digest(data), async () => data);
}
const pending = Object.values(lock.packages);
await Promise.all(Array.from({ length: 6 }, async () => {
  while (pending.length) {
    const pkg = pending.shift();
    await saveVerified(pkg.file_name, pkg.sha256, () => download(pkg.source ?? cdn + pkg.file_name));
  }
}));
const packages = Object.fromEntries(Object.entries(lock.packages).map(([name, { source, ...pkg }]) => [name, pkg]));
await writeFile(join(destination, 'pyodide-lock.json'), JSON.stringify({ info: lock.info, packages }));
console.log(`Prepared Pyodide ${config.version} and ${Object.keys(packages).length} verified packages in ${destination}`);
