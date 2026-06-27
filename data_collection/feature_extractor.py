import sys
import os
sys.path.append(os.path.join(os.path.dirname(__file__), '..', 'backend'))

from datetime import datetime, timezone
from collections import defaultdict
from ml.skill_analysis import (
    build_skill_profile,
    compute_skill_score,
    classify_skill_level
)


def compute_features_at_time(submissions, rating_history, cutoff_timestamp):
    """
    Compute all ML features using only data up to cutoff_timestamp.
    This simulates "what did we know about this user at time T?"

    Returns a dict of features, or None if not enough data.
    """

    # Filter: only use submissions before cutoff
    past_subs = [
        s for s in submissions
        if s.get('creationTimeSeconds', 0) < cutoff_timestamp
    ]

    # Filter: only contests before cutoff
    past_contests = [
        c for c in rating_history
        if c.get('ratingUpdateTimeSeconds', 0) < cutoff_timestamp
    ]

    # Need minimum data to be useful
    if len(past_subs) < 30:
        return None
    if len(past_contests) < 3:
        return None

    # ── Feature 1: Current Rating at cutoff ───────
    if not past_contests:
        return None
    current_rating = past_contests[-1]['newRating']

    # ── Feature 2: Solve Rate Per Week ────────────
    ac_subs = [s for s in past_subs if s.get('verdict') == 'OK']
    if not ac_subs:
        return None

    timestamps  = [s['creationTimeSeconds'] for s in ac_subs]
    oldest_ts   = min(timestamps)
    total_days  = (cutoff_timestamp - oldest_ts) / (60 * 60 * 24)
    total_weeks = max(total_days / 7, 1)
    solve_rate_per_week = round(len(ac_subs) / total_weeks, 2)

    # ── Feature 3: Tag Diversity ───────────────────
    # Number of distinct tags practiced
    all_tags = set()
    for sub in past_subs:
        for tag in sub.get('problem', {}).get('tags', []):
            all_tags.add(tag)
    tag_diversity = len(all_tags)

    # ── Feature 4: Avg Problem Rating Solved ──────
    solved_ratings = [
        sub['problem'].get('rating', 0)
        for sub in past_subs
        if sub.get('verdict') == 'OK'
        and sub.get('problem', {}).get('rating', 0) > 0
    ]
    if not solved_ratings:
        return None
    avg_problem_rating = round(
        sum(solved_ratings) / len(solved_ratings), 1
    )

    # ── Feature 5: Contest Frequency ──────────────
    # Contests per month over the last 3 months before cutoff
    three_months_ago = cutoff_timestamp - (90 * 24 * 60 * 60)
    recent_contests  = [
        c for c in past_contests
        if c.get('ratingUpdateTimeSeconds', 0) > three_months_ago
    ]
    contest_frequency = round(len(recent_contests) / 3, 2)

    # ── Feature 6: Consistency Score ──────────────
    daily_counts = defaultdict(int)
    for sub in past_subs:
        if sub.get('verdict') == 'OK':
            ts  = sub['creationTimeSeconds']
            day = datetime.fromtimestamp(ts).strftime('%Y-%m-%d')
            daily_counts[day] += 1

    counts = list(daily_counts.values())
    if counts:
        mean = sum(counts) / len(counts)
        if mean > 0:
            variance = sum((c - mean) ** 2 for c in counts) / len(counts)
            std_dev  = variance ** 0.5
            cv       = std_dev / mean
            consistency_score = round(1 / (1 + cv), 3)
        else:
            consistency_score = 0.0
    else:
        consistency_score = 0.0

    # ── Feature 7: Weak Tag Count ─────────────────
    # How many topics are currently weak at time T
    tag_features = compute_tag_features_at_time(past_subs)
    skill_profile = build_skill_profile(tag_features)
    weak_tag_count = skill_profile['summary']['weak']

    # ── Feature 8: Rating Volatility ──────────────
    # Std deviation of rating changes (inconsistent performer vs steady)
    if len(past_contests) >= 3:
        rating_changes = [
            c['newRating'] - c['oldRating']
            for c in past_contests[-10:]  # last 10 contests
        ]
        mean_change = sum(rating_changes) / len(rating_changes)
        variance    = sum(
            (r - mean_change) ** 2 for r in rating_changes
        ) / len(rating_changes)
        rating_volatility = round(variance ** 0.5, 1)
    else:
        rating_volatility = 0.0

    # ── Feature 9: Recent Performance ─────────────
    # Avg rating change in last 5 contests (positive = improving)
    if len(past_contests) >= 5:
        last_5_changes = [
            c['newRating'] - c['oldRating']
            for c in past_contests[-5:]
        ]
        recent_performance = round(
            sum(last_5_changes) / len(last_5_changes), 1
        )
    else:
        recent_performance = 0.0

    return {
        'current_rating':      current_rating,
        'solve_rate_per_week': solve_rate_per_week,
        'tag_diversity':       tag_diversity,
        'avg_problem_rating':  avg_problem_rating,
        'contest_frequency':   contest_frequency,
        'consistency_score':   consistency_score,
        'weak_tag_count':      weak_tag_count,
        'rating_volatility':   rating_volatility,
        'recent_performance':  recent_performance,
        'total_ac_count':      len(ac_subs)
    }


