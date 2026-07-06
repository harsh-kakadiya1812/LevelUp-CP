import sys
import os
import random
sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from db.models import SessionLocal, Problem
from data.problem_ladder import (
    get_next_topic_in_path,
    get_topic_set,
    get_prerequisites_for_topic
)


# ── Constants ─────────────────────────────────────

# How far above comfort rating to recommend
STRETCH_LOW  = 100
STRETCH_HIGH = 200

# Minimum problems in a tag/rating range to recommend from
MIN_CANDIDATES = 3

# Rating buffer for quick win problems (below comfort)
QUICK_WIN_BUFFER = 100


# ── Problem Fetching ──────────────────────────────

def get_problems_from_db():
    """
    Fetch all cached CF problems from database.
    Returns list of Problem objects.
    Called once and passed around to avoid repeated DB queries.
    """
    db = SessionLocal()
    try:
        return db.query(Problem).filter(
            Problem.rating > 0
        ).all()
    finally:
        db.close()


def filter_problems(
    all_problems,
    tag,
    rating_low,
    rating_high,
    solved_ids,
    exclude_ids=None
):
    """
    Core filtering function.
    Returns list of unsolved problems matching tag and rating range.
    """
    if exclude_ids is None:
        exclude_ids = set()

    candidates = []
    for p in all_problems:
        # Must have rating in range
        if not p.rating:
            continue
        if not (rating_low <= p.rating <= rating_high):
            continue

        # Must not be already solved
        if p.problem_id in solved_ids:
            continue

        # Must not be excluded (already recommended today)
        if p.problem_id in exclude_ids:
            continue

        # Must have the required tag
        if p.tags and tag in p.tags:
            candidates.append(p)

    return candidates


def pick_random_problem(candidates):
    """
    Picks a problem from candidates.
    Uses weighted random: slightly prefers problems
    in the middle of the rating range (not too easy, not too hard).
    """
    if not candidates:
        return None

    if len(candidates) == 1:
        return candidates[0]

    # Pick randomly from top 20 candidates to avoid always
    # returning the same problem
    pool = candidates[:20]
    return random.choice(pool)


def problem_to_dict(problem, reason, tag_focused):
    """Convert DB Problem object to clean dict for API response."""
    if not problem:
        return None

    return {
        "problem_id":  problem.problem_id,
        "title":       problem.title,
        "rating":      problem.rating,
        "tags":        problem.tags or [],
        "tag_focused": tag_focused,
        "reason":      reason,
        "cf_url":      f"https://codeforces.com/problemset/problem/"
                       f"{problem.problem_id[:-1]}/{problem.problem_id[-1]}"
    }


# ── Daily 3 Recommendations ───────────────────────

