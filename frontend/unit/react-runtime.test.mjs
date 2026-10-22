import assert from 'node:assert/strict';
import { createRequire } from 'node:module';
import { fileURLToPath, URL } from 'node:url';
import { test } from 'node:test';
import { createServer } from 'vite';
import config from '../vite.config.ts';

test('app, renderer and React Flow resolve one React runtime in workspace installs', async () => {
  const root = fileURLToPath(new URL('..', import.meta.url));
  const require = createRequire(new URL('../package.json', import.meta.url));
  // Only exercise resolution; no compiler, dependency optimizer or dev server.
  const server = await createServer({
    root,
    configFile: false,
    // Keep the project's dedupe policy. Symlinks are irrelevant to this probe;
    // preserving them also avoids Windows network-drive discovery subprocesses.
    resolve: { ...config.resolve, preserveSymlinks: true },
    // Ignore the live dev server's optimized cache: it can hide split runtimes.
    cacheDir: fileURLToPath(new URL('../../.cache/studio-runtime-resolution', import.meta.url)),
    server: { middlewareMode: true, watch: null },
    optimizeDeps: { noDiscovery: true, include: [] },
  });
  try {
    const importers = [
      fileURLToPath(new URL('../src/main.tsx', import.meta.url)),
      require.resolve('react-dom/client'),
      require.resolve('@xyflow/react'),
    ];
    for (const dependency of ['react', 'react/jsx-runtime', 'react-dom']) {
      const resolved = await Promise.all(importers.map(importer =>
        server.environments.client.pluginContainer.resolveId(dependency, importer),
      ));
      assert.ok(resolved.every(result => result?.id), `${dependency} must resolve for all consumers`);
      assert.equal(new Set(resolved.map(result => result.id)).size, 1,
        `${dependency} must have one identity across the app and graph library`);
    }
  } finally {
    await server.close();
  }
});
