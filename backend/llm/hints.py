import os
import json
import sys
from pathlib import Path

try:
    from dotenv import load_dotenv
except ModuleNotFoundError:
    def load_dotenv(*args, **kwargs):
        for candidate in Path(__file__).resolve().parents:
            env_path = candidate / ".env"
            if not env_path.exists():
                continue

            for line in env_path.read_text(encoding="utf-8").splitlines():
                line = line.strip()
                if not line or line.startswith("#") or "=" not in line:
                    continue

                key, value = line.split("=", 1)
                os.environ.setdefault(key.strip(), value.strip().strip('"').strip("'"))

            return True

        return False

if __package__ is None or __package__ == "":
    sys.path.append(str(Path(__file__).resolve().parents[1]))

from db.models import SessionLocal, HintSession
try:
    # Import dynamically to avoid static import-time resolution errors
    import importlib
    genai = importlib.import_module("google.generativeai")
except Exception:
    genai = None
from sqlalchemy import and_
from datetime import datetime

load_dotenv()

# Configure Gemini
if genai is not None:
    genai.configure(api_key=os.getenv("GEMINI_API_KEY"))


# ── System Prompt ─────────────────────────────────
# This is the most important part of the hint system.
# It tells Gemini exactly how to behave as a coach.

HINT_SYSTEM_PROMPT = """
You are a competitive programming coach helping a student 
who is stuck on a problem. Your job is to guide them to 
the solution themselves, not to solve it for them.

You must follow these rules strictly, no exceptions:

RULE 1: Never reveal the full solution or approach in one go.
RULE 2: Never write any code whatsoever.
RULE 3: Give ONLY the hint level that is asked. Nothing more.
RULE 4: Each hint must build on the previous hint.
RULE 5: After Hint 3, refuse all further hints politely.

Hint 1 Guidelines:
- Give only a very gentle nudge
- Point toward the general category of approach
- Do NOT mention specific algorithms by name
- Example: "Think about what happens when you process 
  elements from smallest to largest"
- Maximum 2-3 sentences

Hint 2 Guidelines:  
- Be more specific than Hint 1
- You can now mention algorithm categories
- Still do not give the full approach
- Example: "Consider using a stack data structure. 
  Think about what you would push and when you would pop"
- Maximum 3-4 sentences

Hint 3 Guidelines:
- Give the near-complete approach in plain English
- Explain the key insight clearly
- Still no code, no full implementation details
- Example: "Use a monotonic stack. Iterate left to right, 
  for each element pop all smaller elements from the stack,
  the answer for each popped element is the current index
  minus the stack top minus one"
- Maximum 5-6 sentences

If user asks for Hint 4 or beyond:
- Respond with exactly this:
  "You have all the hints you need. Try implementing 
  Hint 3 step by step. If you are truly stuck after 
  trying, read the editorial. You are closer than 
  you think — keep going!"

Remember: A good coach never does the work for the student.
"""


# ── Database Operations ───────────────────────────

def get_hint_session(handle, problem_id):
    """
    Fetch existing hint session from DB.
    Returns None if no session exists yet.
    """
    db = SessionLocal()
    try:
        session = db.query(HintSession).filter(
            and_(
                HintSession.handle     == handle,
                HintSession.problem_id == problem_id
            )
        ).first()

        if not session:
            return None

        return {
            "hint_level":   session.hint_level,
            "conversation": session.conversation or []
        }

    except Exception as e:
        print(f"Error fetching hint session: {e}")
        return None
    finally:
        db.close()


def save_hint_session(handle, problem_id, hint_level, conversation):
    """
    Save or update hint session in DB.
    This is how hints persist across browser refreshes.
    """
    db = SessionLocal()
    try:
        # Check if session already exists
        existing = db.query(HintSession).filter(
            and_(
                HintSession.handle     == handle,
                HintSession.problem_id == problem_id
            )
        ).first()

        if existing:
            # Update existing session
            existing.hint_level   = hint_level
            existing.conversation = conversation
            existing.updated_at   = datetime.now()
        else:
            # Create new session
            new_session = HintSession(
                handle       = handle,
                problem_id   = problem_id,
                hint_level   = hint_level,
                conversation = conversation
            )
            db.add(new_session)

        db.commit()

    except Exception as e:
        db.rollback()
        print(f"Error saving hint session: {e}")
    finally:
        db.close()


def reset_hint_session(handle, problem_id):
    """
    Reset hints for a specific problem.
    Called when user wants to start over.
    """
    db = SessionLocal()
    try:
        db.query(HintSession).filter(
            and_(
                HintSession.handle     == handle,
                HintSession.problem_id == problem_id
            )
        ).delete()
        db.commit()
        return True
    except Exception as e:
        db.rollback()
        print(f"Error resetting session: {e}")
        return False
    finally:
        db.close()


# ── Core Hint Function ────────────────────────────