def compute_tag_features_at_time(submissions):
    """
    Compute per-tag features from a time-bounded submission list.
    Simplified version of data_processor.compute_tag_features.
    """
    tag_problems = defaultdict(
        lambda: defaultdict(lambda: {
            'verdicts': [],
            'rating':   0,
        })
    )

    sorted_subs = sorted(
        submissions,
        key=lambda x: x.get('creationTimeSeconds', 0)
    )

    for sub in sorted_subs:
        problem    = sub.get('problem', {})
        verdict    = sub.get('verdict', '')
        tags       = problem.get('tags', [])
        rating     = problem.get('rating', 0)
        contest_id = problem.get('contestId', '')
        index      = problem.get('index', '')
        problem_id = f"{contest_id}{index}"

        for tag in tags:
            p            = tag_problems[tag][problem_id]
            p['rating']  = rating
            p['verdicts'].append(verdict)

    tag_features = {}

    for tag, problems in tag_problems.items():
        total      = len(problems)
        solved     = sum(1 for p in problems.values() if 'OK' in p['verdicts'])
        solve_rate = solved / total if total > 0 else 0

        attempts_list = []
        ac_ratings    = []
        for p in problems.values():
            if 'OK' in p['verdicts']:
                first_ac = p['verdicts'].index('OK') + 1
                attempts_list.append(first_ac)
                if p['rating'] > 0:
                    ac_ratings.append(p['rating'])

        avg_attempts   = sum(attempts_list) / len(attempts_list) if attempts_list else 0
        highest_rating = max(ac_ratings) if ac_ratings else 0
        avg_rating     = sum(ac_ratings) / len(ac_ratings) if ac_ratings else 0

        if total >= 3:
            tag_features[tag] = {
                'total_attempted':  total,
                'total_solved':     solved,
                'solve_rate':       round(solve_rate, 3),
                'avg_attempts':     round(avg_attempts, 2),
                'highest_rating':   highest_rating,
                'avg_rating_solved': round(avg_rating, 1),
                'recency_days':     0,
                'contest_solve_percentage': 0,
                'first_try_ac_rate': 0,
                'recent_avg_rating': avg_rating,
                'momentum':         0
            }

    return tag_features


def get_rating_at_future_date(rating_history, cutoff_timestamp, months_ahead):
    """
    Find what a user's rating was N months after cutoff_timestamp.
    Returns None if that date hasn't happened yet or no data.
    """
    seconds_per_month = 30 * 24 * 60 * 60
    target_timestamp  = cutoff_timestamp + (months_ahead * seconds_per_month)

    # Get contests after cutoff up to target date
    future_contests = [
        c for c in rating_history
        if cutoff_timestamp < c.get('ratingUpdateTimeSeconds', 0) <= target_timestamp
    ]

    if not future_contests:
        return None

    # Return rating after the last contest in that window
    return future_contests[-1]['newRating']


# Test
if __name__ == "__main__":
    import sys
    sys.path.append('../backend')

    from data.cf_api import (
        get_user_info,
        get_user_submissions,
        get_user_rating_history
    )

    handle  = "tourist"
    subs    = get_user_submissions(handle)
    history = get_user_rating_history(handle)

    # Test snapshot at some historical point
    if len(history) >= 10:
        # Take cutoff at 10th contest
        cutoff = history[10]['ratingUpdateTimeSeconds']

        print(f"Testing snapshot at contest 10 for {handle}")
        print(f"Cutoff date: {datetime.fromtimestamp(cutoff)}")
        print()

        features = compute_features_at_time(subs, history, cutoff)
        if features:
            print("Features computed:")
            for k, v in features.items():
                print(f"  {k:25s}: {v}")

            label_3m = get_rating_at_future_date(history, cutoff, 3)
            label_6m = get_rating_at_future_date(history, cutoff, 6)
            print(f"\nLabel (3 months): {label_3m}")
            print(f"Label (6 months): {label_6m}")
        else:
            print("Not enough data at this snapshot point")