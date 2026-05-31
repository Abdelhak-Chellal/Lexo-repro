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

# 3. Run the experiment
docker run --network host --env-file .env \
  -v $(pwd)/pipeline:/app/pipeline \
  -v $(pwd)/tests:/app/tests \
  -v $(pwd)/results:/app/results \
  lexo-repro python3 pipeline/main.py
```

Results are saved to `results/results.json` and figures to `results/figure3_*.png`.
The experiment resumes automatically if interrupted.

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
| `main.py` | Runs all packages × models, saves results, generates figures |

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
   - On LLM JSON parse failure (e.g., `JSON.parse()` or `json.loads()` fails):
     - Retry up to 3 times
     - Temperature: 0.7 → 0.3 on second attempt
     - Enhanced prompt with `CRITICAL:` block and exact formatting rules
   - Track retry count; mark as failed if all 3 retries exhaust

3. **Verification** (`verify.py`)
   - **I/O pair check:** Write regenerated code to temp file `{source}_lexo_tmp{ext}`, load via require/importlib, run each I/O pair, compare `JSON.stringify(output)` or `==` equality
   - Count mismatches; return `(passed, total)` tuple
   - **Developer tests check:** 
     - Back up original source file
     - Overwrite with regenerated code
     - Run test command from config: `npx mocha test.js` (JS) or `python3 -m pytest tests/` (Python)
     - Parse test output with `parse_test_output(output)` — supports mocha, pytest, TAP formats via regex
     - Restore original file
     - Return `(passed, total, test_output_log)`

4. **Aggregation** (`main.py`)
   - Iterate all (package, model) combinations
   - For each pair, call `regenerate()` → `verify()` pipeline
   - Save full results to JSON with keys: `{model, package, io_pairs_passed, io_pairs_total, dev_tests_passed, dev_tests_total}`
   - Generate Plotly bar chart (Figure 3): x-axis = packages, y-axis = % dev tests passed, color = % I/O pairs passed

**Technical notes:**
- **Function arguments serialization:** `concat-map`, `just-filter-object` take functions as args. Serialize as JSON strings: `[[1,2,3], "function(x) { return x*2; }"]`, eval at runtime.
- **Retry trigger:** Only JSON parse failure triggers retry. Functional failures (wrong output) do not retry.
- **Temp file cleanup:** All temp files (`_lexo_tmp`) are deleted after verification, even on error.
- **Python hardcoding:** Python verification expects `is_prime()` function name (see `verify.py` line 84); package config specifies which functions to regenerate.

## Models

All accessed via [OpenRouter](https://openrouter.ai).

| Model | OpenRouter ID | Paper equivalent | Avg Dev Tests |
|-------|--------------|-----------------|---------------|
| GPT-5.4 mini | openai/gpt-5.4-mini | GPT-5 mini (paper) | 80.1% |
| Owl Alpha | openrouter/owl-alpha | — (added) | 52.0% |
| DeepSeek V4 Flash | deepseek/deepseek-v4-flash | — (added) | 49.5% |
| GPT-4o mini | openai/gpt-4o-mini | GPT-4o (substituted, cost) | 41.3% |
| Claude 3.5 Haiku | anthropic/claude-3.5-haiku | — (added) | 38.7% |
| GPT-3.5 Turbo | openai/gpt-3.5-turbo | GPT-3.5 (paper) | 32.2% |
| Mistral 7B | mistralai/mistral-7b-instruct-v0.1 | Mistral 7B (paper) | 11.9% |

Note: `openai/gpt-5-mini` returned empty responses via OpenRouter — substituted with `openai/gpt-5.4-mini`.

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
- For primality: function must be named exactly as specified (LLMs tend to rename to `f()`)

### Input format
Paper uses JS expression syntax (`[x => x + 1]`). We use JSON arrays of arrays (`[[1], [0], [-1]]`) — Python cannot parse JS expressions. Same goal, different serialization.

### Function arguments
`concat-map` and `just-filter-object` take functions as arguments (not JSON-serializable). Serialized as strings, eval'd at runtime:
[[1,2,3], "function(x) { return x * 2; }"]

### Retry logic
Paper: up to 3 retries with coverage guidance. Ours: up to 3 retries on JSON parse failure with stricter prompt. No coverage measurement.

### Multi-language
Paper: JS, Python, Ruby, C++. This reproduction: JS and Python only.