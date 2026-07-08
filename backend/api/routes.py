import sys
import os
sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from ..ml.rating_predictor import predict_rating, extract_features
from fastapi import APIRouter, HTTPException
from ..data.cf_api import (
    get_user_info,
    get_user_submissions,
    get_user_rating_history,
    get_all_problems,
    validate_handle
)
from ..data.data_processor import (
    process_user_profile,
    compute_tag_features,
    compute_tag_diversity
)
from ..ml.skill_analysis import (
    build_skill_profile,
    compute_comfort_rating,
    find_neglected_topics,
    find_breakthrough_topics,
    detect_stagnation
)
from ..db.models import (
    save_user,
    save_submissions,
    save_problems,
    get_user_from_db,
    get_submissions_from_db
)
from ..ml.recommender import (
    get_daily_recommendations,
    get_problem_ladder,
    get_topic_problem_set,
    get_struggled_problems,
    get_unsolved_from_contests,
    get_problems_from_db
)
from ..llm.hints import (
    get_next_hint,
    get_all_hints_so_far,
    reset_hint_session
)
from pydantic import BaseModel

router = APIRouter()


@router.post("/fetch-user/{handle}")
def fetch_user(handle: str):
    """Fetch and store user data from Codeforces."""
    if not validate_handle(handle):
        raise HTTPException(status_code=404, detail=f"Handle '{handle}' not found")

    user_info   = get_user_info(handle)
    submissions = get_user_submissions(handle)

    save_user(handle, user_info)
    save_submissions(handle, submissions)

    return {"message": f"Data fetched and saved for {handle}"}

@router.get("/skill-profile/{handle}")
def get_skill_profile(handle: str):
    """Get skill profile using cached DB data (no CF refetch)."""
    db_subs = get_submissions_from_db(handle)

    if not db_subs:
        raise HTTPException(
            status_code=404,
            detail=f"No data for {handle}. Call /full-analysis/{handle} first."
        )

    # Reconstruct submissions with participant_type from DB
    raw_subs = []
    for sub in db_subs:
        raw_subs.append({
            "verdict":              sub.verdict,
            "creationTimeSeconds":  sub.timestamp,
            "author": {
                # Use stored participant_type 
                "participantType": getattr(sub, 'participant_type', 'PRACTICE') or 'PRACTICE'
            },
            "problem": {
                "contestId": sub.problem_id[:-1] if getattr(sub, 'problem_id', None) is not None else "",
                "index":     sub.problem_id[-1]  if getattr(sub, 'problem_id', None) is not None else "",
                "rating":    sub.problem_rating,
                "tags":      sub.tags or []
            }
        })

    tag_features   = compute_tag_features(raw_subs)
    user          = get_user_from_db(handle)
    user_rating   = int(getattr(user, "current_rating", 0) or 0) if user else 0
    skill_profile = build_skill_profile(tag_features, user_rating=user_rating)
    comfort_rating = compute_comfort_rating(tag_features)
    neglected      = find_neglected_topics(tag_features)
    breakthroughs  = find_breakthrough_topics(tag_features)

    return {
        "handle":            handle,
        "skill_profile":     skill_profile,
        "comfort_rating":    comfort_rating,
        "neglected_topics":  neglected,
        "breakthrough_topics": breakthroughs
    }


@router.post("/cache-problems")
def cache_problems():
    """Cache all CF problems. Run once."""
    problems = get_all_problems()
    if not problems:
        raise HTTPException(status_code=500, detail="Failed to fetch problems")
    save_problems(problems)
    return {"message": f"Cached {len(problems)} problems"}


@router.get("/health")
def health():
    return {"status": "Phase 2 running correctly"}

