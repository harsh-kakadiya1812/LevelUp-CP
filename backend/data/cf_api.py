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
    Cache this locally — don't call repeatedly.
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
