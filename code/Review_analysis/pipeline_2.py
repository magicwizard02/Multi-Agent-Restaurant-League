import os
import json
import pandas as pd
from urllib import request, error
from dotenv import load_dotenv
import concurrent.futures

# .env 파일 로드
load_dotenv()

def analyze_single_review(restaurant_id, restaurant_name, review_text):
    """
    OpenAI GPT-4o-mini API를 호출하여 개별 리뷰를 상세 분석합니다.
    """
    api_key = os.environ.get("OPENAI_API_KEY")
    if api_key:
        api_key = api_key.strip().strip('"').strip("'")
    if not api_key:
        return None
        
    if not review_text or not str(review_text).strip():
        return None

    url = "https://api.openai.com/v1/chat/completions"
    headers = {
        "Content-Type": "application/json",
        "Authorization": f"Bearer {api_key}"
    }
    
    system_prompt = f"""너는 식당 리뷰 전문 데이터 추출 AI야. 주어진 하나의 리뷰 텍스트를 분석해서 반드시 아래 JSON 형식으로만 응답해. 다른 설명이나 텍스트는 절대 덧붙이지 마.

[엄격한 제약 조건 - 반드시 지킬 것]
1. 명시적 근거 우선: 반드시 리뷰 텍스트에 '직접적으로 언급된 내용'만을 바탕으로 장단점과 점수를 평가해. 사용자의 전반적인 만족도나 분위기를 바탕으로 다른 항목을 임의로 추론하거나 지어내지 마.
2. 기본값 강제: 텍스트에 특정 항목(맛, 서비스, 청결도, 분위기, 가성비)에 대한 직접적인 단어나 문맥적 힌트가 없다면, 무조건 중립 점수인 5점을 부여해.
3. 빈 값 처리: 장점, 단점, 증거 문장이 없다면 임의로 생성하지 말고 빈 리스트 []를 반환해.

{{
  "restaurant_id": {restaurant_id},
  "restaurant_name": "{restaurant_name}",
  "summary": "리뷰의 핵심 내용을 한 줄로 요약",
  "strengths": ["장점 1", "장점 2"],
  "weaknesses": ["단점 1", "단점 2"],
  "scores": {{
    "taste": 맛 점수 (1~10, 언급 없으면 5),
    "service": 서비스 점수 (1~10, 언급 없으면 5),
    "cleanliness": 청결도 점수 (1~10, 언급 없으면 5),
    "atmosphere": 분위기 점수 (1~10, 언급 없으면 5),
    "value": 가성비 점수 (1~10, 언급 없으면 5)
  }},
  "evidence": ["리뷰에서 발췌한 핵심 문장 1"]
}}"""

    data = {
        "model": "gpt-4o-mini",
        "messages": [
            {"role": "system", "content": system_prompt},
            {"role": "user", "content": f"리뷰 원문:\n{review_text}"}
        ],
        "temperature": 0.0
    }
    
    req = request.Request(url, data=json.dumps(data).encode("utf-8"), headers=headers)
    
    try:
        with request.urlopen(req) as response:
            result = json.loads(response.read().decode("utf-8"))
            content = result["choices"][0]["message"]["content"]
            # Markdown 코드 블럭 방어 로직 제거 및 JSON 파싱
            content = content.replace("```json", "").replace("```", "").strip()
            return json.loads(content)
    except Exception as e:
        # 실패시 None 반환하여 건너뜀
        return None

def run_pipeline(review_tasks):
    """
    모든 리뷰 데이터를 병렬로 분석합니다.
    """
    print(f"\n[Step 1] 총 {len(review_tasks)}개의 리뷰를 OpenAI API로 개별 분석 중... (약 2~5분 소요 예상)")
    analyzed_data = []
    
    def fetch_llm(task):
        res = analyze_single_review(task['R_ID'], task['name'], task['detail'])
        if res is not None:
            # 원본 리뷰 텍스트도 같이 저장해주면 유용할 수 있음
            res['original_review'] = task['detail']
        return res
        
    # 최대 20개의 스레드를 사용하여 병렬 처리 (API 제한 고려)
    with concurrent.futures.ThreadPoolExecutor(max_workers=20) as executor:
        futures = {executor.submit(fetch_llm, task): task for task in review_tasks}
        completed = 0
        for future in concurrent.futures.as_completed(futures):
            res = future.result()
            if res:
                analyzed_data.append(res)
            completed += 1
            if completed % 100 == 0 or completed == len(review_tasks):
                print(f"   -> 리뷰 {completed}/{len(review_tasks)} 분석 완료...")
                
    print("\n[Step 2] 전체 리뷰 분석 완료!\n")
    return analyzed_data

