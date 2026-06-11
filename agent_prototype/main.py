import json

from debate_engine import run_debate
from judge_agent import JudgeAgent
from vote_aggregator import aggregate

from openai import OpenAI

client = OpenAI(
    api_key=""
)

from collections import Counter

def build_profile(rank_row, review_data):

    target_name = rank_row["restaurant_name"]

    reviews = [
        r
        for r in review_data
        if r["restaurant_name"] == target_name
    ]

    strengths = []

    for r in reviews:
        strengths.extend(
            r.get("strengths", [])
        )

    top_strengths = [
        s
        for s, _
        in Counter(strengths).most_common(5)
    ]

    return {

        "restaurant_name":
        target_name,

        "summary":
        f"""
        총점 {rank_row['total_score']}
        리뷰수 {rank_row['review_count']}

        맛 {rank_row['scores']['taste']}
        서비스 {rank_row['scores']['service']}
        청결 {rank_row['scores']['cleanliness']}
        분위기 {rank_row['scores']['atmosphere']}
        가성비 {rank_row['scores']['value']}
        """,

        "strengths":
        top_strengths,

        "weaknesses":
        [],

        "scores":
        rank_row["scores"]
    }

with open(
    "test/data/restaurant_ranking_top10.json",
    encoding="utf-8"
) as f:
    ranking_data = json.load(f)

with open(
    "test/data/restaurant_analysis_2838.json",
    encoding="utf-8"
) as f:
    review_data = json.load(f)

a_profile = build_profile(
    ranking_data[0],
    review_data
)

b_profile = build_profile(
    ranking_data[1],
    review_data
)

print("=== 토론 시작 ===")

debate_log = run_debate(
    client,
    a_profile,
    b_profile
)

print(debate_log)

judge = JudgeAgent(client)

results = judge.judge(
    debate_log,
    a_profile,
    b_profile
)

print("\n=== Judge 결과 ===")

for category, result in results.items():

    print(f"\n[{category}]")
    print(result)

votes = {}

for category_result in results.values():

    winner = category_result["winner"]

    votes[winner] = votes.get(
        winner,
        0
    ) + 1

final_winner = max(
    votes,
    key=votes.get
)

print("\n=== 최종 결과 ===")

print({
    "winner": final_winner,
    "votes": votes
})