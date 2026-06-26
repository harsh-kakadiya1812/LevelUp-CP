import sys
import os
sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from fastapi import APIRouter, HTTPException
from data.cf_api import (
    get_user_info,
    get_user_submissions,
    get_user_rating_history,
    get_all_problems,
    validate_handle
)
from data.data_processor import (
    process_user_profile,
    compute_tag_features,
    compute_tag_diversity
)
from ml.skill_analysis import (
    build_skill_profile,
    compute_comfort_rating,
    find_neglected_topics,
    find_breakthrough_topics,
    detect_stagnation
)
from db.models import (
    save_user,
    save_submissions,
    save_problems,
    get_user_from_db,
    get_submissions_from_db
)

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


@router.post("/full-analysis/{handle}")
def full_analysis(handle: str):
    """
    Complete pipeline in one call:
    Fetch from CF → process → skill analysis → return everything.
    This is the main endpoint Streamlit calls.
    """

    # Step 1: Validate
    if not validate_handle(handle):
        raise HTTPException(
            status_code=404,
            detail=f"Handle '{handle}' not found on Codeforces"
        )

    # Step 2: Fetch fresh from CF
    user_info      = get_user_info(handle)
    submissions    = get_user_submissions(handle)
    rating_history = get_user_rating_history(handle)

    # Step 3: Save to DB
    save_user(handle, user_info)
    save_submissions(handle, submissions)

    # Step 4: Process profile
    profile = process_user_profile(user_info, submissions, rating_history)

    # Step 5: Build skill analysis
    skill_profile  = build_skill_profile(profile['tag_features'])
    comfort_rating = compute_comfort_rating(profile['tag_features'])
    neglected      = find_neglected_topics(profile['tag_features'])
    breakthroughs  = find_breakthrough_topics(profile['tag_features'])
    stagnation     = detect_stagnation(skill_profile, profile['rating_history'])

    return {
        # User basics
        "handle":            handle,
        "current_rating":    profile['current_rating'],
        "max_rating":        profile['max_rating'],
        "total_solved":      profile['total_solved'],
        "weekly_solve_rate": profile['weekly_solve_rate'],
        "consistency_score": profile['consistency_score'],
        "contest_count":     profile['contest_count'],
        "avg_solved_rating": profile['avg_solved_rating'],
        "tag_diversity":     compute_tag_diversity(profile['tag_features']),

        # Rating history for chart
        "rating_history":    profile['rating_history'],

        # Skill analysis
        "skill_profile":     skill_profile,
        "comfort_rating":    comfort_rating,
        "neglected_topics":  neglected,
        "breakthrough_topics": breakthroughs,
        "stagnation":        stagnation
    }


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
                # Use stored participant_type (NEW field)
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
    skill_profile  = build_skill_profile(tag_features)
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