import json
import re

class JudgeAgent:

    def __init__(
        self,
        client
    ):
        self.client = client

    def judge(
        self,
        debate_log,
        a_profile,
        b_profile
    ):

        prompt = f"""
        너는 맛집 토론 심사위원이다.

        평가 기준

        taste:
        맛

        service:
        서비스

        cleanliness:
        청결

        atmosphere:
        분위기

        value:
        가성비

        식당 A

        {a_profile}

        식당 B

        {b_profile}

        토론 로그

        {debate_log}

        반드시 아래 JSON 형식만 출력

        {{
            "taste": {{
                "winner":"",
                "reason":""
            }},
            "service": {{
                "winner":"",
                "reason":""
            }},
            "cleanliness": {{
                "winner":"",
                "reason":""
            }},
            "atmosphere": {{
                "winner":"",
                "reason":""
            }},
            "value": {{
                "winner":"",
                "reason":""
            }}
        }}
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

        text = response.choices[0].message.content

        text = re.sub(
            r"```json|```",
            "",
            text
        ).strip()

        try:
            return json.loads(text)

        except Exception:

            return {
                "winner":"ERROR",
                "reason":text
            }