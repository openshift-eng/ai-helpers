#!/usr/bin/env node
/**
 * capture-screenshots.js — Puppeteer screenshot capture for qa-verify-console
 *
 * Captures full-page screenshots of OpenShift Console routes using Puppeteer.
 * Designed for container/pod environments where Chrome needs special flags
 * and the headless shell doesn't render React SPAs properly.
 *
 * Key design decisions:
 *   - Uses the FULL Chrome binary (not chrome-headless-shell) via executablePath
 *   - Passes --headless=new as a Chrome arg (Puppeteer v22+ compatible)
 *   - Waits for PatternFly spinners to disappear before capturing
 *   - Continues on individual route failures (skip & report)
 *   - Outputs JSON summary to stdout for programmatic consumption
 *
 * Usage:
 *   node capture-screenshots.js \
 *     --routes /,/k8s/cluster/nodes,/monitoring/alerts \
 *     --output-dir /workspace/evidence/baseline \
 *     --base-url http://localhost:9000 \
 *     --viewport 1920x1080
 */

'use strict';

const fs = require('fs');
const path = require('path');

// ---------------------------------------------------------------------------
// Argument parsing
// ---------------------------------------------------------------------------

function parseArgs() {
  const args = process.argv.slice(2);
  const config = {
    routes: [],
    outputDir: '/workspace/evidence/baseline',
    baseUrl: 'http://localhost:9000',
    viewportWidth: 1920,
    viewportHeight: 1080,
  };

  for (let i = 0; i < args.length; i++) {
    switch (args[i]) {
      case '--routes':
        i++;
        if (i < args.length) {
          // Accept comma-separated or repeated --routes flags
          config.routes.push(...args[i].split(',').map(r => r.trim()).filter(Boolean));
        }
        break;
      case '--output-dir':
        i++;
        if (i < args.length) config.outputDir = args[i];
        break;
      case '--base-url':
        i++;
        if (i < args.length) config.baseUrl = args[i].replace(/\/+$/, '');
        break;
      case '--viewport':
        i++;
        if (i < args.length) {
          const [w, h] = args[i].split('x').map(Number);
          if (w > 0 && h > 0) {
            config.viewportWidth = w;
            config.viewportHeight = h;
          } else {
            console.error(`[capture] WARNING: Invalid viewport "${args[i]}", using default 1920x1080`);
          }
        }
        break;
      case '--help':
      case '-h':
        console.log(`Usage: node capture-screenshots.js [options]

Options:
  --routes <routes>      Comma-separated console routes (e.g. /,/k8s/cluster/nodes)
  --output-dir <dir>     Directory for screenshot PNGs (default: /workspace/evidence/baseline)
  --base-url <url>       Console base URL (default: http://localhost:9000)
  --viewport <WxH>       Viewport dimensions (default: 1920x1080)
  --help                 Show this help message`);
        process.exit(0);
        break;
      default:
        console.error(`[capture] WARNING: Unknown argument: ${args[i]}`);
    }
  }

  if (config.routes.length === 0) {
    console.error('[capture] ERROR: No routes specified. Use --routes /,/k8s/cluster/nodes,...');
    process.exit(1);
  }

  return config;
}

// ---------------------------------------------------------------------------
// Chrome executable discovery
// ---------------------------------------------------------------------------

/**
 * Find the full Chrome binary path. We explicitly avoid chrome-headless-shell
 * because it does NOT render React SPAs (no DOM paint, blank screenshots).
 *
 * Search order:
 *   1. CHROME_BIN environment variable (set by setup.sh)
 *   2. Puppeteer's default executablePath() — but verify it's not headless-shell
 *   3. Common Puppeteer cache locations
 *   4. System-installed Chrome/Chromium
 */
function findChromeBinary(puppeteer) {
  const candidates = [];

  // 1. Environment variable (highest priority, set by setup.sh)
  if (process.env.CHROME_BIN) {
    candidates.push(process.env.CHROME_BIN);
  }

  // 2. Puppeteer's detected path
  try {
    const pptrPath = puppeteer.executablePath();
    if (pptrPath) candidates.push(pptrPath);
  } catch (_) {
    // executablePath() throws if no browser is installed
  }

  // 3. Common Puppeteer cache paths (glob-like search)
  const homeDir = process.env.HOME || '/root';
  const cacheDirs = [
    path.join(homeDir, '.cache', 'puppeteer', 'chrome'),
    path.join(process.cwd(), 'node_modules', 'puppeteer', '.local-chromium'),
  ];

  for (const cacheDir of cacheDirs) {
    try {
      if (fs.existsSync(cacheDir)) {
        const versions = fs.readdirSync(cacheDir);
        for (const version of versions) {
          // Check both directory naming conventions
          for (const subdir of ['chrome-linux64', 'chrome-linux']) {
            const chromePath = path.join(cacheDir, version, subdir, 'chrome');
            candidates.push(chromePath);
          }
        }
      }
    } catch (_) {
      // Directory may not exist or be readable
    }
  }

  // 4. System Chrome/Chromium paths
  candidates.push(
    '/usr/bin/google-chrome',
    '/usr/bin/google-chrome-stable',
    '/usr/bin/chromium-browser',
    '/usr/bin/chromium',
    '/snap/bin/chromium'
  );

  // Find the first candidate that exists, is executable, and is NOT headless-shell
  for (const candidate of candidates) {
    try {
      if (fs.existsSync(candidate)) {
        const stats = fs.statSync(candidate);
        if (stats.isFile()) {
          const basename = path.basename(candidate);
          // Reject chrome-headless-shell — it doesn't render React SPAs
          if (basename === 'chrome-headless-shell') {
            console.error(`[capture] Skipping headless-shell binary: ${candidate}`);
            continue;
          }
          console.error(`[capture] Using Chrome binary: ${candidate}`);
          return candidate;
        }
      }
    } catch (_) {
      // stat/exists may throw — continue to next candidate
    }
  }

  return null;
}