def get_daily_recommendations(
    handle,
    skill_profile,
    comfort_rating,
    solved_ids,
    all_problems=None
):
    """
    Generate 3 personalized daily problem recommendations.

    Strategy:
    Problem 1 → Weakest tag, stretch rating (+100 to +200)
                Targets biggest skill gap directly
    Problem 2 → Second weakest tag, stretch rating
                Diversifies weak area practice
    Problem 3 → Quick win (strong tag, comfort rating)
                Builds confidence and maintains momentum

    Args:
        handle:         CF handle (for logging)
        skill_profile:  output of build_skill_profile()
        comfort_rating: user's current comfort zone rating
        solved_ids:     set of already solved problem IDs
        all_problems:   cached list of Problem objects

    Returns:
        List of 3 problem dicts with reason explanations
    """
    if all_problems is None:
        all_problems = get_problems_from_db()

    weak_tags   = skill_profile.get('weak', [])
    strong_tags = skill_profile.get('strong', [])

    recommendations = []
    used_ids        = set()

    stretch_low  = comfort_rating + STRETCH_LOW
    stretch_high = comfort_rating + STRETCH_HIGH

    # ── Problem 1: Weakest Tag ─────────────────────
    problem_1 = None
    for weak_tag in weak_tags:
        candidates = filter_problems(
            all_problems,
            tag        = weak_tag,
            rating_low = stretch_low,
            rating_high = stretch_high,
            solved_ids = solved_ids,
            exclude_ids = used_ids
        )

        if len(candidates) >= MIN_CANDIDATES:
            problem_1 = pick_random_problem(candidates)
            if problem_1:
                used_ids.add(problem_1.problem_id)
                recommendations.append(problem_to_dict(
                    problem_1,
                    reason     = (
                        f"Your weakest topic is '{weak_tag}' "
                        f"(solve rate < 30%). This problem at "
                        f"rating {problem_1.rating} will directly "
                        f"target your biggest gap."
                    ),
                    tag_focused = weak_tag
                ))
                break

    # If no problem found at stretch, try at comfort level
    if not problem_1 and weak_tags:
        for weak_tag in weak_tags:
            candidates = filter_problems(
                all_problems,
                tag         = weak_tag,
                rating_low  = comfort_rating - 100,
                rating_high = comfort_rating + 100,
                solved_ids  = solved_ids,
                exclude_ids = used_ids
            )
            if candidates:
                p = pick_random_problem(candidates)
                if p:
                    used_ids.add(p.problem_id)
                    recommendations.append(problem_to_dict(
                        p,
                        reason     = (
                            f"Targeting weak tag '{weak_tag}' "
                            f"at your current comfort level "
                            f"(no harder problems available in range)."
                        ),
                        tag_focused = weak_tag
                    ))
                    break

    # ── Problem 2: Second Weakest Tag ─────────────
    problem_2     = None
    skip_first    = len(recommendations) > 0
    weak_tag_used = recommendations[0]['tag_focused'] if recommendations else None

    for weak_tag in weak_tags:
        # Skip the tag already used for Problem 1
        if weak_tag == weak_tag_used:
            continue

        candidates = filter_problems(
            all_problems,
            tag         = weak_tag,
            rating_low  = stretch_low,
            rating_high = stretch_high,
            solved_ids  = solved_ids,
            exclude_ids = used_ids
        )

        if len(candidates) >= MIN_CANDIDATES:
            problem_2 = pick_random_problem(candidates)
            if problem_2:
                used_ids.add(problem_2.problem_id)
                recommendations.append(problem_to_dict(
                    problem_2,
                    reason     = (
                        f"Second weakest topic '{weak_tag}'. "
                        f"Diversifying weak area practice prevents "
                        f"over-relying on one topic."
                    ),
                    tag_focused = weak_tag
                ))
                break

    # Fallback: try moderate tags if no second weak found
    if not problem_2:
        moderate_tags = skill_profile.get('moderate', [])
        for mod_tag in moderate_tags[:5]:
            if mod_tag == weak_tag_used:
                continue
            candidates = filter_problems(
                all_problems,
                tag         = mod_tag,
                rating_low  = stretch_low,
                rating_high = stretch_high,
                solved_ids  = solved_ids,
                exclude_ids = used_ids
            )
            if candidates:
                p = pick_random_problem(candidates)
                if p:
                    used_ids.add(p.problem_id)
                    recommendations.append(problem_to_dict(
                        p,
                        reason     = (
                            f"Moderate topic '{mod_tag}' at stretch "
                            f"difficulty — push your ceiling here."
                        ),
                        tag_focused = mod_tag
                    ))
                    break

    # ── Problem 3: Quick Win ───────────────────────
    # Strong tag, at or below comfort rating
    # Purpose: confidence boost, keeps streak going
    for strong_tag in strong_tags:
        candidates = filter_problems(
            all_problems,
            tag         = strong_tag,
            rating_low  = comfort_rating - QUICK_WIN_BUFFER,
            rating_high = comfort_rating,
            solved_ids  = solved_ids,
            exclude_ids = used_ids
        )

        if candidates:
            p = pick_random_problem(candidates)
            if p:
                used_ids.add(p.problem_id)
                recommendations.append(problem_to_dict(
                    p,
                    reason     = (
                        f"Quick win! You're strong in '{strong_tag}'. "
                        f"Solving this builds confidence and maintains "
                        f"your daily streak without too much struggle."
                    ),
                    tag_focused = strong_tag
                ))
                break

    # Final fallback: any unsolved problem near comfort rating
    if len(recommendations) < 3:
        candidates = [
            p for p in all_problems
            if p.problem_id not in solved_ids
            and p.problem_id not in used_ids
            and p.rating is not None
            and (comfort_rating - 100) <= p.rating <= (comfort_rating + 100)
        ]
        random.shuffle(candidates)
        for p in candidates[:3 - len(recommendations)]:
            recommendations.append(problem_to_dict(
                p,
                reason     = (
                    f"At your comfort rating level — good for "
                    f"general practice."
                ),
                tag_focused = p.tags[0] if isinstance(p.tags, (list, tuple)) and p.tags else "general"
            ))

    return recommendations[:3]


# ── Problem Ladder Recommendations ────────────────

