import assert from "node:assert/strict";
import { test } from "node:test";

import { APP_ID, assertLicenseEnvironment } from "../src/model.js";

function env(overrides = {}) {
  return { DAL_APP_ID: APP_ID, ...overrides };
}

test("die erwartete App-Kennung ist gesetzt", () => {
  assert.equal(APP_ID, "photosort");
  assert.doesNotThrow(() => assertLicenseEnvironment(env()));
});

test("ein fehlendes oder fremdes DAL_APP_ID bricht ab", () => {
  assert.throws(() => assertLicenseEnvironment({}), /DAL_APP_ID/);
  assert.throws(() => assertLicenseEnvironment(env({ DAL_APP_ID: "photosort-eye-eval" })), /DAL_APP_ID/);
});

test("eine umgeleitete Lizenzprüfung bricht ab", () => {
  assert.throws(
    () => assertLicenseEnvironment(env({ DAL_LICENSE_ENDPOINT: "https://example.test" })),
    /Lizenz/,
  );
});

test("ein Download-Token bricht ab", () => {
  assert.throws(() => assertLicenseEnvironment(env({ HF_TOKEN: "hf_x" })), /Token/);
});

test("eine gesetzte Proxy-Variable bricht ab", () => {
  assert.throws(() => assertLicenseEnvironment(env({ HTTPS_PROXY: "http://proxy.test:3128" })), /Proxy/);
  assert.throws(() => assertLicenseEnvironment(env({ ALL_PROXY: "socks5://proxy.test:1080" })), /Proxy/);
});

test("eine leere Proxy-Variable bricht nicht ab", () => {
  assert.doesNotThrow(() => assertLicenseEnvironment(env({ HTTP_PROXY: "" })));
});

test("die Meldungen nennen keinen Host, keine Version und keinen Pin", () => {
  const faelle = [
    env({ DAL_LICENSE_ENDPOINT: "https://events.example.test/collect" }),
    env({ HF_TOKEN: "hf_geheim" }),
    env({ HTTPS_PROXY: "http://10.1.2.3:3128" }),
    env({ DAL_APP_ID: "falsch" }),
  ];
  for (const fall of faelle) {
    try {
      assertLicenseEnvironment(fall);
    } catch (error) {
      for (const verboten of ["example.test", "hf_geheim", "10.1.2.3", "v1.0.0", "4.2.3"]) {
        assert.equal(error.message.includes(verboten), false, error.message);
      }
    }
  }
});
