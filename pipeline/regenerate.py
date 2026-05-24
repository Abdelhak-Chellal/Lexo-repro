import os
import re
from openai import OpenAI
from dotenv import load_dotenv

load_dotenv()

client = OpenAI(
    base_url="https://openrouter.ai/api/v1",
    api_key=os.getenv("OPENROUTER_API_KEY"),
)

def io_pairs_to_algorithm(io_pairs, model):
    # format I/O pairs as f(input) = output
    formatted = []
    for p in io_pairs:
        args = ", ".join(repr(a) for a in p["input"])
        if p["error"]:
            formatted.append(f"f({args}) => throws {p['error']}")
        else:
            formatted.append(f"f({args}) = {repr(p['output'])}")
    io_str = "\n".join(formatted)

    # prompt from LEXO paper Appendix A
    prompt = f"""Given this test suite of a function, design an algorithm that describes the function.

1) Understand the Test Suite: Familiarize yourself with the requirements, inputs, outputs, and any implicit criteria in the test cases.
2) Analyze the Problem: Define the problem based on the test suite, understanding applicable concepts and complexity constraints.
3) Design the Algorithm: Develop a step-by-step approach, selecting suitable algorithms and ensuring coverage of test case scenarios.
4) Handle Edge Cases: Identify and address any edge cases not explicitly covered in the test suite.

I/O Pairs:
{io_str}"""

    response = client.chat.completions.create(
        model=model,
        messages=[{"role": "user", "content": prompt}],
        temperature=0.7,
    )
    return response.choices[0].message.content.strip()

def algorithm_to_code(io_pairs, algorithm, package_name, model):
    # format I/O pairs as f(input) = output
    formatted = []
    for p in io_pairs:
        args = ", ".join(repr(a) for a in p["input"])
        if p["error"]:
            formatted.append(f"f({args}) => throws {p['error']}")
        else:
            formatted.append(f"f({args}) = {repr(p['output'])}")
    io_str = "\n".join(formatted)

    # prompt from LEXO paper Appendix A
    prompt = f"""Generate a function given a set of input-output examples.

1) Understanding Test Specifications: Before writing code, thoroughly understand what each test in the suite is checking. Know the input and output requirements, and what constitutes a pass or fail.
2) Functional Correctness: Ensure your code meets the functional requirements outlined in the tests. It should correctly handle all specified cases, including edge cases.
3) Code Quality: Write clean, readable, and well-structured code. Use descriptive variable names, avoid hard-coding, and follow best practices.
4) Context: You might need to understand the context of the function, such as the purpose of the component it belongs to, to write the function correctly.
5) Refactoring: After your code passes the tests, look for opportunities to refactor. Simplify complex parts, remove duplicated code, and improve the overall structure.

Library Name: {package_name}
I/O Pairs:
{io_str}
Algorithm:
{algorithm}

Output ONLY a valid JavaScript module using module.exports = function(...) {{ ... }}
Do not include any explanation, just the code."""

    response = client.chat.completions.create(
        model=model,
        messages=[{"role": "user", "content": prompt}],
        temperature=0.7,
    )
    return response.choices[0].message.content.strip()

def extract_code(raw):
    # strip markdown code blocks
    raw = re.sub(r'```javascript', '', raw)
    raw = re.sub(r'```js', '', raw)
    raw = re.sub(r'```', '', raw)
    return raw.strip()

def regenerate(package_name, io_pairs, model):
    print(f"  Generating algorithm for {package_name}...")
    algorithm = io_pairs_to_algorithm(io_pairs, model)

    print(f"  Generating code for {package_name}...")
    raw_code = algorithm_to_code(io_pairs, algorithm, package_name, model)
    code = extract_code(raw_code)

    return code, algorithm

if __name__ == "__main__":
    from input_gen import generate_io_pairs

    io_pairs, source = generate_io_pairs("is-number", "openai/gpt-4o-mini")
    code, algorithm = regenerate("is-number", io_pairs, "openai/gpt-4o-mini")

    print("=== ALGORITHM ===")
    print(algorithm)
    print("\n=== GENERATED CODE ===")
    print(code)
