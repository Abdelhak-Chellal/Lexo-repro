import os
import re
from openai import OpenAI
from dotenv import load_dotenv

load_dotenv()

client = OpenAI(
    base_url="https://openrouter.ai/api/v1",
    api_key=os.getenv("OPENROUTER_API_KEY"),
)

PYTHON_PACKAGES = ["primality"]

def format_io_pairs(io_pairs):
    formatted = []
    for p in io_pairs:
        args = ", ".join(repr(a) for a in p["input"])
        if p["error"]:
            formatted.append(f"f({args}) => throws {p['error']}")
        else:
            formatted.append(f"f({args}) = {repr(p['output'])}")
    return "\n".join(formatted)

def io_pairs_to_algorithm(io_pairs, model):
    io_str = format_io_pairs(io_pairs)

    prompt = """Given this test suite of a function, design an algorithm that describes the function.

1) Understand the Test Suite: Familiarize yourself with the requirements, inputs, outputs, and any implicit criteria in the test cases.
2) Analyze the Problem: Define the problem based on the test suite, understanding applicable concepts and complexity constraints.
3) Design the Algorithm: Develop a step-by-step approach, selecting suitable algorithms and ensuring coverage of test case scenarios.
4) Handle Edge Cases: Identify and address any edge cases not explicitly covered in the test suite.

I/O Pairs:
""" + io_str

    response = client.chat.completions.create(
        model=model,
        messages=[{"role": "user", "content": prompt}],
        temperature=0.7,
        max_tokens=2000,
        timeout=60,
    )
    return response.choices[0].message.content.strip()

def algorithm_to_code_js(io_pairs, algorithm, package_name, model):
    io_str = format_io_pairs(io_pairs)

    prompt = """Generate a function given a set of input-output examples.

1) Understanding Test Specifications: Before writing code, thoroughly understand what each test in the suite is checking.
2) Functional Correctness: Ensure your code meets the functional requirements outlined in the tests. It should correctly handle all specified cases, including edge cases.
3) Code Quality: Write clean, readable, and well-structured code. Use descriptive variable names, avoid hard-coding, and follow best practices.
4) Context: You might need to understand the context of the function, such as the purpose of the component it belongs to, to write the function correctly.
5) Refactoring: After your code passes the tests, look for opportunities to refactor.

Library Name: """ + package_name + """
I/O Pairs:
""" + io_str + """
Algorithm:
""" + algorithm + """

Output ONLY a valid JavaScript module using module.exports = function(...) { ... }
Do not include any explanation, just the code."""

    response = client.chat.completions.create(
        model=model,
        messages=[{"role": "user", "content": prompt}],
        temperature=0.7,
        max_tokens=2000,
        timeout=60,
    )
    return response.choices[0].message.content.strip()

def algorithm_to_code_py(io_pairs, algorithm, package_name, model):
    io_str = format_io_pairs(io_pairs)

    prompt = """Generate a Python function given a set of input-output examples.

1) Understanding Test Specifications: Before writing code, thoroughly understand what each test in the suite is checking.
2) Functional Correctness: Ensure your code meets the functional requirements outlined in the tests.
3) Code Quality: Write clean, readable, and well-structured code.
4) Context: The function is part of the """ + package_name + """ Python package.
5) Refactoring: After your code passes the tests, look for opportunities to refactor.

Library Name: """ + package_name + """
I/O Pairs:
""" + io_str + """
Algorithm:
""" + algorithm + """

Output ONLY a valid Python function named is_prime(p).
Include necessary imports at the top.
Do not include any explanation, just the code."""

    response = client.chat.completions.create(
        model=model,
        messages=[{"role": "user", "content": prompt}],
        temperature=0.7,
        max_tokens=2000,
        timeout=60,
    )
    return response.choices[0].message.content.strip()

def extract_code(raw, lang="js"):
    if lang == "py":
        raw = re.sub(r'```python', '', raw)
    else:
        raw = re.sub(r'```javascript', '', raw)
        raw = re.sub(r'```js', '', raw)
    raw = re.sub(r'```', '', raw)
    return raw.strip()

def regenerate(package_name, io_pairs, model):
    is_python = package_name in PYTHON_PACKAGES
    lang = "py" if is_python else "js"

    print(f"  Generating algorithm for {package_name}...")
    algorithm = io_pairs_to_algorithm(io_pairs, model)

    print(f"  Generating code for {package_name}...")
    if is_python:
        raw_code = algorithm_to_code_py(io_pairs, algorithm, package_name, model)
    else:
        raw_code = algorithm_to_code_js(io_pairs, algorithm, package_name, model)

    code = extract_code(raw_code, lang=lang)
    return code, algorithm

if __name__ == "__main__":
    from input_gen import generate_io_pairs

    print("\n=== primality ===")
    io_pairs, source = generate_io_pairs("primality", "openai/gpt-4o-mini")
    code, algorithm = regenerate("primality", io_pairs, "openai/gpt-4o-mini")
    print("=== GENERATED CODE ===")
    print(code)

def regenerate_primality(all_io_pairs, model):
    all_code = []
    all_code.append("import random")
    all_code.append("import math")
    all_code.append("")

    for func_name, io_pairs in all_io_pairs.items():
        print(f"  Regenerating {func_name}...")
        try:
            io_pairs_limited = io_pairs[:15]
            algorithm = io_pairs_to_algorithm(io_pairs_limited, model)
            prompt = (
                "Generate a Python function given a set of input-output examples.\n\n"
                "CRITICAL RULES:\n"
                "- The function MUST be named exactly: " + func_name + "\n"
                "- Do NOT rename it to f() or anything else\n"
                "- Do NOT redefine is_prime inside the function, assume it exists\n"
                "- Output ONLY the single function, no imports, no explanation\n\n"
                "I/O Pairs:\n" + format_io_pairs(io_pairs_limited) + "\n\n"
                "Algorithm:\n" + algorithm + "\n\n"
                "Output the function named " + func_name + " only:"
            )

            response = client.chat.completions.create(
                model=model,
                messages=[{"role": "user", "content": prompt}],
                temperature=0.7,
                max_tokens=2000,
            )
            code = extract_code(response.choices[0].message.content.strip(), lang="py")
            all_code.append(code)
            all_code.append("")
        except Exception as e:
            print(f"  Warning: {func_name} regeneration failed: {e}")

    # add rand_prime as a simple wrapper since it uses randomness
    all_code.append("""def rand_prime(m, n, strategy=None):
    import random
    primes = between(m, n)
    if not primes:
        return -1
    return random.choice(primes)
""")

    return "\n".join(all_code)
