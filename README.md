# LEXO Reproduction — Figure 3

Partial reproduction of the paper:
**"Lexo: Eliminating Stealthy Supply-Chain Attacks via LLM-Assisted Program Regeneration"**
(Lamprou et al., 2025 — https://arxiv.org/pdf/2510.14522)

## Objective

Reproduce Figure 3 of the paper, which shows LEXO regeneration correctness across packages and LLM models. Each bar represents a package, the y-axis shows percentage of developer tests passed by the regenerated code, and the shading shows percentage of I/O pairs passed.

## Models Used

| Model | OpenRouter ID | Input | Output | Context | Released |
|-------|--------------|-------|--------|---------|---------|
| GPT-5 mini | openai/gpt-5-mini | $0.25 | $2.00 | 400,000 | Aug 2025 |
| GPT-4o mini | openai/gpt-4o-mini | $0.15 | $0.60 | 128,000 | Jul 2024 |
| GPT-3.5 Turbo | openai/gpt-3.5-turbo | $0.50 | $1.50 | 16,385 | May 2023 |
| Mistral 7B | mistralai/mistral-7b-instruct-v0.1 | $0.11 | $0.19 | 4,096 | Sep 2023 |
| Claude 3.5 Haiku | anthropic/claude-3.5-haiku | $0.80 | $4.00 | 200,000 | Nov 2024 |

Note: The original paper uses GPT-5 mini, GPT-4o, GPT-3.5, and Mistral 7B. We substitute GPT-4o with GPT-4o mini due to cost, and add Claude 3.5 Haiku as a bonus model. All accessed via OpenRouter.

## Packages Evaluated (13/15)

| Package | Language | Domain | Status |
|---------|----------|--------|--------|
| is-number | JavaScript | Is | Full |
| arr-diff | JavaScript | Array | Full |
| is-odd | JavaScript | Math | Full |
| is-even | JavaScript | Math | Full |
| is-object | JavaScript | Is | Full |
| left-pad | JavaScript | String | Full |
| concat-map | JavaScript | Collection | Full |
| replace-ext | JavaScript | String | Full |
| array-ify | JavaScript | Array | Full |
| just-pick | JavaScript | Object | Full |
| just-filter-object | JavaScript | Object | Full |
| has-proto | JavaScript | Has | Full |
| primality | Python | Math | Partial (6/9 tests) |

## Packages Dropped (2/15)

| Package | Language | Reason |
|---------|----------|--------|
| fast_blank | Ruby | Requires C extension compilation (fast_blank.so). Bundler version conflicts prevented compilation inside Docker. |
| character-count | C++ | Native Node.js addon requiring node-gyp build system. Not feasible without a full C++ toolchain. |

## Other Packages Attempted but Dropped

| Package | Reason |
|---------|--------|
| split-on-first | ESM module format incompatible with our CommonJS-based pipeline |

## Prompts — What We Kept vs What We Modified

The paper provides exact prompts in Appendix A. We used them as the base but had to add several practical constraints.

### Input generation prompt — kept from paper
- 5-step structure: Code Understanding, Inputs and Outputs, Errors, Explore, Format
- Instruction to include edge cases, default arguments, error-triggering inputs

### Input generation prompt — added by us
We added a STRICT RULES section after the 5 steps to handle practical LLM output issues:
- Do not use NaN, undefined, Infinity, Number.MAX_VALUE or any JS expression — LLMs frequently output these which are not valid JSON
- Do not add comments inside the JSON — LLMs add // comments which break JSON parsing
- Maximum 30 inputs — to avoid context length issues with large packages
- For function arguments, represent them as JSON strings — needed for concat-map and just-filter-object which take function arguments; we serialize them as strings and eval() them at runtime
- Language-specific notes — added py vs js distinction since the paper only targets JS in Appendix A but we also handle Python

### Algorithm inference prompt — kept exactly from paper
No modifications. The 4-step structure (Understand, Analyze, Design, Handle Edge Cases) was used as-is.

### Code regeneration prompt — kept from paper
- 5-step structure: Understanding Test Specifications, Functional Correctness, Code Quality, Context, Refactoring
- Library Name, I/O Pairs, Algorithm inputs

### Code regeneration prompt — added by us
For primality specifically, we added CRITICAL RULES:
- Function must be named exactly X — without this, the LLM sometimes renames the function to f() or uses a generic name
- Do not redefine is_prime inside other functions — the LLM tends to copy-paste a local is_prime helper into every function

### Why we deviated
The paper assumes the LLM always returns clean parseable output. In practice, across different models and packages, LLMs return invalid JSON, Python-style booleans (True/False/None), bare JavaScript function literals, and truncated responses. Our additions were necessary engineering decisions to make the pipeline work reliably across all 5 models and 13 packages.

## Engineering Challenges and Decisions

### 1. Function arguments in I/O pairs
concat-map and just-filter-object take function arguments which are not JSON-serializable. We solved this by representing functions as strings and using eval() at runtime.

### 2. Multi-language support
The paper evaluates JS, Python, Ruby, and C++ packages. We implemented a Python sub-pipeline for primality. Ruby (fast_blank) and C++ (character-count) were dropped due to native compilation complexity inside Docker.

### 3. primality — partial reproduction
The primality package exposes 7 functions. We regenerate all 6 deterministic functions (rand_prime is added as a simple wrapper around between + random.choice). We achieve 6/9 developer tests passing. The 3 failing tests involve performance-sensitive operations where the LLM generates correct but unoptimized implementations that time out.

### 4. Multiple test frameworks
Packages use Mocha, TAP (tape), and pytest. We implemented a unified output parser for all three formats.

### 5. LLM output robustness
LLMs frequently return non-JSON values: NaN, undefined, None, True, False, bare function literals, Python-style booleans. We implemented a cleaning pipeline to normalize all of these before parsing.

### 6. Node.js ESM vs CommonJS
Upgraded from Node 18 to Node 20 to fix ESM compatibility issues. split-on-first still failed due to its test framework requiring import syntax.

### 7. Context length limits
When regenerating primality functions, I/O pairs for functions like prange exceed the context window of some models. We limit I/O pairs to 15 per function during regeneration.

### 8. Docker network configuration
API calls require --network host flag when running Docker on Mac due to Docker Desktop network isolation.

## Differences from Original Paper

| Aspect | Paper | This reproduction |
|--------|-------|------------------|
| Packages | 147 | 13 |
| Models | GPT-5 mini, GPT-4o, GPT-3.5, Mistral 7B | Same + Claude 3.5 Haiku, GPT-4o replaced by GPT-4o mini |
| Revision loop | Up to 3 retries | Single attempt |
| Code coverage | Measured with nyc, guides input generation | Not implemented |
| Sandboxing | Original packages run in isolated environment | Run directly |
| Languages | JS, Python, Ruby, C++ | JS, Python |
| Prompts | Exact prompts from Appendix A | Appendix A prompts + practical additions for JSON robustness |

## Pipeline

We implemented the LEXO pipeline from scratch based on the paper:

1. Input generation — LLM generates test inputs from source code using prompts based on Appendix A
2. I/O pair collection — inputs run against original package, outputs recorded
3. Algorithm inference — LLM describes the function in natural language from I/O pairs
4. Code regeneration — LLM regenerates clean code from I/O pairs and algorithm
5. Verification — regenerated code verified against I/O pairs and developer tests

## Project Structure

- Dockerfile — Ubuntu 24 + Node 20 + Python 3
- requirements.txt — Python dependencies
- pipeline/input_gen.py — Stage 1: generate inputs, collect I/O pairs
- pipeline/regenerate.py — Stage 2: infer algorithm, regenerate code
- pipeline/verify.py — Stage 3: verify against I/O pairs and dev tests
- pipeline/main.py — Orchestrator: runs all packages x models, plots Figure 3
- tests/ — Cloned package repos with developer test suites
- results/ — Output: results.json and figure3.png

## How to Run

Build the container:

    docker build --network host -t lexo-repro .

Run the full experiment:

    docker run --network host --env-file .env \
      -v $(pwd)/pipeline:/app/pipeline \
      -v $(pwd)/tests:/app/tests \
      -v $(pwd)/results:/app/results \
      lexo-repro python3 pipeline/main.py

Results are saved to results/results.json and results/figure3.png.
