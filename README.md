# LEXO Reproduction — Figure 3

Partial reproduction of the paper:
**"Lexo: Eliminating Stealthy Supply-Chain Attacks via LLM-Assisted Program Regeneration"**
(Lamprou et al., 2025 — https://arxiv.org/pdf/2510.14522)

## Objective

Reproduce Figure 3 of the paper, which shows LEXO regeneration correctness across packages and LLM models. Each bar represents a package, the y-axis shows percentage of developer tests passed by the regenerated code, and the shading shows percentage of I/O pairs passed.

## Pipeline

We implemented the LEXO pipeline from scratch based on the paper:

1. Input generation — LLM generates test inputs from source code
2. I/O pair collection — inputs run against original package, outputs recorded
3. Algorithm inference — LLM describes the function in natural language from I/O pairs
4. Code regeneration — LLM regenerates clean code from I/O pairs and algorithm
5. Verification — regenerated code verified against I/O pairs and developer tests

## Models

- openai/gpt-4o-mini (strong model)
- mistralai/mistral-7b-instruct-v0.1 (weak model)

## Packages Evaluated (12)

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

## Packages Dropped

| Package | Reason |
|---------|--------|
| split-on-first | ESM module format incompatible with CommonJS pipeline |
| has-proto | TypeScript compilation errors in test dependencies |
| fast_blank | Requires C extension compilation |
| character-count | C++ native Node.js addon requires node-gyp build |

## Engineering Challenges

**Function arguments in I/O pairs** — concat-map and just-filter-object take function arguments which are not JSON-serializable. Solved by representing functions as strings and using eval() at runtime.

**Multi-language support** — Implemented a Python sub-pipeline for primality. Ruby and C++ dropped due to native compilation complexity.

**Multiple test frameworks** — Packages use Mocha, TAP (tape), and pytest. Implemented a unified output parser for all three.

**LLM output robustness** — LLMs return non-JSON values such as NaN, undefined, None, True, and bare function literals. Implemented a cleaning pipeline to normalize these.

**Node.js ESM vs CommonJS** — Upgraded from Node 18 to Node 20 to fix ESM compatibility issues.

## Project Structure

- Dockerfile — Ubuntu 24 + Node 20 + Python 3 + Ruby
- requirements.txt — Python dependencies
- pipeline/input_gen.py — Stage 1: generate inputs, collect I/O pairs
- pipeline/regenerate.py — Stage 2: infer algorithm, regenerate code
- pipeline/verify.py — Stage 3: verify against I/O pairs and dev tests
- pipeline/main.py — Orchestrator: runs all packages x models, plots Figure 3
- setup_tests.sh — Script to clone all test package repos
- results/ — Output: results.json and figure3.png

## How to Run

Build the container:

    docker build --network host -t lexo-repro .

Clone test packages:

    bash setup_tests.sh

Run the full experiment:

    docker run --network host --env-file .env \
      -v $(pwd)/pipeline:/app/pipeline \
      -v $(pwd)/tests:/app/tests \
      -v $(pwd)/results:/app/results \
      lexo-repro python3 pipeline/main.py

Results are saved to results/results.json and results/figure3.png.

## Limitations vs Original Paper

- 12 of 147 packages evaluated
- 2 models instead of 4
- No revision loop (paper retries up to 3 times on failure)
- primality: only is_prime regenerated, not all 7 functions
- No code coverage measurement
- No sandboxing of original packages during inference
