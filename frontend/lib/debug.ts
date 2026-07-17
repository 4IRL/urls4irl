/**
 * Namespaced runtime debug logger. `debug(namespace)` returns a logging function
 * that emits `console.log("[namespace]", ...args)` only when the namespace is
 * enabled, and a no-op otherwise. Enable namespaces from DevTools:
 *   localStorage.debug = "metrics,ajax"; location.reload();
 * Allow-list syntax mirrors the `debug` npm module: `*` (all), `metrics:*`
 * (colon hierarchy), `-noise` (negation). The five splash namespaces are public
 * (any user); every other namespace additionally requires APP_CONFIG.debugEnabled.
 */
import { APP_CONFIG } from "./config.js";

export const PUBLIC_NAMESPACES = new Set([
  "splash",
  "splash:login",
  "splash:register",
  "splash:password",
  "splash:email",
]);

const STORAGE_KEY = "debug";
const NOOP = (..._args: unknown[]): void => {};

interface AllowList {
  include: string[];
  exclude: string[];
}

function parseAllowList(raw: string | null): AllowList {
  const include: string[] = [];
  const exclude: string[] = [];
  for (const segment of (raw ?? "").split(",")) {
    const pattern = segment.trim();
    if (!pattern) continue;
    if (pattern.startsWith("-")) {
      exclude.push(pattern.slice(1));
    } else {
      include.push(pattern);
    }
  }
  return { include, exclude };
}

function matches({
  namespace,
  pattern,
}: {
  namespace: string;
  pattern: string;
}): boolean {
  if (pattern === "*") return true;
  if (pattern.endsWith(":*")) {
    return namespace.startsWith(pattern.slice(0, -1));
  }
  return namespace === pattern;
}

function isEnabled({
  namespace,
  raw,
}: {
  namespace: string;
  raw: string | null;
}): boolean {
  const { include, exclude } = parseAllowList(raw);
  if (exclude.some((pattern) => matches({ namespace, pattern }))) return false;
  return include.some((pattern) => matches({ namespace, pattern }));
}

// Reading localStorage can throw (sandboxed iframes, some privacy modes,
// storage disabled). The 5 public splash namespaces ship to every anonymous
// user, so a throw here would break splash-page init — swallow it and treat a
// failed read as "no allow-list" (silent).
function readAllowList(): string | null {
  try {
    return localStorage.getItem(STORAGE_KEY);
  } catch {
    return null;
  }
}

export function debug(namespace: string): (...args: unknown[]) => void {
  if (!PUBLIC_NAMESPACES.has(namespace) && !APP_CONFIG.debugEnabled)
    return NOOP;
  const raw = readAllowList();
  if (!isEnabled({ namespace, raw })) return NOOP;
  const prefix = `[${namespace}]`;
  return (...args: unknown[]): void => {
    console.log(prefix, ...args);
  };
}
