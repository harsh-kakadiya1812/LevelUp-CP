import joblib
import json
import numpy as np
import os

# ── Load Models at Startup ────────────────────────

# Build path relative to this file
BASE_DIR   = os.path.dirname(os.path.dirname(os.path.dirname(__file__)))
MODELS_DIR = os.path.join(BASE_DIR, 'models')

def load_models():
    """
    Load trained models and metadata.
    Called once at server startup.
    """
    try:
        model_3m  = joblib.load(os.path.join(MODELS_DIR, 'rating_model_3m.pkl'))
        model_6m  = joblib.load(os.path.join(MODELS_DIR, 'rating_model_6m.pkl'))

        with open(os.path.join(MODELS_DIR, 'model_metadata.json'), 'r') as f:
            metadata = json.load(f)

        print(f"✅ Rating models loaded")
        print(f"   Features: {metadata['features']}")
        print(f"   MAE 3M:   {metadata['mae_3m']:.1f} rating points")
        return model_3m, model_6m, metadata

    except FileNotFoundError as e:
        print(f"❌ Model files not found: {e}")
        print("   Run the Jupyter notebook to train models first")
        return None, None, None


# Load once at module import
MODEL_3M, MODEL_6M, METADATA = load_models()


# ── Feature Extraction ────────────────────────────

def extract_features(profile, skill_profile):
    """
    Extract model input features from a user profile.

    Takes the output from data_processor.process_user_profile()
    and ml.skill_analysis.build_skill_profile() and converts
    them into the exact feature vector the model expects.
    """
    if METADATA is None:
        return None

    feature_map = {
        'current_rating':      profile.get('current_rating', 0),
        'solve_rate_per_week': profile.get('weekly_solve_rate', 0),
        'tag_diversity':       profile.get('tag_diversity', 0),
        'avg_problem_rating':  profile.get('avg_solved_rating', 0),
        'contest_frequency':   compute_contest_frequency(profile),
        'consistency_score':   profile.get('consistency_score', 0),
        'weak_tag_count':      skill_profile['summary'].get('weak', 0),
        'rating_volatility':   compute_rating_volatility(profile),
        'recent_performance':  compute_recent_performance(profile),
        'total_ac_count':      profile.get('total_solved', 0)
    }

    # Build feature vector in the exact order the model expects
    features = METADATA['features']
    vector   = [feature_map.get(f, 0) for f in features]

    return vector


def compute_contest_frequency(profile):
    """
    Contests per month in the last 3 months.
    Derived from rating history.
    """
    import time
    rating_history = profile.get('rating_history', [])
    if not rating_history:
        return 0.0

    now          = time.time()
    three_months = now - (90 * 24 * 60 * 60)
    recent       = [
        c for c in rating_history
        if c.get('timestamp', 0) > three_months
    ]

    return round(len(recent) / 3, 2)


def compute_rating_volatility(profile):
    """
    Standard deviation of rating changes in last 10 contests.
    High volatility = inconsistent performance.
    """
    rating_history = profile.get('rating_history', [])
    if len(rating_history) < 3:
        return 0.0

    recent_10 = rating_history[-10:]
    changes   = [
        c['new_rating'] - c['old_rating']
        for c in recent_10
        if 'new_rating' in c and 'old_rating' in c
    ]

    if not changes:
        return 0.0

    mean     = sum(changes) / len(changes)
    variance = sum((c - mean) ** 2 for c in changes) / len(changes)
    return round(variance ** 0.5, 1)


def compute_recent_performance(profile):
    """
    Average rating change in last 5 contests.
    Positive = on upward trend.
    """
    rating_history = profile.get('rating_history', [])
    if len(rating_history) < 2:
        return 0.0

    last_5 = rating_history[-5:]
    changes = [
        c['new_rating'] - c['old_rating']
        for c in last_5
        if 'new_rating' in c and 'old_rating' in c
    ]

    if not changes:
        return 0.0

    return round(sum(changes) / len(changes), 1)


# ── Main Prediction Function ──────────────────────

