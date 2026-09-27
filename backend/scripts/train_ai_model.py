"""Generate synthetic data (if missing) and train the AI model."""
import sys
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parent.parent
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

from ai_engine.data.generator import generate_dataset, save_dataset  # noqa: E402
from ai_engine.training.train import train                            # noqa: E402

if __name__ == "__main__":
    data_path = PROJECT_ROOT / "ai_engine" / "data" / "raw" / "events.csv"
    data_path.parent.mkdir(parents=True, exist_ok=True)

    if not data_path.exists():
        print("Generating synthetic dataset…")
        df = generate_dataset(n_users=30, n_events=3000, anomaly_fraction=0.08, seed=42)
        save_dataset(df, str(data_path))
        print(f"Wrote {len(df)} events to {data_path}")

    print("Training Isolation Forest…")
    train(dataset_path=str(data_path))
    print("Done. Model saved to models/anomaly_model.joblib")