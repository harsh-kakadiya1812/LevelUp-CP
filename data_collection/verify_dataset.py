import sys
import os
sys.path.append(os.path.join(os.path.dirname(__file__), '..', 'backend'))

import pandas as pd
import numpy as np
from db.models import SessionLocal, TrainingData


def load_dataset_from_db():
    """Load all training data from database."""
    db = SessionLocal()
    try:
        rows = db.query(TrainingData).all()
        data = []
        for r in rows:
            data.append({
                'handle':              r.handle,
                'snapshot_date':       r.snapshot_date,
                'current_rating':      r.current_rating,
                'solve_rate_per_week': r.solve_rate_per_week,
                'tag_diversity':       r.tag_diversity,
                'avg_problem_rating':  r.avg_problem_rating,
                'contest_frequency':   r.contest_frequency,
                'consistency_score':   r.consistency_score,
                'weak_tag_count':      r.weak_tag_count,
                'label_3m':            r.label_3m,
                'label_6m':            r.label_6m
            })
        return pd.DataFrame(data)
    finally:
        db.close()


def verify_dataset(df):
    """
    Run quality checks on the collected dataset.
    Flags problems before you waste time training on bad data.
    """
    print("=" * 60)
    print("Dataset Quality Report")
    print("=" * 60)
    print()

    # ── Basic Stats ────────────────────────────────
    print("BASIC STATS")
    print(f"  Total rows:          {len(df)}")
    print(f"  Unique handles:      {df['handle'].nunique()}")
    print(f"  Avg rows per handle: {len(df) / max(df['handle'].nunique(), 1):.1f}")
    print()

    # ── Check Minimum Requirements ─────────────────
    print("MINIMUM REQUIREMENTS")
    min_rows = 1000
    status   = "✅" if len(df) >= min_rows else "❌"
    print(f"  {status} Rows >= {min_rows}: {len(df)}")

    min_users = 300
    status    = "✅" if df['handle'].nunique() >= min_users else "❌"
    print(f"  {status} Users >= {min_users}: {df['handle'].nunique()}")

    if len(df) < min_rows:
        print()
        print("  ⚠️  Not enough data yet. Run collection longer.")
    print()

    # ── Rating Distribution ────────────────────────
    print("RATING DISTRIBUTION (current_rating)")
    bins   = [0, 800, 1200, 1400, 1600, 1900, 2100, 2400, 3500]
    labels = [
        '<800', '800-1200', '1200-1400', '1400-1600',
        '1600-1900', '1900-2100', '2100-2400', '2400+'
    ]
    df['rating_bucket'] = pd.cut(
        df['current_rating'], bins=bins, labels=labels
    )
    dist = df['rating_bucket'].value_counts().sort_index()
    for bucket, count in dist.items():
        bar = '█' * (count // max(len(df) // 50, 1))
        print(f"  {bucket:12s}: {count:5d} {bar}")
    print()

    # ── Label Distribution ─────────────────────────
    print("LABEL: Rating change (label_3m - current_rating)")
    df['rating_change_3m'] = df['label_3m'] - df['current_rating']
    print(f"  Mean change:  {df['rating_change_3m'].mean():.1f}")
    print(f"  Std dev:      {df['rating_change_3m'].std():.1f}")
    print(f"  Min change:   {df['rating_change_3m'].min():.0f}")
    print(f"  Max change:   {df['rating_change_3m'].max():.0f}")
    print()

    # ── Missing Values ─────────────────────────────
    print("MISSING VALUES")
    missing = df.isnull().sum()
    has_missing = False
    for col, count in missing.items():
        if count > 0:
            print(f"  ❌ {col}: {count} missing ({count/len(df)*100:.1f}%)")
            has_missing = True
    if not has_missing:
        print("  ✅ No missing values")
    print()

    # ── Feature Distributions ──────────────────────
    print("FEATURE DISTRIBUTIONS")
    features = [
        'solve_rate_per_week', 'tag_diversity',
        'avg_problem_rating',  'contest_frequency',
        'consistency_score',   'weak_tag_count'
    ]
    for f in features:
        if f in df.columns:
            print(
                f"  {f:25s}: "
                f"mean={df[f].mean():6.2f}  "
                f"std={df[f].std():6.2f}  "
                f"min={df[f].min():6.2f}  "
                f"max={df[f].max():6.2f}"
            )
    print()

    # ── Correlations with Label ────────────────────
    print("FEATURE CORRELATIONS with label_3m")
    print("(higher absolute value = stronger predictor)")
    for f in features:
        if f in df.columns:
            corr = df[f].corr(df['label_3m'])
            bar  = '█' * int(abs(corr) * 20)
            sign = '+' if corr > 0 else '-'
            print(f"  {f:25s}: {sign}{abs(corr):.3f}  {bar}")
    print()

    # ── Outliers Check ─────────────────────────────
    print("OUTLIER CHECK")
    outliers_rating = df[df['current_rating'] < 100]
    if len(outliers_rating) > 0:
        print(f"  ❌ {len(outliers_rating)} rows with rating < 100 (suspicious)")
    else:
        print("  ✅ No suspicious low ratings")

    outliers_label = df[df['label_3m'] < 100]
    if len(outliers_label) > 0:
        print(f"  ❌ {len(outliers_label)} rows with label_3m < 100 (suspicious)")
    else:
        print("  ✅ No suspicious labels")

    outliers_solve = df[df['solve_rate_per_week'] > 100]
    if len(outliers_solve) > 0:
        print(f"  ⚠️  {len(outliers_solve)} rows with solve_rate > 100/week (very high, verify)")
    else:
        print("  ✅ Solve rates look reasonable")

    print()
    print("=" * 60)

    # ── Final Verdict ──────────────────────────────
    if len(df) >= 1000 and df['handle'].nunique() >= 300 and not has_missing:
        print("✅ DATASET READY FOR MODEL TRAINING")
    elif len(df) >= 500:
        print("⚠️  DATASET USABLE but collect more for better model")
    else:
        print("❌ DATASET NOT READY: collect more data first")

    print()
    return df


if __name__ == "__main__":
    print("Loading dataset from database...")
    df = load_dataset_from_db()

    if len(df) == 0:
        print("No data found. Run collect_users.py first.")
    else:
        df = verify_dataset(df)

        # Also save verified dataset to CSV for model training
        output_path = "data_collection/training_data_verified.csv"
        df.to_csv(output_path, index=False)
        print(f"Verified dataset saved to: {output_path}")