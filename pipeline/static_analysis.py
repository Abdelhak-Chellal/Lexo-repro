"""
static_analysis.py

Extracts function signatures and metadata from JS and Python packages.
- JS: delegates to extract_signatures.js via subprocess (uses acorn AST)
- Python: uses the built-in ast module

Main entry point: analyze_package(package_name, tests_dir)
Returns a dict with extracted metadata, ready to inject into prompts.
"""

import ast
import json
import os
import subprocess

# Mirrors PACKAGE_CONFIG from verify.py
PACKAGE_SOURCE = {
    "is-number":          "index.js",
    "arr-diff":           "index.js",
    "is-odd":             "index.js",
    "is-even":            "index.js",
    "is-object":          "index.js",
    "left-pad":           "index.js",
    "concat-map":         "index.js",
    "replace-ext":        "index.js",
    "array-ify":          "index.js",
    "has-proto":          "index.js",
    "just-pick":          "packages/object-pick/index.cjs",
    "just-filter-object": "packages/object-filter/index.cjs",
    "primality":          "primality/primality.py",
}

PYTHON_PACKAGES = ["primality"]

SCRIPT_DIR = os.path.dirname(os.path.abspath(__file__))
EXTRACTOR_JS = os.path.join(SCRIPT_DIR, "extract_signatures.js")


# ---------------------------------------------------------------------------
# JS extraction
# ---------------------------------------------------------------------------

def analyze_js(source_path):
    """Run extract_signatures.js on a JS file and return parsed JSON."""
    result = subprocess.run(
        ["node", EXTRACTOR_JS, source_path],
        capture_output=True,
        text=True,
    )
    if result.returncode != 0:
        return {"error": result.stderr.strip(), "functions": []}
    try:
        return json.loads(result.stdout)
    except json.JSONDecodeError as e:
        return {"error": f"JSON parse error: {e}", "functions": []}


# ---------------------------------------------------------------------------
# Python extraction
# ---------------------------------------------------------------------------

def _param_info(arg, defaults_map):
    """Build a param descriptor from an ast.arg node."""
    name = arg.arg
    type_annotation = None
    if arg.annotation:
        try:
            type_annotation = ast.unparse(arg.annotation)
        except Exception:
            type_annotation = None

    default = defaults_map.get(name)
    default_type = None
    if default is not None:
        try:
            val = ast.literal_eval(default)
            default_type = type(val).__name__
        except Exception:
            default_type = None

    return {
        "name": name,
        "default": default,
        "defaultType": default_type,
        "inferredType": type_annotation,
        "rest": False,
    }


def _extract_docstring(node):
    """Return the docstring of a function node, or None."""
    if (
        node.body
        and isinstance(node.body[0], ast.Expr)
        and isinstance(node.body[0].value, ast.Constant)
        and isinstance(node.body[0].value.value, str)
    ):
        return node.body[0].value.value.strip()
    return None


def _parse_docstring(docstring):
    """
    Parse a NumPy / Google / plain docstring into structured fields.
    Returns dict with description, params, returns, raises.
    """
    if not docstring:
        return None

    lines = docstring.split("\n")
    result = {
        "description": [],
        "params": [],
        "returns": None,
        "raises": [],
    }

    current = "description"
    current_param = None

    for line in lines:
        stripped = line.strip()

        # Section headers (NumPy style)
        if stripped in ("Parameters", "Args", "Arguments"):
            current = "params"
            continue
        if stripped in ("Returns", "Return"):
            current = "returns"
            continue
        if stripped in ("Raises", "Raise", "Except", "Exceptions"):
            current = "raises"
            continue
        if stripped.startswith("---"):
            continue

        # Google style: "    param (type): description"
        if current == "params":
            m = __import__("re").match(r"^\s+(\w+)\s*(?:\(([^)]*)\))?:\s*(.*)", line)
            if m:
                current_param = {"name": m.group(1), "type": m.group(2), "description": m.group(3)}
                result["params"].append(current_param)
                continue
            if current_param and stripped:
                current_param["description"] += " " + stripped
            continue

        if current == "returns":
            if result["returns"] is None:
                result["returns"] = {"type": None, "description": stripped}
            else:
                result["returns"]["description"] += " " + stripped
            continue

        if current == "raises":
            m = __import__("re").match(r"^\s+(\w+):\s*(.*)", line)
            if m:
                result["raises"].append({"type": m.group(1), "description": m.group(2)})
            continue

        if current == "description" and stripped:
            result["description"].append(stripped)

    result["description"] = " ".join(result["description"]).strip() or None
    return result


