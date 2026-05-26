import os
import json
import subprocess
import re

PACKAGE_CONFIG = {
    "is-number":          {"source": "index.js",                         "test_cmd": "npx mocha test.js",                    "lang": "js"},
    "arr-diff":           {"source": "index.js",                         "test_cmd": "npx mocha test.js",                    "lang": "js"},
    "is-odd":             {"source": "index.js",                         "test_cmd": "npx mocha test.js",                    "lang": "js"},
    "is-even":            {"source": "index.js",                         "test_cmd": "npx mocha test.js",                    "lang": "js"},
    "is-object":          {"source": "index.js",                         "test_cmd": "npx mocha test.js",                    "lang": "js"},
    "left-pad":           {"source": "index.js",                         "test_cmd": "node test.js",                         "lang": "js"},
    "concat-map":         {"source": "index.js",                         "test_cmd": "npx tape test/map.js",                 "lang": "js"},
    "replace-ext":        {"source": "index.js",                         "test_cmd": "npx mocha test/main.js",               "lang": "js"},
    "array-ify":          {"source": "index.js",                         "test_cmd": "npx mocha test.js",                    "lang": "js"},
    "has-proto":          {"source": "index.js",                         "test_cmd": "npx mocha",                            "lang": "js"},
    "just-pick":          {"source": "packages/object-pick/index.cjs",   "test_cmd": "npx tape test/object-pick/index.cjs",  "lang": "js"},
    "just-filter-object": {"source": "packages/object-filter/index.cjs", "test_cmd": "npx tape test/object-filter/index.cjs","lang": "js"},
    "primality":          {"source": "primality/primality.py",            "test_cmd": "python3 -m pytest tests/ -v",          "lang": "py"},
}

def get_tmp_path(source_path):
    base, ext = os.path.splitext(source_path)
    return base + "_lexo_tmp" + ext

def verify_io_pairs_js(package_name, generated_code, io_pairs, tests_dir):
    package_path = os.path.join(tests_dir, package_name)
    config = PACKAGE_CONFIG[package_name]
    source_path = os.path.join(package_path, config["source"])
    tmp_path = get_tmp_path(source_path)
    tmp_require = "./" + os.path.relpath(tmp_path, package_path)

    with open(tmp_path, "w") as f:
        f.write(generated_code)

    js_code = f"""
const fn = require('{tmp_require}');
const pairs = {json.dumps(io_pairs)};
let passed = 0;
for (const p of pairs) {{
    try {{
        const output = fn(...p.input);
        if (JSON.stringify(output) === JSON.stringify(p.output)) {{
            passed++;
        }}
    }} catch(e) {{
        if (p.error !== null) passed++;
    }}
}}
console.log(JSON.stringify({{ passed, total: pairs.length }}));
"""

    result = subprocess.run(
        ["node", "-e", js_code],
        capture_output=True, text=True, cwd=package_path
    )
    os.remove(tmp_path)

    if result.returncode != 0:
        raise Exception(f"Node error: {result.stderr}")

    data = json.loads(result.stdout)
    return data["passed"], data["total"]

def verify_io_pairs_py(package_name, generated_code, io_pairs, tests_dir):
    package_path = os.path.join(tests_dir, package_name)
    config = PACKAGE_CONFIG[package_name]
    source_path = os.path.join(package_path, config["source"])
    tmp_path = get_tmp_path(source_path)

    with open(tmp_path, "w") as f:
        f.write(generated_code)

    with open('/tmp/lexo_verify_pairs.json', 'w') as f:
        json.dump(io_pairs, f)

    runner = """
import json, sys, importlib.util
sys.path.insert(0, '""" + package_path + """')

spec = importlib.util.spec_from_file_location("tmp_mod", '""" + tmp_path + """')
mod = importlib.util.module_from_spec(spec)
spec.loader.exec_module(mod)
fn = mod.is_prime

with open('/tmp/lexo_verify_pairs.json') as f:
    pairs = json.load(f)

passed = 0
for p in pairs:
    try:
        output = fn(*p['input'])
        if output == p['output']:
            passed += 1
    except Exception:
        if p['error'] is not None:
            passed += 1
print(json.dumps({"passed": passed, "total": len(pairs)}))
"""

    with open('/tmp/lexo_verify_runner.py', 'w') as f:
        f.write(runner)

    result = subprocess.run(
        ["python3", "/tmp/lexo_verify_runner.py"],
        capture_output=True, text=True, cwd=package_path
    )
    os.remove(tmp_path)

    if result.returncode != 0:
        raise Exception(f"Python error: {result.stderr}")

    data = json.loads(result.stdout)
    return data["passed"], data["total"]

