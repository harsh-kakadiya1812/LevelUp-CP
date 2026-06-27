import sys
import os
sys.path.append(os.path.join(os.path.dirname(__file__), '..', 'backend'))

import requests
import time

BASE_URL = "https://codeforces.com/api"

def test_rated_list():
    """
    Test user.ratedList API.
    This is the correct alternative to contest.standings.
    Returns all active rated CF users.
    """
    print("Testing user.ratedList API...")
    print()

    try:
        res = requests.get(
            f"{BASE_URL}/user.ratedList",
            params={
                "activeOnly":      True,
                "includeRetired":  False
            },
            timeout=30
        )
        data = res.json()

        print(f"Status:        {data['status']}")

        if data['status'] == 'OK':
            users = data['result']
            print(f"Total users:   {len(users)}")
            print()

            # Show distribution across rating brackets
            brackets = {
                'Newbie (<1200)':        0,
                'Pupil (1200-1400)':     0,
                'Specialist (1400-1600)':0,
                'Expert (1600-1900)':    0,
                'CM (1900-2100)':        0,
                'Master+ (2100+)':       0
            }

            for u in users:
                r = u.get('rating', 0)
                if r < 1200:
                    brackets['Newbie (<1200)'] += 1
                elif r < 1400:
                    brackets['Pupil (1200-1400)'] += 1
                elif r < 1600:
                    brackets['Specialist (1400-1600)'] += 1
                elif r < 1900:
                    brackets['Expert (1600-1900)'] += 1
                elif r < 2100:
                    brackets['CM (1900-2100)'] += 1
                else:
                    brackets['Master+ (2100+)'] += 1

            print("Rating Distribution:")
            for bracket, count in brackets.items():
                bar = '█' * (count // 100)
                print(f"  {bracket:25s}: {count:5d}  {bar}")

            print()
            print("Sample handles:")
            for u in users[:10]:
                print(f"  {u['handle']:<20s} rating: {u.get('rating', '?')}")

            return [u['handle'] for u in users]
        else:
            print(f"Failed: {data.get('comment')}")
            return []

    except Exception as e:
        print(f"Exception: {e}")
        return []


def test_contest_standings_fixed():
    """
    Test contest.standings with ONLY contestId (no extra params).
    This is the new requirement from CF.
    """
    print()
    print("Testing contest.standings (fixed - no extra params)...")

    # Use a known old contest that definitely exists
    contest_id = 1800

    try:
        # CORRECT: only contestId, no from/count/showUnofficial
        url = f"{BASE_URL}/contest.standings?contestId={contest_id}"
        print(f"URL: {url}")

        res  = requests.get(url, timeout=20)
        data = res.json()

        print(f"Status:  {data['status']}")

        if data['status'] == 'OK':
            rows    = data['result']['rows']
            handles = [
                r['party']['members'][0]['handle']
                for r in rows
                if r['party'].get('members')
            ]
            print(f"Rows returned: {len(rows)}")
            print(f"Sample handles: {handles[:5]}")
        else:
            print(f"Comment: {data.get('comment')}")

    except Exception as e:
        print(f"Exception: {e}")


if __name__ == "__main__":
    # Test 1: user.ratedList (our new primary method)
    handles = test_rated_list()

    if handles:
        print()
        print(f"✅ user.ratedList works perfectly")
        print(f"✅ Got {len(handles)} handles")
        print(f"✅ This is our new handle collection method")
    else:
        print("❌ user.ratedList failed")

    print()
    print("=" * 50)

    # Test 2: Fixed contest.standings
    test_contest_standings_fixed()