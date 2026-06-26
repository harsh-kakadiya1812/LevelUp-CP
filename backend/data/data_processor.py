from datetime import datetime, timezone
from collections import defaultdict


def process_user_profile(user_info, submissions, rating_history):
    """
    Master function: takes all raw CF data and returns
    one clean structured profile object.
    """
    tag_features    = compute_tag_features(submissions)
    solved_problems = get_solved_problem_ids(submissions)
    avg_rating      = compute_avg_solved_rating(submissions)
    weekly_rate     = compute_weekly_solve_rate(submissions)
    consistency     = compute_consistency_score(submissions)

    return {
        "handle":            user_info['handle'],
        "current_rating":    user_info.get('rating', 0),
        "max_rating":        user_info.get('maxRating', 0),
        "total_solved":      len(solved_problems),
        "solved_ids":        list(solved_problems),
        "avg_solved_rating": avg_rating,
        "weekly_solve_rate": weekly_rate,
        "consistency_score": consistency,
        "tag_features":      tag_features,
        "rating_history":    format_rating_history(rating_history),
        "contest_count":     len(rating_history)
    }


def compute_tag_features(submissions):
    """
    For every topic tag, compute 8 features that
    together give a complete picture of skill level.

    New features added:
    1. avg_rating_solved     - true comfort zone
    2. contest_solve_pct     - live contest mastery
    3. first_try_ac_rate     - precision / confidence
    4. recent_avg_rating     - momentum / recent trend
    5. momentum              - are they improving recently?
    """

    # Per tag, per problem: track all submission data
    # Structure: tag -> problem_id -> {verdicts, rating, ac_timestamps, has_contest_ac}
    tag_problems = defaultdict(
        lambda: defaultdict(lambda: {
            'verdicts':        [],
            'rating':          0,
            'ac_timestamps':   [],
            'has_contest_ac':  False
        })
    )

    # Sort oldest first (important for attempt order)
    sorted_subs = sorted(
        submissions,
        key=lambda x: x.get('creationTimeSeconds', 0)
    )

    for sub in sorted_subs:
        problem    = sub.get('problem', {})
        verdict    = sub.get('verdict', '')
        tags       = problem.get('tags', [])
        rating     = problem.get('rating', 0)
        timestamp  = sub.get('creationTimeSeconds', 0)

        # Get participant type
        # Works for both fresh CF API data and DB-reconstructed data
        author           = sub.get('author', {})
        participant_type = author.get('participantType', 'PRACTICE')
        is_contest_sub   = (participant_type == 'CONTESTANT')

        contest_id = problem.get('contestId', '')
        index      = problem.get('index', '')
        problem_id = f"{contest_id}{index}"

        for tag in tags:
            p            = tag_problems[tag][problem_id]
            p['rating']  = rating    # same problem, same rating each time
            p['verdicts'].append(verdict)

            if verdict == 'OK':
                p['ac_timestamps'].append(timestamp)
                if is_contest_sub:
                    p['has_contest_ac'] = True

    # ── Compute features per tag ──────────────────
    tag_features = {}

    for tag, problems in tag_problems.items():

        total_attempted  = len(problems)
        solved_count     = 0
        ac_ratings       = []
        all_ac_timestamps_with_ratings = []  # [(timestamp, rating)]
        contest_solves   = 0
        first_try_solves = 0
        attempts_list    = []

        for prob_id, p in problems.items():
            verdicts   = p['verdicts']
            rating     = p['rating']
            has_ac     = 'OK' in verdicts

            if has_ac:
                solved_count += 1

                # Attempts before first AC
                first_ac_idx = verdicts.index('OK')
                attempts_list.append(first_ac_idx + 1)

                # First-try AC (solved on first submission)
                if first_ac_idx == 0:
                    first_try_solves += 1

                # Contest solve
                if p['has_contest_ac']:
                    contest_solves += 1

                # Ratings for avg/highest calculation
                if rating > 0:
                    ac_ratings.append(rating)

                    # For recent trend: pair first AC timestamp with rating
                    if p['ac_timestamps']:
                        first_ac_ts = min(p['ac_timestamps'])
                        all_ac_timestamps_with_ratings.append(
                            (first_ac_ts, rating)
                        )

        # ── Feature 1: Solve Rate ──────────────────
        solve_rate = solved_count / total_attempted if total_attempted > 0 else 0

        # ── Feature 2: Avg Attempts Before AC ─────
        avg_attempts = (
            sum(attempts_list) / len(attempts_list)
            if attempts_list else 0
        )

        # ── Feature 3: Highest Rating Solved ──────
        highest_rating = max(ac_ratings) if ac_ratings else 0

        # ── Feature 4: Average Rating Solved ──────
        # (TRUE comfort zone, not just the best day)
        avg_rating_solved = (
            sum(ac_ratings) / len(ac_ratings)
            if ac_ratings else 0
        )

        # ── Feature 5: Recency ─────────────────────
        if all_ac_timestamps_with_ratings:
            all_ts     = [ts for ts, _ in all_ac_timestamps_with_ratings]
            last_ac_ts = max(all_ts)
            now        = datetime.now(timezone.utc).timestamp()
            recency_days = (now - last_ac_ts) / (60 * 60 * 24)
        else:
            recency_days = 999

        # ── Feature 6: Contest Solve % ─────────────
        # % of solved problems that were during live contest
        contest_solve_pct = (
            contest_solves / solved_count
            if solved_count > 0 else 0
        )

        # ── Feature 7: First-Try AC Rate ───────────
        # % of solved problems solved on very first submission
        first_try_ac_rate = (
            first_try_solves / solved_count
            if solved_count > 0 else 0
        )

        # ── Feature 8: Recent Trend / Momentum ────
        # Average rating of last 5 AC problems (by timestamp)
        # Sorted oldest → newest, take last 5
        sorted_by_time = sorted(
            all_ac_timestamps_with_ratings,
            key=lambda x: x[0]
        )
        last_5 = sorted_by_time[-5:]
        recent_avg_rating = (
            sum(r for _, r in last_5) / len(last_5)
            if last_5 else avg_rating_solved
        )

        # Momentum: difference between recent avg and all-time avg
        # Positive = improving (recent problems harder than average)
        # Negative = declining (recent problems easier than average)
        momentum = round(recent_avg_rating - avg_rating_solved, 1)

        tag_features[tag] = {
            # Core features
            'total_attempted':         total_attempted,
            'total_solved':            solved_count,
            'solve_rate':              round(solve_rate, 3),
            'avg_attempts':            round(avg_attempts, 2),
            'highest_rating':          highest_rating,

            # New features
            'avg_rating_solved':       round(avg_rating_solved, 1),
            'recency_days':            round(recency_days, 1),
            'contest_solve_percentage': round(contest_solve_pct, 3),
            'first_try_ac_rate':       round(first_try_ac_rate, 3),
            'recent_avg_rating':       round(recent_avg_rating, 1),
            'momentum':                momentum
        }

    return tag_features


