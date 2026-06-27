import sys
import os
import time
import csv
import requests
from datetime import datetime

sys.path.append(os.path.join(os.path.dirname(__file__), '..', 'backend'))

from dotenv import load_dotenv
load_dotenv(os.path.join(os.path.dirname(__file__), '..', '.env'))

from db.models import SessionLocal, TrainingData, create_tables
from data.cf_api import get_user_submissions, get_user_rating_history
from feature_extractor import (
    compute_features_at_time,
    get_rating_at_future_date
)


# ── Configuration ─────────────────────────────────

BASE_URL = "https://codeforces.com/api"

TARGET_USERS       = 3000
SNAPSHOTS_PER_USER = 5
MIN_CONTESTS       = 10

SLEEP_BETWEEN_USERS    = 2.0
SLEEP_BETWEEN_REQUESTS = 1.0

PROGRESS_FILE = "data_collection/progress.txt"
OUTPUT_CSV    = "data_collection/training_data.csv"


# ── Step 1: Get Handles via user.ratedList ─────────

def get_handles_from_rated_list(target_count=3000):
    """
    Primary handle collection method.

    user.ratedList returns ALL active rated CF users.
    This is better than contest.standings because:
    - No API restrictions
    - Covers all rating levels automatically
    - Always returns fresh, valid handles
    - Huge pool (50,000+ users)

    We sample strategically across rating brackets
    to ensure diverse training data.
    """
    print("Fetching active rated users from Codeforces...")
    print("(This may take 10-15 seconds, it's a large list)")
    print()

    try:
        res = requests.get(
            f"{BASE_URL}/user.ratedList",
            params={
                "activeOnly":     True,
                "includeRetired": False
            },
            timeout=60
        )
        data = res.json()

        if data['status'] != 'OK':
            print(f"❌ user.ratedList failed: {data.get('comment')}")
            return get_fallback_handles()

        users = data['result']
        print(f"Total active rated users: {len(users)}")
        print()

        # ── Bucket users by rating ─────────────────
        # We want balanced training data across skill levels
        # not just top 3000 users (all would be 2000+ rated)

        buckets = {
            'newbie':     [],   # < 1200
            'pupil':      [],   # 1200 - 1400
            'specialist': [],   # 1400 - 1600
            'expert':     [],   # 1600 - 1900
            'cm':         [],   # 1900 - 2100
            'master':     [],   # 2100+
        }

        for u in users:
            rating = u.get('rating', 0)
            handle = u['handle']

            if rating < 1200:
                buckets['newbie'].append(handle)
            elif rating < 1400:
                buckets['pupil'].append(handle)
            elif rating < 1600:
                buckets['specialist'].append(handle)
            elif rating < 1900:
                buckets['expert'].append(handle)
            elif rating < 2100:
                buckets['cm'].append(handle)
            else:
                buckets['master'].append(handle)

        # Print distribution
        print("Users per rating bracket:")
        for bucket, handles in buckets.items():
            print(f"  {bucket:12s}: {len(handles):6d} users")
        print()

        # ── Sample evenly from each bracket ────────
        # Target: equal representation across skill levels
        per_bucket = target_count // len(buckets)

        selected = []
        for bucket, handles in buckets.items():
            # Take min of available and target
            sample_size = min(len(handles), per_bucket)
            # Take from middle of list (not just top rated in bracket)
            step         = max(len(handles) // sample_size, 1)
            sampled      = handles[::step][:sample_size]
            selected.extend(sampled)
            print(f"  {bucket:12s}: selected {len(sampled)}")

        print()
        print(f"Total selected: {len(selected)} handles")

        # If still short of target, fill from largest buckets
        if len(selected) < target_count:
            remaining_needed = target_count - len(selected)
            all_handles      = [u['handle'] for u in users]
            selected_set     = set(selected)
            extras           = [
                h for h in all_handles
                if h not in selected_set
            ][:remaining_needed]
            selected.extend(extras)
            print(f"Added {len(extras)} extras to reach target")

        return selected[:target_count]

    except requests.exceptions.Timeout:
        print("❌ Timeout fetching rated list")
        return get_fallback_handles()
    except Exception as e:
        print(f"❌ Error: {e}")
        return get_fallback_handles()


def get_fallback_handles():
    """
    Last resort: hardcoded known CF handles covering all levels.
    These are real handles that definitely have enough history.
    """
    print("Using fallback hardcoded handles...")
    return [
        # Legendary (3000+)
        "tourist", "jiangly", "Um_nik", "Petr",
        # Master (2400+)
        "ecnerwala", "neal", "radewoosh", "ksun48",
        # International Master (2200+)
        "Benq", "maroonrk", "tmwilliamlin", "pajenegod",
        # Master (2000+)
        "hld", "duality", "feecIe6418", "maomao90",
        # Candidate Master (1900+)
        "1-gon", "uwi", "Retired_MiFaFaOvO", "MicroSofty",
        # Expert (1600+)
        "KAN", "_overrated_", "Neko_nyaa", "nishkarsh",
        # Specialist (1400+)
        "demoralizer", "Retired_MiFaFaOvO", "arbitary", "Vercingetorix",
        # Pupil (1200+)
        "nlogn_fan", "o_logn", "oliVAR", "Applejack-pony",
    ]


# ── Step 2: Progress Tracking ─────────────────────

def load_progress():
    """Load already-processed handles to enable resuming."""
    if not os.path.exists(PROGRESS_FILE):
        return set()
    with open(PROGRESS_FILE, 'r') as f:
        return set(line.strip() for line in f if line.strip())


def save_progress(handle):
    """Mark a handle as done."""
    with open(PROGRESS_FILE, 'a') as f:
        f.write(handle + '\n')


# ── Step 3: Process One User ───────────────────────

def process_user(handle, submissions, rating_history):
    """
    Take multiple snapshots from a user's history.
    Each snapshot = one training row.
    """
    rows       = []
    n_contests = len(rating_history)

    if n_contests < MIN_CONTESTS:
        return rows

    # Sample snapshot points evenly across history
    # Skip first 5 (too little data) and last 10 (need room for labels)
    start = 5
    end   = max(n_contests - 10, start + 1)

    if end <= start:
        return rows

    step             = max((end - start) // SNAPSHOTS_PER_USER, 1)
    snapshot_indices = list(range(start, end, step))[:SNAPSHOTS_PER_USER]

    for idx in snapshot_indices:
        contest   = rating_history[idx]
        cutoff_ts = contest['ratingUpdateTimeSeconds']

        # Compute features using only data up to cutoff
        features = compute_features_at_time(
            submissions,
            rating_history,
            cutoff_ts
        )

        if not features:
            continue

        # Get ground truth labels (actual future ratings)
        label_3m = get_rating_at_future_date(
            rating_history, cutoff_ts, months_ahead=3
        )
        label_6m = get_rating_at_future_date(
            rating_history, cutoff_ts, months_ahead=6
        )

        # Skip if 3-month label doesn't exist
        if label_3m is None:
            continue

        snapshot_date = datetime.fromtimestamp(cutoff_ts).date()

        rows.append({
            'handle':              handle,
            'snapshot_date':       snapshot_date,
            'current_rating':      features['current_rating'],
            'solve_rate_per_week': features['solve_rate_per_week'],
            'tag_diversity':       features['tag_diversity'],
            'avg_problem_rating':  features['avg_problem_rating'],
            'contest_frequency':   features['contest_frequency'],
            'consistency_score':   features['consistency_score'],
            'weak_tag_count':      features['weak_tag_count'],
            'rating_volatility':   features['rating_volatility'],
            'recent_performance':  features['recent_performance'],
            'total_ac_count':      features['total_ac_count'],
            'label_3m':            label_3m,
            'label_6m':            label_6m if label_6m else label_3m
        })

    return rows


# ── Step 4: Save Data ──────────────────────────────

def save_rows_to_db(rows):
    """Save training rows to PostgreSQL."""
    if not rows:
        return

    db = SessionLocal()
    try:
        for row in rows:
            entry = TrainingData(
                handle              = row['handle'],
                snapshot_date       = row['snapshot_date'],
                current_rating      = row['current_rating'],
                solve_rate_per_week = row['solve_rate_per_week'],
                tag_diversity       = row['tag_diversity'],
                avg_problem_rating  = row['avg_problem_rating'],
                contest_frequency   = row['contest_frequency'],
                consistency_score   = row['consistency_score'],
                weak_tag_count      = row['weak_tag_count'],
                label_3m            = row['label_3m'],
                label_6m            = row['label_6m']
            )
            db.add(entry)
        db.commit()
    except Exception as e:
        db.rollback()
        print(f"    DB error: {e}")
    finally:
        db.close()


def save_rows_to_csv(rows, csv_path, write_header=False):
    """Append training rows to CSV."""
    if not rows:
        return

    fieldnames = [
        'handle', 'snapshot_date', 'current_rating',
        'solve_rate_per_week', 'tag_diversity',
        'avg_problem_rating', 'contest_frequency',
        'consistency_score', 'weak_tag_count',
        'rating_volatility', 'recent_performance',
        'total_ac_count', 'label_3m', 'label_6m'
    ]

    mode = 'w' if write_header else 'a'
    with open(csv_path, mode, newline='') as f:
        writer = csv.DictWriter(f, fieldnames=fieldnames)
        if write_header:
            writer.writeheader()
        writer.writerows(rows)


# ── Step 5: Test Mode ──────────────────────────────

def run_test(n_users=10):
    """
    Test with 10 users to verify the full pipeline works.
    """
    print("=" * 60)
    print("CP Coach — Data Collection TEST MODE")
    print("=" * 60)
    print()

    create_tables()

    # Get handles using new method
    all_handles  = get_handles_from_rated_list(target_count=100)
    test_handles = all_handles[:n_users]

    if not test_handles:
        test_handles = get_fallback_handles()[:n_users]

    print(f"Testing with: {test_handles}")
    print()

    rows_collected = 0
    csv_path       = "data_collection/test_data.csv"

    for i, handle in enumerate(test_handles):
        print(f"[{i+1}/{len(test_handles)}] {handle}")

        try:
            subs    = get_user_submissions(handle)
            history = get_user_rating_history(handle)

            print(f"    Fetched: {len(subs)} submissions, "
                  f"{len(history)} contests")

            if len(history) < MIN_CONTESTS:
                print(f"    ⚠️  Only {len(history)} contests, "
                      f"need {MIN_CONTESTS}. Skipping.")
                time.sleep(SLEEP_BETWEEN_USERS)
                continue

            rows = process_user(handle, subs, history)

            if rows:
                save_rows_to_db(rows)
                save_rows_to_csv(
                    rows,
                    csv_path,
                    write_header=(rows_collected == 0)
                )
                rows_collected += len(rows)

                print(f"    ✅ {len(rows)} snapshots saved")
                print(f"    Sample row:")
                print(f"      rating={rows[0]['current_rating']} "
                      f"→ 3m={rows[0]['label_3m']} "
                      f"→ 6m={rows[0]['label_6m']}")
            else:
                print(f"    ⚠️  No valid snapshots")

            time.sleep(SLEEP_BETWEEN_USERS)

        except Exception as e:
            print(f"    ❌ Error: {e}")
            import traceback
            traceback.print_exc()
            time.sleep(SLEEP_BETWEEN_USERS)
            continue

    print()
    print("=" * 60)
    print(f"TEST COMPLETE")
    print(f"Handles tried:  {len(test_handles)}")
    print(f"Rows collected: {rows_collected}")

    if rows_collected > 0:
        print(f"CSV saved:      {csv_path}")
        print()

        # Quick preview of collected data
        import csv as csv_module
        with open(csv_path, 'r') as f:
            reader     = csv_module.DictReader(f)
            all_rows   = list(reader)
            print(f"Preview of collected data ({len(all_rows)} rows):")
            print(f"{'handle':<20} {'rating':>6} {'label_3m':>8} {'label_6m':>8}")
            print("-" * 45)
            for row in all_rows[:10]:
                print(f"{row['handle']:<20} "
                      f"{row['current_rating']:>6} "
                      f"{row['label_3m']:>8} "
                      f"{row['label_6m']:>8}")

        print()
        print("✅ Pipeline working correctly!")
        print("Run full collection with:")
        print("   python data_collection/collect_users.py --mode full")
    else:
        print()
        print("❌ No rows collected. Check errors above.")
    print("=" * 60)


# ── Step 6: Full Collection Mode ───────────────────

def run_collection():
    """
    Full overnight collection. Collects 3000+ users.
    Resumable if interrupted.
    """
    print("=" * 60)
    print("CP Coach — Training Data Collection (FULL MODE)")
    print("=" * 60)
    print()

    create_tables()

    # Get all handles using rated list
    handles      = get_handles_from_rated_list(TARGET_USERS)
    done_handles = load_progress()
    remaining    = [h for h in handles if h not in done_handles]

    print(f"Target handles:    {len(handles)}")
    print(f"Already processed: {len(done_handles)}")
    print(f"Remaining:         {len(remaining)}")
    print()

    if not remaining:
        print("All handles already processed!")
        print("Delete progress.txt to restart.")
        return

    csv_needs_header = not os.path.exists(OUTPUT_CSV)
    total_rows       = 0
    start_time       = time.time()

    for i, handle in enumerate(remaining):
        # ETA calculation
        elapsed = time.time() - start_time
        rate    = (i + 1) / max(elapsed / 60, 0.01)
        eta     = (len(remaining) - i - 1) / max(rate, 0.01)

        print(
            f"[{i+1:4d}/{len(remaining)}] "
            f"{handle:<25s} "
            f"| ETA: {eta:.0f}min "
            f"| Rows: {total_rows}"
        )

        try:
            subs    = get_user_submissions(handle)
            history = get_user_rating_history(handle)
            rows    = process_user(handle, subs, history)

            if rows:
                save_rows_to_db(rows)
                save_rows_to_csv(
                    rows, OUTPUT_CSV,
                    write_header=csv_needs_header
                )
                csv_needs_header = False
                total_rows      += len(rows)
                print(f"  → ✅ {len(rows)} snapshots | "
                      f"rating={rows[0]['current_rating']} "
                      f"→ {rows[0]['label_3m']}")
            else:
                print(f"  → ⚠️  Skipped (not enough history)")

            save_progress(handle)
            time.sleep(SLEEP_BETWEEN_USERS)

        except KeyboardInterrupt:
            print()
            print("Interrupted by user. Progress saved.")
            print(f"Collected {total_rows} rows so far.")
            print("Re-run to continue from where you left off.")
            break

        except Exception as e:
            print(f"  → ❌ Error: {e}")
            save_progress(handle)
            time.sleep(SLEEP_BETWEEN_USERS)
            continue

    elapsed_total = (time.time() - start_time) / 60
    print()
    print("=" * 60)
    print("COLLECTION COMPLETE")
    print(f"Total rows: {total_rows}")
    print(f"Time taken: {elapsed_total:.1f} minutes")
    print(f"CSV:        {OUTPUT_CSV}")
    print("=" * 60)


# ── Entry Point ────────────────────────────────────

if __name__ == "__main__":
    import argparse

    parser = argparse.ArgumentParser(
        description='CP Coach Training Data Collector'
    )
    parser.add_argument(
        '--mode',
        choices=['test', 'full'],
        default='test',
        help='test = 10 users to verify, full = overnight collection'
    )
    args = parser.parse_args()

    if args.mode == 'test':
        run_test(n_users=10)
    else:
        run_collection()