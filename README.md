# LEXO Reproduction — Figure 3

Partial reproduction of the paper:
**"Lexo: Eliminating Stealthy Supply-Chain Attacks via LLM-Assisted Program Regeneration"**
(Lamprou et al., 2025 — https://arxiv.org/pdf/2510.14522)

## Objective

Reproduce Figure 3 of the paper, which shows LEXO's regeneration correctness across multiple packages and LLM models. Each bar represents a package, the y-axis shows % of developer tests passed by the regenerated code, and the shading shows % of I/O pairs passed.

---

## What We Reproduced

We implemented the LEXO pipeline from scratch based on the paper:

1. **Input generation** — LLM generates test inputs from source code
2. **I/O pair collection** — inputs run against original package, outputs recorded
3. **Algorithm inference** — LLM describes the function in natural language from I/O pairs
4. **Code regeneration** — LLM regenerates clean code from I/O pairs + algorithm
5. **Verification** — regenerated code verified against I/O pairs and developer tests

### Models used
- `openai/gpt-4o-mini` (strong model)
- `mistralai/mistral-7b-instruct-v0.1` (weak model)

### Packages evaluated (12 total)
From Table 2 of the paper:

| Package | Language | Domain |
|---------|----------|--------|
| is-number | JavaScript | Is |
| arr-diff | JavaScript | Array |
| is-odd | JavaScript | Math |
| is-even | JavaScript | Math |
| is-object | JavaScript | Is |
| left-pad | JavaScript | String |
| concat-map | JavaScript | Collection |
| replace-ext | JavaScript | String |
| array-ify | JavaScript | Array |
| just-pick | JavaScript | Object |
| just-filter-object | JavaScript | Object |
| primality | Python | Math |

---

## Packages Dropped and Why

| Package | Reason |
|---------|--------|
| `split-on-first` | ESM module format incompatible with CommonJS pipeline |
| `has-proto` | TypeScript compilation errors in test dependencies |
| `fast_blank` | Requires C extension compilation (`fast_blank.so`) |
| `character-count` | C++ native Node.js addon, requires `node-gyp` build |

These represent genuine infrastructure limitations documented for transparency.

---

## Engineering Challenges

### 1. Function arguments in I/O pairs
Packages like `concat-map` and `just-filter-object` take function arguments, which aren't JSON-serializable. We solved this by representing functions as strings and using `eval()` at runtime — consistent with the paper's mention of "function-like constructs" in inputs.

### 2. Multi-language support
The paper evaluates Python (`primality`), Ruby (`fast_blank`), and C++ (`character-count`) packages. We implemented a Python sub-pipeline for `primality`. Ruby and C++ were dropped due to native compilation complexity.

### 3. Multiple test formats
Packages use different test frameworks: Mocha, TAP (tape), and pytest. We implemented a unified parser for all three.

### 4. LLM output robustness
LLMs frequently return non-JSON values (`NaN`, `undefined`, `None`, `True`, bare function literals). We implemented a cleaning pipeline to normalize these.

### 5. Node.js ESM vs CommonJS
Node 18 couldn't run `split-on-first` (ESM). Upgrading to Node 20 fixed most ESM issues.

---

## Project Structure
lexo-repro/
├── Dockerfile              # Ubuntu 24 + Node 20 + Python 3 + Ruby
├── docker-compose.yml
├── requirements.txt
├── .env                    # OPENROUTER_API_KEY (not committed)
├── pipeline/
│   ├── input_gen.py        # Stage 1: generate inputs, collect I/O pairs
│   ├── regenerate.py       # Stage 2: infer algorithm, regenerate code
│   ├── verify.py           # Stage 3: verify against I/O pairs and dev tests
│   └── main.py             # Orchestrator: runs all packages × models, plots Figure 3
├── tests/                  # Cloned package repos with developer test suites
├── packages/               # Installed npm packages
└── results/                # Output: results.json + figure3.png

---

## How to Run

```bash
# Build
docker build --network host -t lexo-repro .

# Run full experiment
docker run --network host --env-file .env \
  -v $(pwd)/pipeline:/app/pipeline \
  -v $(pwd)/tests:/app/tests \
  -v $(pwd)/results:/app/results \
  lexo-repro python3 pipeline/main.py
```

Results saved to `results/results.json` and `results/figure3.png`.

---

## Limitations vs Original Paper

- **Subset of packages**: 12/147 packages from the paper
- **2 models** instead of 4 (no GPT-3.5, no GPT-5 mini)
- **No revision loop**: paper retries up to 3 times on failure; we do single-shot
- **primality**: only `is_prime` function regenerated, not all 7 functions
- **No code coverage measurement**: paper uses `nyc` to measure and improve coverage iteratively
- **No sandboxing**: paper runs original packages in isolated environments; we run directly

