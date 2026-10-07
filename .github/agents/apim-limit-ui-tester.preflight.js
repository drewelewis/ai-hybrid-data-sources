const ALLOWED_SCENARIOS = new Set([
  "smoke",
  "rpm-serial",
  "rpm-concurrent",
  "tpm-serial",
  "tpm-concurrent",
  "cross-model-rpm",
  "recovery-after-429",
  "workbook-visual-check",
]);

const SINGLE_ATTEMPT_SCENARIOS = new Set([
  "smoke",
  "recovery-after-429",
  "workbook-visual-check",
]);

const CONCURRENT_SCENARIOS = new Set([
  "rpm-concurrent",
  "tpm-concurrent",
]);

function fail(message) {
  const error = new Error(message);
  error.code = "BLOCKED_PREFLIGHT";
  throw error;
}

function requirePositiveInteger(value, name) {
  if (!Number.isInteger(value) || value <= 0) {
    fail(`${name} must be a positive integer.`);
  }
  return value;
}

function isIpLiteral(hostname) {
  const host = hostname.replace(/^\[|\]$/g, "");
  return (
    /^\d{1,3}(?:\.\d{1,3}){3}$/.test(host) ||
    /^[0-9a-f:]+$/i.test(host)
  );
}

function normalizeApprovedHosts(hosts, name) {
  if (!Array.isArray(hosts) || hosts.length === 0) {
    fail(`${name} must contain at least one exact host.`);
  }

  const normalized = hosts.map((host) => {
    if (
      typeof host !== "string" ||
      host.trim() === "" ||
      host.includes("*") ||
      host.includes("/") ||
      isIpLiteral(host.trim())
    ) {
      fail(`${name} contains an invalid host.`);
    }
    return host.trim().toLowerCase();
  });

  return [...new Set(normalized)];
}

function validateUrl(rawUrl, approvedHosts, name) {
  let parsed;
  try {
    parsed = new URL(rawUrl);
  } catch {
    fail(`${name} must be a valid absolute URL.`);
  }

  if (
    parsed.protocol !== "https:" ||
    parsed.username !== "" ||
    parsed.password !== "" ||
    isIpLiteral(parsed.hostname) ||
    !approvedHosts.includes(parsed.hostname.toLowerCase())
  ) {
    fail(`${name} must use HTTPS and an exact approved non-IP host.`);
  }
  return parsed.toString();
}

function parseUtc(rawValue, name) {
  if (
    typeof rawValue !== "string" ||
    !rawValue.endsWith("Z") ||
    Number.isNaN(Date.parse(rawValue))
  ) {
    fail(`${name} must be an ISO 8601 UTC value ending in Z.`);
  }
  return new Date(rawValue);
}

function rejectSecretFields(manifest) {
  const forbidden = /^(authorization|apiKey|subscriptionKey|cookie|bearer|password|secret|credential)$/i;
  for (const key of Object.keys(manifest)) {
    if (forbidden.test(key)) {
      fail(`Manifest field '${key}' is forbidden.`);
    }
  }
}

