import os
import json
import subprocess
import re
from openai import OpenAI
from dotenv import load_dotenv

load_dotenv()

client = OpenAI(
    base_url="https://openrouter.ai/api/v1",
    api_key=os.getenv("OPENROUTER_API_KEY"),
)

PACKAGE_SOURCE = {
    "just-pick":          "packages/object-pick/index.cjs",
    "just-filter-object": "packages/object-filter/index.cjs",
    "primality":          "primality/primality.py",
}

FUNCTION_ARG_PACKAGES = ["concat-map", "just-filter-object"]
PYTHON_PACKAGES = ["primality"]

def get_source(package_name, tests_dir="/app/tests"):
    relative = PACKAGE_SOURCE.get(package_name, "index.js")
    path = os.path.join(tests_dir, package_name, relative)
    if os.path.exists(path):
        with open(path) as f:
            return f.read()
    return None

def generate_inputs(source_code, model, use_function_strings=False, lang="js"):
    if use_function_strings:
        function_note = """- For function arguments, you MUST represent them as JSON strings
- CORRECT:   ["function(x) { return x * 2; }"]
- INCORRECT: [function(x) { return x * 2; }]"""
    else:
        function_note = "- Do NOT use functions, undefined, NaN, Infinity or any JS expression"

    if lang == "py":
        example = "Example for f(n): [[2], [3], [0], [-1], [17], [100]]"
        lang_note = "The function is written in Python."
    else:
        example = 'Example for f(x, y): [[1, 2], [0, 0], [-1, 5], ["hello", "world"], [null, true]]'
        lang_note = "The function is written in JavaScript."

    prompt = f"""Given a component, generate an input test suite that will test thoroughly the component's behavior. These input/output pairs will then be used to regenerate the module. Make sure to include all edge cases and key behaviors.

1) Code Understanding: Explain the code's purpose and functionality. Identify key behaviors that require testing.
2) Inputs and Outputs: Brainstorm concise tests that are not repetitive for input/output correctness, including key behaviors as well as edge cases. Make sure to test default arguments and optional parameters.
3) Errors: Incorporate test cases triggering errors or exceptions for inputs where the provided module throws errors.
4) Explore: Include tests that are slight variations of the ones in the test suite. Modify the inputs slightly to test the function's behavior with different inputs.
5) Format: Wrap all argument objects in an array. Keep the list concise — maximum 30 inputs.

STRICT RULES for the final JSON:
- Output ONLY a JSON array of arrays, each inner array contains ONLY the INPUT arguments
- Use only valid JSON values: numbers, strings, booleans, null, arrays, objects
{function_note}
- Do NOT add comments
- Do NOT include expected outputs
- {lang_note}
- Maximum 30 inputs total

{example}

Code: {source_code}"""

    response = client.chat.completions.create(
        model=model,
        messages=[{"role": "user", "content": prompt}],
        temperature=0.7,
        max_tokens=2000,
    )
    return response.choices[0].message.content.strip()

def clean_json(raw):
    raw = raw.replace("```json", "").replace("```", "").strip()
    raw = re.sub(r'//[^\n]*', '', raw)
    raw = re.sub(r'/\*.*?\*/', '', raw, flags=re.DOTALL)
    raw = re.sub(r'Number\.MAX_VALUE', '1.7976931348623157e+308', raw)
    raw = re.sub(r'Number\.MIN_VALUE', '5e-324', raw)
    raw = re.sub(r'Number\.POSITIVE_INFINITY', 'null', raw)
    raw = re.sub(r'Number\.NEGATIVE_INFINITY', 'null', raw)
    raw = re.sub(r'Number\.NaN', 'null', raw)
    raw = re.sub(r'Math\.\w+', 'null', raw)
    raw = re.sub(r'-?NaN', 'null', raw)
    raw = re.sub(r'-?Infinity', 'null', raw)
    raw = re.sub(r'\bundefined\b', 'null', raw)
    raw = re.sub(r'\bNone\b', 'null', raw)
    raw = re.sub(r'\bTrue\b', 'true', raw)
    raw = re.sub(r'\bFalse\b', 'false', raw)
    raw = re.sub(r'-null', 'null', raw)
    raw = re.sub(r',\s*([}\]])', r'\1', raw)
    return raw

