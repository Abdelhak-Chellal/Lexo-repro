/**
 * extract_signatures.js
 *
 * Statically analyses a JavaScript source file and extracts:
 *   - exported function signatures (name, params, defaults, rest args)
 *   - JSDoc annotations (description, @param, @returns, @throws, @example)
 *   - inferred type hints from JSDoc or default values
 *
 * Usage:
 *   node extract_signatures.js <path/to/source.js>
 *
 * Output: JSON printed to stdout
 */

const fs    = require("fs");
const path  = require("path");
const acorn = require("acorn");
const walk  = require("acorn-walk");

// ---------------------------------------------------------------------------
// JSDoc parser
// ---------------------------------------------------------------------------
function parseJsDoc(commentText) {
  if (!commentText) return null;

  const lines = commentText
    .replace(/^\s*\/\*\*?/, "")
    .replace(/\*\/\s*$/, "")
    .split("\n")
    .map(l => l.replace(/^\s*\*\s?/, "").trim())
    .filter(Boolean);

  const result = {
    description: [],
    params: [],
    returns: null,
    throws: [],
    examples: [],
  };

  let current = "description";
  let currentTag = null;

  for (const line of lines) {
    if (line.startsWith("@param")) {
      const m = line.match(/@param\s+(?:\{([^}]*)\}\s+)?(\S+)\s*(.*)/);
      if (m) {
        currentTag = { name: m[2].replace(/[\[\]]/g, "").split("=")[0], type: m[1] || null, description: m[3] || "" };
        result.params.push(currentTag);
        current = "param";
      }
    } else if (line.startsWith("@returns") || line.startsWith("@return")) {
      const m = line.match(/@returns?\s+(?:\{([^}]*)\}\s*)?(.*)/);
      currentTag = { type: m ? m[1] || null : null, description: m ? m[2] || "" : "" };
      result.returns = currentTag;
      current = "returns";
    } else if (line.startsWith("@throws") || line.startsWith("@exception")) {
      const m = line.match(/@throws?\s+(?:\{([^}]*)\}\s*)?(.*)/);
      currentTag = { type: m ? m[1] || null : null, description: m ? m[2] || "" : "" };
      result.throws.push(currentTag);
      current = "throws";
    } else if (line.startsWith("@example")) {
      result.examples.push(line.replace(/@example\s*/, ""));
      current = "example";
    } else if (line.startsWith("@")) {
      current = "other";
      currentTag = null;
    } else {
      if (current === "description") result.description.push(line);
      else if (current === "param" && currentTag) currentTag.description += " " + line;
      else if (current === "returns" && currentTag) currentTag.description += " " + line;
      else if (current === "example") result.examples[result.examples.length - 1] += "\n" + line;
    }
  }

  result.description = result.description.join(" ").trim() || null;
  return result;
}

// ---------------------------------------------------------------------------
// AST helpers
// ---------------------------------------------------------------------------
function inferTypeFromDefault(node) {
  if (!node) return null;
  switch (node.type) {
    case "Literal":
      if (node.value === null) return "null";
      return typeof node.value;
    case "ArrayExpression":  return "array";
    case "ObjectExpression": return "object";
    case "UnaryExpression":
      if (node.operator === "-" && node.argument.type === "Literal") return "number";
      return null;
    default: return null;
  }
}

function defaultValueStr(node) {
  if (!node) return null;
  if (node.type === "Literal")          return JSON.stringify(node.value);
  if (node.type === "ArrayExpression")  return "[]";
  if (node.type === "ObjectExpression") return "{}";
  if (node.type === "UnaryExpression")  return node.operator + defaultValueStr(node.argument);
  if (node.type === "Identifier")       return node.name;
  return null;
}

function extractParams(fnNode) {
  return (fnNode.params || []).map(p => {
    if (p.type === "Identifier") {
      return { name: p.name, default: null, defaultType: null, rest: false };
    }
    if (p.type === "AssignmentPattern") {
      return {
        name: p.left.name || "param",
        default: defaultValueStr(p.right),
        defaultType: inferTypeFromDefault(p.right),
        rest: false,
      };
    }
    if (p.type === "RestElement") {
      return { name: p.argument.name || "args", default: null, defaultType: "array", rest: true };
    }
    if (p.type === "ObjectPattern") {
      const keys = (p.properties || []).map(pr => pr.key && pr.key.name).filter(Boolean).join(", ");
      return { name: `{${keys}}`, default: null, defaultType: "object", rest: false };
    }
    if (p.type === "ArrayPattern") {
      return { name: "[destructured]", default: null, defaultType: "array", rest: false };
    }
    return { name: "param", default: null, defaultType: null, rest: false };
  });
}

function buildSignature(name, params) {
  const paramStr = params.map(p => {
    let s = p.rest ? "..." + p.name : p.name;
    if (p.default !== null) s += " = " + p.default;
    return s;
  }).join(", ");
  return `${name}(${paramStr})`;
}

