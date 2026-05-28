import os
import json
import time
import matplotlib
matplotlib.use('Agg')
import matplotlib.pyplot as plt
import numpy as np
from input_gen import generate_io_pairs, generate_io_pairs_primality, PRIMALITY_FUNCTIONS
from regenerate import regenerate, regenerate_primality
from verify import verify_io_pairs, verify_developer_tests

MODELS = [
    "openai/gpt-5.4-mini",
    "openai/gpt-4o-mini",
    "openai/gpt-3.5-turbo",
    "mistralai/mistral-7b-instruct-v0.1",
    "anthropic/claude-3.5-haiku",
]

MODEL_LABELS = {
    "openai/gpt-5.4-mini":                 "GPT-5.4 mini",
    "openai/gpt-4o-mini":                "GPT-4o mini",
    "openai/gpt-3.5-turbo":              "GPT-3.5 Turbo",
    "mistralai/mistral-7b-instruct-v0.1":"Mistral 7B",
    "anthropic/claude-3.5-haiku":        "Claude 3.5 Haiku",
}

PACKAGES = [
    "is-number",
    "arr-diff",
    "is-odd",
    "is-even",
    "is-object",
    "left-pad",
    "concat-map",
    "replace-ext",
    "array-ify",
    "just-pick",
    "just-filter-object",
    "has-proto",
    "primality",
]

TESTS_DIR = "/app/tests"
RESULTS_DIR = "/app/results"

def run_lexo(package_name, model):
    print(f"\n[{package_name}] model={model}")
    try:
        if package_name == "primality":
            all_io_pairs, source = generate_io_pairs_primality(model, TESTS_DIR)
            io_pairs = [p for pairs in all_io_pairs.values() for p in pairs]
            code = regenerate_primality(all_io_pairs, model)
        else:
            io_pairs, source = generate_io_pairs(package_name, model, TESTS_DIR, max_retries=1)
            code, algorithm = regenerate(package_name, io_pairs, model)

        passed_io, total_io = verify_io_pairs(package_name, code, io_pairs, TESTS_DIR)
        passed_dev, total_dev, _ = verify_developer_tests(package_name, code, TESTS_DIR)

        io_pct = round(100 * passed_io / total_io, 1) if total_io > 0 else 0
        dev_pct = round(100 * passed_dev / total_dev, 1) if total_dev > 0 else 0

        print(f"  I/O pairs: {passed_io}/{total_io} ({io_pct}%)")
        print(f"  Dev tests: {passed_dev}/{total_dev} ({dev_pct}%)")

        return {
            "package": package_name,
            "model": model,
            "io_passed": passed_io,
            "io_total": total_io,
            "io_pct": io_pct,
            "dev_passed": passed_dev,
            "dev_total": total_dev,
            "dev_pct": dev_pct,
            "status": "ok"
        }

    except Exception as e:
        print(f"  ERROR: {e}")
        return {
            "package": package_name,
            "model": model,
            "status": "error",
            "error": str(e),
            "io_pct": 0,
            "dev_pct": 0,
        }