def get_problem_ladder(
    handle,
    skill_profile,
    current_rating,
    solved_ids,
    all_problems=None
):
    """
    Returns the "Solve This Before That" sequenced path.

    Finds:
    1. Where the user is in the learning path
    2. What topic to focus on next
    3. 5 problems in that topic at increasing difficulty
    """
    if all_problems is None:
        all_problems = get_problems_from_db()

    weak_tags      = skill_profile.get('weak', [])
    all_practiced  = list(skill_profile.get('scores', {}).keys())

    # Find next topic in learning path
    next_topic = get_next_topic_in_path(
        rating         = current_rating,
        practiced_tags = all_practiced,
        weak_tags      = weak_tags
    )

    if not next_topic:
        return {
            "message": "You have covered all recommended topics for your level!",
            "problems": []
        }

    if not next_topic.get('ready'):
        # User needs to learn prerequisites first
        prereq_problems = []
        for prereq in next_topic['unmet_prereqs'][:2]:
            candidates = filter_problems(
                all_problems,
                tag         = prereq,
                rating_low  = max(800, current_rating - 300),
                rating_high = current_rating,
                solved_ids  = solved_ids
            )
            if candidates:
                p = pick_random_problem(candidates)
                if p:
                    prereq_problems.append(problem_to_dict(
                        p,
                        reason     = (
                            f"Learn '{prereq}' first — "
                            f"required before '{next_topic['topic']}'"
                        ),
                        tag_focused = prereq
                    ))

        return {
            "message":       next_topic['message'],
            "next_topic":    next_topic['topic'],
            "ready":         False,
            "prereq_problems": prereq_problems,
            "problems":      []
        }

    # User is ready for next topic
    # Find 5 problems in increasing difficulty
    tag         = next_topic['topic']
    base_rating = max(800, current_rating - 200)
    ladder_problems = []
    used_ids        = set()

    for i in range(5):
        target_rating = base_rating + (i * 100)
        candidates    = filter_problems(
            all_problems,
            tag         = tag,
            rating_low  = target_rating,
            rating_high = target_rating + 100,
            solved_ids  = solved_ids,
            exclude_ids = used_ids
        )

        if candidates:
            p = pick_random_problem(candidates)
            if p:
                used_ids.add(p.problem_id)
                ladder_problems.append(problem_to_dict(
                    p,
                    reason     = f"Step {i+1} of 5: {tag} at {p.rating}",
                    tag_focused = tag
                ))

    return {
        "message":    next_topic['message'],
        "next_topic": tag,
        "ready":      True,
        "problems":   ladder_problems,
        "prereq_problems": []
    }


# ── Topic-Based Problem Sets ──────────────────────

def get_topic_problem_set(
    tag,
    current_rating,
    solved_ids,
    all_problems=None
):
    """
    Returns a curated set of problems for mastering one topic.
    Starts from appropriate difficulty for user's level.
    """
    if all_problems is None:
        all_problems = get_problems_from_db()

    topic_info  = get_topic_set(tag, current_rating, solved_ids)
    if not topic_info:
        return {
            "error": f"No curated problem set available for '{tag}'"
        }

    # Find actual problems for each level
    problems_by_level = []
    used_ids          = set()

    for level in topic_info['levels']:
        rating      = level['rating']
        candidates  = filter_problems(
            all_problems,
            tag         = tag,
            rating_low  = rating,
            rating_high = rating + 150,
            solved_ids  = solved_ids,
            exclude_ids = used_ids
        )

        if candidates:
            p = pick_random_problem(candidates)
            if p:
                used_ids.add(p.problem_id)
                problems_by_level.append({
                    **(problem_to_dict(
                        p,
                        reason     = level['description'],
                        tag_focused = tag
                    ) or {}),
                    "level_description": level['description'],
                    "target_rating":     rating
                })

    return {
        "tag":           tag,
        "title":         topic_info['title'],
        "description":   topic_info['description'],
        "problems":      problems_by_level,
        "total_levels":  topic_info['total_levels'],
        "start_rating":  current_rating - 200
    }


# ── Struggled Problem Finder ──────────────────────

def get_struggled_problems(submissions, solved_ids):
    """
    Find problems where the user:
    - Had multiple WA/TLE submissions
    - Eventually got AC (or gave up)

    These are the most valuable problems to revisit
    because they reveal specific weakness patterns.
    """
    from collections import defaultdict

    problem_attempts = defaultdict(lambda: {
        'verdicts': [],
        'problem_id': None,
        'rating': 0,
        'tags': []
    })

    for sub in submissions:
        problem    = sub.get('problem', {})
        problem_id = f"{problem.get('contestId', '')}{problem.get('index', '')}"
        verdict    = sub.get('verdict', '')
        rating     = problem.get('rating', 0)
        tags       = problem.get('tags', [])

        p = problem_attempts[problem_id]
        p['problem_id'] = problem_id
        p['rating']     = rating
        p['tags']       = tags
        p['verdicts'].append(verdict)

    struggled = []
    for prob_id, data in problem_attempts.items():
        verdicts  = data['verdicts']
        ac_count  = verdicts.count('OK')
        wa_count  = verdicts.count('WRONG_ANSWER')
        tle_count = verdicts.count('TIME_LIMIT_EXCEEDED')

        # Struggled = many wrong attempts before (or without) AC
        total_wrong = wa_count + tle_count
        if total_wrong >= 3:
            struggled.append({
                "problem_id":    prob_id,
                "rating":        data['rating'],
                "tags":          data['tags'],
                "wa_count":      wa_count,
                "tle_count":     tle_count,
                "got_ac":        ac_count > 0,
                "total_attempts": len(verdicts),
                "cf_url": (
                    f"https://codeforces.com/problemset/problem/"
                    f"{prob_id[:-1]}/{prob_id[-1]}"
                )
            })

    # Sort by most attempts (most struggled first)
    struggled.sort(
        key=lambda x: x['wa_count'] + x['tle_count'],
        reverse=True
    )

    return struggled[:20]


