import requests
import time

BASE_URL = "https://codeforces.com/api"

def get_user_info(handle):
    """
    Fetch basic user info: rating, max rating, name etc.
    """
    try:
        url = f"{BASE_URL}/user.info?handles={handle}"
        response = requests.get(url, timeout=10)
        data = response.json()

        if data['status'] != 'OK':
            return None

        return data['result'][0]

    except Exception as e:
        print(f"Error fetching user info for {handle}: {e}")
        return None


def get_user_submissions(handle):
    """
    Fetch ALL submissions ever made by the user.
    Each submission has: problem name, tags, rating,
    verdict (AC/WA/TLE etc), timestamp, language.
    """
    try:
        url = f"{BASE_URL}/user.status?handle={handle}&from=1&count=10000"
        response = requests.get(url, timeout=30)
        data = response.json()

        if data['status'] != 'OK':
            return []

        return data['result']

    except Exception as e:
        print(f"Error fetching submissions for {handle}: {e}")
        return []


def get_user_rating_history(handle):
    """
    Fetch full contest history: every contest the user
    participated in and their rating change.
    """
    try:
        url = f"{BASE_URL}/user.rating?handle={handle}"
        response = requests.get(url, timeout=10)
        data = response.json()

        if data['status'] != 'OK':
            return []

        return data['result']

    except Exception as e:
        print(f"Error fetching rating history for {handle}: {e}")
        return []


def get_all_problems():
    """
    Fetch ALL problems from Codeforces problemset.
    Returns list of problems with tags and ratings.
    Used for recommendations.
    """
    try:
        url = f"{BASE_URL}/problemset.problems"
        response = requests.get(url, timeout=30)
        data = response.json()

        if data['status'] != 'OK':
            return []

        return data['result']['problems']

    except Exception as e:
        print(f"Error fetching problems: {e}")
        return []


def validate_handle(handle):
    """
    Check if a CF handle actually exists.
    Returns True if valid, False if not.
    """
    result = get_user_info(handle)
    return result is not None

def get_all_tags():
    """
    Returns the complete list of all Codeforces problem tags.
    These are hardcoded because CF doesn't have an API for just tags.
    Updated as of 2024 — covers all tags that appear in CF problemset.
    """
    return [
        # Algorithms
        "dp",
        "greedy",
        "graphs",
        "math",
        "brute force",
        "binary search",
        "trees",
        "strings",
        "number theory",
        "geometry",
        "combinatorics",
        "two pointers",
        "sorting",
        "dfs and similar",
        "bfs",
        "data structures",
        "implementation",
        "divide and conquer",

        # Data Structures
        "dsu",
        "segment tree",
        "fenwick tree",
        "binary indexed tree",
        "sparse table",
        "stack",
        "queue",
        "deque",
        "linked list",
        "hashing",

        # Graph Algorithms
        "shortest paths",
        "flows",
        "bipartite",
        "matching",
        "strongly connected components",
        "topological sort",
        "minimum spanning tree",
        "euler path",
        "2-sat",
        "lca",
        "centroid decomposition",
        "heavy-light decomposition",

        # String Algorithms
        "string suffix structures",
        "aho-corasick",
        "kmp",
        "z-function",
        "suffix array",
        "palindromes",

        # Math
        "probabilities",
        "matrices",
        "fft",
        "game theory",
        "chinese remainder theorem",
        "meet-in-the-middle",
        "gaussian elimination",
        "inclusion-exclusion",
        "mobius function",
        "modular arithmetic",

        # DP Types
        "bitmask",
        "dp on trees",
        "dp on graphs",
        "knapsack",
        "digit dp",
        "sos dp",

        # Advanced
        "interactive",
        "constructive algorithms",
        "randomized algorithms",
        "schedules",
        "sqrt decomposition",
        "convex hull",
        "line sweep",
        "ternary search",
        "expression parsing",
        "tries"
    ]