def plot_results(all_results):
    fig, axes = plt.subplots(len(MODELS), 1, figsize=(14, 5 * len(MODELS)))
    if len(MODELS) == 1:
        axes = [axes]

    for ax, model in zip(axes, MODELS):
        model_results = [r for r in all_results if r["model"] == model]
        model_results.sort(key=lambda x: x["dev_pct"], reverse=True)

        packages = [r["package"] for r in model_results]
        dev_pcts = [r["dev_pct"] for r in model_results]
        io_pcts = [r["io_pct"] for r in model_results]

        x = np.arange(len(packages))
        ax.bar(x, dev_pcts, color=[
            plt.cm.RdYlGn(io / 100) for io in io_pcts
        ], edgecolor='black', linewidth=0.5)

        ax.set_xticks(x)
        ax.set_xticklabels(packages, rotation=45, ha='right', fontsize=9)
        ax.set_ylim(0, 110)
        ax.set_ylabel("Tests (%)")
        ax.set_title(f"Correctness results for LEXO using {MODEL_LABELS[model]}")
        ax.axhline(y=100, color='gray', linestyle='--', linewidth=0.5)

        sm = plt.cm.ScalarMappable(cmap='RdYlGn', norm=plt.Normalize(0, 100))
        sm.set_array([])
        cbar = plt.colorbar(sm, ax=ax)
        cbar.set_label("I/Os (%)", fontsize=8)

    plt.tight_layout()
    out_path = os.path.join(RESULTS_DIR, "figure3.png")
    plt.savefig(out_path, dpi=150)
    print(f"\nFigure saved to {out_path}")

    # also save individual figures per model
    for model in MODELS:
        fig_single, ax_single = plt.subplots(1, 1, figsize=(14, 5))
        model_results = [r for r in all_results if r["model"] == model]
        model_results.sort(key=lambda x: x["dev_pct"], reverse=True)
        packages = [r["package"] for r in model_results]
        dev_pcts = [r["dev_pct"] for r in model_results]
        io_pcts = [r["io_pct"] for r in model_results]
        x = np.arange(len(packages))
        ax_single.bar(x, dev_pcts, color=[
            plt.cm.RdYlGn(io / 100) for io in io_pcts
        ], edgecolor='black', linewidth=0.5)
        ax_single.set_xticks(x)
        ax_single.set_xticklabels(packages, rotation=45, ha='right', fontsize=9)
        ax_single.set_ylim(0, 110)
        ax_single.set_ylabel("Tests (%)")
        ax_single.set_title(f"Correctness results for LEXO using {MODEL_LABELS[model]}")
        ax_single.axhline(y=100, color='gray', linestyle='--', linewidth=0.5)
        sm = plt.cm.ScalarMappable(cmap='RdYlGn', norm=plt.Normalize(0, 100))
        sm.set_array([])
        cbar = plt.colorbar(sm, ax=ax_single)
        cbar.set_label("I/Os (%)", fontsize=8)
        plt.tight_layout()
        model_name = MODEL_LABELS[model].replace(" ", "_").replace(".", "")
        single_path = os.path.join(RESULTS_DIR, f"figure3_{model_name}.png")
        fig_single.savefig(single_path, dpi=150)
        plt.close(fig_single)
        print(f"Individual figure saved to {single_path}")

def main():
    os.makedirs(RESULTS_DIR, exist_ok=True)

    # resume from existing results if available
    results_path = os.path.join(RESULTS_DIR, "results.json")
    if os.path.exists(results_path):
        with open(results_path) as f:
            all_results = json.load(f)
        print(f"Resuming from {len(all_results)} existing results")
    else:
        all_results = []

    done = {(r["model"], r["package"]) for r in all_results}
    total = len(MODELS) * len(PACKAGES)
    completed = len(done)

    for model in MODELS:
        print(f"\n{'='*60}")
        print(f"MODEL: {MODEL_LABELS[model]}")
        print(f"{'='*60}")
        for package in PACKAGES:
            if (model, package) in done:
                print(f"  [{completed}/{total}] Skipping {package} (already done)")
                completed += 1
                continue
            print(f"\n  [{completed+1}/{total}] Starting {package} with {MODEL_LABELS[model]}...")
            start_time = time.time()
            result = run_lexo(package, model)
            elapsed = round(time.time() - start_time, 1)
            completed += 1
            status = f"{result['dev_pct']}% dev tests" if result['status'] == 'ok' else f"ERROR: {result.get('error','')[:50]}"
            print(f"  [{completed}/{total}] Done {package} in {elapsed}s — {status}")
            all_results.append(result)
            with open(results_path, "w") as f:
                json.dump(all_results, f, indent=2)
            time.sleep(1)

    print("\n=== SUMMARY ===")
    for model in MODELS:
        model_results = [r for r in all_results if r["model"] == model and r["status"] == "ok"]
        perfect = [r for r in model_results if r["dev_pct"] == 100]
        print(f"{MODEL_LABELS[model]}: {len(perfect)}/{len(PACKAGES)} packages at 100% dev tests")

    plot_results(all_results)

if __name__ == "__main__":
    main()