// ---------------------------------------------------------------------------
// Main extraction
// ---------------------------------------------------------------------------
function extractSignatures(filePath) {
  let src;
  try {
    src = fs.readFileSync(filePath, "utf8");
  } catch (e) {
    return { error: `Cannot read file: ${e.message}`, file: filePath, functions: [] };
  }

  const collectedComments = [];
  const parseOpts = {
    ecmaVersion: 2022,
    locations: true,
    onComment: collectedComments,
  };

  let ast;
  for (const sourceType of ["module", "script"]) {
    try {
      ast = acorn.parse(src, { ...parseOpts, sourceType });
      break;
    } catch (e) {
      if (sourceType === "script") {
        return { error: `Parse error: ${e.message}`, file: filePath, functions: [] };
      }
    }
  }

  function findJsDoc(nodeStart) {
    for (let i = collectedComments.length - 1; i >= 0; i--) {
      const c = collectedComments[i];
      if (c.type === "Block" && c.end <= nodeStart) {
        const gap = src.slice(c.end, nodeStart);
        if (/^\s*$/.test(gap)) return c.value;
        break;
      }
    }
    return null;
  }

  const functions = [];
  const seen = new Set();

  function register(name, fnNode, exportedAs) {
    const key = name + ":" + fnNode.start;
    if (seen.has(key)) return;
    seen.add(key);

    const params = extractParams(fnNode);
    const rawDoc = findJsDoc(fnNode.start);
    const jsDoc  = parseJsDoc(rawDoc ? "/**" + rawDoc + "*/" : null);

    // Merge JSDoc param info into params
    if (jsDoc && jsDoc.params.length) {
      params.forEach(p => {
        const doc = jsDoc.params.find(d => d.name === p.name);
        if (doc) {
          if (doc.type && !p.defaultType) p.inferredType = doc.type;
          if (doc.description)            p.description  = doc.description.trim();
        }
      });
    }

    // Extract function body slice (first 15 lines, skipping the signature line)
    const bodyLines = src.split("\n").slice(fnNode.loc.start.line, fnNode.loc.end.line);
    const bodySlice = bodyLines.slice(0, 15).join("\n").trim();

    functions.push({
      name,
      exportedAs: exportedAs || name,
      signature:  buildSignature(name, params),
      params,
      jsDoc:      jsDoc || null,
      bodySlice,
      loc:        { start: fnNode.loc.start.line, end: fnNode.loc.end.line },
      isAsync:    fnNode.async     || false,
      isGenerator: fnNode.generator || false,
    });
  }

  // 1) Named function declarations
  walk.simple(ast, {
    FunctionDeclaration(node) {
      if (node.id) register(node.id.name, node, null);
    },
  });

  // 2) module.exports = function / module.exports.foo = function / exports.foo = function
  walk.simple(ast, {
    AssignmentExpression(node) {
      const left  = node.left;
      const right = node.right;
      const isFn  = right.type === "FunctionExpression" || right.type === "ArrowFunctionExpression";
      if (!isFn) return;

      if (
        left.type === "MemberExpression" &&
        left.object.type === "Identifier" && left.object.name === "module" &&
        left.property.type === "Identifier" && left.property.name === "exports"
      ) {
        const name = right.id ? right.id.name : "exports";
        register(name, right, "module.exports");
        return;
      }

      if (left.type === "MemberExpression" && left.property.type === "Identifier") {
        const obj = left.object;
        const isModuleExports = obj.type === "MemberExpression" && obj.object.name === "module" && obj.property.name === "exports";
        const isExports       = obj.type === "Identifier" && obj.name === "exports";
        if (isModuleExports || isExports) {
          const exportName = left.property.name;
          const fnName     = right.id ? right.id.name : exportName;
          register(fnName, right, exportName);
        }
      }
    },
  });

  // 3) const/let/var foo = function / arrow at top level
  walk.simple(ast, {
    VariableDeclaration(node) {
      for (const decl of node.declarations) {
        if (!decl.init) continue;
        const init = decl.init;
        if (init.type === "FunctionExpression" || init.type === "ArrowFunctionExpression") {
          const name = decl.id && decl.id.name ? decl.id.name : "anonymous";
          register(name, init, null);
        }
      }
    },
  });

  // 4) ES module exports
  walk.simple(ast, {
    ExportNamedDeclaration(node) {
      if (node.declaration && node.declaration.type === "FunctionDeclaration" && node.declaration.id) {
        register(node.declaration.id.name, node.declaration, node.declaration.id.name);
      }
    },
    ExportDefaultDeclaration(node) {
      const decl = node.declaration;
      if (decl.type === "FunctionDeclaration" || decl.type === "FunctionExpression") {
        const name = decl.id ? decl.id.name : "default";
        register(name, decl, "default");
      }
    },
  });

  return {
    file:          path.resolve(filePath),
    functionCount: functions.length,
    functions,
  };
}

// ---------------------------------------------------------------------------
// CLI
// ---------------------------------------------------------------------------
if (require.main === module) {
  const filePath = process.argv[2];
  if (!filePath) {
    console.error("Usage: node extract_signatures.js <path/to/file.js>");
    process.exit(1);
  }
  const result = extractSignatures(filePath);
  console.log(JSON.stringify(result, null, 2));
}

module.exports = { extractSignatures };
