"""
Problem Ladder — Topic Prerequisites and Learning Sequences.

Defines which topics build on others so recommendations
follow a logical learning order rather than random picks.

This is manually curated based on competitive programming
pedagogy — topics are ordered by dependency and difficulty.
"""


# ── Topic Prerequisite Graph ──────────────────────
# Format: topic → list of topics that should be learned first
# If user is weak in a topic, check if prerequisites are strong first

PREREQUISITES = {
    # ── Graph Topics ──────────────────────────────
    "dfs and similar":        ["graphs", "recursion"],
    "bfs":                    ["graphs", "queues"],
    "shortest paths":         ["graphs", "bfs", "greedy"],
    "minimum spanning tree":  ["graphs", "dsu", "greedy"],
    "topological sort":       ["graphs", "dfs and similar"],
    "strongly connected components": ["graphs", "dfs and similar"],
    "bipartite":              ["graphs", "bfs"],
    "flows":                  ["graphs", "shortest paths", "bfs"],
    "matching":               ["graphs", "flows"],
    "2-sat":                  ["graphs", "strongly connected components"],
    "euler path":             ["graphs", "dfs and similar"],
    "lca":                    ["trees", "dfs and similar"],
    "centroid decomposition": ["trees", "dfs and similar"],
    "heavy-light decomposition": ["trees", "lca"],

    # ── Data Structure Topics ─────────────────────
    "dsu":                    ["graphs", "data structures"],
    "segment tree":           ["data structures", "binary search"],
    "fenwick tree":           ["data structures", "prefix sums"],
    "sparse table":           ["data structures", "binary search"],
    "sqrt decomposition":     ["data structures", "segment tree"],
    "convex hull":            ["geometry", "sorting"],

    # ── DP Topics ─────────────────────────────────
    "dp":                     ["greedy", "math"],
    "bitmask":                ["dp", "math"],
    "digit dp":               ["dp", "math", "number theory"],
    "dp on trees":            ["dp", "trees", "dfs and similar"],
    "sos dp":                 ["dp", "bitmask"],
    "knapsack":               ["dp"],

    # ── String Topics ─────────────────────────────
    "string suffix structures": ["strings", "binary search"],
    "aho-corasick":           ["strings", "string suffix structures"],
    "suffix array":           ["strings", "sorting", "binary search"],
    "z-function":             ["strings"],
    "kmp":                    ["strings"],

    # ── Math Topics ───────────────────────────────
    "number theory":          ["math"],
    "combinatorics":          ["math", "number theory"],
    "probabilities":          ["math", "combinatorics"],
    "matrices":               ["math"],
    "fft":                    ["math", "matrices"],
    "game theory":            ["math", "dp"],
    "chinese remainder theorem": ["math", "number theory"],
    "gaussian elimination":   ["math", "matrices"],
    "inclusion-exclusion":    ["math", "combinatorics"],
    "meet-in-the-middle":     ["binary search", "brute force"],

    # ── Advanced Topics ───────────────────────────
    "interactive":            ["binary search", "greedy"],
    "constructive algorithms": ["greedy", "math"],
    "randomized algorithms":  ["math", "data structures"],
    "ternary search":         ["binary search", "math"],
    "line sweep":             ["geometry", "sorting", "segment tree"],
    "divide and conquer":     ["binary search", "recursion"],
    "expression parsing":     ["strings", "stack"],
}


# ── Learning Sequence by Rating Level ─────────────
# Ordered curriculum: what to learn at each rating bracket

LEARNING_PATH = {
    "beginner": {
        "rating_range": (0, 1200),
        "topics_in_order": [
            "implementation",
            "brute force",
            "math",
            "sorting",
            "greedy",
            "binary search",
            "two pointers",
            "strings",
            "data structures",
        ],
        "description": "Foundation topics every CP programmer needs"
    },

    "pupil": {
        "rating_range": (1200, 1400),
        "topics_in_order": [
            "number theory",
            "graphs",
            "dfs and similar",
            "bfs",
            "trees",
            "dp",
            "combinatorics",
            "hashing",
            "constructive algorithms",
        ],
        "description": "Core algorithmic topics for 1200-1400 range"
    },

    "specialist": {
        "rating_range": (1400, 1600),
        "topics_in_order": [
            "dsu",
            "shortest paths",
            "segment tree",
            "divide and conquer",
            "bitmask",
            "game theory",
            "topological sort",
            "bipartite",
            "probabilities",
        ],
        "description": "Intermediate topics for 1400-1600 range"
    },

    "expert": {
        "rating_range": (1600, 1900),
        "topics_in_order": [
            "minimum spanning tree",
            "fenwick tree",
            "string suffix structures",
            "meet-in-the-middle",
            "matrices",
            "strongly connected components",
            "2-sat",
            "lca",
            "digit dp",
            "dp on trees",
        ],
        "description": "Advanced topics for 1600-1900 range"
    },

    "candidate_master": {
        "rating_range": (1900, 2100),
        "topics_in_order": [
            "flows",
            "matching",
            "suffix array",
            "centroid decomposition",
            "heavy-light decomposition",
            "sqrt decomposition",
            "convex hull",
            "fft",
            "aho-corasick",
        ],
        "description": "Expert-level topics for 1900-2100 range"
    }
}


