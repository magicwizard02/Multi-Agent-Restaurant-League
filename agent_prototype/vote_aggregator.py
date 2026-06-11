from collections import Counter


def aggregate(results):

    votes = Counter(
        result["winner"]
        for result in results
    )

    winner = votes.most_common(1)[0][0]

    return {
        "winner": winner,
        "votes": dict(votes)
    }