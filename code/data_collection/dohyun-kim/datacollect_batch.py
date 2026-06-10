import requests
import json
import time
import re
import os
import sys
from datetime import datetime
from selenium import webdriver
from selenium.webdriver.chrome.options import Options
from selenium.webdriver.common.by import By
from selenium.webdriver.support.ui import WebDriverWait
from selenium.webdriver.support import expected_conditions as EC


def extract_restaurant_info(place_id, headers):
    """
    네이버 플레이스 홈 화면(HTML)에서 __APOLLO_STATE__ 데이터를 파싱하여
    식당의 기본 정보와 추가 정보(편의시설, 결제수단 등)를 추출합니다.
    """
    url = f"https://m.place.naver.com/restaurant/{place_id}/home"

    print(f"   [1] 식당 기본 정보 추출 시작 (Place ID: {place_id})")

    max_retries = 3
    for attempt in range(max_retries):
        try:
            response = requests.get(url, headers=headers, timeout=10)
            response.encoding = 'utf-8'

            if response.status_code == 429:
                wait = 15 * (attempt + 1)
                print(f"      ⚠️ 429 제한 감지. {wait}초 대기 후 재시도 ({attempt+1}/{max_retries})...")
                time.sleep(wait)
                continue

            if response.status_code != 200:
                print(f"      ❌ HTTP 오류: {response.status_code}")
                return {}

            match = re.search(r"window\.__APOLLO_STATE__\s*=\s*(\{.*?\});", response.text)
            if not match:
                print("      ⚠️ APOLLO_STATE를 찾을 수 없습니다.")
                return {}

            state = json.loads(match.group(1))

            base_node = None
            for k, v in state.items():
                if place_id in k and isinstance(v, dict) and "name" in v:
                    base_node = v
                    break

            if not base_node:
                print("      ⚠️ 식당 세부 정보 노드를 찾을 수 없습니다.")
                return {}

            # ── 기본 정보 ──
            info = {
                "name": base_node.get("name"),
                "category": base_node.get("category"),
                "address": base_node.get("address"),
                "road_address": base_node.get("roadAddress"),
                "phone": base_node.get("phone") or base_node.get("virtualPhone"),
                "visitor_review_count": base_node.get("visitorReviewsTotal"),
                "blog_review_count": base_node.get("cafeBlogReviewsTotal"),
                "booking_available": "예약" in (base_node.get("conveniences") or []),
                "business_hours": base_node.get("businessHours")
            }

            # ── 추가 정보 (이전 버전과 동일하게 유지) ──
            additional_info = {
                "편의시설": base_node.get("conveniences") or [],
                "결제수단": base_node.get("paymentInfo") or [],
                "찾아오는길_및_주차안내": base_node.get("road") or "",
            }

            info["additional_info"] = additional_info

            print(f"      ✅ 식당 정보 추출 성공: {info['name']} (방문자 리뷰 {info['visitor_review_count']}개)")
            return info

        except Exception as e:
            print(f"      ❌ 식당 정보 추출 중 오류 발생: {e}")
            if attempt < max_retries - 1:
                time.sleep(5)
            else:
                return {}

    return {}


