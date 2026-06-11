from google import genai

class RestaurantAgent:

    def __init__(self, client, profile):
        self.client = client
        self.profile = profile

    def opening(self, opponent):

        prompt = f"""
너는 {self.profile['restaurant_name']}의 대변인이다.

우리 식당 정보

{self.profile}

상대 식당 정보

{opponent}

우리 식당이 더 우수한 이유를 주장하라.

4~5문장으로 답변.
"""

        response = self.client.chat.completions.create(
            model="gpt-4.1-mini",
            messages=[
                {
                    "role": "user",
                    "content": prompt
                }
            ]
        )

        return response.choices[0].message.content

    def rebuttal(
        self,
        opponent,
        opponent_argument
    ):

        prompt = f"""
너는 {self.profile['restaurant_name']}의 대변인이다.

상대 주장:

{opponent_argument}

우리 식당 정보:

{self.profile}

상대 주장에 반박하라.

반드시 상대 주장을 직접 언급하라.
"""

        response = self.client.chat.completions.create(
            model="gpt-4.1-mini",
            messages=[
                {
                    "role": "user",
                    "content": prompt
                }
            ]
        )

        return response.choices[0].message.content

    def closing(
        self,
        opponent_argument
    ):

        prompt = f"""
너는 {self.profile['restaurant_name']}의 대변인이다.

상대 최종 주장:

{opponent_argument}

우리 식당이 최종적으로 더 좋은 선택인 이유를 정리하라.
"""

        response = self.client.chat.completions.create(
            model="gpt-4.1-mini",
            messages=[
                {
                    "role": "user",
                    "content": prompt
                }
            ]
        )

        return response.choices[0].message.content