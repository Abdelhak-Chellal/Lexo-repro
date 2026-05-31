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
   - Read the original source code
   - Prompt LLM to generate up to 30 test inputs that cover the function's behavior
   - Execute each input against the original package
   - Collect and store the results as I/O pairs (input → output, or input → error)

2. **Regeneration** (`regenerate.py`)
   - Take the I/O pairs from step 1
   - Prompt LLM to describe the algorithm based on the I/O pairs
   - Prompt LLM to write clean, correct code implementing that algorithm
   - If JSON parsing fails, retry up to 3 times with:
     - Stricter JSON format reminders
     - Lower temperature (0.3 vs 0.7) for more deterministic output
     - Modified prompt to catch common LLM mistakes (`NaN`, `undefined`, `True/False`, bare functions)

3. **Verification** (`verify.py`)
   - **I/O pair check:** Run the regenerated code against all I/O pairs from step 1; count how many produce the same output
   - **Developer tests check:** Replace the original source file with regenerated code, run the full test suite (mocha, pytest, or TAP), restore the original file, count passing tests
   - Save pass/fail metrics

4. **Aggregation** (`main.py`)
   - Run steps 1–3 for all packages × models
   - Save detailed results to JSON
   - Generate Figure 3 visualization (model vs. success rate)

**Note on retries:** JSON parse failures trigger retries within `regenerate.py`. The retry limit is per (package, model) pair — if all retries fail, that pair is marked as failed.

**Special case — primality (Python):** The function signature is `is_prime(n)` (hardcoded in verify.py), so the regenerated code must preserve this exact name. Other packages are more flexible with return types and error handling.

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