function validateRunManifest(manifest, now = new Date()) {
  if (!manifest || typeof manifest !== "object" || Array.isArray(manifest)) {
    fail("Manifest must be an object.");
  }
  rejectSecretFields(manifest);

  if (!ALLOWED_SCENARIOS.has(manifest.scenario)) {
    fail("Unknown scenario.");
  }

  const approvedUiHosts = normalizeApprovedHosts(
    manifest.approvedUiHosts,
    "approvedUiHosts",
  );
  const approvedWorkbookHosts = normalizeApprovedHosts(
    manifest.approvedWorkbookHosts,
    "approvedWorkbookHosts",
  );
  const uiUrl = validateUrl(manifest.uiUrl, approvedUiHosts, "uiUrl");
  const workbookUrl = validateUrl(
    manifest.workbookUrl,
    approvedWorkbookHosts,
    "workbookUrl",
  );

  const startUtc = parseUtc(manifest.startUtc, "startUtc");
  const endUtc = parseUtc(manifest.endUtc, "endUtc");
  if (
    startUtc.getTime() > now.getTime() ||
    now.getTime() >= endUtc.getTime() ||
    endUtc.getTime() - startUtc.getTime() > 60 * 60 * 1000
  ) {
    fail("The run must be active now and no longer than 60 minutes.");
  }

  const testRpm = requirePositiveInteger(manifest.testRpm, "testRpm");
  const testSkuTpm = requirePositiveInteger(
    manifest.testSkuTpm,
    "testSkuTpm",
  );
  const testModelTpm = requirePositiveInteger(
    manifest.testModelTpm,
    "testModelTpm",
  );
  const backendDeploymentTpm = requirePositiveInteger(
    manifest.backendDeploymentTpm,
    "backendDeploymentTpm",
  );
  const calibratedRequestTokens = requirePositiveInteger(
    manifest.calibratedRequestTokens,
    "calibratedRequestTokens",
  );
  const responseTokenCap = requirePositiveInteger(
    manifest.responseTokenCap,
    "responseTokenCap",
  );
  const operatorAttempts = requirePositiveInteger(
    manifest.maximumRequestAttempts,
    "maximumRequestAttempts",
  );
  const operatorConcurrency = requirePositiveInteger(
    manifest.maximumConcurrency,
    "maximumConcurrency",
  );

  if (
    testModelTpm >= testSkuTpm ||
    testSkuTpm >= backendDeploymentTpm ||
    testModelTpm >= backendDeploymentTpm
  ) {
    fail("TPM hierarchy is unsafe.");
  }
  if (responseTokenCap > 8) {
    fail("responseTokenCap must not exceed 8.");
  }
  if (
    manifest.temporaryLimitsConfirmed !== true ||
    manifest.tracingEnabled !== true
  ) {
    fail("Temporary limits and tracing must be confirmed.");
  }
  if (
    typeof manifest.correlationMechanism !== "string" ||
    manifest.correlationMechanism.trim() === ""
  ) {
    fail("correlationMechanism is required.");
  }
  if (
    manifest.scenario === "cross-model-rpm" &&
    (typeof manifest.secondModel !== "string" ||
      manifest.secondModel.trim() === "")
  ) {
    fail("secondModel is required for cross-model-rpm.");
  }
  if (typeof manifest.fixedModelMode !== "boolean") {
    fail("fixedModelMode must be explicitly true or false.");
  }
  if (manifest.scenario === "cross-model-rpm" && manifest.fixedModelMode) {
    fail("cross-model-rpm requires a model selector.");
  }

  let scenarioAttemptCap;
  if (SINGLE_ATTEMPT_SCENARIOS.has(manifest.scenario)) {
    scenarioAttemptCap = 1;
  } else if (manifest.scenario.startsWith("rpm-")) {
    scenarioAttemptCap = testRpm + 2;
  } else if (manifest.scenario.startsWith("tpm-")) {
    scenarioAttemptCap = Math.ceil(
      (1.25 * testSkuTpm) / calibratedRequestTokens,
    );
  } else {
    scenarioAttemptCap = 2 * testRpm;
  }

  const maximumRequestAttempts = Math.min(
    operatorAttempts,
    scenarioAttemptCap,
  );
  const maximumConcurrency = CONCURRENT_SCENARIOS.has(manifest.scenario)
    ? Math.min(operatorConcurrency, 4)
    : 1;

  return Object.freeze({
    ...manifest,
    uiUrl,
    workbookUrl,
    approvedUiHosts,
    approvedWorkbookHosts,
    startUtc: startUtc.toISOString(),
    endUtc: endUtc.toISOString(),
    maximumRequestAttempts,
    maximumConcurrency,
  });
}

if (typeof module !== "undefined") {
  module.exports = { validateRunManifest };
}
