/**
 * Pure-function scale helpers for SVG chart math.
 *
 * No DOM access. All functions return numbers or arrays for use as SVG
 * attribute values.
 */

/**
 * Build a linear scale function mapping a numeric domain to a numeric range.
 *
 * Example: `linearScale({ domain: [0, 100], range: [0, 1] })(50) === 0.5`.
 */
export function linearScale({
  domain,
  range,
}: {
  domain: [number, number];
  range: [number, number];
}): (value: number) => number {
  const [domainMin, domainMax] = domain;
  const [rangeMin, rangeMax] = range;
  const domainSpan = domainMax - domainMin;

  // Domain-collapse guard: a zero-width domain would divide by zero. Map every
  // input to the midpoint of the range — visually that places the bar/line at
  // the chart's vertical center, which is the most informative neutral choice.
  if (domainSpan === 0) {
    const midpoint = (rangeMin + rangeMax) / 2;
    return () => midpoint;
  }

  const slope = (rangeMax - rangeMin) / domainSpan;
  return (value: number) => rangeMin + (value - domainMin) * slope;
}

/**
 * Wilkinson-style round-number tick generator.
 *
 * Picks a step in the family `{1, 2, 2.5, 5, 10} × 10^n` such that the
 * produced ticks cover `[min, max]` with approximately `count` divisions.
 * Ticks are aligned to multiples of the step using `Math.floor`/`Math.ceil`
 * at the boundaries (NOT `Math.round`) to avoid floating-point drift when an
 * axis value lies exactly on the step.
 *
 * Examples:
 *   niceTicks({ min: 0, max: 95, count: 5 })   -> [0, 25, 50, 75, 100]
 *   niceTicks({ min: -3, max: 4, count: 5 })   -> [-4, -2, 0, 2, 4]
 *   niceTicks({ min: 7, max: 7, count: 5 })    -> [7]
 */
export function niceTicks({
  min,
  max,
  count,
}: {
  min: number;
  max: number;
  count: number;
}): number[] {
  if (min === max) {
    return [min];
  }

  const range = max - min;
  // Divide by `count - 1` so a request for N ticks lays out N - 1 intervals
  // across the range (e.g. count=5 over 0..95 ⇒ step=25 ⇒ [0, 25, 50, 75, 100]).
  const intervals = Math.max(count - 1, 1);
  const roughStep = range / intervals;
  const magnitude = Math.pow(10, Math.floor(Math.log10(roughStep)));
  const normalizedStep = roughStep / magnitude;

  // Extended Wilkinson step family: 1, 2, 2.5, 5, 10 × 10^n. The 2.5 entry is
  // what makes `niceTicks({min:0, max:95, count:5})` produce step=25 (and the
  // canonical [0, 25, 50, 75, 100] series) instead of step=20.
  let niceStepMultiplier: number;
  if (normalizedStep < 1.5) {
    niceStepMultiplier = 1;
  } else if (normalizedStep < 2.25) {
    niceStepMultiplier = 2;
  } else if (normalizedStep < 3.5) {
    niceStepMultiplier = 2.5;
  } else if (normalizedStep < 7.5) {
    niceStepMultiplier = 5;
  } else {
    niceStepMultiplier = 10;
  }
  const step = niceStepMultiplier * magnitude;

  const tickStart = Math.floor(min / step) * step;
  const tickEnd = Math.ceil(max / step) * step;

  const ticks: number[] = [];
  // Use a strict numeric loop with floating-point-tolerant comparison to avoid
  // accumulator drift across many steps.
  const tolerance = step * 1e-9;
  // Pick the decimal precision needed to represent `step` exactly. The +1 on
  // the `niceStepMultiplier === 2.5` branch handles the "half-step" case
  // where `step = 0.25` etc. — without it we'd round 0.25 to 0.3.
  const baseDecimals = Math.max(0, -Math.floor(Math.log10(magnitude)));
  const decimals = niceStepMultiplier === 2.5 ? baseDecimals + 1 : baseDecimals;
  for (
    let currentTick = tickStart;
    currentTick <= tickEnd + tolerance;
    currentTick += step
  ) {
    // Round to the step's decimal precision to remove accumulated FP error
    // (e.g. 0.1 + 0.2 = 0.30000000000000004).
    ticks.push(Number(currentTick.toFixed(decimals)));
  }
  return ticks;
}
