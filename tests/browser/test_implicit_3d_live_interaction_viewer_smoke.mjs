import { createRequire } from "module";
import { createServer } from "net";
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

async function nonBlankPixels(page) {
  return await page.evaluate(() => {
    const canvas = document.getElementById("world-canvas");
    const data = canvas.getContext("2d").getImageData(0, 0, canvas.width, canvas.height).data;
    let count = 0;
    for (let i = 0; i < data.length; i += 4) {
      if (data[i] > 28 || data[i + 1] > 28 || data[i + 2] > 28 || data[i + 3] > 28) count += 1;
    }
    return count;
  });
}

async function main() {
  const repoRoot = path.resolve(".");
  const port = await freePort();
  const server = spawn(
    "python3",
    ["scripts/serve_implicit_3d_field_window.py", "--port", String(port), "--max-advance-ticks", "8"],
    { cwd: repoRoot, stdio: ["ignore", "pipe", "pipe"] },
  );
  server.stderr.on("data", (chunk) => process.stderr.write(chunk));
  const { chromium } = loadPlaywright();
  const url = `http://127.0.0.1:${port}/viewer.html`;
  await waitForServer(`http://127.0.0.1:${port}/session`);
  const browser = await launchChromium(chromium);
  const page = await browser.newPage({ viewport: { width: 1280, height: 900 } });
  const consoleErrors = [];
  const interactionBodies = [];
  const cameraBodies = [];
  const runStepBodies = [];
  const postPaths = [];
  page.on("console", (message) => {
    if (message.type() === "error") consoleErrors.push(message.text());
  });
  page.on("pageerror", (error) => consoleErrors.push(error.message));
  page.on("request", (request) => {
    if (request.method() === "POST") {
      postPaths.push(new URL(request.url()).pathname);
    }
    if (request.method() === "POST" && request.url().endsWith("/interaction")) {
      interactionBodies.push(request.postData() || "");
    }
    if (request.method() === "POST" && request.url().endsWith("/camera")) {
      cameraBodies.push(request.postData() || "");
    }
    if (request.method() === "POST" && request.url().endsWith("/run_step")) {
      runStepBodies.push(request.postData() || "");
    }
  });

  try {
    await page.goto(url, { waitUntil: "networkidle" });
    await page.waitForFunction(() => Number(document.getElementById("frame-count")?.textContent || "0") > 0);
    const bodyText = await page.locator("body").textContent();
    if (!bodyText.includes("live implicit 3D session ready")) {
      throw new Error("viewer did not detect live implicit runtime");
    }
    await page.waitForFunction(() => {
      const canvas = document.getElementById("world-canvas");
      const data = canvas.getContext("2d").getImageData(0, 0, canvas.width, canvas.height).data;
      let count = 0;
      for (let i = 0; i < data.length; i += 4) {
        if (data[i] > 28 || data[i + 1] > 28 || data[i + 2] > 28 || data[i + 3] > 28) count += 1;
      }
      return count > 1000;
    });
    const pixels = await nonBlankPixels(page);
    if (pixels < 1000) {
      throw new Error(`live implicit canvas appears blank: ${pixels}`);
    }
    const modeSelector = await page.$("#playback-mode-selector");
    if (!modeSelector) throw new Error("missing playback mode selector");

    await page.selectOption("#playback-mode-selector", "run_world");
    const beforeRunTick = await page.$eval("#tick-readout", (el) => el.textContent);
    await page.click("#play-toggle");
    await page.waitForFunction(() => {
      const status = document.querySelector("#interaction-status")?.textContent || "";
      return status.includes("running world") || status.includes("world advanced");
    });
    await page.waitForFunction((before) => {
      const tick = document.querySelector("#tick-readout")?.textContent || "";
      return tick !== before;
    }, beforeRunTick);
    await page.click("#play-toggle");
    const afterRunTick = await page.$eval("#tick-readout", (el) => el.textContent);
    if (beforeRunTick === afterRunTick) throw new Error("Run World play did not advance tick");
    if (!runStepBodies.some((body) => body.includes("implicit_world_run_step_request"))) {
      throw new Error("Run World play did not submit /run_step request");
    }

    await page.waitForFunction(() => !document.getElementById("interactive-toggle")?.disabled);
    await page.selectOption("#playback-mode-selector", "inspect_tick");
    await page.locator("#interactive-toggle").check();
    await page.locator("#tool-selector").selectOption("local_excite");
    await page.locator("#radius-control").fill("1");
    await page.locator("#amplitude-control").fill("0.3");
    await page.locator("#duration-control").fill("2.25");
    const box = await page.locator("#world-canvas").boundingBox();
    if (!box) throw new Error("missing canvas bounding box");
    const x = box.x + box.width * 0.5;
    const y = box.y + box.height * 0.5;
    const countBeforeExcite = Number(await page.locator("#frame-count").textContent());
    const exciteResponsePromise = page.waitForResponse(
      (response) => response.request().method() === "POST" && response.url().endsWith("/interaction"),
    );
    await page.mouse.move(x, y);
    await page.mouse.down();
    await page.mouse.up();
    const exciteResponse = await exciteResponsePromise;
    if (!exciteResponse.ok()) throw new Error(`excite request failed: ${await exciteResponse.text()}`);
    await page.waitForFunction((previous) => Number(document.getElementById("frame-count")?.textContent || "0") > previous, countBeforeExcite);
    await page.waitForFunction(() => (document.getElementById("interaction-status")?.textContent || "").includes("interaction accepted"));
    const exciteStatus = await page.locator("#interaction-status").textContent();
    if (!exciteStatus.includes("interaction accepted")) throw new Error(`excite failed: ${exciteStatus}`);
    const afterAudit = await page.locator("#audit-panel").textContent();
    for (const required of [
      "implicit_interaction_audit",
      "implicit_local_excite",
      "implicit_ray_sample_record",
      "implicit_spectral_image_plane",
      "implicit_3d_field_observation",
      "five_phase_live_summary_v1",
      "pattern_response",
      "stability_score",
      "five_phase_live_response_stability_v2",
      "q_user",
      "Q_live",
      "fixed_support_kappa_density_norm_over_setpoint_v1",
      "energy_response",
      "ledger_count",
      "feedback_application",
      '"viewer_generated": false',
      '"display_only": true',
      '"is_authority_state": false',
    ]) {
      if (!afterAudit.includes(required)) {
        throw new Error(`audit panel missing ${required}`);
      }
    }
    if (!interactionBodies.some((body) => body.includes("implicit_interaction_request") && body.includes("implicit_local_excite"))) {
      throw new Error("viewer did not submit implicit interaction request");
    }
    const exciteRequest = interactionBodies.map((body) => JSON.parse(body)).find((body) => body.tool === "implicit_local_excite");
    if (
      !exciteRequest ||
      exciteRequest.amplitude !== 0.3 ||
      exciteRequest.radius_world !== 1 ||
      exciteRequest.duration_ticks !== 2.25 ||
      !exciteRequest.source_projection_frame_id ||
      !exciteRequest.source_state_id ||
      !exciteRequest.source_ray_sample_record_id
    ) {
      throw new Error("viewer excite request did not preserve signed-control magnitude, locality, duration, and source lineage");
    }

    await page.locator("#tool-selector").selectOption("local_dampen");
    await page.locator("#radius-control").fill("2");
    await page.locator("#amplitude-control").fill("0.2");
    await page.locator("#duration-control").fill("1.5");
    const countBeforeDampen = Number(await page.locator("#frame-count").textContent());
    const dampenResponsePromise = page.waitForResponse(
      (response) => response.request().method() === "POST" && response.url().endsWith("/interaction"),
    );
    await page.mouse.move(x, y);
    await page.mouse.down();
    await page.mouse.up();
    const dampenResponse = await dampenResponsePromise;
    if (!dampenResponse.ok()) throw new Error(`dampen request failed: ${await dampenResponse.text()}`);
    await page.waitForFunction((previous) => Number(document.getElementById("frame-count")?.textContent || "0") > previous, countBeforeDampen);
    await page.waitForFunction(() => (document.getElementById("interaction-status")?.textContent || "").includes("interaction accepted"));
    const dampenStatus = await page.locator("#interaction-status").textContent();
    if (!dampenStatus.includes("interaction accepted")) throw new Error(`dampen failed: ${dampenStatus}`);
    const dampenRequest = interactionBodies.map((body) => JSON.parse(body)).find((body) => body.tool === "implicit_local_dampen");
    if (
      !dampenRequest ||
      dampenRequest.amplitude !== 0.2 ||
      dampenRequest.radius_world !== 2 ||
      dampenRequest.duration_ticks !== 1.5
    ) {
      throw new Error("viewer did not submit the bounded local dampen request");
    }

    await page.selectOption("#playback-mode-selector", "inspect_tick");
    const inspectBefore = await page.$eval("#tick-readout", (el) => el.textContent);
    const countBeforeCamera = Number(await page.locator("#frame-count").textContent());
    const causalAuditBeforeCamera = await page.evaluate(async () => (await fetch("/audit")).json());
    await page.locator('button[data-camera-action="forward"]').click();
    await page.waitForFunction((previous) => Number(document.getElementById("frame-count")?.textContent || "0") > previous, countBeforeCamera);
    await page.waitForFunction(() => (document.getElementById("interaction-status")?.textContent || "").includes("camera moved"));
    const inspectAfter = await page.$eval("#tick-readout", (el) => el.textContent);
    if (inspectBefore !== inspectAfter) throw new Error("Inspect Tick camera move changed world tick");
    const causalAuditAfterCamera = await page.evaluate(async () => (await fetch("/audit")).json());
    for (const family of ["implicit_live_steps", "five_phase_live_steps", "five_phase_feedback_records"]) {
      if (causalAuditAfterCamera[family].length !== causalAuditBeforeCamera[family].length) {
        throw new Error(`camera-only observation mutated causal family ${family}`);
      }
    }
    const cameraAudit = await page.locator("#audit-panel").textContent();
    for (const required of [
      "implicit_camera_move_request",
      "source_projection_frame_id",
      "state_digest_unchanged",
    ]) {
      if (!cameraAudit.includes(required)) {
        throw new Error(`camera audit panel missing ${required}`);
      }
    }
    if (!cameraBodies.some((body) => body.includes("implicit_camera_move_request") && body.includes("source_projection_frame_id"))) {
      throw new Error("viewer did not submit implicit camera move request");
    }

    await page.selectOption("#playback-mode-selector", "replay_artifact");
    const replayLabel = await page.$eval("#playback-mode-note", (el) => el.textContent);
    if (!replayLabel.includes("audit replay")) throw new Error("Replay Artifact mode is not labeled as audit replay");

    const countBeforeAdvance = Number(await page.locator("#frame-count").textContent());
    await page.locator("#advance-button").click();
    await page.waitForFunction((previous) => Number(document.getElementById("frame-count")?.textContent || "0") > previous, countBeforeAdvance);
    const allowedPostPaths = new Set(["/advance", "/camera", "/interaction", "/run_step"]);
    const unexpectedPostPaths = postPaths.filter((pathName) => !allowedPostPaths.has(pathName));
    if (unexpectedPostPaths.length) {
      throw new Error(`viewer used unexpected write endpoint(s): ${unexpectedPostPaths.join(", ")}`);
    }
    const timelineXssProbe = await page.evaluate(() => {
      window.__genewordXssProbe = 0;
      const malicious = '<img src=x onerror="window.__genewordXssProbe=1">';
      renderTimeline({
        observer_id: "observer::xss-probe",
        payload: {
          event_timeline: {
            interaction_record_ids: [malicious],
          },
        },
      });
      return {
        executed: window.__genewordXssProbe,
        injectedElement: Boolean(document.querySelector("#event-timeline img")),
        renderedText: document.getElementById("event-timeline")?.textContent || "",
      };
    });
    if (timelineXssProbe.executed || timelineXssProbe.injectedElement) {
      throw new Error("event timeline executed or injected untrusted markup");
    }
    if (!timelineXssProbe.renderedText.includes("<img src=x")) {
      throw new Error("event timeline did not preserve untrusted markup as inert text");
    }
    if (consoleErrors.length) {
      throw new Error(`browser console errors: ${consoleErrors.join(" | ")}`);
    }
    console.log("implicit 3D live interaction viewer smoke passed");
  } finally {
    await browser.close();
    server.kill();
  }
}

main().catch((error) => {
  console.error(error);
  process.exit(1);
});
