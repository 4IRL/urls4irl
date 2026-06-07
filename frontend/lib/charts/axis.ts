/**
 * Pure-function axis helpers for SVG chart axes.
 *
 * No DOM access. Maps numeric ticks through a caller-supplied scale into
 * `{ position, label }` records and formats UTC ISO bucket boundaries into
 * compact axis labels.
 */

const EN_US_LOCALE = "en-US";
const UTC_TIME_ZONE = "UTC";

const HOUR_FORMATTER = new Intl.DateTimeFormat(EN_US_LOCALE, {
  hour: "2-digit",
  minute: "2-digit",
  hour12: false,
  timeZone: UTC_TIME_ZONE,
});

const DAY_FORMATTER = new Intl.DateTimeFormat(EN_US_LOCALE, {
  month: "short",
  day: "2-digit",
  timeZone: UTC_TIME_ZONE,
});

/**
 * Map a list of numeric tick values through a scale function and return their
 * pixel positions plus rendered string labels. `axisLength` is currently
 * unused by the math but kept in the signature so callers can later add
 * label-overflow logic without changing the function shape.
 */
export function buildAxisTicks({
  ticks,
  scale,
  axisLength,
}: {
  ticks: number[];
  scale: (value: number) => number;
  axisLength: number;
}): { position: number; label: string }[] {
  void axisLength;

  return ticks.map((tickValue) => ({
    position: scale(tickValue),
    label: String(tickValue),
  }));
}

/**
 * Format an ISO 8601 timestamp into a compact axis label.
 *
 * Examples:
 *   formatBucketLabel({ iso: "2026-06-06T14:00:00Z", resolution: "hour" }) -> "14:00"
 *   formatBucketLabel({ iso: "2026-06-06T00:00:00Z", resolution: "day" })  -> "Jun 06"
 *
 * Server bucket boundaries are emitted in UTC, so labels are also rendered in
 * UTC to avoid local-timezone drift across machines. The en-US locale is
 * pinned at the module level so test output is deterministic regardless of
 * the host runtime locale.
 */
export function formatBucketLabel({
  iso,
  resolution,
}: {
  iso: string;
  resolution: "hour" | "day";
}): string {
  const parsedDate = new Date(iso);
  const formatter = resolution === "hour" ? HOUR_FORMATTER : DAY_FORMATTER;
  return formatter.format(parsedDate);
}
