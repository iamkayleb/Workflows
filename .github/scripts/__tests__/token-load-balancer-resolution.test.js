const test = require('node:test');
const assert = require('node:assert/strict');
const fs = require('node:fs');
const os = require('node:os');
const path = require('node:path');
const { spawnSync } = require('node:child_process');

test('refreshAllRateLimits resolves Octokit from NODE_PATH-installed action deps', () => {
  const tempDir = fs.mkdtempSync(path.join(os.tmpdir(), 'token-load-balancer-node-path-'));
  const nodePath = path.join(tempDir, 'node_modules');
  const restDir = path.join(nodePath, '@octokit', 'rest');
  fs.mkdirSync(restDir, { recursive: true });
  fs.writeFileSync(
    path.join(restDir, 'package.json'),
    JSON.stringify({ name: '@octokit/rest', main: 'index.js' }) + '\n'
  );
  fs.writeFileSync(
    path.join(restDir, 'index.js'),
    `
class Octokit {
  constructor(options) {
    this.auth = options.auth;
    this.rateLimit = {
      get: async () => ({
        data: {
          resources: {
            core: {
              limit: 5000,
              remaining: 4999,
              used: 1,
              reset: 2000000000
            }
          }
        }
      })
    };
  }
}
module.exports = { Octokit };
`
  );

  const scriptPath = path.resolve(__dirname, '..', 'token_load_balancer.js');
  const child = spawnSync(
    process.execPath,
    [
      '-e',
      `
(async () => {
  const balancer = require(process.argv[1]);
  const errors = [];
  balancer.tokenRegistry.tokens.clear();
  balancer.tokenRegistry.lastRefresh = 0;
  balancer.registerToken({
    id: 'TEST_TOKEN',
    token: 'token',
    type: 'PAT',
    source: 'TEST_TOKEN',
    capabilities: ['read-repo'],
    priority: 5
  });
  await balancer.refreshAllRateLimits({
    core: {
      error: (message) => errors.push(message),
      warning: (message) => errors.push(message),
      debug: () => {}
    }
  });
  const rateLimit = balancer.tokenRegistry.tokens.get('TEST_TOKEN').rateLimit;
  process.stdout.write(JSON.stringify({ errors, rateLimit }));
})().catch((error) => {
  console.error(error);
  process.exit(1);
});
`,
      scriptPath,
    ],
    {
      env: {
        ...process.env,
        NODE_PATH: nodePath,
      },
      encoding: 'utf8',
    }
  );

  assert.equal(child.status, 0, child.stderr);
  const result = JSON.parse(child.stdout);
  assert.deepEqual(result.errors, []);
  assert.equal(result.rateLimit.remaining, 4999);
  assert.equal(result.rateLimit.importFailed, undefined);
});