def serialize_bare_functions(raw):
    result = []
    i = 0
    while i < len(raw):
        if raw[i:i+8] == 'function' and (i == 0 or raw[i-1] not in ('"', "'")):
            start = i
            depth = 0
            j = i
            found = False
            while j < len(raw):
                if raw[j] == '{':
                    depth += 1
                elif raw[j] == '}':
                    depth -= 1
                    if depth == 0:
                        fn_str = raw[start:j+1]
                        fn_str = fn_str.replace('"', '\\"')
                        result.append('"' + fn_str + '"')
                        i = j + 1
                        found = True
                        break
                j += 1
            if found:
                continue
        result.append(raw[i])
        i += 1
    return ''.join(result)

def extract_json_array(raw):
    try:
        parsed = json.loads(raw.strip())
        if isinstance(parsed, list) and len(parsed) > 0:
            return parsed
    except json.JSONDecodeError:
        pass

    start = raw.find('[')
    if start == -1:
        raise Exception("No array found in response")

    depth = 0
    for i, ch in enumerate(raw[start:], start):
        if ch == '[':
            depth += 1
        elif ch == ']':
            depth -= 1
            if depth == 0:
                candidate = raw[start:i+1]
                try:
                    parsed = json.loads(candidate)
                    if isinstance(parsed, list) and len(parsed) > 0:
                        return parsed
                except json.JSONDecodeError:
                    pass

    raise Exception("Could not find valid JSON array in response")

def run_inputs_on_package_js(package_name, inputs, tests_dir):
    package_path = os.path.join(tests_dir, package_name)
    source_relative = PACKAGE_SOURCE.get(package_name, "index.js")
    require_path = "./" + source_relative if "/" in source_relative else "."
    use_fn_strings = package_name in FUNCTION_ARG_PACKAGES

    inputs_json = json.dumps(inputs)

    if use_fn_strings:
        eval_logic = """
        function deserializeArg(arg) {
            if (typeof arg === 'string' && arg.trim().startsWith('function')) {
                try { return eval('(' + arg + ')'); } catch(e) { return arg; }
            }
            return arg;
        }
        const deserializedInputs = inputs.map(args => args.map(deserializeArg));
        """
        run_var = "deserializedInputs"
    else:
        eval_logic = ""
        run_var = "inputs"

    js_code = f"""
const fn = require('{require_path}');
const inputs = {inputs_json};
{eval_logic}
const results = [];
for (const args of {run_var}) {{
    try {{
        const output = fn(...args);
        results.push({{ input: args.map(a => typeof a === 'function' ? a.toString() : a), output: output, error: null }});
    }} catch (e) {{
        results.push({{ input: args.map(a => typeof a === 'function' ? a.toString() : a), output: null, error: e.message }});
    }}
}}
console.log(JSON.stringify(results));
"""

    result = subprocess.run(
        ["node", "-e", js_code],
        capture_output=True, text=True, cwd=package_path
    )

    if result.returncode != 0:
        raise Exception(f"Node error: {result.stderr}")

    return json.loads(result.stdout)

def run_inputs_on_package_py(package_name, inputs, tests_dir):
    package_path = os.path.join(tests_dir, package_name)

    with open('/tmp/lexo_inputs.json', 'w') as f:
        json.dump(inputs, f)

    runner = f"""
import json, sys
sys.path.insert(0, '{package_path}')
from primality import primality
fn = primality.is_prime

with open('/tmp/lexo_inputs.json') as f:
    inputs = json.load(f)

results = []
for args in inputs:
    try:
        output = fn(*args)
        results.append({{"input": args, "output": output, "error": None}})
    except Exception as e:
        results.append({{"input": args, "output": None, "error": str(e)}})
print(json.dumps(results))
"""

    with open('/tmp/lexo_runner.py', 'w') as f:
        f.write(runner)

    result = subprocess.run(
        ["python3", "/tmp/lexo_runner.py"],
        capture_output=True, text=True, cwd=package_path
    )

    if result.returncode != 0:
        raise Exception(f"Python error: {result.stderr}")

    return json.loads(result.stdout)