def crawl_reviews(place_id, headers):
    """GraphQL API로 방문자 리뷰를 수집합니다."""
    print(f"   [2] 방문자 리뷰 수집 시작 (GraphQL API)")

    url = "https://pcmap-api.place.naver.com/graphql"
    graphql_query = """query getVisitorReviews($input: VisitorReviewsInput) {
        visitorReviews(input: $input) {
            items {
                id
                rating
                author { nickname }
                body
                created
                visitedDate
                reply { body }
            }
            total
        }
    }"""

    all_reviews = []
    page = 1
    page_size = 50
    total_reviews = None

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
                print(f"      ⚠️ 요청 제한 감지 (429). 20초 대기 후 재시도...")
                time.sleep(20)
                continue

            if response.status_code != 200:
                print(f"      ❌ HTTP 오류: {response.status_code}")
                break

            data = response.json()
            visitor_reviews = data[0]["data"]["visitorReviews"]
            items = visitor_reviews["items"]

            if total_reviews is None:
                total_reviews = visitor_reviews["total"]
                print(f"      → 총 등록된 리뷰 수: {total_reviews}개 확인!\n")

            if not items:
                print(f"      → 더 이상 리뷰가 없습니다. 수집 종료.")
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

            print(f"      → 페이지 {page} 완료: {len(items)}개 수집 (누적: {len(all_reviews)}/{total_reviews})")

            if len(all_reviews) >= total_reviews:
                break

            page += 1
            time.sleep(1.5)

        except requests.exceptions.RequestException as e:
            print(f"      ❌ 네트워크 오류: {e}")
            time.sleep(5)
            continue

    return all_reviews, total_reviews


def crawl_naver_restaurant(place_id):
    """한 식당의 기본정보 + 추가정보 + 방문자 리뷰를 모두 수집합니다."""
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

    restaurant_info = extract_restaurant_info(place_id, headers)
    if not restaurant_info:
        return False

    name = restaurant_info.get("name", "Unknown")
    safe_name = re.sub(r'[\\/*?:"<>|]', "", name).replace(" ", "_")
    output_path = f"data/{safe_name}_{place_id}.json"

    # 이미 수집된 파일이면 건너뜀
    if os.path.exists(output_path):
        print(f"   ⚠️ 이미 수집된 식당입니다. 건너뜁니다: {output_path}")
        return True

    all_reviews, total_reviews = crawl_reviews(place_id, headers)

    print(f"   [3] 수집 완료! 최종 JSON 저장 중...")

    output_data = {
        "restaurant_info": restaurant_info,
        "review_stats": {
            "total_reviews_on_naver": total_reviews,
            "total_extracted_reviews": len(all_reviews),
        },
        "reviews": all_reviews
    }

    with open(output_path, "w", encoding="utf-8") as f:
        json.dump(output_data, f, ensure_ascii=False, indent=4)

    print(f"   ✅ 파일 저장 성공: {output_path} (리뷰 {len(all_reviews)}건)")
    return True


def get_top_20_places(query="강남구 돼지고기구이"):
    """
    네이버 모바일 검색을 통해 입력한 쿼리(기본: 강남구 돼지고기구이)의 
    검색 결과 상위 20개 식당 ID를 동적으로 추출합니다.
    """
    print("=" * 60)
    print(f"▶ 네이버 지도 검색 시작 ('{query}')")
    print("=" * 60)

    options = Options()
    options.add_argument("--headless=new")
    options.add_argument("--no-sandbox")
    options.add_argument("--disable-dev-shm-usage")
    options.add_argument("user-agent=Mozilla/5.0 (iPhone; CPU iPhone OS 16_6 like Mac OS X) AppleWebKit/605.1.15 (KHTML, like Gecko) Version/16.6 Mobile/15E148 Safari/604.1")

    driver = webdriver.Chrome(options=options)
    
    import urllib.parse
    encoded_query = urllib.parse.quote(query)
    driver.get(f"https://m.search.naver.com/search.naver?query={encoded_query}")
    time.sleep(3)

    seen = set()
    ordered_ids = []

    # 스크롤 및 더보기 클릭 반복
    for _ in range(3):
        # 1. 밑으로 스크롤 (15개 로딩)
        for _ in range(5):
            driver.execute_script("window.scrollTo(0, document.body.scrollHeight);")
            time.sleep(1)

        # 2. 현재 로딩된 ID 파싱
        html = driver.page_source
        matches = re.findall(r"place\.naver\.com/restaurant/(\d+)", html)
        for m in matches:
            if m not in seen:
                seen.add(m)
                ordered_ids.append(m)

        if len(ordered_ids) >= 20:
            break
            
        # 3. 20개가 안 되면 "더보기" 버튼 찾아서 클릭
        try:
            more_btns = driver.find_elements(By.XPATH, "//*[contains(text(), '더보기') or contains(text(), '장소 더보기')]")
            clicked = False
            for btn in more_btns:
                if btn.is_displayed():
                    driver.execute_script("arguments[0].click();", btn)
                    time.sleep(2)
                    clicked = True
                    break
            
            # 더보기 버튼도 없고 스크롤도 더 안 되면 종료
            if not clicked:
                break
        except Exception:
            pass

    driver.quit()

    top_20 = ordered_ids[:20]
    print(f"\n▶ 추출된 식당 ID 목록 ({len(top_20)}개):")
    for i, pid in enumerate(top_20, 1):
        print(f"   {i:2d}. {pid}")

    if len(top_20) < 20:
        print(f"\n   ⚠️ {len(top_20)}개만 추출되었습니다. (검색 결과 수량 부족)")

    return top_20