// ---------------------------------------------------------------------------
// Route slug generation
// ---------------------------------------------------------------------------

/**
 * Convert a route path to a safe filename slug.
 * Examples:
 *   /                     -> root
 *   /k8s/cluster/nodes    -> k8s_cluster_nodes
 *   /monitoring/alerts    -> monitoring_alerts
 */
function routeToSlug(route) {
  if (route === '/' || route === '') return 'root';
  return route
    .replace(/^\/+/, '')  // strip leading slashes
    .replace(/\/+$/, '')  // strip trailing slashes
    .replace(/[\/\\]+/g, '_')  // slashes to underscores
    .replace(/[^a-zA-Z0-9_-]/g, '_')  // sanitize special chars
    .replace(/_+/g, '_')  // collapse repeated underscores
    .toLowerCase();
}

// ---------------------------------------------------------------------------
// Spinner wait helper
// ---------------------------------------------------------------------------

/**
 * Wait for PatternFly / Console loading spinners to disappear.
 * Uses a 10-second timeout — if spinners haven't cleared by then,
 * we capture anyway (some pages may have perpetual spinners).
 */
async function waitForSpinnersToDisappear(page) {
  const spinnerSelectors = [
    '.co-m-loader',         // Console's main loader
    '.pf-c-spinner',        // PatternFly v4 spinner
    '.pf-v6-c-spinner',     // PatternFly v6 spinner (newer console versions)
    '.pf-v5-c-spinner',     // PatternFly v5 spinner
    '.loading-box',         // Console loading box
  ];

  for (const selector of spinnerSelectors) {
    try {
      await page.waitForFunction(
        (sel) => {
          const elements = document.querySelectorAll(sel);
          if (elements.length === 0) return true;
          // Check if all spinners are hidden
          return Array.from(elements).every(el => {
            const style = window.getComputedStyle(el);
            return style.display === 'none' || style.visibility === 'hidden' || style.opacity === '0';
          });
        },
        { timeout: 10000 },
        selector
      );
    } catch (_) {
      // Timeout waiting for this spinner selector — continue anyway
      console.error(`[capture] Spinner "${selector}" still present after 10s — continuing`);
    }
  }
}

// ---------------------------------------------------------------------------
// Main capture logic
// ---------------------------------------------------------------------------

