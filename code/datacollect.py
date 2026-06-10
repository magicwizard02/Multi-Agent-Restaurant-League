import requests
import json
import time

def crawl_naver_restaurant():
    """
    네이버 플레이스 GraphQL API를 이용하여 방문자 리뷰를 수집합니다.
    Selenium 없이 직접 API 호출 방식으로, IP 차단 위험이 훨씬 낮고 빠릅니다.
    """
    
    place_id = "702447560"  # 칼맞은 삼겹살 강남본점
    url = "https://pcmap-api.place.naver.com/graphql"
    
    headers = {
        "User-Agent": "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) "
                       "AppleWebKit/537.36 (KHTML, like Gecko) "
                       "Chrome/131.0.0.0 Safari/537.36",
        "Referer": f"https://pcmap.place.naver.com/restaurant/{place_id}/review/visitor",
        "Origin": "https://pcmap.place.naver.com",
        "Content-Type": "application/json",
        "Accept": "application/json",
        "Accept-Language": "ko-KR,ko;q=0.9",
    }
    
    graphql_query = """query getVisitorReviews($input: VisitorReviewsInput) {
        visitorReviews(input: $input) {
            items {
                id
                rating
                author {
                    nickname
                }
                body
                created
                visitedDate
                reply {
                    body
                }
            }
            total
        }
    }"""
    
    all_reviews = []
    page = 1
    page_size = 50  # 한 번에 50개씩 요청
    total_reviews = None
    
    print(f"[1] 네이버 플레이스 GraphQL API를 통해 리뷰 수집 시작!")
    print(f"    대상: 칼맞은 삼겹살 강남본점 (Place ID: {place_id})")
    print(f"{'='*60}")
    
    while True:
        payload = [
            {
                "operationName": "getVisitorReviews",
                "variables": {
                    "input": {
                        "businessId": place_id,
                        "businessType": "restaurant",
                        "page": page,
                        "size": page_size,
                        "isPhotoUsed": False,
                        "item": "0",
                        "bookingBusinessId": None
                    },
                    "id": place_id
                },
                "query": graphql_query
            }
        ]
        
        try:
            response = requests.post(url, json=payload, headers=headers, timeout=15)
            
            if response.status_code == 429:
                print(f"   ⚠️ 요청 제한 감지 (429). 10초 대기 후 재시도...")
                time.sleep(10)
                continue
            
            if response.status_code != 200:
                print(f"   ❌ HTTP 오류: {response.status_code}")
                break
            
            data = response.json()
            
            # 응답 구조: [{data: {visitorReviews: {items: [...], total: N}}}]
            visitor_reviews = data[0]["data"]["visitorReviews"]
            items = visitor_reviews["items"]
            
            if total_reviews is None:
                total_reviews = visitor_reviews["total"]
                print(f"[2] 총 리뷰 수: {total_reviews}개 확인! 수집 시작...\n")
            
            if not items:
                print(f"   → 더 이상 리뷰가 없습니다. 수집 종료.")
                break
            
            for item in items:
                review_data = {
                    "id": item.get("id"),
                    "author": item.get("author", {}).get("nickname", ""),
                    "rating": item.get("rating"),
                    "body": item.get("body", ""),
                    "created": item.get("created", ""),
                    "visited_date": item.get("visitedDate", ""),
                    "reply": item.get("reply", {}).get("body") if item.get("reply") else None
                }
                all_reviews.append(review_data)
            
            print(f"   → 페이지 {page} 완료: {len(items)}개 수집 (누적: {len(all_reviews)}/{total_reviews})")
            
            # 모든 리뷰를 다 수집했으면 종료
            if len(all_reviews) >= total_reviews:
                break
            
            page += 1
            
            # 너무 빠른 요청 방지 (1~2초 랜덤 대기)
            time.sleep(1.5)
            
        except requests.exceptions.RequestException as e:
            print(f"   ❌ 네트워크 오류: {e}")
            print(f"   → 5초 후 재시도...")
            time.sleep(5)
            continue
    
    print(f"\n{'='*60}")
    print(f"[3] 수집 완료! 총 {len(all_reviews)}개의 방문자 리뷰 추출")
    
    # JSON 저장
    output_data = {
        "restaurant_name": "칼맞은 삼겹살 강남본점",
        "place_id": place_id,
        "total_reviews_on_naver": total_reviews,
        "total_extracted_reviews": len(all_reviews),
        "reviews": all_reviews
    }
    
    output_path = "kalmajeun_samgyeopsal.json"
    with open(output_path, "w", encoding="utf-8") as f:
        json.dump(output_data, f, ensure_ascii=False, indent=4)
    
    # 결과 미리보기
    print(f"\n{'='*60}")
    print(f"식당명: 칼맞은 삼겹살 강남본점")
    print(f"네이버 등록 리뷰 수: {total_reviews}건")
    print(f"실제 추출 리뷰 수: {len(all_reviews)}건")
    
    if all_reviews:
        print(f"\n[리뷰 샘플 - 처음 3개]")
        for i, r in enumerate(all_reviews[:3], 1):
            body_preview = r["body"][:100].replace("\n", " ")
            print(f"  {i}. [{r['author']}] ({r['visited_date']}) {body_preview}...")
    
    print(f"{'='*60}")
    print(f"\n✅ {output_path} 파일에 저장 완료!")

    print("thank you")

if __name__ == "__main__":
    crawl_naver_restaurant()
