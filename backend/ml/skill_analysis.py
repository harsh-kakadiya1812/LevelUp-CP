import numpy as np
import time


# ── Constants ─────────────────────────────────────

WEAK_THRESHOLD     = 0.30
MODERATE_THRESHOLD = 0.55

# Minimum problems attempted to include a tag
MIN_ATTEMPTS = 3

MAX_RATING  = 3500
VOLUME_CAP  = 50    # cap volume score at 50 problems


# ── Core Scoring Function ─────────────────────────

def compute_skill_score(tag_features):
    """
    Computes a skill score from 0.0 to 1.0 using
    7 features with the updated formula.

    Formula:
    0.20 × Solve Rate
    0.20 × Avg Rating Solved
    0.15 × Highest Rating Solved
    0.15 × Recency
    0.10 × Volume (capped at 50)
    0.10 × First-Try AC Rate
    0.10 × Attempt Score

    Contest % and Momentum are computed but shown
    as additional insights, not in the main score.
    """

    # Extract features
    solve_rate        = tag_features.get('solve_rate', 0)
    avg_attempts      = tag_features.get('avg_attempts', 1)
    highest_rating    = tag_features.get('highest_rating', 0)
    recency_days      = tag_features.get('recency_days', 999)
    total_solved      = tag_features.get('total_solved', 0)
    first_try_ac_rate = tag_features.get('first_try_ac_rate', 0)
    avg_rating_solved = tag_features.get('avg_rating_solved', 0)

    # ── Normalize each feature to 0–1 ─────────────

    # Feature 1: Solve Rate (already 0-1)
    solve_score = solve_rate

    # Feature 2: Avg Rating Score
    # Avg rating of 1400 → score of 0.40
    # Avg rating of 2100 → score of 0.60
    # This is the TRUE comfort zone metric
    avg_rating_score = min(avg_rating_solved / MAX_RATING, 1.0)

    # Feature 3: Highest Rating Score
    # Still matters but lower weight since avg_rating handles the fluke
    highest_rating_score = min(highest_rating / MAX_RATING, 1.0)

    # Feature 4: Recency Score (exponential decay)
    # Practiced today    = 1.00
    # Practiced 30d ago  = 0.37 (e^-1)
    # Practiced 60d ago  = 0.14 (e^-2)
    # Practiced 90d ago  = 0.05 (e^-3)
    # Never practiced    = ~0.00
    recency_score = np.exp(-recency_days / 30)

    # Feature 5: Volume Score (capped at 50 problems)
    # 10 solved  → 0.20
    # 25 solved  → 0.50
    # 50+ solved → 1.00 (max)
    # Prevents single-problem 1700 flukes from scoring high
    volume_score = min(total_solved / VOLUME_CAP, 1.0)

    # Feature 6: First-Try AC Rate (already 0-1)
    # 90% first-try = precision master
    # 30% first-try = needs many attempts
    first_try_score = first_try_ac_rate

    # Feature 7: Attempt Score (fewer attempts = better)
    # 1 attempt  → 0.50
    # 2 attempts → 0.33
    # 5 attempts → 0.17
    attempt_score = 1 / (1 + avg_attempts)

    # ── Apply Weighted Formula ─────────────────────
    score = (
        0.20 * solve_score          +
        0.20 * avg_rating_score     +
        0.15 * highest_rating_score +
        0.15 * recency_score        +
        0.10 * volume_score         +
        0.10 * first_try_score      +
        0.10 * attempt_score
    )

    return round(float(score), 4)


# ── Classification ────────────────────────────────

def classify_skill_level(score):
    if score < WEAK_THRESHOLD:
        return "Weak"
    elif score < MODERATE_THRESHOLD:
        return "Moderate"
    else:
        return "Strong"


# ── Momentum Classifier ───────────────────────────

def classify_momentum(momentum):
    """
    Converts momentum value into a readable label.
    Momentum = recent_avg_rating - all_time_avg_rating
    """
    if momentum > 200:
        return "🚀 Breaking Through"
    elif momentum > 50:
        return "📈 Improving"
    elif momentum > -50:
        return "➡️  Stable"
    elif momentum > -200:
        return "📉 Declining"
    else:
        return "⚠️  Avoiding Harder Problems"


# ── Main Skill Profile Builder ────────────────────