async function captureScreenshots() {
  const config = parseArgs();

  console.error('[capture] Configuration:');
  console.error(`[capture]   Routes:     ${config.routes.join(', ')}`);
  console.error(`[capture]   Output:     ${config.outputDir}`);
  console.error(`[capture]   Base URL:   ${config.baseUrl}`);
  console.error(`[capture]   Viewport:   ${config.viewportWidth}x${config.viewportHeight}`);

  // Ensure output directory exists
  fs.mkdirSync(config.outputDir, { recursive: true });

  // Load puppeteer
  let puppeteer;
  try {
    puppeteer = require('puppeteer');
  } catch (err) {
    console.error(`[capture] ERROR: Failed to load puppeteer: ${err.message}`);
    console.error('[capture] Run: cd frontend && npm install puppeteer');
    process.exit(1);
  }

  // Find Chrome binary
  const chromeBin = findChromeBinary(puppeteer);
  if (!chromeBin) {
    console.error('[capture] ERROR: No suitable Chrome binary found.');
    console.error('[capture] Run: npx puppeteer browsers install chrome');
    console.error('[capture] Or set CHROME_BIN=/path/to/chrome');
    process.exit(1);
  }

  // Launch browser
  // CRITICAL: We use the full Chrome binary (not chrome-headless-shell) and pass
  // --headless=new as a Chrome arg. Setting headless: true or headless: 'new' in
  // Puppeteer v22+ causes it to use chrome-headless-shell internally, which does
  // NOT render React SPAs (blank pages, no paint events).
  let browser;
  try {
    browser = await puppeteer.launch({
      executablePath: chromeBin,
      headless: false,  // We control headless via Chrome args below
      args: [
        '--headless=new',           // Full Chrome in new headless mode
        '--no-sandbox',             // Required in containers
        '--disable-setuid-sandbox', // Required in containers
        '--disable-dev-shm-usage',  // Use /tmp instead of /dev/shm (limited in pods)
        '--disable-gpu',            // No GPU in containers
        '--disable-software-rasterizer',
        '--disable-extensions',
        '--disable-background-networking',
        '--disable-default-apps',
        '--disable-sync',
        '--disable-translate',
        '--metrics-recording-only',
        '--mute-audio',
        '--no-first-run',
        `--window-size=${config.viewportWidth},${config.viewportHeight}`,
      ],
    });
  } catch (err) {
    console.error(`[capture] ERROR: Failed to launch Chrome: ${err.message}`);
    console.error(`[capture] Chrome binary: ${chromeBin}`);
    console.error('[capture] Check that Chrome system libraries are installed.');
    console.error('[capture] Ensure LD_LIBRARY_PATH includes /workspace/chrome-libs/usr/lib64');
    process.exit(1);
  }

  const startTime = new Date().toISOString();
  const screenshots = [];
  let capturedCount = 0;
  let skippedCount = 0;
  let failedCount = 0;

  try {
    for (const route of config.routes) {
      const slug = routeToSlug(route);
      const filename = `${slug}.png`;
      const filepath = path.join(config.outputDir, filename);
      const url = `${config.baseUrl}${route.startsWith('/') ? route : '/' + route}`;

      console.error(`[capture] Capturing: ${route} -> ${filename}`);

      const result = {
        route,
        slug,
        filename,
        url,
        httpStatus: null,
        pageTitle: null,
        fileSize: null,
        success: false,
        error: null,
      };

      let page;
      try {
        page = await browser.newPage();

        // Set viewport
        await page.setViewport({
          width: config.viewportWidth,
          height: config.viewportHeight,
        });

        // Capture HTTP status from the main navigation response
        const response = await page.goto(url, {
          waitUntil: 'networkidle2',
          timeout: 30000,
        });

        result.httpStatus = response ? response.status() : null;

        if (response && !response.ok()) {
          console.error(`[capture] WARNING: ${route} returned HTTP ${result.httpStatus}`);
        }

        // Wait for spinners to disappear
        await waitForSpinnersToDisappear(page);

        // Additional settle time — gives async React components time to render
        // after spinners clear. 2 seconds is a reasonable balance between
        // thoroughness and speed.
        await new Promise(resolve => setTimeout(resolve, 2000));

        // Get page title for metadata
        result.pageTitle = await page.title();

        // Take full-page screenshot
        await page.screenshot({
          path: filepath,
          fullPage: true,
        });

        // Get file size
        const stats = fs.statSync(filepath);
        result.fileSize = stats.size;
        result.success = true;
        capturedCount++;

        console.error(`[capture] OK: ${filename} (${(result.fileSize / 1024).toFixed(1)} KB, "${result.pageTitle}")`);
      } catch (err) {
        result.error = err.message;
        failedCount++;
        console.error(`[capture] FAILED: ${route} — ${err.message}`);

        // Mark as skipped if the file wasn't created
        if (!fs.existsSync(filepath)) {
          skippedCount++;
        }
      } finally {
        if (page) {
          try {
            await page.close();
          } catch (_) {
            // Page may already be closed
          }
        }
      }

      screenshots.push(result);
    }
  } finally {
    // Always close the browser
    try {
      await browser.close();
    } catch (_) {
      // Browser may already be closed
    }
  }

  const endTime = new Date().toISOString();

  // Build summary
  const summary = {
    baseUrl: config.baseUrl,
    viewport: `${config.viewportWidth}x${config.viewportHeight}`,
    outputDir: config.outputDir,
    startTime,
    endTime,
    screenshots,
    summary: {
      total: config.routes.length,
      captured: capturedCount,
      skipped: skippedCount,
      failed: failedCount,
    },
  };

  // Print JSON summary to stdout (all other output goes to stderr)
  console.log(JSON.stringify(summary, null, 2));

  // Exit 0 even if some routes failed — the summary JSON reports individual failures
  // This allows the caller to process partial results
  console.error(`[capture] Done: ${capturedCount}/${config.routes.length} captured, ${failedCount} failed, ${skippedCount} skipped`);
}

// ---------------------------------------------------------------------------
// Entry point — handle unhandled rejections gracefully
// ---------------------------------------------------------------------------

process.on('unhandledRejection', (reason) => {
  console.error(`[capture] Unhandled rejection: ${reason}`);
  process.exit(1);
});

captureScreenshots().catch((err) => {
  console.error(`[capture] Fatal error: ${err.message}`);
  process.exit(1);
});
