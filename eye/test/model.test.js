import assert from "node:assert/strict";
import { test } from "node:test";

import { APP_ID, analyzeBytes, assertLicenseEnvironment } from "../src/model.js";

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

async function einPixelJpeg() {
  const { default: sharp } = await import("sharp");
  return sharp({ create: { width: 1, height: 1, channels: 3, background: "#fff" } })
    .jpeg()
    .toBuffer();
}

test("nicht dekodierbare Bytes werden als unlesbares Bild gemeldet, ohne das Modell zu rufen", async () => {
  let aufrufe = 0;
  const eye = { analyze: async () => (aufrufe += 1) };

  await assert.rejects(analyzeBytes(eye, Buffer.from([0xff, 0xd8, 0xff, 0x00])), {
    code: "UNREADABLE_IMAGE",
  });
  assert.equal(aufrufe, 0);
});

test("ein Fehler des Modells bleibt ein gewöhnlicher Fehler", async () => {
  const eye = {
    analyze: async () => {
      throw new Error("Inferenz kaputt");
    },
  };

  await assert.rejects(analyzeBytes(eye, await einPixelJpeg()), (error) => {
    assert.equal(error.code, undefined);
    assert.equal(error.message, "Inferenz kaputt");
    return true;
  });
});

test("ein lesbares Bild geht als Pixelpuffer an das Modell", async () => {
  const gesehen = [];
  const eye = {
    analyze: async (bild) => {
      gesehen.push({ width: bild.width, height: bild.height });
      return { kind: "landscape" };
    },
  };

  assert.deepEqual(await analyzeBytes(eye, await einPixelJpeg()), { kind: "landscape" });
  assert.deepEqual(gesehen, [{ width: 1, height: 1 }]);
});