def get_next_hint(handle, problem_id, problem_text):
    """
    Main function: get the next hint for a user on a problem.

    Args:
        handle:       CF handle of the user
        problem_id:   unique identifier for the problem
                      (e.g. "1234A" or any string the user provides)
        problem_text: full problem statement text

    Returns:
        dict with:
        - hint_number:  which hint this is (1, 2, 3)
        - hint_text:    the actual hint content
        - is_final:     True if this was the last allowed hint
        - message:      status message
    """

    # ── Step 1: Load existing session ─────────────
    session = get_hint_session(handle, problem_id)

    if session is None:
        # First time this user is asking about this problem
        current_hint_level = 0
        conversation       = []
    else:
        current_hint_level = session['hint_level']
        conversation       = session['conversation']

    # ── Step 2: Check if already at max hints ─────
    MAX_HINTS = 3

    if current_hint_level >= MAX_HINTS:
        return {
            "hint_number": current_hint_level,
            "hint_text": (
                "You have already received all 3 hints for this problem. "
                "Try implementing Hint 3 step by step. "
                "If you are truly stuck after trying, read the editorial. "
                "You are closer than you think — keep going!"
            ),
            "is_final":    True,
            "already_max": True,
            "hints_remaining": 0,
            "message":     f"Maximum {MAX_HINTS} hints reached"
        }

    # ── Step 3: Increment hint level ──────────────
    next_hint_number = current_hint_level + 1

    # ── Step 4: Build conversation for Gemini ─────
    # First message always includes the problem
    if not conversation:
        conversation.append({
            "role":    "user",
            "content": (
                f"I am stuck on this competitive programming problem. "
                f"Please give me Hint {next_hint_number}.\n\n"
                f"Problem Statement:\n{problem_text}"
            )
        })
    else:
        # Add next hint request to existing conversation
        conversation.append({
            "role":    "user",
            "content": f"I am still stuck. Please give me Hint {next_hint_number}."
        })

    # ── Step 5: Call Gemini API ───────────────────
    try:
        if genai is None:
            raise RuntimeError("Google Generative AI library not available")
        
        model = genai.GenerativeModel(
            model_name        = "gemini-3.5-flash",
            system_instruction = HINT_SYSTEM_PROMPT
        )

        # Convert conversation to Gemini format
        gemini_history = []
        for msg in conversation[:-1]:   # all except last message
            gemini_history.append({
                "role":  msg["role"],
                "parts": [msg["content"]]
            })

        # Start chat with history
        chat = model.start_chat(history=gemini_history)

        # Send the latest message
        response = chat.send_message(
            conversation[-1]["content"]
        )

        hint_text = response.text.strip()

    except Exception as e:
        print(f"Gemini API error: {e}")
        return {
            "hint_number": next_hint_number,
            "hint_text":   None,
            "is_final":    False,
            "already_max": False,
            "error":       f"AI service error: {str(e)}",
            "hints_remaining": MAX_HINTS - next_hint_number,
            "message":     "Failed to generate hint"
        }

    # ── Step 6: Add Gemini response to history ────
    conversation.append({
        "role":    "model",
        "content": hint_text
    })

    # ── Step 7: Save updated session to DB ────────
    save_hint_session(
        handle       = handle,
        problem_id   = problem_id,
        hint_level   = next_hint_number,
        conversation = conversation
    )

    # ── Step 8: Return result ──────────────────────
    is_final = (next_hint_number >= MAX_HINTS)

    return {
        "hint_number":   next_hint_number,
        "hint_text":     hint_text,
        "is_final":      is_final,
        "already_max":   False,
        "hints_remaining": MAX_HINTS - next_hint_number,
        "message":       (
            f"Hint {next_hint_number} of {MAX_HINTS}"
            if not is_final
            else "This is your final hint. Try to implement it!"
        )
    }


def get_all_hints_so_far(handle, problem_id):
    """
    Returns all hints given so far for a problem.
    Used to restore hint history when user comes back.
    """
    session = get_hint_session(handle, problem_id)

    if not session or not session['conversation']:
        return {
            "hint_level":  0,
            "hints":       [],
            "has_session": False
        }

    # Extract only the model (Gemini) responses from conversation
    hints = []
    hint_number = 0

    for msg in session['conversation']:
        if msg['role'] == 'model':
            hint_number += 1
            hints.append({
                "hint_number": hint_number,
                "hint_text":   msg['content']
            })

    return {
        "hint_level":  session['hint_level'],
        "hints":       hints,
        "has_session": True
    }


# # ── Test ──────────────────────────────────────────

# if __name__ == "__main__":
#     print("Testing Progressive Hint System...")
#     print()

#     # Test problem (classic two-sum style)
#     test_problem = """
#     Given an array of n integers and a target sum k,
#     find if there exist two elements in the array
#     whose sum equals k.
    
#     Constraints: 1 <= n <= 100000, -10^9 <= a[i] <= 10^9
#     """

#     handle     = "test_user"
#     problem_id = "test_001"

#     # Reset any existing session
#     reset_hint_session(handle, problem_id)

#     # Test Hint 1
#     print("=== Getting Hint 1 ===")
#     result = get_next_hint(handle, problem_id, test_problem)
#     print(f"Hint {result['hint_number']}: {result['hint_text']}")
#     print(f"Is Final: {result['is_final']}")
#     print(f"Remaining: {result['hints_remaining']}")
#     print()

#     # Test Hint 2
#     print("=== Getting Hint 2 ===")
#     result = get_next_hint(handle, problem_id, test_problem)
#     print(f"Hint {result['hint_number']}: {result['hint_text']}")
#     print()

#     # Test Hint 3
#     print("=== Getting Hint 3 ===")
#     result = get_next_hint(handle, problem_id, test_problem)
#     print(f"Hint {result['hint_number']}: {result['hint_text']}")
#     print(f"Is Final: {result['is_final']}")
#     print()

#     # Test asking for Hint 4 (should be refused)
#     print("=== Trying Hint 4 (should be refused) ===")
#     result = get_next_hint(handle, problem_id, test_problem)
#     print(f"Response: {result['hint_text']}")
#     print(f"Already Max: {result['already_max']}")
#     print()

#     # Test restoring session
#     print("=== Restoring Session ===")
#     history = get_all_hints_so_far(handle, problem_id)
#     print(f"Hint level: {history['hint_level']}")
#     print(f"Total hints given: {len(history['hints'])}")