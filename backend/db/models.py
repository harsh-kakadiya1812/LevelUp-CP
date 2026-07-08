from sqlalchemy import (
    create_engine, Column, String, Integer,
    Float, BigInteger, ARRAY, JSON, DateTime, Date
)
from sqlalchemy.orm import declarative_base, sessionmaker
from sqlalchemy.sql import func
import os
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

load_dotenv()

DATABASE_URL = os.getenv("DATABASE_URL")
if not DATABASE_URL:
    raise ValueError("DATABASE_URL environment variable is not set")

engine       = create_engine(DATABASE_URL)
SessionLocal = sessionmaker(bind=engine)
Base         = declarative_base()


# ── Table Definitions ─────────────────────────────

class User(Base):
    __tablename__  = "users"
    handle         = Column(String, primary_key=True)
    current_rating = Column(Integer)
    max_rating     = Column(Integer)
    fetched_at     = Column(DateTime, server_default=func.now())


class Submission(Base):
    __tablename__    = "submissions"
    id               = Column(Integer, primary_key=True, autoincrement=True)
    handle           = Column(String)
    problem_id       = Column(String)
    problem_rating   = Column(Integer)
    tags             = Column(ARRAY(String))
    verdict          = Column(String)
    timestamp        = Column(BigInteger)
    language         = Column(String)
    participant_type = Column(String, default='PRACTICE')


class Problem(Base):
    __tablename__ = "problems"
    problem_id    = Column(String, primary_key=True)
    title         = Column(String)
    rating        = Column(Integer)
    tags          = Column(ARRAY(String))


class HintSession(Base):
    __tablename__ = "hint_sessions"
    id            = Column(Integer, primary_key=True, autoincrement=True)
    handle        = Column(String)
    problem_id    = Column(String)
    hint_level    = Column(Integer, default=0)
    conversation  = Column(JSON, default=list)
    updated_at    = Column(DateTime, server_default=func.now())


class TrainingData(Base):
    __tablename__       = "training_data"
    id                  = Column(Integer, primary_key=True, autoincrement=True)
    handle              = Column(String)
    snapshot_date       = Column(Date)
    current_rating      = Column(Integer)
    solve_rate_per_week = Column(Float)
    tag_diversity       = Column(Integer)
    avg_problem_rating  = Column(Float)
    contest_frequency   = Column(Float)
    consistency_score   = Column(Float)
    weak_tag_count      = Column(Integer)
    label_3m            = Column(Integer)
    label_6m            = Column(Integer)


# ── Database Operations ───────────────────────────

def save_user(handle, user_info):
    db = SessionLocal()
    try:
        user = db.query(User).filter(User.handle == handle).first()
        if user:
            user.current_rating = user_info.get('rating', 0)
            user.max_rating     = user_info.get('maxRating', 0)
        else:
            user = User(
                handle         = handle,
                current_rating = user_info.get('rating', 0),
                max_rating     = user_info.get('maxRating', 0)
            )
            db.add(user)
        db.commit()
        print(f"✅ User {handle} saved")
    except Exception as e:
        db.rollback()
        print(f"❌ Error saving user: {e}")
    finally:
        db.close()


def save_submissions(handle, submissions):
    db = SessionLocal()
    try:
        # Delete old submissions for this user first
        db.query(Submission).filter(
            Submission.handle == handle
        ).delete()

        for sub in submissions:
            problem          = sub.get('problem', {})
            contest_id       = problem.get('contestId', '')
            index            = problem.get('index', '')
            author           = sub.get('author', {})

            # NEW: store participant type
            participant_type = author.get('participantType', 'PRACTICE')

            submission = Submission(
                handle           = handle,
                problem_id       = f"{contest_id}{index}",
                problem_rating   = problem.get('rating', 0),
                tags             = problem.get('tags', []),
                verdict          = sub.get('verdict', ''),
                timestamp        = sub.get('creationTimeSeconds', 0),
                language         = sub.get('programmingLanguage', ''),
                participant_type = participant_type   # NEW
            )
            db.add(submission)

        db.commit()
        print(f"✅ {len(submissions)} submissions saved for {handle}")
    except Exception as e:
        db.rollback()
        print(f"❌ Error saving submissions: {e}")
    finally:
        db.close()


def save_problems(problems):
    db = SessionLocal()
    try:
        saved = 0
        for prob in problems:
            contest_id = prob.get('contestId', '')
            index      = prob.get('index', '')
            problem_id = f"{contest_id}{index}"

            existing = db.query(Problem).filter(
                Problem.problem_id == problem_id
            ).first()

            if not existing:
                problem = Problem(
                    problem_id = problem_id,
                    title      = prob.get('name', ''),
                    rating     = prob.get('rating', 0),
                    tags       = prob.get('tags', [])
                )
                db.add(problem)
                saved += 1

        db.commit()
        print(f"✅ {saved} new problems cached")
    except Exception as e:
        db.rollback()
        print(f"❌ Error saving problems: {e}")
    finally:
        db.close()


def get_user_from_db(handle):
    db = SessionLocal()
    try:
        return db.query(User).filter(User.handle == handle).first()
    finally:
        db.close()


def get_submissions_from_db(handle):
    db = SessionLocal()
    try:
        return db.query(Submission).filter(
            Submission.handle == handle
        ).all()
    finally:
        db.close()


def get_all_problems_from_db():
    db = SessionLocal()
    try:
        return db.query(Problem).all()
    finally:
        db.close()


# def test_connection():
#     from sqlalchemy import text
#     try:
#         with engine.connect() as conn:
#             conn.execute(text("SELECT 1"))
#             print("Database connected")
#             return True
#     except Exception as e:
#         print(f"Connection failed: {e}")
#         return False


def create_tables():
    Base.metadata.create_all(engine)
    print("All tables verified")


# if __name__ == "__main__":
#     test_connection()
#     create_tables()