def build_skill_profile(tag_features):
    """
    Takes full tag_features dict and returns
    complete skill profile with all new metrics.

    Output includes:
    - weak / moderate / strong lists
    - scores per tag
    - momentum per tag
    - contest mastery per tag
    - first-try precision per tag
    """
    scored_tags = []

    for tag, features in tag_features.items():
        # Skip tags with too few attempts
        if features.get('total_attempted', 0) < MIN_ATTEMPTS:
            continue

        score     = compute_skill_score(features)
        level     = classify_skill_level(score)
        momentum  = features.get('momentum', 0)
        mom_label = classify_momentum(momentum)

        scored_tags.append({
            # Identity
            "tag":   tag,
            "level": level,
            "score": score,

            # Core features
            "solve_rate":      features.get('solve_rate', 0),
            "avg_attempts":    features.get('avg_attempts', 0),
            "highest_rating":  features.get('highest_rating', 0),
            "total_solved":    features.get('total_solved', 0),
            "total_attempted": features.get('total_attempted', 0),

            # New features
            "avg_rating_solved":        features.get('avg_rating_solved', 0),
            "recency_days":             features.get('recency_days', 999),
            "contest_solve_percentage": features.get('contest_solve_percentage', 0),
            "first_try_ac_rate":        features.get('first_try_ac_rate', 0),
            "recent_avg_rating":        features.get('recent_avg_rating', 0),
            "momentum":                 momentum,
            "momentum_label":           mom_label
        })

    # Sort weakest first
    scored_tags.sort(key=lambda x: x['score'])

    weak_tags     = [t for t in scored_tags if t['level'] == "Weak"]
    moderate_tags = [t for t in scored_tags if t['level'] == "Moderate"]
    strong_tags   = [t for t in scored_tags if t['level'] == "Strong"]

    # Lookup dicts for quick access
    scores   = {t['tag']: t['score']         for t in scored_tags}
    levels   = {t['tag']: t['level']         for t in scored_tags}
    momentum = {t['tag']: t['momentum']      for t in scored_tags}

    return {
        "weak":     [t['tag'] for t in weak_tags],
        "moderate": [t['tag'] for t in moderate_tags],
        "strong":   [t['tag'] for t in strong_tags],
        "scores":   scores,
        "levels":   levels,
        "momentum": momentum,
        "details":  scored_tags,
        "summary": {
            "total":    len(scored_tags),
            "weak":     len(weak_tags),
            "moderate": len(moderate_tags),
            "strong":   len(strong_tags)
        }
    }


# ── Comfort Rating ────────────────────────────────

def compute_comfort_rating(tag_features):
    """
    Uses AVG RATING (not highest) for comfort zone.
    More accurate for recommendations now.
    """
    weak_avg_ratings = []

    for tag, features in tag_features.items():
        score = compute_skill_score(features)
        level = classify_skill_level(score)

        if level == "Weak":
            avg_r = features.get('avg_rating_solved', 0)
            if avg_r > 0:
                weak_avg_ratings.append(avg_r)

    if not weak_avg_ratings:
        all_avgs = [
            f.get('avg_rating_solved', 0)
            for f in tag_features.values()
            if f.get('avg_rating_solved', 0) > 0
        ]
        return int(sum(all_avgs) / len(all_avgs)) if all_avgs else 1200

    return int(sum(weak_avg_ratings) / len(weak_avg_ratings))


# ── Neglected Topics ──────────────────────────────

def find_neglected_topics(tag_features, days_threshold=60):
    """Topics not practiced in days_threshold days."""
    neglected = []
    for tag, features in tag_features.items():
        recency = features.get('recency_days', 999)
        if recency > days_threshold:
            neglected.append({
                "tag":              tag,
                "days_since":       round(recency),
                "avg_rating":       features.get('avg_rating_solved', 0),
                "total_solved":     features.get('total_solved', 0)
            })

    neglected.sort(key=lambda x: x['days_since'], reverse=True)
    return neglected


# ── Breakthrough Topics ───────────────────────────

