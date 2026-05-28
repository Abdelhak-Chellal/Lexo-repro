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
| character-count | C++ | The C++ addon (using NAN library) fails to compile on Node.js v20 due to V8 API breaking changes (AccessorSignature removed, ToString() now returns MaybeLocal). Downgrading Node would break other packages. Worth noting: the paper states LEXO interacts with packages in a black-box manner via I/O pairs — meaning LEXO itself does not need to understand or compile the C++ code. The blocker is purely infrastructure: we cannot load the compiled .node binary without a successful build. |

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
- Maximum 30 inputs — to avoid context length issues with large packages. The paper uses a coverage-based iteration loop (up to 3 rounds) which naturally limits inputs; we do not implement this loop.
- For function arguments, represent them as JSON strings — needed for concat-map and just-filter-object which take function arguments; we serialize them as strings and eval() them at runtime
- Language-specific notes — added py vs js distinction since the paper only targets JS in Appendix A but we also handle Python

### Input format — justified deviation from paper
The paper's Appendix A says "Output one object per line with language primitives as values" and uses JavaScript expression syntax like [x => x + 1]. This format is not JSON-serializable and cannot be parsed by Python.

We changed to a JSON array of arrays format: [[1], [0], [-1], ["hello"], [null]]. This achieves the same goal — the LLM generates inputs, we run them against the original package to collect real outputs — but via a format that both Python and Node.js can reliably exchange.

Importantly, we tell the LLM to output ONLY inputs, not expected outputs. This matches the paper's intent: the paper's prompt asks the LLM to generate inputs, then the system runs them against the original package to collect the real outputs. The LLM never predicts outputs — it only suggests what inputs to try. Our implementation is faithful to this design.

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

## Observations from the Experiment

### Non-determinism of LLMs
One of the most striking findings is that the same prompt on the same package can succeed with one model and fail with another, or even fail and succeed on different runs of the same model. For example:
- `is-number` succeeded with GPT-5.4 mini (100% dev tests) but failed with GPT-4o mini (JSON parse error)
- `concat-map` passed all dev tests (100%) despite only 16% of I/O pairs matching — the LLM correctly inferred the function behavior from partial examples
- `has-proto` generated correct I/O pairs (100%) but dev tests showed 0/0 — a test runner configuration issue

This non-determinism makes it very hard to build a reliable pipeline. The paper addresses this with a revision loop (up to 3 retries), which we did not implement in the first run. Our retry experiment will show how much this improves results.

### "Could not find valid JSON array in response"
This was the most common error across weaker models. The LLM either:
- Returns a Python-style list instead of JSON (True/False/None instead of true/false/null)
- Adds explanatory text around the JSON that our parser cannot find
- Returns a truncated response due to context length limits
- Returns a completely different format (prose explanation instead of JSON)

This highlights a fundamental challenge: the paper assumes the LLM always follows the output format specification. In practice, especially with smaller or older models, this assumption breaks frequently. A production implementation would need much more robust output parsing, possibly using structured outputs or constrained decoding.

### Model quality directly impacts pipeline reliability
Results without retry:
- GPT-5.4 mini: 10/13 at 100%, 1 error, avg 82.7%
- GPT-4o mini: 1/13 at 100%, 7 errors, avg 35.4%
- GPT-3.5 Turbo: 1/13 at 100%, 8 errors, avg 19.0%
- Claude 3.5 Haiku: 1/13 at 100%, 10 errors, avg 15.7%
- Mistral 7B: 0/13 at 100%, 11 errors, avg 5.3%

The trend perfectly matches Figure 3 of the paper: better models produce better regenerations. Weaker models fail not just at code generation but at the earlier input generation stage — they cannot reliably produce valid JSON.

### args.map is not a function (GPT-3.5, Mistral)
Some weaker models generate inputs that are not arrays — they return a flat list instead of a list of lists. For example `[1, 2, 3]` instead of `[[1], [2], [3]]`. This causes a Node.js runtime error when we try to spread the arguments.

### Manual engineering per package type
The paper presents LEXO as fully automatic, but our reproduction shows that significant manual engineering was needed per package type:
- Function arguments required special handling (eval-based deserialization)
- Python packages needed a separate sub-pipeline
- has-proto needed a specific test command (npx mocha test/)
- primality needed input size limits per function to avoid timeouts
- concat-map and just-filter-object needed function-as-string serialization

This suggests the paper's claim of "language and domain agnostic" regeneration holds conceptually but requires non-trivial engineering effort in practice.