# ── Topic-Based Problem Sets ──────────────────────
# Curated difficulty progressions per major topic
# Format: tag → [list of (rating, description) pairs]

TOPIC_PROBLEM_SETS = {
    "dp": {
        "title":       "Dynamic Programming Mastery",
        "description": "Complete DP curriculum from basics to advanced",
        "levels": [
            {"rating": 800,  "description": "Fibonacci-style, simple recurrence"},
            {"rating": 1000, "description": "1D DP with simple transitions"},
            {"rating": 1200, "description": "2D DP and grid problems"},
            {"rating": 1400, "description": "DP with optimization"},
            {"rating": 1600, "description": "Interval DP"},
            {"rating": 1800, "description": "DP on trees"},
            {"rating": 2000, "description": "Bitmask DP"},
            {"rating": 2200, "description": "Digit DP"},
            {"rating": 2400, "description": "DP + complex data structures"},
        ]
    },

    "graphs": {
        "title":       "Graph Algorithms Complete Path",
        "description": "From basic traversal to advanced flow algorithms",
        "levels": [
            {"rating": 800,  "description": "Basic adjacency, simple traversal"},
            {"rating": 1000, "description": "DFS/BFS applications"},
            {"rating": 1200, "description": "Connected components"},
            {"rating": 1400, "description": "Shortest paths (Dijkstra)"},
            {"rating": 1600, "description": "MST and DSU problems"},
            {"rating": 1800, "description": "SCC and Toposort"},
            {"rating": 2000, "description": "Bipartite matching"},
            {"rating": 2200, "description": "Network flow"},
            {"rating": 2400, "description": "Advanced flow applications"},
        ]
    },

    "binary search": {
        "title":       "Binary Search Deep Dive",
        "description": "From basic search to binary search on answer",
        "levels": [
            {"rating": 800,  "description": "Basic binary search on sorted array"},
            {"rating": 1000, "description": "Binary search on answer"},
            {"rating": 1200, "description": "Binary search with complex predicates"},
            {"rating": 1400, "description": "Parallel binary search"},
            {"rating": 1600, "description": "Binary search + other algorithms"},
            {"rating": 1800, "description": "Fractional cascading"},
        ]
    },

    "dsu": {
        "title":       "Disjoint Set Union Mastery",
        "description": "DSU from basics to offline queries",
        "levels": [
            {"rating": 1000, "description": "Basic union-find"},
            {"rating": 1200, "description": "DSU with path compression"},
            {"rating": 1400, "description": "DSU applications in graphs"},
            {"rating": 1600, "description": "Weighted DSU"},
            {"rating": 1800, "description": "Offline DSU queries"},
            {"rating": 2000, "description": "DSU on trees"},
        ]
    },

    "segment tree": {
        "title":       "Segment Tree Mastery",
        "description": "From basic range queries to lazy propagation",
        "levels": [
            {"rating": 1200, "description": "Basic range sum query"},
            {"rating": 1400, "description": "Range min/max query"},
            {"rating": 1600, "description": "Point update range query"},
            {"rating": 1800, "description": "Lazy propagation"},
            {"rating": 2000, "description": "Segment tree beats"},
            {"rating": 2200, "description": "Persistent segment tree"},
            {"rating": 2400, "description": "Segment tree + other structures"},
        ]
    },

    "greedy": {
        "title":       "Greedy Algorithm Fundamentals",
        "description": "Proving and applying greedy strategies",
        "levels": [
            {"rating": 800,  "description": "Obvious greedy choices"},
            {"rating": 1000, "description": "Greedy with sorting"},
            {"rating": 1200, "description": "Exchange argument proofs"},
            {"rating": 1400, "description": "Greedy with priority queues"},
            {"rating": 1600, "description": "Non-obvious greedy"},
            {"rating": 1800, "description": "Greedy + complex data structures"},
        ]
    },

    "strings": {
        "title":       "String Algorithms Path",
        "description": "From basic string ops to advanced suffix structures",
        "levels": [
            {"rating": 800,  "description": "Basic string operations"},
            {"rating": 1000, "description": "String hashing"},
            {"rating": 1200, "description": "KMP / Z-function"},
            {"rating": 1400, "description": "Palindrome problems"},
            {"rating": 1600, "description": "Suffix arrays"},
            {"rating": 1800, "description": "Aho-Corasick"},
            {"rating": 2000, "description": "Suffix automaton"},
        ]
    },

    "trees": {
        "title":       "Tree Algorithms Mastery",
        "description": "From DFS on trees to heavy path decomposition",
        "levels": [
            {"rating": 800,  "description": "Basic tree traversal"},
            {"rating": 1000, "description": "Tree diameter and paths"},
            {"rating": 1200, "description": "Rooted tree DP"},
            {"rating": 1400, "description": "LCA (Lowest Common Ancestor)"},
            {"rating": 1600, "description": "Centroid decomposition"},
            {"rating": 1800, "description": "Heavy-Light Decomposition"},
            {"rating": 2000, "description": "Link-Cut Trees"},
        ]
    },

    "math": {
        "title":       "Mathematical Foundations",
        "description": "Number theory, combinatorics and beyond",
        "levels": [
            {"rating": 800,  "description": "Basic arithmetic, modular math"},
            {"rating": 1000, "description": "GCD, LCM, prime checking"},
            {"rating": 1200, "description": "Sieve of Eratosthenes"},
            {"rating": 1400, "description": "Modular exponentiation"},
            {"rating": 1600, "description": "Combinatorics and counting"},
            {"rating": 1800, "description": "Number theoretic transform"},
            {"rating": 2000, "description": "Advanced number theory"},
        ]
    }
}