def verify_io_pairs(package_name, generated_code, io_pairs, tests_dir="/app/tests"):
    config = PACKAGE_CONFIG[package_name]
    if config["lang"] == "py":
        return verify_io_pairs_py(package_name, generated_code, io_pairs, tests_dir)
    return verify_io_pairs_js(package_name, generated_code, io_pairs, tests_dir)

def parse_test_output(output):
    # mocha
    passing = re.search(r'(\d+) passing', output)
    failing = re.search(r'(\d+) failing', output)
    if passing:
        passed = int(passing.group(1))
        failed = int(failing.group(1)) if failing else 0
        return passed, passed + failed

    # pytest
    pytest_pass = re.search(r'(\d+) passed', output)
    pytest_fail = re.search(r'(\d+) failed', output)
    if pytest_pass:
        passed = int(pytest_pass.group(1))
        failed = int(pytest_fail.group(1)) if pytest_fail else 0
        return passed, passed + failed

    # TAP: "# pass X"
    tap_pass = re.search(r'#\s*pass\s+(\d+)', output)
    tap_fail = re.search(r'#\s*fail\s+(\d+)', output)
    if tap_pass:
        passed = int(tap_pass.group(1))
        failed = int(tap_fail.group(1)) if tap_fail else 0
        return passed, passed + failed

    # TAP fallback
    ok_lines = re.findall(r'^ok \d+', output, re.MULTILINE)
    not_ok_lines = re.findall(r'^not ok \d+', output, re.MULTILINE)
    if ok_lines or not_ok_lines:
        return len(ok_lines), len(ok_lines) + len(not_ok_lines)

    return 0, 0

def verify_developer_tests_js(package_name, generated_code, tests_dir):
    package_path = os.path.join(tests_dir, package_name)
    config = PACKAGE_CONFIG[package_name]
    source_path = os.path.join(package_path, config["source"])

    with open(source_path) as f:
        original = f.read()
    with open(source_path, "w") as f:
        f.write(generated_code)

    subprocess.run(
        ["npm", "install", "--silent"],
        capture_output=True, text=True, cwd=package_path
    )

    result = subprocess.run(
        config["test_cmd"].split(),
        capture_output=True, text=True, cwd=package_path
    )

    with open(source_path, "w") as f:
        f.write(original)

    output = result.stdout + result.stderr
    passed, total = parse_test_output(output)
    return passed, total, output

def verify_developer_tests_py(package_name, generated_code, tests_dir):
    package_path = os.path.join(tests_dir, package_name)
    config = PACKAGE_CONFIG[package_name]
    source_path = os.path.join(package_path, config["source"])

    with open(source_path) as f:
        original = f.read()
    with open(source_path, "w") as f:
        f.write(generated_code)

    subprocess.run(
        ["pip3", "install", "-e", ".", "--break-system-packages", "-q"],
        capture_output=True, text=True, cwd=package_path
    )

    result = subprocess.run(
        config["test_cmd"].split(),
        capture_output=True, text=True, cwd=package_path
    )

    with open(source_path, "w") as f:
        f.write(original)

    output = result.stdout + result.stderr
    passed, total = parse_test_output(output)
    return passed, total, output

def verify_developer_tests(package_name, generated_code, tests_dir="/app/tests"):
    config = PACKAGE_CONFIG[package_name]
    if config["lang"] == "py":
        return verify_developer_tests_py(package_name, generated_code, tests_dir)
    return verify_developer_tests_js(package_name, generated_code, tests_dir)