@router.get("/predict-rating/{handle}")
def get_rating_prediction(handle: str):
    """
    Predict future rating for a CF handle.
    Requires that /full-analysis/{handle} was called first
    to have the user's data in the database.
    """
    # Get submissions from DB
    db_subs = get_submissions_from_db(handle)
    if not db_subs:
        raise HTTPException(
            status_code=404,
            detail=f"No data for {handle}. Call /full-analysis/{handle} first."
        )

    # Reconstruct raw submissions
    raw_subs = []
    for sub in db_subs:
        problem_id = str(sub.problem_id) if sub.problem_id is not None else ""
        raw_subs.append({
            "verdict":             sub.verdict,
            "creationTimeSeconds": sub.timestamp,
            "author": {
                "participantType": getattr(sub, 'participant_type', 'PRACTICE') or 'PRACTICE'
            },
            "problem": {
                "contestId": problem_id[:-1] if len(problem_id) > 0 else "",
                "index":     problem_id[-1]  if len(problem_id) > 0 else "",
                "rating":    sub.problem_rating,
                "tags":      sub.tags or []
            }
        })

    # Rebuild profile from stored data
    from ..data.data_processor import (
        compute_tag_features,
        compute_avg_solved_rating,
        compute_weekly_solve_rate,
        compute_consistency_score
    )
    from ..ml.skill_analysis import (
        build_skill_profile,
        compute_comfort_rating
    )

    tag_features = compute_tag_features(raw_subs)
    skill_profile = build_skill_profile(tag_features)

    # Get user from DB for rating
    user = get_user_from_db(handle)
    if user is None:
        raise HTTPException(
            status_code=404,
            detail=f"User {handle} not in database"
        )

    # Build profile dict
    rating_history = get_user_rating_history(handle)
    profile = {
        'current_rating':    user.current_rating,
        'weekly_solve_rate': compute_weekly_solve_rate(raw_subs),
        'avg_solved_rating': compute_avg_solved_rating(raw_subs),
        'consistency_score': compute_consistency_score(raw_subs),
        'total_solved':      sum(1 for s in raw_subs if s['verdict'] == 'OK'),
        'tag_diversity':     len(tag_features),
        'rating_history':    [
            {
                'timestamp':   c.get('ratingUpdateTimeSeconds', 0),
                'new_rating':  c.get('newRating', 0),
                'old_rating':  c.get('oldRating', 0)
            }
            for c in rating_history
        ]
    }

    # Make prediction
    prediction = predict_rating(profile, skill_profile)

    if prediction.get('error'):
        raise HTTPException(
            status_code=500,
            detail=prediction['error']
        )

    return prediction


@router.post("/full-analysis/{handle}")
def full_analysis(handle: str):
    """
    Complete pipeline in one call.
    Now includes recommendations.
    """
    if not validate_handle(handle):
        raise HTTPException(
            status_code=404,
            detail=f"Handle '{handle}' not found"
        )

    # Fetch from CF
    user_info      = get_user_info(handle)
    submissions    = get_user_submissions(handle)
    rating_history = get_user_rating_history(handle)

    # Save
    save_user(handle, user_info)
    save_submissions(handle, submissions)

    # Process
    from ..data.data_processor import process_user_profile, compute_tag_diversity
    from ..ml.skill_analysis import (
        build_skill_profile,
        compute_comfort_rating,
        find_neglected_topics,
        find_breakthrough_topics,
        detect_stagnation
    )
    from ..ml.rating_predictor import predict_rating

    profile = process_user_profile(user_info, submissions, rating_history)

    skill_profile  = build_skill_profile(
        profile['tag_features'],
        user_rating=profile['current_rating']
    )
    comfort_rating = compute_comfort_rating(profile['tag_features'])
    neglected      = find_neglected_topics(profile['tag_features'])
    breakthroughs  = find_breakthrough_topics(profile['tag_features'])
    stagnation     = detect_stagnation(skill_profile, profile['rating_history'])
    prediction     = predict_rating(profile, skill_profile)

    # Recommendations
    solved_ids   = set(
        f"{sub.get('problem', {}).get('contestId', '')}"
        f"{sub.get('problem', {}).get('index', '')}"
        for sub in submissions
        if sub.get('verdict') == 'OK'
    )

    all_problems = get_problems_from_db()

    daily_recs  = []
    ladder_recs = {}

    if all_problems:
        daily_recs = get_daily_recommendations(
            handle         = handle,
            skill_profile  = skill_profile,
            comfort_rating = comfort_rating,
            solved_ids     = solved_ids,
            all_problems   = all_problems
        )
        ladder_recs = get_problem_ladder(
            handle         = handle,
            skill_profile  = skill_profile,
            current_rating = profile['current_rating'],
            solved_ids     = solved_ids,
            all_problems   = all_problems
        )

    return {
        "handle":              handle,
        "current_rating":      profile['current_rating'],
        "max_rating":          profile['max_rating'],
        "total_solved":        profile['total_solved'],
        "weekly_solve_rate":   profile['weekly_solve_rate'],
        "consistency_score":   profile['consistency_score'],
        "contest_count":       profile['contest_count'],
        "avg_solved_rating":   profile['avg_solved_rating'],
        "tag_diversity":       compute_tag_diversity(profile['tag_features']),
        "rating_history":      profile['rating_history'],
        "skill_profile":       skill_profile,
        "comfort_rating":      comfort_rating,
        "neglected_topics":    neglected,
        "breakthrough_topics": breakthroughs,
        "stagnation":          stagnation,
        "rating_prediction":   prediction,
        "recommendations": {
            "daily":  daily_recs,
            "ladder": ladder_recs
        }
    }