# ── Helper Functions ──────────────────────────────

def get_prerequisites_for_topic(topic):
    """
    Returns list of topics that should be learned
    before attempting the given topic.
    """
    return PREREQUISITES.get(topic, [])


def get_learning_path_for_rating(rating):
    """
    Returns the appropriate learning path
    for a user at this rating level.
    """
    for level, data in LEARNING_PATH.items():
        low, high = data['rating_range']
        if low <= rating < high:
            return level, data
    return "candidate_master", LEARNING_PATH["candidate_master"]


def get_next_topic_in_path(rating, practiced_tags, weak_tags):
    """
    Given a user's rating and what they've practiced,
    find the next topic they should focus on.

    Logic:
    1. Find their rating-appropriate learning path
    2. Find first topic in that path they haven't mastered
    3. Check if prerequisites are met
    4. Return the topic with context
    """
    level, path = get_learning_path_for_rating(rating)
    strong_and_moderate = set(practiced_tags) - set(weak_tags)

    for topic in path['topics_in_order']:
        # Skip if already mastered
        if topic in strong_and_moderate:
            continue

        # Check prerequisites
        prereqs  = get_prerequisites_for_topic(topic)
        unmet    = [p for p in prereqs if p not in strong_and_moderate]

        if unmet:
            # Suggest learning prerequisites first
            return {
                "topic":          topic,
                "ready":          False,
                "unmet_prereqs":  unmet,
                "message":        f"Learn {', '.join(unmet)} before {topic}"
            }
        else:
            return {
                "topic":    topic,
                "ready":    True,
                "unmet_prereqs": [],
                "message":  f"You are ready to learn {topic}!"
            }

    return None


def get_topic_set(tag, user_rating, solved_ids):
    """
    Returns curated problem set for a topic
    starting from appropriate difficulty for user.
    """
    if tag not in TOPIC_PROBLEM_SETS:
        return None

    topic_data = TOPIC_PROBLEM_SETS[tag]
    levels     = topic_data['levels']

    # Find starting level (just below user's comfort)
    start_rating = max(800, user_rating - 200)

    relevant_levels = [
        l for l in levels
        if l['rating'] >= start_rating
    ]

    return {
        "tag":         tag,
        "title":       topic_data['title'],
        "description": topic_data['description'],
        "levels":      relevant_levels,
        "total_levels": len(levels)
    }


if __name__ == "__main__":
    # Quick test
    print("Testing problem ladder...")
    print()

    # Test prerequisites
    print("Prerequisites for 'flows':")
    print(f"  {get_prerequisites_for_topic('flows')}")
    print()

    # Test learning path
    level, path = get_learning_path_for_rating(1350)
    print(f"Learning path for 1350 rated user: {level}")
    print(f"  Topics: {path['topics_in_order'][:5]}...")
    print()

    # Test next topic
    next_t = get_next_topic_in_path(
        rating         = 1350,
        practiced_tags = ['math', 'greedy', 'sorting', 'binary search'],
        weak_tags      = ['binary search']
    )
    print(f"Next topic to learn: {next_t}")