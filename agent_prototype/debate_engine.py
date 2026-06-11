from restaurant_agent import RestaurantAgent


def run_debate(
    client,
    a_profile,
    b_profile
):

    a_agent = RestaurantAgent(
        client,
        a_profile
    )

    b_agent = RestaurantAgent(
        client,
        b_profile
    )

    opening = a_agent.opening(
        b_profile
    )

    rebuttal = b_agent.rebuttal(
        a_profile,
        opening
    )

    closing = a_agent.closing(
        rebuttal
    )

    debate_log = f"""
    [A Opening]

    {opening}

    [B Rebuttal]

    {rebuttal}

    [A Closing]

    {closing}
    """

    return debate_log