def predict_rating(profile, skill_profile):
    """
    Given a user's profile and skill analysis,
    predict their rating in 3 and 6 months.

    Returns a dict with:
    - 3_months: {low, mid, high}
    - 6_months: {low, mid, high}
    - features_used: what values were passed to model
    - explanation: human readable breakdown
    """
    if MODEL_3M is None or MODEL_6M is None:
        return {
            "error": "Models not loaded. Train models first.",
            "3_months": None,
            "6_months": None
        }

    # Extract features
    feature_vector = extract_features(profile, skill_profile)
    if feature_vector is None:
        return {
            "error": "Could not extract features from profile",
            "3_months": None,
            "6_months": None
        }

    # Get MAE for confidence interval
    # METADATA may be None; guard against that
    _meta = METADATA or {}
    mae_3m = _meta.get('mae_3m', 100)
    mae_6m = _meta.get('mae_6m', 130)

    # Make predictions
    X         = [feature_vector]
    pred_3m   = float(MODEL_3M.predict(X)[0])
    pred_6m   = float(MODEL_6M.predict(X)[0])

    # Round to nearest 10 (more honest than exact number)
    pred_3m_rounded = round(pred_3m / 10) * 10
    pred_6m_rounded = round(pred_6m / 10) * 10

    # Build feature breakdown for explanation
    # METADATA may be None or missing 'features'; fall back to generated names
    features_list = (_meta.get('features') if isinstance(_meta, dict) else None) or []
    if not features_list:
        features_list = [f'feature_{i}' for i in range(len(feature_vector))]

    features_used = {f: v for f, v in zip(features_list, feature_vector)}

    # Generate explanation
    explanation = generate_explanation(
        profile,
        skill_profile,
        features_used,
        pred_3m,
        mae_3m
    )

    return {
        "3_months": {
            "low":  int(pred_3m_rounded - mae_3m),
            "mid":  int(pred_3m_rounded),
            "high": int(pred_3m_rounded + mae_3m)
        },
        "6_months": {
            "low":  int(pred_6m_rounded - mae_6m),
            "mid":  int(pred_6m_rounded),
            "high": int(pred_6m_rounded + mae_6m)
        },
        "current_rating":  profile.get('current_rating', 0),
        "features_used":   features_used,
        "model_mae_3m":    round(mae_3m, 1),
        "model_mae_6m":    round(mae_6m, 1),
        "explanation":     explanation,
        "confidence_note": (
            f"Model accuracy: ±{mae_3m:.0f} rating points on average. "
            f"Trained on {_meta.get('n_training', 0)} real CF user snapshots."
        )
    }