def print_progress_bar(current, total, width=30):
    """진행 상황을 시각적으로 표시합니다."""
    pct = current / total if total > 0 else 0
    filled = int(width * pct)
    bar = "█" * filled + "░" * (width - filled)
    sys.stdout.write(f"\r   전체 진행: [{bar}] {current}/{total} ({pct*100:.0f}%)")
    sys.stdout.flush()


if __name__ == "__main__":
    start_time = datetime.now()

    print()
    print("╔" + "═" * 58 + "╗")
    print("║  네이버 플레이스 강남구 돼지고기구이 TOP 20 데이터 수집기  ║")
    print("╚" + "═" * 58 + "╝")
    print(f"  시작 시간: {start_time.strftime('%Y-%m-%d %H:%M:%S')}")
    print()

    # data 폴더 초기화
    if not os.path.exists("data"):
        os.makedirs("data")

    # 1단계: 상위 20개 식당 ID 추출
    place_ids = get_top_20_places()
    total_count = len(place_ids)

    if total_count == 0:
        print("\n❌ 식당 ID를 추출하지 못했습니다. 네트워크 상태를 확인해 주세요.")
        sys.exit(1)

    # 2단계: 각 식당 데이터 수집
    print(f"\n{'=' * 60}")
    print(f"▶ 총 {total_count}개 식당 순차 수집을 시작합니다.")
    print(f"  (식당 간 10초 대기 적용, 예상 소요 시간: 약 {total_count * 1.5:.0f}분)")
    print(f"{'=' * 60}")

    success_count = 0
    fail_count = 0

    for idx, pid in enumerate(place_ids, 1):
        print(f"\n{'─' * 60}")
        print(f"  [{idx}/{total_count}] 식당 수집 시작 (ID: {pid})")
        print(f"{'─' * 60}")

        result = crawl_naver_restaurant(pid)

        if result:
            success_count += 1
        else:
            fail_count += 1

        # 진행 바 출력
        print_progress_bar(idx, total_count)
        print()

        if idx < total_count:
            print(f"\n   ⏳ 차단 방지를 위해 10초 대기 중...")
            time.sleep(10)

    # 3단계: 최종 요약
    end_time = datetime.now()
    elapsed = end_time - start_time

    print(f"\n\n{'═' * 60}")
    print(f"  🎉 전체 수집 작업 완료!")
    print(f"{'═' * 60}")
    print(f"  ✅ 성공: {success_count}개")
    print(f"  ❌ 실패: {fail_count}개")
    print(f"  ⏱️  총 소요 시간: {elapsed}")
    print(f"  📁 저장 위치: data/ 폴더")
    print(f"{'═' * 60}")

    # data 폴더 내 파일 목록 출력
    files = [f for f in os.listdir("data") if f.endswith(".json")]
    print(f"\n  📋 수집된 파일 목록 ({len(files)}개):")
    for i, f in enumerate(files, 1):
        size_kb = os.path.getsize(f"data/{f}") / 1024
        print(f"   {i:2d}. {f} ({size_kb:.0f}KB)")