def find_breakthrough_topics(tag_features):
    """
    Topics where momentum is strongly positive.
    User is currently solving harder than their avg → push them!
    """
    breakthroughs = []
    for tag, features in tag_features.items():
        momentum      = features.get('momentum', 0)
        solve_rate    = features.get('solve_rate', 0)
        recent_avg    = features.get('recent_avg_rating', 0)
        avg_rating    = features.get('avg_rating_solved', 0)
        total_solved  = features.get('total_solved', 0)

        # Breakthrough: strong momentum + decent solve rate + enough data
        if momentum > 150 and solve_rate > 0.40 and total_solved >= 5:
            breakthroughs.append({
                "tag":              tag,
                "momentum":         momentum,
                "avg_rating":       avg_rating,
                "recent_avg":       recent_avg,
                "message":          (
                    f"Your last 5 {tag} problems averaged "
                    f"{recent_avg:.0f}, up from your all-time avg of "
                    f"{avg_rating:.0f}. You're ready for harder problems!"
                )
            })

    breakthroughs.sort(key=lambda x: x['momentum'], reverse=True)
    return breakthroughs


# ── Stagnation Detector ───────────────────────────

def detect_stagnation(skill_profile, rating_history):
    """
    Detects flat rating despite active practice.
    """
    if not rating_history:
        return {
            "is_stagnant": False,
            "reason": "No contest history available"
        }

    now         = time.time()
    days_90_ago = now - (90 * 24 * 60 * 60)

    recent = [
        c for c in rating_history
        if c.get('timestamp', 0) > days_90_ago
    ]

    if len(recent) < 2:
        return {
            "is_stagnant": False,
            "reason": "Need at least 2 recent contests to detect stagnation"
        }

    oldest_rating = recent[0]['new_rating']
    latest_rating = recent[-1]['new_rating']
    rating_change = latest_rating - oldest_rating
    weak_count    = skill_profile['summary']['weak']

    # Stagnant: barely moved + actively practicing + multiple weak areas
    is_stagnant = (
        abs(rating_change) < 50 and
        weak_count >= 3
    )

    if is_stagnant:
        weak_top3 = ', '.join(skill_profile['weak'][:3])
        reason = (
            f"Rating changed only {rating_change:+d} points in 90 days. "
            f"You have {weak_count} unresolved weak topics. "
            f"Top priorities: {weak_top3}"
        )
    else:
        reason = "No stagnation detected. Keep going!"

    return {
        "is_stagnant":       is_stagnant,
        "reason":            reason,
        "rating_change_90d": rating_change,
        "weak_tag_count":    weak_count
    }


# # ── Test ──────────────────────────────────────────

# if __name__ == "__main__":
#     import sys, os
#     sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

#     from data.cf_api import (
#         get_user_info,
#         get_user_submissions,
#         get_user_rating_history
#     )
#     from data.data_processor import process_user_profile

#     handle = "tourist"
#     print(f"Building skill profile for {handle}...")
#     print()

#     info    = get_user_info(handle)
#     subs    = get_user_submissions(handle)
#     history = get_user_rating_history(handle)
#     profile = process_user_profile(info, subs, history)

#     skill          = build_skill_profile(profile['tag_features'])
#     comfort        = compute_comfort_rating(profile['tag_features'])
#     neglected      = find_neglected_topics(profile['tag_features'])
#     breakthroughs  = find_breakthrough_topics(profile['tag_features'])
#     stagnation     = detect_stagnation(skill, profile['rating_history'])

#     print(f"📊 Skill Summary:")
#     print(f"   Total tags: {skill['summary']['total']}")
#     print(f"   Weak:       {skill['summary']['weak']}")
#     print(f"   Moderate:   {skill['summary']['moderate']}")
#     print(f"   Strong:     {skill['summary']['strong']}")
#     print()
#     print(f"🔴 Weak Topics:   {skill['weak'][:5]}")
#     print(f"🟡 Moderate:      {skill['moderate'][:5]}")
#     print(f"🟢 Strong Topics: {skill['strong'][:5]}")
#     print()
#     print(f"🎯 Comfort Rating: {comfort}")
#     print()
#     print(f"🚀 Breakthrough Topics:")
#     for b in breakthroughs[:3]:
#         print(f"   {b['tag']}: {b['message']}")
#     print()
#     print(f"😴 Neglected Topics (60+ days):")
#     for t in neglected[:3]:
#         print(f"   {t['tag']}: {t['days_since']} days ago")
#     print()
#     print(f"⚠️  Stagnation: {stagnation['is_stagnant']}")
#     if stagnation['is_stagnant']:
#         print(f"   {stagnation['reason']}")

#     print()
#     print("Sample tag details (first weak tag):")
#     if skill['weak']:
#         first_weak = skill['weak'][0]
#         tag_detail = next(t for t in skill['details'] if t['tag'] == first_weak)
#         for key, val in tag_detail.items():
#             print(f"   {key:30s}: {val}")