def generate_explanation(profile, skill_profile, features_used, pred_3m, mae):
    """
    Generate human readable explanation of what's driving
    the prediction up or down.
    """
    current  = profile.get('current_rating', 0)
    change   = pred_3m - current
    factors  = []

    # Analyze each feature
    solve_rate = features_used.get('solve_rate_per_week', 0)
    if solve_rate >= 7:
        factors.append({
            "feature": "Practice Volume",
            "impact":  "positive",
            "detail":  f"Solving {solve_rate:.1f} problems/week is excellent"
        })
    elif solve_rate >= 3:
        factors.append({
            "feature": "Practice Volume",
            "impact":  "neutral",
            "detail":  f"Solving {solve_rate:.1f} problems/week is decent, aim for 7+"
        })
    else:
        factors.append({
            "feature": "Practice Volume",
            "impact":  "negative",
            "detail":  f"Only {solve_rate:.1f} problems/week — not enough for rating growth"
        })

    weak_count = features_used.get('weak_tag_count', 0)
    if weak_count == 0:
        factors.append({
            "feature": "Weak Topics",
            "impact":  "positive",
            "detail":  "No weak topics detected — well-rounded profile"
        })
    elif weak_count <= 3:
        factors.append({
            "feature": "Weak Topics",
            "impact":  "neutral",
            "detail":  f"{weak_count} weak topics — addressable with focused practice"
        })
    else:
        factors.append({
            "feature": "Weak Topics",
            "impact":  "negative",
            "detail":  f"{weak_count} weak topics — major bottleneck for rating growth"
        })

    contest_freq = features_used.get('contest_frequency', 0)
    if contest_freq >= 2:
        factors.append({
            "feature": "Contest Frequency",
            "impact":  "positive",
            "detail":  f"Participating in {contest_freq:.1f} contests/month is great"
        })
    elif contest_freq >= 1:
        factors.append({
            "feature": "Contest Frequency",
            "impact":  "neutral",
            "detail":  f"{contest_freq:.1f} contests/month — try to increase to 2+"
        })
    else:
        factors.append({
            "feature": "Contest Frequency",
            "impact":  "negative",
            "detail":  "Rarely contesting — contests are essential for rating gain"
        })

    consistency = features_used.get('consistency_score', 0)
    if consistency >= 0.7:
        factors.append({
            "feature": "Consistency",
            "impact":  "positive",
            "detail":  f"Very consistent practice pattern (score: {consistency:.2f})"
        })
    elif consistency >= 0.4:
        factors.append({
            "feature": "Consistency",
            "impact":  "neutral",
            "detail":  f"Moderate consistency (score: {consistency:.2f}) — practice more evenly"
        })
    else:
        factors.append({
            "feature": "Consistency",
            "impact":  "negative",
            "detail":  f"Inconsistent practice (score: {consistency:.2f}) — bursty practice is less effective"
        })

    recent_perf = features_used.get('recent_performance', 0)
    if recent_perf > 50:
        factors.append({
            "feature": "Recent Trend",
            "impact":  "positive",
            "detail":  f"On an upward trend (+{recent_perf:.0f} avg per contest recently)"
        })
    elif recent_perf < -50:
        factors.append({
            "feature": "Recent Trend",
            "impact":  "negative",
            "detail":  f"Downward trend ({recent_perf:.0f} avg per contest recently)"
        })

    # What to do to improve
    suggestions = []
    if solve_rate < 7:
        suggestions.append(f"Increase to 7+ problems/week (currently {solve_rate:.1f})")
    if weak_count > 3:
        top_weak = skill_profile.get('weak', [])[:3]
        suggestions.append(f"Fix weak topics: {', '.join(top_weak)}")
    if contest_freq < 2:
        suggestions.append("Participate in at least 2 contests per month")
    if consistency < 0.5:
        suggestions.append("Practice every day instead of in bursts")

    return {
        "change_predicted": round(change),
        "direction":        "increase" if change > 0 else "decrease",
        "factors":          factors,
        "suggestions":      suggestions,
        "summary": (
            f"Your rating is predicted to "
            f"{'increase' if change > 0 else 'decrease'} by "
            f"~{abs(change):.0f} points in 3 months"
        )
    }


# # ── Test ──────────────────────────────────────────

# if __name__ == "__main__":
#     if MODEL_3M is None:
#         print("No model found. Train it in Jupyter notebook first.")
#         exit()

#     # Test with dummy profile
#     dummy_profile = {
#         'current_rating':    1350,
#         'weekly_solve_rate': 5.2,
#         'avg_solved_rating': 1280,
#         'consistency_score': 0.65,
#         'total_solved':      423,
#         'tag_diversity':     14,
#         'rating_history': [
#             {'timestamp': 1700000000, 'new_rating': 1300, 'old_rating': 1250},
#             {'timestamp': 1702000000, 'new_rating': 1350, 'old_rating': 1300},
#         ]
#     }

#     dummy_skill = {
#         'summary': {'weak': 4, 'moderate': 8, 'strong': 3},
#         'weak': ['graphs', 'dsu', 'flows', 'trees']
#     }

#     result = predict_rating(dummy_profile, dummy_skill)

#     print("Rating Prediction Test:")
#     print(f"Current: {result['current_rating']}")
#     print()
#     print(f"3 Months: {result['3_months']['low']} – {result['3_months']['high']}")
#     print(f"          (mid: {result['3_months']['mid']})")
#     print()
#     print(f"6 Months: {result['6_months']['low']} – {result['6_months']['high']}")
#     print()
#     print(f"Summary: {result['explanation']['summary']}")
#     print()
#     print("Factors:")
#     for f in result['explanation']['factors']:
#         icon = "✅" if f['impact'] == 'positive' else ("⚠️" if f['impact'] == 'neutral' else "❌")
#         print(f"  {icon} {f['feature']}: {f['detail']}")
#     print()
#     print("Suggestions:")
#     for s in result['explanation']['suggestions']:
#         print(f"  → {s}")