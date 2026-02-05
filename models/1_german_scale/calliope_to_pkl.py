from __future__ import annotations

import pickle
import sys
from pathlib import Path

# Script-local configuration (edit if needed).
BASE_DIR = Path(__file__).resolve().parent
MODEL_PATH = BASE_DIR / "model.yaml"
INPUTS_PKL = BASE_DIR / "german_model_inputs.pkl"
RESULTS_PKL = BASE_DIR / "german_model_results_planning.pkl"
RESULTS_OPERATE_PKL = BASE_DIR / "german_model_results_operate.pkl"


def main() -> int:
    if not MODEL_PATH.exists():
        print(f"Model file not found: {MODEL_PATH}", file=sys.stderr)
        return 1

    try:
        import calliope  # type: ignore
    except ImportError:
        print("Calliope is not installed. Install it before running this script.", file=sys.stderr)
        return 1

    model = calliope.Model(str(MODEL_PATH))
    model.run()

    INPUTS_PKL.parent.mkdir(parents=True, exist_ok=True)
    RESULTS_PKL.parent.mkdir(parents=True, exist_ok=True)

    with open(INPUTS_PKL, "wb") as f:
        pickle.dump(model.inputs, f, protocol=pickle.HIGHEST_PROTOCOL)

    with open(RESULTS_PKL, "wb") as f:
        pickle.dump(model.results, f, protocol=pickle.HIGHEST_PROTOCOL)

    print(f"Saved inputs to: {INPUTS_PKL}")
    print(f"Saved results to: {RESULTS_PKL}")

    operate_model = calliope.Model(str(MODEL_PATH), scenario="operate_fixed")
    operate_model.run()

    with open(RESULTS_OPERATE_PKL, "wb") as f:
        pickle.dump(operate_model.results, f, protocol=pickle.HIGHEST_PROTOCOL)

    print(f"Saved operate results to: {RESULTS_OPERATE_PKL}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
