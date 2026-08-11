import { createRequire } from "module";
import { createServer } from "net";
import { mkdtemp, readFile, rm } from "fs/promises";
import { tmpdir } from "os";
import { spawn } from "child_process";
import path from "path";

const require = createRequire(import.meta.url);

function loadPlaywright() {
  return require("playwright");
}

async function launchChromium(chromium) {
  try {
    return await chromium.launch({ headless: true });
  } catch (error) {
    if (!String(error).includes("Executable doesn't exist")) throw error;
    return await chromium.launch({ headless: true, channel: "chrome" });
  }
}

async function freePort() {
  return await new Promise((resolve, reject) => {
    const server = createServer();
    server.listen(0, "127.0.0.1", () => {
      const address = server.address();
      server.close(() => resolve(address.port));
    });
    server.on("error", reject);
  });
}

async function waitForServer(url, timeoutMs = 15000) {
  const started = Date.now();
  while (Date.now() - started < timeoutMs) {
    try {
      const response = await fetch(url);
      if (response.ok) return;
    } catch {
      await new Promise((resolve) => setTimeout(resolve, 100));
    }
  }
  throw new Error(`Timed out waiting for ${url}`);
}

async function runCommand(command, args, cwd) {
  await new Promise((resolve, reject) => {
    const child = spawn(command, args, { cwd, stdio: ["ignore", "pipe", "pipe"] });
    let stderr = "";
    child.stderr.on("data", (chunk) => {
      stderr += chunk.toString();
    });
    child.on("close", (code) => {
      if (code === 0) resolve();
      else reject(new Error(`${command} failed with ${code}: ${stderr}`));
    });
  });
}

async function main() {
  const repoRoot = path.resolve(".");
  const outputDir = await mkdtemp(path.join(tmpdir(), "five-phase-live-world-"));
  await runCommand(
    "python3",
    [
      "scripts/run_five_phase_live_world_validation.py",
      "--ticks",
      "8",
      "--output-dir",
      outputDir,
    ],
    repoRoot,
  );

  const report = JSON.parse(await readFile(path.join(outputDir, "five_phase_live_world_report.json"), "utf8"));
  if (report.overall_status !== "passed") throw new Error("five phase live validation did not pass");
  const viewerDir = report.viewer_dir;
  const frames = (await readFile(path.join(viewerDir, "projection_frames.jsonl"), "utf8"))
    .trim()
    .split("\n")
    .map((line) => JSON.parse(line));
  if (!frames.some((frame) => frame.payload?.five_phase_live_summary)) {
    throw new Error("viewer case has no FivePhase live summary");
  }

  const port = await freePort();
  const server = spawn("python3", ["-m", "http.server", String(port), "--bind", "127.0.0.1"], {
    cwd: viewerDir,
    stdio: ["ignore", "pipe", "pipe"],
  });
  server.stderr.on("data", (chunk) => process.stderr.write(chunk));

  const { chromium } = loadPlaywright();
  const browser = await launchChromium(chromium);
  const url = `http://127.0.0.1:${port}/viewer.html`;
  const errors = [];
  try {
    await waitForServer(url);
    const page = await browser.newPage({ viewport: { width: 1280, height: 900 } });
    page.on("console", (message) => {
      if (message.type() === "error" && !message.text().includes("Failed to load resource")) {
        errors.push(message.text());
      }
    });
    page.on("pageerror", (error) => errors.push(error.message));
    await page.goto(url, { waitUntil: "networkidle" });
    await page.waitForFunction(() => document.querySelector("#load-status")?.textContent?.includes("Loaded frame_count="));
    await page.waitForFunction(() => {
      const canvas = document.getElementById("world-canvas");
      if (!canvas) return false;
      const data = canvas.getContext("2d").getImageData(0, 0, canvas.width, canvas.height).data;
      let count = 0;
      for (let i = 0; i < data.length; i += 4) {
        if (data[i] > 25 || data[i + 1] > 25 || data[i + 2] > 25 || data[i + 3] > 25) count += 1;
      }
      return count > 1000;
    });
    const auditText = await page.locator("#audit-panel").textContent();
    if (!auditText.includes("five_phase_live_summary")) throw new Error("audit panel missing FivePhase summary");
    if (!auditText.includes("aggregate_phase")) throw new Error("audit panel missing aggregate phase");
    const nonBackgroundPixels = await page.evaluate(() => {
      const canvas = document.getElementById("world-canvas");
      const data = canvas.getContext("2d").getImageData(0, 0, canvas.width, canvas.height).data;
      let count = 0;
      for (let i = 0; i < data.length; i += 4) {
        if (data[i] > 25 || data[i + 1] > 25 || data[i + 2] > 25 || data[i + 3] > 25) count += 1;
      }
      return count;
    });
    if (nonBackgroundPixels < 1000) throw new Error(`FivePhase live viewer canvas appears blank: ${nonBackgroundPixels}`);
    if (errors.length) throw new Error(`browser console errors: ${errors.join(" | ")}`);
    console.log("five phase live world viewer smoke passed");
  } finally {
    await browser.close();
    server.kill();
    await rm(outputDir, { recursive: true, force: true });
  }
}

main().catch((error) => {
  console.error(error);
  process.exit(1);
});