if __name__ == "__main__":
    actual_data_path = "data/final_reviews.json"
    restaurants_path = "data/final_restaurants.json"
    
    if os.path.exists(actual_data_path) and os.path.exists(restaurants_path):
        print("🚀 실제 리뷰 데이터 전체 로드 및 개별 분석 시작")
        
        with open(actual_data_path, "r", encoding="utf-8") as f:
            reviews_data = json.load(f)
        with open(restaurants_path, "r", encoding="utf-8") as f:
            restaurants_data = json.load(f)
            
        reviews_df = pd.DataFrame(reviews_data)
        restaurants_df = pd.DataFrame(restaurants_data)
        
        print(f"전체 리뷰 수: {len(reviews_df)}")
        
        # 리뷰와 가게 이름 매핑
        review_tasks = []
        for _, row in reviews_df.iterrows():
            r_id = row['R_ID']
            match = restaurants_df[restaurants_df['ID'] == r_id]
            name = match.iloc[0]['name'] if not match.empty else "Unknown"
            
            review_tasks.append({
                'R_ID': r_id,
                'name': name,
                'detail': str(row.get('detail', ''))
            })
            
        # 병렬 분석 실행 (전체 2838개)
        final_results = run_pipeline(review_tasks)
        
        # 1. 전체 리뷰 분석 결과 저장 (2838개 예상)
        analysis_output_path = "data/restaurant_analysis.json"
        with open(analysis_output_path, "w", encoding="utf-8") as f:
            json.dump(final_results, f, ensure_ascii=False, indent=4)
            
        print(f"✅ 전체 리뷰 개별 분석 결과가 '{analysis_output_path}'에 저장되었습니다. (총 {len(final_results)}개)")
        
        # 2. 식당별 점수 집계 및 상위 10개 추출
        if final_results:
            # 리스트 딕셔너리를 평탄화하여 데이터프레임으로 변환
            res_df = pd.json_normalize(final_results)
            
            # 가게별 각 항목 평균 점수 계산
            agg_df = res_df.groupby(['restaurant_id', 'restaurant_name']).agg({
                'scores.taste': 'mean',
                'scores.service': 'mean',
                'scores.cleanliness': 'mean',
                'scores.atmosphere': 'mean',
                'scores.value': 'mean'
            }).reset_index()
            
            # 합산 점수 계산
            agg_df['total_score'] = (
                agg_df['scores.taste'] + 
                agg_df['scores.service'] + 
                agg_df['scores.cleanliness'] + 
                agg_df['scores.atmosphere'] + 
                agg_df['scores.value']
            )
            
            # 리뷰 수(review_count) 정보 결합
            agg_df = pd.merge(agg_df, restaurants_df[['ID', 'review_count']], left_on='restaurant_id', right_on='ID', how='left')
            
            # 합산 점수 기준 내림차순 정렬 후 상위 10개만 추출
            agg_df = agg_df.sort_values(by='total_score', ascending=False)
            top_10_df = agg_df.head(10).copy()
            top_10_df['rank'] = range(1, len(top_10_df) + 1)
            
            # JSON 포맷으로 변환
            ranking_data = []
            for _, row in top_10_df.iterrows():
                ranking_data.append({
                    'rank': int(row['rank']),
                    'restaurant_name': row['restaurant_name'],
                    'scores': {
                        'taste': round(row['scores.taste'], 1),
                        'service': round(row['scores.service'], 1),
                        'cleanliness': round(row['scores.cleanliness'], 1),
                        'atmosphere': round(row['scores.atmosphere'], 1),
                        'value': round(row['scores.value'], 1)
                    },
                    'total_score': round(row['total_score'], 1),
                    'review_count': int(row['review_count']) if pd.notna(row['review_count']) else 0
                })
                
            # 10개의 상위 가게만 JSON으로 저장
            ranking_output_path = "data/restaurant_ranking.json"
            with open(ranking_output_path, "w", encoding="utf-8") as f:
                json.dump(ranking_data, f, ensure_ascii=False, indent=4)
                
            print(f"✅ 상위 10개 가게 순위 결과가 '{ranking_output_path}'에 저장되었습니다.")
            
            print("\n" + "="*50)
            print("🏆 종합 점수(합산) 상위 10개 가게 🏆")
            print("="*50)
            for item in ranking_data:
                print(f"{item['rank']:2d}위. {item['restaurant_name']} - 합산 점수: {item['total_score']:.1f}점 (총 리뷰수: {item['review_count']}개)")
            print("="*50)
            
    else:
        print("데이터 파일이 존재하지 않습니다.")