def extract_python_function(source, func_name):
    lines = source.split('\n')
    result = []
    in_func = False
    for line in lines:
        if line.startswith(f'def {func_name}('):
            in_func = True
        elif in_func and line.startswith('def ') and not line.startswith(f'def {func_name}('):
            break
        if in_func:
            result.append(line)
    return '\n'.join(result)

def generate_io_pairs(package_name, model, tests_dir="/app/tests"):
    print(f"  Reading source for {package_name}...")
    source = get_source(package_name, tests_dir)
    if not source:
        raise Exception(f"No source found for {package_name}")

    is_python = package_name in PYTHON_PACKAGES
    use_fn_strings = package_name in FUNCTION_ARG_PACKAGES
    lang = "py" if is_python else "js"

    if package_name == "primality":
        source = extract_python_function(source, "is_prime")

    print(f"  Generating inputs with {model}...")
    raw = generate_inputs(source, model, use_function_strings=use_fn_strings, lang=lang)
    cleaned = clean_json(raw)
    if use_fn_strings:
        cleaned = serialize_bare_functions(cleaned)

    inputs = extract_json_array(cleaned)

    print(f"  Running {len(inputs)} inputs on original package...")
    if is_python:
        io_pairs = run_inputs_on_package_py(package_name, inputs, tests_dir)
    else:
        io_pairs = run_inputs_on_package_js(package_name, inputs, tests_dir)

    print(f"  Got {len(io_pairs)} I/O pairs")
    return io_pairs, source

if __name__ == "__main__":
    print("\n=== primality ===")
    pairs, source = generate_io_pairs("primality", "openai/gpt-4o-mini")
    for p in pairs[:5]:
        print(p)

PRIMALITY_FUNCTIONS = ["is_prime", "nth_prime", "prange", "between", "next_prime", "prev_prime"]

def generate_io_pairs_primality(model, tests_dir="/app/tests"):
    package_path = os.path.join(tests_dir, "primality")
    source_path = os.path.join(package_path, "primality/primality.py")
    with open(source_path) as f:
        full_source = f.read()

    all_io_pairs = {}
    for func_name in PRIMALITY_FUNCTIONS:
        print(f"  Generating inputs for {func_name}...")
        func_source = extract_python_function(full_source, func_name)
        try:
            raw = generate_inputs(func_source, model, lang="py")
            cleaned = clean_json(raw)
            inputs = extract_json_array(cleaned)

            with open('/tmp/lexo_inputs.json', 'w') as f:
                json.dump(inputs, f)

            runner = f"""
import json, sys
sys.path.insert(0, '{package_path}')
from primality import primality
fn = getattr(primality, '{func_name}')

with open('/tmp/lexo_inputs.json') as f:
    inputs = json.load(f)

results = []
for args in inputs:
    try:
        output = fn(*args)
        results.append({{"input": args, "output": output, "error": None}})
    except Exception as e:
        results.append({{"input": args, "output": None, "error": str(e)}})
print(json.dumps(results))
"""
            with open('/tmp/lexo_runner.py', 'w') as f:
                f.write(runner)

            result = subprocess.run(
                ["python3", "/tmp/lexo_runner.py"],
                capture_output=True, text=True, cwd=package_path
            )

            if result.returncode != 0:
                print(f"  Warning: {func_name} failed: {result.stderr[:100]}")
                continue

            io_pairs = json.loads(result.stdout)
            all_io_pairs[func_name] = io_pairs
            print(f"  Got {len(io_pairs)} I/O pairs for {func_name}")
        except Exception as e:
            print(f"  Warning: {func_name} skipped: {e}")

    return all_io_pairs, full_source
