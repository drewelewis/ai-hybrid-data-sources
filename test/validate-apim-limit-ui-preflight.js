"use strict";

const assert = require("node:assert/strict");
const {
  validateRunManifest,
} = require("../.github/agents/apim-limit-ui-tester.preflight.js");

const now = new Date("2026-10-03T16:00:00Z");

function validManifest(overrides = {}) {
  return {
    runId: "run-001",
    scenario: "rpm-concurrent",
    uiUrl: "https://ui.example.test/chat",
    workbookUrl: "https://portal.azure.com/workbook",
    approvedUiHosts: ["ui.example.test"],
    approvedWorkbookHosts: ["portal.azure.com"],
    startUtc: "2026-10-03T15:55:00Z",
    endUtc: "2026-10-03T16:30:00Z",
    model: "existing-model",
    fixedModelMode: false,
    testRpm: 6,
    testSkuTpm: 400,
    testModelTpm: 300,
    backendDeploymentTpm: 1000,
    calibratedRequestTokens: 100,
    responseTokenCap: 8,
    maximumRequestAttempts: 100,
    maximumConcurrency: 10,
    temporaryLimitsConfirmed: true,
    tracingEnabled: true,
    correlationMechanism: "traceparent",
    ...overrides,
  };
}

const bounded = validateRunManifest(validManifest(), now);
assert.equal(bounded.maximumRequestAttempts, 8);
assert.equal(bounded.maximumConcurrency, 4);

const tpmBounded = validateRunManifest(
  validManifest({
    scenario: "tpm-concurrent",
    maximumRequestAttempts: 99,
  }),
  now,
);
assert.equal(tpmBounded.maximumRequestAttempts, 5);

const serialBounded = validateRunManifest(
  validManifest({ scenario: "rpm-serial", maximumConcurrency: 4 }),
  now,
);
assert.equal(serialBounded.maximumConcurrency, 1);

for (const overrides of [
  { scenario: "unknown" },
  { uiUrl: "https://evil.example.test", approvedUiHosts: ["example.test"] },
  { uiUrl: "https://ui.example.test.evil.test", approvedUiHosts: ["ui.example.test"] },
  { uiUrl: "https://user:pass@ui.example.test" },
  { uiUrl: "https://127.0.0.1" },
  { approvedUiHosts: ["*.example.test"] },
  { startUtc: "2026-10-03T16:01:00Z" },
  { endUtc: "2026-10-03T17:30:00Z" },
  { testModelTpm: 400 },
  { testModelTpm: 500 },
  { backendDeploymentTpm: 400 },
  { responseTokenCap: 9 },
  { tracingEnabled: false },
  { correlationMechanism: "" },
  { scenario: "cross-model-rpm" },
  { scenario: "cross-model-rpm", secondModel: "model-b", fixedModelMode: true },
  { fixedModelMode: "true" },
  { authorization: "forbidden" },
]) {
  assert.throws(
    () => validateRunManifest(validManifest(overrides), now),
    (error) => error.code === "BLOCKED_PREFLIGHT",
  );
}

console.log("Validated executable APIM limit UI preflight bounds.");
