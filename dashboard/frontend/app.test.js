const test = require("node:test");
const assert = require("node:assert/strict");

const { deriveSmaPulse, formatMetric } = require("./app.js");

test("deriveSmaPulse reports the latest close above the SMA", () => {
  const pulse = deriveSmaPulse(
    { dates: ["2026-07-29", "2026-07-30"], close: [10, 12] },
    { dates: ["2026-07-29", "2026-07-30"], sma: [null, 10] },
  );

  assert.deepEqual(pulse, {
    date: "2026-07-30",
    close: 12,
    sma: 10,
    distancePct: 20,
    position: "above",
  });
});

test("deriveSmaPulse reports the latest close below the SMA", () => {
  const pulse = deriveSmaPulse(
    { dates: ["2026-07-30"], close: [8] },
    { dates: ["2026-07-30"], sma: [10] },
  );
  assert.equal(pulse.position, "below");
  assert.equal(pulse.distancePct, -20);
});

test("deriveSmaPulse returns null until an SMA exists", () => {
  assert.equal(
    deriveSmaPulse(
      { dates: ["2026-07-30"], close: [8] },
      { dates: ["2026-07-30"], sma: [null] },
    ),
    null,
  );
});

test("formatMetric renders return and drawdown as signed percentages", () => {
  assert.equal(formatMetric("total_return", 4.18), "+418.0%");
  assert.equal(formatMetric("max_drawdown", 0.397), "−39.7%");
});

test("formatMetric renders Sharpe as a ratio", () => {
  assert.equal(formatMetric("sharpe", 0.993), "0.99");
});