@router.get("/recommendations/{handle}")
def get_recommendations(handle: str):
    """
    Get all recommendations for a user.
    Requires /full-analysis/{handle} called first.

    Returns:
    - Daily 3 problems
    - Problem ladder (next topic sequence)
    - Unsolved from past contests
    """
    db_subs = get_submissions_from_db(handle)
    if not db_subs:
        raise HTTPException(
            status_code=404,
            detail=f"No data for {handle}. Call /full-analysis/{handle} first."
        )

    user = get_user_from_db(handle)
    if not user:
        raise HTTPException(
            status_code=404,
            detail=f"User {handle} not found"
        )

    # Reconstruct raw submissions
    raw_subs = []
    for sub in db_subs:
        raw_subs.append({
            "verdict":             sub.verdict,
            "creationTimeSeconds": sub.timestamp,
            "author": {
                "participantType": getattr(sub, 'participant_type', 'PRACTICE') or 'PRACTICE'
            },
            "problem": {
                "contestId": sub.problem_id[:-1] if sub.problem_id is not None else "",
                "index":     sub.problem_id[-1]  if sub.problem_id is not None else "",
                "rating":    sub.problem_rating,
                "tags":      sub.tags or []
            }
        })

    # Rebuild skill profile
    from ..data.data_processor import compute_tag_features
    from ..ml.skill_analysis import (
        build_skill_profile,
        compute_comfort_rating
    )

    tag_features   = compute_tag_features(raw_subs)
    skill_profile  = build_skill_profile(
        tag_features,
        user_rating=int(getattr(user, "current_rating", 0) or 0)
    )
    comfort_rating = compute_comfort_rating(tag_features)

    # Solved IDs
    solved_ids = set(
        sub.problem_id for sub in db_subs
        if getattr(sub, "verdict", None) == 'OK'
    )

    # Load problems once
    all_problems = get_problems_from_db()

    if not all_problems:
        raise HTTPException(
            status_code=500,
            detail="No problems cached. Call /api/cache-problems first."
        )

    # Generate all recommendations
    daily     = get_daily_recommendations(
        handle         = handle,
        skill_profile  = skill_profile,
        comfort_rating = comfort_rating,
        solved_ids     = solved_ids,
        all_problems   = all_problems
    )

    ladder = get_problem_ladder(
        handle         = handle,
        skill_profile  = skill_profile,
        current_rating = user.current_rating,
        solved_ids     = solved_ids,
        all_problems   = all_problems
    )

    struggled = get_struggled_problems(raw_subs, solved_ids)

    unsolved_contests = get_unsolved_from_contests(raw_subs, all_problems)

    return {
        "handle":            handle,
        "comfort_rating":    comfort_rating,
        "daily":             daily,
        "ladder":            ladder,
        "struggled":         struggled[:10],
        "unsolved_contests": unsolved_contests[:10]
    }


@router.get("/topic-set/{handle}/{tag}")
def get_topic_set_endpoint(handle: str, tag: str):
    """
    Get curated problem set for mastering one specific topic.
    Example: /api/topic-set/tourist/dp
    """
    user = get_user_from_db(handle)
    if not user:
        raise HTTPException(
            status_code=404,
            detail=f"User {handle} not found"
        )

    db_subs    = get_submissions_from_db(handle)
    solved_ids = set(
        sub.problem_id for sub in db_subs
        if getattr(sub, "verdict", None) == 'OK'
    )

    all_problems = get_problems_from_db()
    topic_set    = get_topic_problem_set(
        tag            = tag,
        current_rating = user.current_rating,
        solved_ids     = solved_ids,
        all_problems   = all_problems
    )

    return topic_set

# ── Request Models ─────────────────────────────────
class HintRequest(BaseModel):
    handle:       str
    problem_id:   str
    problem_text: str


class ResetRequest(BaseModel):
    handle:     str
    problem_id: str


# ── Hint Endpoints ─────────────────────────────────

@router.post("/hint/next")
def get_hint(request: HintRequest):
    """
    Get the next hint for a user on a specific problem.

    Automatically tracks hint level.
    First call → Hint 1
    Second call → Hint 2
    Third call → Hint 3
    Fourth call → Refused politely
    """
    if not request.problem_text.strip():
        raise HTTPException(
            status_code = 400,
            detail      = "Problem text cannot be empty"
        )

    if len(request.problem_text) < 20:
        raise HTTPException(
            status_code = 400,
            detail      = "Problem text too short. Paste the full problem statement."
        )

    result = get_next_hint(
        handle       = request.handle,
        problem_id   = request.problem_id,
        problem_text = request.problem_text
    )

    if result.get('error'):
        raise HTTPException(
            status_code = 500,
            detail      = result['error']
        )

    return result


@router.get("/hint/history/{handle}/{problem_id}")
def get_hint_history(handle: str, problem_id: str):
    """
    Get all hints given so far for a problem.
    Used when user comes back to same problem.
    """
    history = get_all_hints_so_far(handle, problem_id)
    return history


@router.post("/hint/reset")
def reset_hints(request: ResetRequest):
    """
    Reset hints for a problem.
    User wants to start fresh.
    """
    success = reset_hint_session(
        handle     = request.handle,
        problem_id = request.problem_id
    )

    if success:
        return {"message": "Hint session reset successfully"}
    else:
        raise HTTPException(
            status_code = 500,
            detail      = "Failed to reset hint session"
        )