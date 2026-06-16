# LEXO Reproduction — Figure 3

Reproduction of Figure 3 from:
**"Lexo: Eliminating Stealthy Supply-Chain Attacks via LLM-Assisted Program Regeneration"**
(Lamprou et al., 2025 — https://arxiv.org/pdf/2510.14522)

## How to Run

```bash
# 1. Build the container
docker build --network host -t lexo-repro .

# 2. Set your OpenRouter API key
echo "OPENROUTER_API_KEY=your_key_here" > .env

# 3. Run the baseline experiment
docker run --network host --env-file .env \
  -v $(pwd)/pipeline:/app/pipeline \
  -v $(pwd)/tests:/app/tests \
  -v $(pwd)/results:/app/results \
  lexo-repro python3 pipeline/main.py

# 4. Run enriched v1 (signatures + JSDoc)
docker run --network host --env-file .env \
  -v $(pwd)/pipeline:/app/pipeline \
  -v $(pwd)/tests:/app/tests \
  -v $(pwd)/results:/app/results \
  lexo-repro python3 pipeline/main_enriched.py

# 5. Run enriched v2 (v1 + function body slice)
docker run --network host --env-file .env \
  -v $(pwd)/pipeline:/app/pipeline \
  -v $(pwd)/tests:/app/tests \
  -v $(pwd)/results:/app/results \
  lexo-repro python3 pipeline/main_enriched_v2.py
```

Results are saved to `results/results.json`, `results/results_enriched.json`, `results/results_enriched_v2.json`.
Figures are saved to `results/figure3_*.png`. All experiments resume automatically if interrupted.

## Understanding the Metrics

**I/O pairs passed** = Does the regenerated code produce the same outputs as the original on the LLM-generated test inputs?

**Developer tests passed** = Does the regenerated code pass the original package's full test suite?

Developer tests are the real goal. I/O pairs are a proxy used during regeneration.

## Pipeline

| File | Role |
|------|------|
| `input_gen.py` | Reads source code, asks LLM to generate inputs, runs them against original package, records I/O pairs |
| `regenerate.py` | Takes I/O pairs, asks LLM for algorithm description, then generates new clean code |
| `verify.py` | Checks regenerated code against I/O pairs and original developer tests |
| `main.py` | Baseline: runs all packages × models, saves results, generates figures |
| `extract_signatures.js` | Statically analyses JS source files via AST, extracts signatures and JSDoc |
| `static_analysis.py` | Unified wrapper: calls JS extractor or Python `ast` module, formats metadata for prompt injection |
| `main_enriched.py` | Enriched v1: same as `main.py` with static analysis metadata injected into input generation prompt |
| `main_enriched_v2.py` | Enriched v2: same as v1 with additional function body slice injected |

### Pipeline in Detail

For each (package, model) pair, the workflow is:

1. **Input Generation** (`input_gen.py`)
   - Extract source code from package path (e.g., `is-number/index.js`, `primality/primality.py`)
   - Call LLM with `generate_inputs(source_code, model)` to produce JSON array of input arrays (max 30 inputs)
   - Example prompt output for `is-number`: `[[1], ["hello"], [null], [true], [NaN], [Infinity], [[]]]`
   - Execute each input: `require(package)(input)` for JS, or Python equivalent
   - Capture return value or exception: `{input: [...], output: X, error: null}` or `{input: [...], output: null, error: "TypeError"}`
   - Store all I/O pairs to JSON file for regeneration stage

2. **Regeneration** (`regenerate.py`)
   - Format I/O pairs as readable lines: `f(1) = true`, `f("hello") = false`, `f(x,y) => throws TypeError`
   - Call `io_pairs_to_algorithm(io_pairs, model)` → LLM outputs natural language algorithm
   - Call `algorithm_to_code_js/py(io_pairs, algorithm, model)` → LLM outputs module.exports or Python function
   - Extract code: `extract_code(raw, lang)` removes markdown backticks and whitespace
   - On LLM JSON parse failure:
     - Retry up to 3 times with stricter prompt and lower temperature (0.3)
   - Track retry count; mark as failed if all retries exhaust

3. **Verification** (`verify.py`)
   - **I/O pair check:** Write regenerated code to temp file, load via require/importlib, run each I/O pair, compare output
   - **Developer tests check:** Overwrite source with regenerated code, run test suite, parse output (mocha/pytest/TAP), restore original
   - Return `(passed, total, test_output_log)`

4. **Aggregation** (`main.py`)
   - Iterate all (package, model) combinations
   - Save full results to JSON; generate bar charts (Figure 3)

**Technical notes:**
- **Function arguments serialization:** `concat-map`, `just-filter-object` take functions as args. Serialized as JSON strings, eval'd at runtime.
- **Retry trigger:** Only JSON parse failure triggers retry. Functional failures do not retry.
- **Temp file cleanup:** All temp files (`_lexo_tmp`) deleted after verification, even on error.
- **Python hardcoding:** Verification expects `is_prime()` function name; package config specifies which functions to regenerate.

## Models

All accessed via [OpenRouter](https://openrouter.ai).

Note: The baseline used `mistralai/mistral-7b-instruct-v0.1`, which became unavailable on OpenRouter during the enriched experiments. It was replaced with `mistralai/mistral-nemo` for v1 and v2. Baseline Mistral results are therefore not directly comparable.

| Model | OpenRouter ID | Baseline avg | V1 avg | V2 avg |
|-------|--------------|-------------|--------|--------|
| GPT-5.4 mini | openai/gpt-5.4-mini | 86.8% | 99.5% | 94.1% |
| GPT-4o mini | openai/gpt-4o-mini | 59.7% | 62.6% | 72.6% |
| GPT-3.5 Turbo | openai/gpt-3.5-turbo | 52.2% | 50.4% | 47.2% |
| Mistral Nemo | mistralai/mistral-nemo | 38.5%* | 31.7% | 23.0% |
| Claude 3.5 Haiku | anthropic/claude-3.5-haiku | 83.8% | 85.6% | 79.2% |
| Owl Alpha | openrouter/owl-alpha | 84.5% | 70.2% | 66.9% |
| DeepSeek v4 Flash | deepseek/deepseek-v4-flash | 80.5% | 88.8% | 84.4% |

\* Baseline Mistral used `mistral-7b-instruct-v0.1`, not Nemo.

## Packages (13/15 from Table 2)

| Package | Language | Notes |
|---------|----------|-------|
| is-number | JavaScript | Full |
| arr-diff | JavaScript | Full |
| is-odd | JavaScript | Full |
| is-even | JavaScript | Full |
| is-object | JavaScript | Full |
| left-pad | JavaScript | Full |
| concat-map | JavaScript | Function args serialized as strings |
| replace-ext | JavaScript | Full |
| array-ify | JavaScript | Full |
| just-pick | JavaScript | Full |
| just-filter-object | JavaScript | Function args serialized as strings |
| has-proto | JavaScript | Uses `npx tape test/*.js` |
| primality | Python | 6 of 7 functions regenerated |

**Dropped:**
- `fast_blank` (Ruby) — C extension compilation fails, bundler version conflicts
- `character-count` (C++) — NAN library incompatible with Node.js v20 V8 API
- `split-on-first` (JavaScript) — ESM incompatible with CommonJS pipeline

## Deviations from the Paper

### Prompts
Used exact prompts from Appendix A, plus:
- `STRICT RULES` block — LLMs frequently return `NaN`, `undefined`, `True/False`, or bare function literals instead of valid JSON
- Maximum 30 inputs — paper uses coverage-based iteration (not implemented)
- On retry: stricter JSON reminder + lower temperature (0.3 vs 0.7)
- For primality: function must be named exactly as specified

### Input format
Paper uses JS expression syntax (`[x => x + 1]`). We use JSON arrays of arrays (`[[1], [0], [-1]]`) — Python cannot parse JS expressions.

### Function arguments
`concat-map` and `just-filter-object` take functions as arguments. Serialized as strings, eval'd at runtime:
[[1,2,3], "function(x) { return x * 2; }"]

### Retry logic
Paper: up to 3 retries with coverage guidance. Ours: up to 3 retries on JSON parse failure with stricter prompt.

### Multi-language
Paper: JS, Python, Ruby, C++. This reproduction: JS and Python only.

---

## Extension: Static Analysis Enrichment

### Motivation

During the baseline experiment, some packages were regenerated trivially without implementing real logic. The clearest example was `has-proto`, regenerated by multiple models as:

```js
module.exports = function () { return true; };
```

This passed all developer tests because the LLM-generated I/O pairs contained only positive cases — the model overfit the examples. The root cause: the input generation prompt receives only raw source code, with no structured semantic context about the function.

### What We Added

**`extract_signatures.js`** — parses JS source files using the [acorn](https://github.com/acornjs/acorn) AST parser and extracts function name, parameter list with defaults and inferred types, and JSDoc annotations (`@param`, `@returns`, `@throws`, `@example`).

**`static_analysis.py`** — unified wrapper calling the JS extractor for JS packages and Python's `ast` module for Python packages. Exposes `analyze_package()` and `format_metadata_for_prompt()` which formats the metadata into a structured snippet injected into the `generate_inputs()` prompt. Falls back silently if analysis fails. Saves extracted metadata to `pipeline/results/<package>/metadata.txt` for inspection.

### Enrichment V1 — Signatures and Documentation

The first enrichment injected function signatures, parameter types, and JSDoc/docstrings into the prompt.

For packages with rich documentation (e.g. `just-pick`, `primality`), this produced useful context:
Function Metadata (from static analysis)
pick(obj, select)

description: pick(obj, ['a', 'c']); // {a: 3, c: 9}

pick(obj, 'a', 'c');    // {a: 3, c: 9}
params:

obj
select




For undocumented packages (e.g. `is-number`, `has-proto`), the metadata was minimal — only parameter names, no semantic context:
Function Metadata (from static analysis)
exports(num)

params:

num




This motivated a second enrichment iteration.

### Enrichment V2 — Adding Function Body

V2 added the first 15 lines of the function body to the metadata snippet. For packages whose logic lives outside the exported function (like `has-proto`, which uses an IIFE to pre-compute a result), the full module-level context is included instead:
hasProto()

body:

var test = { proto: null, foo: {} };

var result = { proto: test }.foo === test.foo

&& !(test instanceof Object);

module.exports = function hasProto() {

// --- function body ---

return result;

};


### Results

| Model | Baseline | V1 | V2 | V1 Δ | V2 Δ |
|-------|----------|----|----|-------|-------|
| GPT-5.4 mini | 86.8% | 99.5% | 94.1% | +12.7% | +7.3% |
| GPT-4o mini | 59.7% | 62.6% | 72.6% | +2.9% | +12.9% |
| GPT-3.5 Turbo | 52.2% | 50.4% | 47.2% | -1.8% | -5.0% |
| Mistral Nemo | 38.5% | 31.7% | 23.0% | -6.8% | -15.5% |
| Claude 3.5 Haiku | 83.8% | 85.6% | 79.2% | +1.8% | -4.6% |
| Owl Alpha | 84.5% | 70.2% | 66.9% | -14.3% | -17.6% |
| DeepSeek v4 Flash | 80.5% | 88.8% | 84.4% | +8.3% | +3.9% |

### Analysis

V1 consistently improves stronger models (GPT-5.4 mini +12.7%, DeepSeek +8.3%) where JSDoc or docstrings were available — most notably `primality`, where GPT-4o mini improved from 0% to 77.8% and Claude Haiku from 55.6% to 77.8%. Weaker models (Owl Alpha, Mistral Nemo) regressed, likely because the added prompt length increased JSON parse failure rates.

V2 produced mixed results. GPT-4o mini improved further (+12.9% total), with `left-pad` going from 28.6% to 100% and `concat-map` from 60% to 100% — cases where seeing the implementation helped. However, error counts increased for Owl Alpha (2→6) and DeepSeek (6→9), suggesting the body slice adds noise for models already near their context handling limit.

**Recommendation:** V1 is the more robust improvement. V2 benefits are model-dependent and come at the cost of increased prompt complexity.