# ── Unsolved From Past Contests ───────────────────

def get_unsolved_from_contests(submissions, all_problems=None):
    """
    Find problems from contests the user participated in
    but never solved during or after the contest.

    These are especially valuable because:
    - User already saw them in a contest context
    - They represent real rating opportunity missed
    - Solving them now means learning from a specific failure
    """
    if all_problems is None:
        all_problems = get_problems_from_db()

    problems_dict = {p.problem_id: p for p in all_problems}

    # Find contest submissions (CONTESTANT type)
    contested_problems = set()
    solved_problems    = set()

    for sub in submissions:
        author  = sub.get('author', {})
        ptype   = author.get('participantType', '')
        problem = sub.get('problem', {})
        prob_id = f"{problem.get('contestId', '')}{problem.get('index', '')}"

        if ptype == 'CONTESTANT':
            contested_problems.add(prob_id)

        if sub.get('verdict') == 'OK':
            solved_problems.add(prob_id)

    # Problems seen in contest but never solved
    unsolved = contested_problems - solved_problems

    result = []
    for prob_id in unsolved:
        if prob_id in problems_dict:
            p = problems_dict[prob_id]
            result.append({
                "problem_id":  prob_id,
                "title":       p.title,
                "rating":      p.rating,
                "tags":        p.tags or [],
                "reason":      (
                    "You attempted this in a contest but never solved it. "
                    "Upsolving contest problems is the highest-ROI practice."
                ),
                "cf_url": (
                    f"https://codeforces.com/problemset/problem/"
                    f"{prob_id[:-1]}/{prob_id[-1]}"
                )
            })

    # Sort by rating (easier first)
    result.sort(key=lambda x: x.get('rating') or 0)
    return result[:15]


# # ── Test ──────────────────────────────────────────

# if __name__ == "__main__":
#     print("Testing recommender...")
#     print()

#     # Load problems
#     all_problems = get_problems_from_db()
#     print(f"Loaded {len(all_problems)} problems from DB")
#     print()

#     if not all_problems:
#         print("No problems in DB. Run /api/cache-problems first.")
#         exit()

#     # Dummy skill profile for testing
#     dummy_skill = {
#         'weak':     ['dsu', 'flows', 'graphs'],
#         'moderate': ['dp', 'trees'],
#         'strong':   ['greedy', 'binary search', 'math'],
#         'scores':   {
#             'dsu': 0.15, 'flows': 0.10, 'graphs': 0.25,
#             'dp': 0.45, 'trees': 0.50,
#             'greedy': 0.70, 'binary search': 0.75, 'math': 0.65
#         }
#     }

#     dummy_solved  = set()
#     comfort_rating = 1280

#     # Test daily recommendations
#     print("=== Daily 3 Recommendations ===")
#     recs = get_daily_recommendations(
#         handle         = "test_user",
#         skill_profile  = dummy_skill,
#         comfort_rating = comfort_rating,
#         solved_ids     = dummy_solved,
#         all_problems   = all_problems
#     )

#     for i, rec in enumerate(recs, 1):
#         if rec:
#             print(f"\nProblem {i}: {rec['title']} (Rating: {rec['rating']})")
#             print(f"  Tag:    {rec['tag_focused']}")
#             print(f"  URL:    {rec['cf_url']}")
#             print(f"  Reason: {rec['reason'][:60]}...")

#     print()
#     print("=== Problem Ladder ===")
#     ladder = get_problem_ladder(
#         handle         = "test_user",
#         skill_profile  = dummy_skill,
#         current_rating = 1350,
#         solved_ids     = dummy_solved,
#         all_problems   = all_problems
#     )
#     print(f"Next topic: {ladder.get('next_topic')}")
#     print(f"Message:    {ladder.get('message')}")
#     print(f"Problems:   {len(ladder.get('problems', []))}")

#     print()
#     print("=== Topic Problem Set (DP) ===")
#     dp_set = get_topic_problem_set(
#         tag            = "dp",
#         current_rating = 1350,
#         solved_ids     = dummy_solved,
#         all_problems   = all_problems
#     )
#     print(f"Title:    {dp_set.get('title')}")
#     print(f"Problems: {len(dp_set.get('problems', []))}")
#     for p in dp_set.get('problems', [])[:3]:
#         print(f"  - {p['title']} ({p['rating']}): {p['level_description']}")