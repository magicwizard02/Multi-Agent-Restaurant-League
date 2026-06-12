import os
import json
import chromadb
from chromadb.utils import embedding_functions
from dotenv import load_dotenv

# 환경 변수 로드 (.env 파일에서 OPENAI_API_KEY 가져오기)
load_dotenv()
openai_api_key = os.environ.get("OPENAI_API_KEY")
if openai_api_key:
    openai_api_key = openai_api_key.strip()

def build_vector_db():
    print("=== Step 1: Vector DB 구축 시작 ===")
    
    # 1. ChromaDB 클라이언트 설정 (로컬 디렉토리 저장)
    db_path = "./restaurant_vector_db"
    client = chromadb.PersistentClient(path=db_path)
    
    # 2. OpenAI 임베딩 함수 설정 (text-embedding-3-small)
    openai_ef = embedding_functions.OpenAIEmbeddingFunction(
        api_key=openai_api_key,
        model_name="text-embedding-3-small"
    )
    
    # 3. Collection 생성 (이미 존재하면 가져오기)
    collection = client.get_or_create_collection(
        name="restaurants_reviews",
        embedding_function=openai_ef
    )
    
    # 만약 컬렉션에 이미 데이터가 있다면 스킵
    if collection.count() > 0:
        print(f"이미 DB에 {collection.count()}개의 데이터가 존재합니다. 구축 단계를 건너뜁니다.")
        return collection
        
    # 4. 데이터 로드 (vectorDB/restaurant_analysis_2838_2.json 사용)
    data_file = "./vectorDB/restaurant_analysis_2838_2.json"
    with open(data_file, "r", encoding="utf-8") as f:
        raw_data = json.load(f)
        
    print(f"총 {len(raw_data)}개의 리뷰 데이터를 로드했습니다.")
    
    # 식당별로 리뷰와 분석결과 통합 (Group by restaurant_name)
    restaurants = {}
    for r in raw_data:
        name = r.get("restaurant_name", "Unknown")
        rid = r.get("restaurant_id", "0")
        
        if name not in restaurants:
            restaurants[name] = {
                "restaurant_id": rid,
                "restaurant_name": name,
                "reviews": [],
                "strengths": [],
                "weaknesses": []
            }
            
        # 리뷰, 강점, 약점 텍스트 누적
        if r.get("original_review"):
            restaurants[name]["reviews"].append(r["original_review"])
        if r.get("strengths"):
            restaurants[name]["strengths"].extend(r["strengths"])
        if r.get("weaknesses"):
            restaurants[name]["weaknesses"].extend(r["weaknesses"])
            
    documents = []
    metadatas = []
    ids = []
    
    print(f"식당 단위로 취합된 개수: {len(restaurants)}개")
    
    # 5. DB 삽입용 Document 생성
    for idx, (name, info) in enumerate(restaurants.items()):
        # 고유값 추출
        unique_strengths = list(set(info["strengths"]))
        
        # 리뷰가 너무 길어지지 않게 최대 20개만 취합
        joined_reviews = " / ".join(info["reviews"][:20])
        joined_strengths = ", ".join(unique_strengths)
        
        doc_text = f"식당 이름: {name}\n주요 강점: {joined_strengths}\n리뷰 모음: {joined_reviews}"
        
        documents.append(doc_text)
        metadatas.append({
            "restaurant_name": name,
            "restaurant_id": str(info["restaurant_id"])
        })
        ids.append(str(info["restaurant_id"]) + "_" + str(idx))
        
    # 6. DB에 추가 (배치 처리)
    batch_size = 100
    for i in range(0, len(documents), batch_size):
        batch_docs = documents[i:i+batch_size]
        batch_metas = metadatas[i:i+batch_size]
        batch_ids = ids[i:i+batch_size]
        
        collection.add(
            documents=batch_docs,
            metadatas=batch_metas,
            ids=batch_ids
        )
        print(f"{i + len(batch_docs)} / {len(documents)} 개 처리 완료...")
        
    print("=== Step 1: Vector DB 구축 완료 ===")
    return collection

def query_vector_db(collection, query_text):
    print(f"\n=== Step 2: RAG 검색 쿼리 실행 ===")
    print(f"사용자 질문: '{query_text}'")
    
    # 상위 3개 검색
    results = collection.query(
        query_texts=[query_text],
        n_results=3
    )
    
    result_md = f"# RAG 검색 결과\n\n**질문:** {query_text}\n\n"
    
    # 결과 출력 포맷팅 및 마크다운 구성
    print("\n[검색된 의미 있는 상위 3개 식당 데이터]")
    for i in range(len(results['ids'][0])):
        res_id = results['ids'][0][i]
        meta = results['metadatas'][0][i]
        dist = results['distances'][0][i]
        doc = results['documents'][0][i]
        
        print(f"\n--- Rank {i+1} ---")
        print(f"식당 이름: {meta['restaurant_name']} (거리: {dist:.4f})")
        
        # 전체 문서를 다 출력하면 기니, 앞부분 200자만 출력
        preview = doc[:300] + "..." if len(doc) > 300 else doc
        print(f"데이터 요약: {preview}")
        
        result_md += f"## Rank {i+1} : {meta['restaurant_name']}\n"
        result_md += f"- **유사도 거리(Distance):** {dist:.4f}\n"
        result_md += f"- **데이터 전체 요약:** {doc}\n\n"
        
    md_path = "./vectorDB/rag_query_result.md"
    with open(md_path, "w", encoding="utf-8") as f:
        f.write(result_md)
    print(f"\n✅ 검색 결과가 '{md_path}' 파일로 저장되었습니다.")

if __name__ == "__main__":
    col = build_vector_db()
    query_vector_db(col, "강남역 단체 회식 삼겹살집 추천해줘")
