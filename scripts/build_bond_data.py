"""Авторская сборка практикума; остальные снимки и главы не изменяются.

python scripts/build_bond_data.py --date 2026-09-30
Нужны moexutils, moex-analytics и доступ к DuckLake; читателям они не нужны.
"""

import argparse
import shutil
from pathlib import Path

from moex_analytics import bonds
from moex_analytics.bond_data import load_lake_dataset, save_snapshot


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--date", default="2026-09-30")
    parser.add_argument("--start", default="2024-01-01")
    args = parser.parse_args()
    root = Path(__file__).resolve().parents[1]
    dataset = load_lake_dataset(args.date, args.start)
    save_snapshot(dataset, root / "data" / "bonds")
    # Exact standalone copy: reader needs only the existing book requirements.
    shutil.copyfile(Path(bonds.__file__), root / "qf" / "bonds.py")
    print(f"Bond snapshot {args.date}: data/bonds and qf/bonds.py")


if __name__ == "__main__":
    main()