def analyze_python(source_path):
    """Parse a Python source file and extract function signatures."""
    try:
        with open(source_path) as f:
            src = f.read()
    except OSError as e:
        return {"error": str(e), "functions": []}

    try:
        tree = ast.parse(src)
    except SyntaxError as e:
        return {"error": f"SyntaxError: {e}", "functions": []}

    functions = []

    for node in ast.walk(tree):
        if not isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef)):
            continue
        if node.name.startswith("_") and not node.name.startswith("__"):
            continue  # skip private helpers

        args = node.args
        all_args = args.args + args.posonlyargs + args.kwonlyargs

        # Map defaults: Python aligns defaults to the END of args
        defaults_map = {}
        offset = len(args.args) - len(args.defaults)
        for i, d in enumerate(args.defaults):
            arg_name = args.args[offset + i].arg
            try:
                defaults_map[arg_name] = ast.unparse(d)
            except Exception:
                defaults_map[arg_name] = None

        for kw_arg, kw_default in zip(args.kwonlyargs, args.kw_defaults):
            if kw_default is not None:
                try:
                    defaults_map[kw_arg.arg] = ast.unparse(kw_default)
                except Exception:
                    pass

        params = [_param_info(a, defaults_map) for a in all_args]

        # vararg (*args)
        if args.vararg:
            params.append({
                "name": args.vararg.arg,
                "default": None,
                "defaultType": "list",
                "inferredType": None,
                "rest": True,
            })

        # return annotation
        return_type = None
        if node.returns:
            try:
                return_type = ast.unparse(node.returns)
            except Exception:
                pass

        docstring = _extract_docstring(node)
        doc_parsed = _parse_docstring(docstring)

        param_str = ", ".join(
            ("*" if p["rest"] else "") + p["name"] +
            ((" = " + p["default"]) if p["default"] is not None else "")
            for p in params
        )
        signature = f"{node.name}({param_str})"

        functions.append({
            "name": node.name,
            "exportedAs": node.name,
            "signature": signature,
            "params": params,
            "returnType": return_type,
            "jsDoc": doc_parsed,
            "loc": {"start": node.lineno, "end": node.end_lineno},
            "isAsync": isinstance(node, ast.AsyncFunctionDef),
            "isGenerator": any(isinstance(n, ast.Yield) for n in ast.walk(node)),
        })

    return {
        "file": os.path.abspath(source_path),
        "functionCount": len(functions),
        "functions": functions,
    }


# ---------------------------------------------------------------------------
# Unified entry point
# ---------------------------------------------------------------------------

def analyze_package(package_name, tests_dir="/app/tests"):
    """
    Analyze a package and return extracted metadata.
    Works for both JS and Python packages.
    """
    relative_source = PACKAGE_SOURCE.get(package_name, "index.js")
    source_path = os.path.join(tests_dir, package_name, relative_source)

    if not os.path.exists(source_path):
        return {"error": f"Source not found: {source_path}", "functions": []}

    if package_name in PYTHON_PACKAGES:
        result = analyze_python(source_path)
    else:
        result = analyze_js(source_path)

    # Save metadata once per package (skip if already exists)
    snippet = format_metadata_for_prompt(result)
    if snippet:
        meta_dir = os.path.join(SCRIPT_DIR, "results", package_name)
        os.makedirs(meta_dir, exist_ok=True)
        meta_path = os.path.join(meta_dir, "metadata.txt")
        if not os.path.exists(meta_path):
            with open(meta_path, "w") as f:
                f.write(snippet)
            print(f"  [saved] {meta_path}")

    return result


def format_metadata_for_prompt(metadata):
    """
    Convert extracted metadata into a concise string to inject into the
    input generation prompt, giving the LLM structured context.
    """
    if not metadata or metadata.get("error") or not metadata.get("functions"):
        return ""

    lines = ["## Function Metadata (from static analysis)"]

    for fn in metadata["functions"]:
        lines.append(f"\n### `{fn['signature']}`")

        if fn.get("isAsync"):
            lines.append("- **async** function")
        if fn.get("returnType"):
            lines.append(f"- **returns**: `{fn['returnType']}`")

        doc = fn.get("jsDoc")
        if doc and doc.get("description"):
            lines.append(f"- **description**: {doc['description']}")

        if fn.get("params"):
            lines.append("- **params**:")
            for p in fn["params"]:
                parts = []
                if p.get("rest"):
                    parts.append("rest/variadic")
                t = p.get("inferredType")
                if t:
                    parts.append(f"type: `{t}`")
                if p.get("default") is not None:
                    parts.append(f"default: `{p['default']}`")
                if p.get("description"):
                    parts.append(p["description"].lstrip("- ").strip())
                detail = " | ".join(parts)
                lines.append(f"  - `{p['name']}`" + (f": {detail}" if detail else ""))

        if doc and doc.get("returns"):
            r = doc["returns"]
            ret_str = ""
            if r.get("type"):
                ret_str += f"`{r['type']}`"
            if r.get("description"):
                ret_str += f" — {r['description'].strip()}"
            if ret_str:
                lines.append(f"- **returns**: {ret_str}")

        if doc and doc.get("throws"):
            for t in doc["throws"]:
                lines.append(f"- **throws** `{t.get('type','?')}`: {t.get('description','')}")

        if doc and doc.get("examples"):
            lines.append("- **examples**:")
            for ex in doc["examples"]:
                lines.append(f"  ```\n  {ex.strip()}\n  ```")



    return "\n".join(lines)


# ---------------------------------------------------------------------------
# CLI  (python3 pipeline/static_analysis.py <package_name>)
# ---------------------------------------------------------------------------
if __name__ == "__main__":
    import sys
    pkg = sys.argv[1] if len(sys.argv) > 1 else "is-number"
    tests = sys.argv[2] if len(sys.argv) > 2 else "/app/tests"

    meta = analyze_package(pkg, tests)
    print("=== RAW METADATA ===")
    print(json.dumps(meta, indent=2))
    print("\n=== PROMPT SNIPPET ===")
    print(format_metadata_for_prompt(meta))
