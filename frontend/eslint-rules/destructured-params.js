/**
 * u4i/destructured-params: a function taking 2+ positional params, or a single
 * bare boolean, must accept one destructured object instead so call sites are
 * self-documenting.
 *
 * Inline callbacks (a function passed directly as a call/`new` argument) are
 * skipped (also through `as` / `satisfies` / `!` wrappers): their arity is
 * dictated by the API they are handed to. Setters are skipped: their single
 * param is fixed by the language.
 *
 * Legacy violators are grandfathered by `baseline` keys of the form
 * `<path relative to root>:<name>`, where `root` is the `root` option (falling
 * back to ESLint's cwd), so keys are stable wherever ESLint is launched from.
 * A baseline key that no longer violates is itself reported, so the baseline
 * only ever shrinks.
 *
 * Known limits: same-named functions in one file share a key, so one baseline
 * entry covers all of them. Anonymous functions (including computed keys) are
 * never baselined: they are always reported, and a `<path>:<anonymous>` entry
 * is reported as stale.
 */

import path from "node:path";

const ANONYMOUS = "<anonymous>";

/** @param {any} key */
function keyName(key) {
  if (!key) return null;
  if (key.type === "Identifier") return key.name;
  if (key.type === "PrivateIdentifier") return `#${key.name}`;
  if (key.type === "Literal") return String(key.value);
  return null;
}

/** @param {any} node */
function functionName(node) {
  if (node.id) return node.id.name;
  const parent = node.parent;
  switch (parent?.type) {
    case "VariableDeclarator":
      return keyName(parent.id) ?? ANONYMOUS;
    case "Property":
    case "MethodDefinition":
    case "PropertyDefinition":
      if (parent.computed) return ANONYMOUS;
      return keyName(parent.key) ?? ANONYMOUS;
    case "AssignmentExpression":
      if (parent.left.type === "MemberExpression" && !parent.left.computed) {
        return keyName(parent.left.property) ?? ANONYMOUS;
      }
      return keyName(parent.left) ?? ANONYMOUS;
    default:
      return ANONYMOUS;
  }
}

/** @param {any} param */
function isDestructuredObject(param) {
  return (
    param.type === "ObjectPattern" ||
    (param.type === "AssignmentPattern" && param.left.type === "ObjectPattern")
  );
}

/** @param {any} param */
function isBareBoolean(param) {
  const unwrapped =
    param.type === "TSParameterProperty" ? param.parameter : param;
  const target =
    unwrapped.type === "AssignmentPattern" ? unwrapped.left : unwrapped;
  if (target.typeAnnotation?.typeAnnotation?.type === "TSBooleanKeyword") {
    return true;
  }
  return (
    unwrapped.type === "AssignmentPattern" &&
    unwrapped.right.type === "Literal" &&
    typeof unwrapped.right.value === "boolean"
  );
}

const TYPE_WRAPPERS = new Set([
  "TSAsExpression",
  "TSSatisfiesExpression",
  "TSNonNullExpression",
]);

/** @param {any} node */
function isInlineCallback(node) {
  let argument = node;
  while (TYPE_WRAPPERS.has(argument.parent?.type)) {
    argument = argument.parent;
  }
  const parent = argument.parent;
  return (
    (parent?.type === "CallExpression" || parent?.type === "NewExpression") &&
    parent.arguments.includes(argument)
  );
}

/** @param {any} node */
function isSetter(node) {
  const parent = node.parent;
  return (
    (parent?.type === "Property" || parent?.type === "MethodDefinition") &&
    parent.kind === "set"
  );
}

/** @type {import("eslint").Rule.RuleModule} */
const rule = {
  meta: {
    type: "suggestion",
    docs: {
      description:
        "Require a destructured object param for 2+ positional params or a bare boolean",
    },
    schema: [
      {
        type: "object",
        properties: {
          allowNames: { type: "array", items: { type: "string" } },
          baseline: { type: "array", items: { type: "string" } },
          root: { type: "string" },
        },
        additionalProperties: false,
      },
    ],
    messages: {
      positional:
        "{{name}} takes {{count}} positional params — accept one destructured object instead (baseline key: {{key}})",
      booleanParam:
        "{{name}} takes a bare boolean — accept a destructured object instead (baseline key: {{key}})",
      staleBaseline:
        "baseline entry {{key}} no longer violates — remove it from destructured-params-baseline.json",
    },
  },

  create(context) {
    const options = context.options[0] ?? {};
    const allowNames = new Set(options.allowNames ?? []);
    const baseline = new Set(options.baseline ?? []);
    const relativePath = path
      .relative(options.root ?? context.cwd, context.filename)
      .replaceAll("\\", "/");
    const hitKeys = new Set();

    /** @param {any} node */
    function check(node) {
      if (isInlineCallback(node) || isSetter(node)) return;

      const params = node.params.filter(
        (param) => !(param.type === "Identifier" && param.name === "this"),
      );
      const positionalCount = params.filter(
        (param) => !isDestructuredObject(param),
      ).length;

      let messageId = null;
      if (positionalCount >= 2) {
        messageId = "positional";
      } else if (params.length === 1 && isBareBoolean(params[0])) {
        messageId = "booleanParam";
      }
      if (messageId === null) return;

      const name = functionName(node);
      if (allowNames.has(name)) return;

      const key = `${relativePath}:${name}`;
      if (name !== ANONYMOUS) {
        hitKeys.add(key);
        if (baseline.has(key)) return;
      }

      context.report({
        node,
        messageId,
        data: { name, count: String(positionalCount), key },
      });
    }

    return {
      FunctionDeclaration: check,
      FunctionExpression: check,
      ArrowFunctionExpression: check,
      "Program:exit"(program) {
        const filePrefix = `${relativePath}:`;
        for (const key of baseline) {
          if (key.startsWith(filePrefix) && !hitKeys.has(key)) {
            context.report({
              node: program,
              messageId: "staleBaseline",
              data: { key },
            });
          }
        }
      },
    };
  },
};

export default rule;