def get_solved_problem_ids(submissions):
    """Returns set of all problem IDs the user has solved (AC)."""
    solved = set()
    for sub in submissions:
        if sub.get('verdict') == 'OK':
            problem    = sub.get('problem', {})
            contest_id = problem.get('contestId', '')
            index      = problem.get('index', '')
            solved.add(f"{contest_id}{index}")
    return solved


def compute_avg_solved_rating(submissions):
    """Average difficulty of all solved problems (comfort level)."""
    solved_ratings = [
        sub['problem']['rating']
        for sub in submissions
        if sub.get('verdict') == 'OK'
        and sub.get('problem', {}).get('rating', 0) > 0
    ]
    if not solved_ratings:
        return 800
    return round(sum(solved_ratings) / len(solved_ratings))


def compute_weekly_solve_rate(submissions):
    """Problems solved per week on average."""
    ac_subs = [s for s in submissions if s.get('verdict') == 'OK']
    if not ac_subs:
        return 0.0

    timestamps  = [s['creationTimeSeconds'] for s in ac_subs]
    oldest      = min(timestamps)
    newest      = max(timestamps)
    total_days  = (newest - oldest) / (60 * 60 * 24)
    total_weeks = max(total_days / 7, 1)

    return round(len(ac_subs) / total_weeks, 2)


def compute_consistency_score(submissions):
    """
    How evenly distributed is practice across days?
    0 = all practice in one day, 1 = perfectly even every day.
    """
    if not submissions:
        return 0.0

    daily_counts = defaultdict(int)
    for sub in submissions:
        if sub.get('verdict') == 'OK':
            ts  = sub['creationTimeSeconds']
            day = datetime.fromtimestamp(ts).strftime('%Y-%m-%d')
            daily_counts[day] += 1

    if not daily_counts:
        return 0.0

    counts = list(daily_counts.values())
    mean   = sum(counts) / len(counts)
    if mean == 0:
        return 0.0

    variance = sum((c - mean) ** 2 for c in counts) / len(counts)
    std_dev  = variance ** 0.5
    cv       = std_dev / mean

    return round(1 / (1 + cv), 3)


def format_rating_history(rating_history):
    """Clean up rating history for frontend chart."""
    formatted = []
    for entry in rating_history:
        formatted.append({
            "contest_name": entry.get('contestName', ''),
            "timestamp":    entry.get('ratingUpdateTimeSeconds', 0),
            "old_rating":   entry.get('oldRating', 0),
            "new_rating":   entry.get('newRating', 0),
            "rank":         entry.get('rank', 0)
        })
    return formatted


def compute_tag_diversity(tag_features):
    """Number of distinct tags practiced."""
    return len(tag_features)


# # ── Test ──────────────────────────────────────────
# if __name__ == "__main__":
#     from cf_api import (
#         get_user_info,
#         get_user_submissions,
#         get_user_rating_history
#     )

#     handle = "tourist"
#     print(f"Testing data processor for {handle}...")
#     print()

#     info    = get_user_info(handle)
#     subs    = get_user_submissions(handle)
#     history = get_user_rating_history(handle)

#     profile = process_user_profile(info, subs, history)

#     print(f"✅ Handle:               {profile['handle']}")
#     print(f"✅ Current Rating:       {profile['current_rating']}")
#     print(f"✅ Total Solved:         {profile['total_solved']}")
#     print(f"✅ Avg Solved Rating:    {profile['avg_solved_rating']}")
#     print(f"✅ Weekly Solve Rate:    {profile['weekly_solve_rate']}/week")
#     print(f"✅ Consistency Score:    {profile['consistency_score']}")
#     print(f"✅ Tags analyzed:        {len(profile['tag_features'])}")
#     print()

#     # Show sample tag with ALL new features
#     sample_tag = 'dp'
#     if sample_tag in profile['tag_features']:
#         print(f"Sample features for '{sample_tag}':")
#         for key, val in profile['tag_features'][sample_tag].items():
#             print(f"   {key:30s}: {val}")
#     else:
#         # Show first available tag
#         first_tag = list(profile['tag_features'].keys())[0]
#         print(f"Sample features for '{first_tag}':")
#         for key, val in profile['tag_features'][first_tag].items():
#             print(f"   {key:30s}: {val}")