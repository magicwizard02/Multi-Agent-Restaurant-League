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
    print("=== Step 1: Vector DB 구축 시작 (3개 파일 병합) ===")
    
    db_path = "./restaurant_vector_db"
    client = chromadb.PersistentClient(path=db_path)
    
    openai_ef = embedding_functions.OpenAIEmbeddingFunction(
        api_key=openai_api_key,
        model_name="text-embedding-3-small"
    )
    
    collection_name = "restaurants_reviews_v2"
    
    try:
        client.delete_collection(name=collection_name)
        print(f"기존 컬렉션 '{collection_name}'을 삭제했습니다.")
    except Exception:
        pass
        
    collection = client.create_collection(
        name=collection_name,
        embedding_function=openai_ef
    )
    
    # 1. Load data
    print("데이터 파일 3개를 로드합니다...")
    with open("./vectorDB/final_restaurants.json", "r", encoding="utf-8") as f:
        rests_data = json.load(f)
    with open("./vectorDB/final_reviews.json", "r", encoding="utf-8") as f:
        reviews_data = json.load(f)
    with open("./vectorDB/restaurant_analysis_2838_2.json", "r", encoding="utf-8") as f:
        analysis_data = json.load(f)

    # 2. Group by Restaurant ID
    restaurants = {}
    
    # Process final_restaurants.json
    for r in rests_data:
        rid = str(r["ID"])
        add_info = r.get("additional_info")
        if not isinstance(add_info, dict):
            add_info = {}
            
        restaurants[rid] = {
            "name": r.get("name", "Unknown"),
            "address": r.get("address", "주소 없음"),
            "facilities": add_info.get("편의시설", []),
            "strengths": [],
            "reviews": []
        }
        
    # Process final_reviews.json
    for rv in reviews_data:
        rid = str(rv["R_ID"])
        if rid in restaurants and rv.get("detail"):
            restaurants[rid]["reviews"].append(rv["detail"].replace('\n', ' '))
            
    # Process restaurant_analysis_2838_2.json
    for a in analysis_data:
        rid = str(a.get("restaurant_id"))
        if rid in restaurants:
            if a.get("strengths"):
                restaurants[rid]["strengths"].extend(a["strengths"])
                
    documents = []
    metadatas = []
    ids = []
    
    print(f"식당 단위로 취합된 개수: {len(restaurants)}개")
    
    for rid, info in restaurants.items():
        if not info["reviews"] and not info["strengths"]:
            continue # Skip if no data at all
            
        unique_strengths = list(set(info["strengths"]))
        joined_strengths = ", ".join(unique_strengths) if unique_strengths else "정보 없음"
        joined_facilities = ", ".join(info["facilities"]) if info["facilities"] else "정보 없음"
        
        joined_reviews = " / ".join(info["reviews"][:20]) if info["reviews"] else "리뷰 없음"
        
        doc_text = f"식당 이름: {info['name']}\n주소: {info['address']}\n편의시설: {joined_facilities}\n주요 강점: {joined_strengths}\n리뷰 모음: {joined_reviews}"
        
        documents.append(doc_text)
        metadatas.append({
            "restaurant_name": info["name"],
            "restaurant_id": rid,
            "address": info["address"]
        })
        ids.append(rid)
        
    # 6. Insert to DB
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
        print(f"{min(i + batch_size, len(documents))} / {len(documents)} 개 식당 DB 삽입 완료...")
        
    print("=== Step 1: Vector DB 구축 완료 ===")
    return collection

def query_vector_db(collection, query_text):
    print(f"\n=== Step 2: RAG 검색 쿼리 실행 ===")
    print(f"사용자 질문: '{query_text}'")
    
    results = collection.query(
        query_texts=[query_text],
        n_results=3
    )
    
    result_md = f"# RAG 검색 결과 (V2 - 3개 파일 병합 버전)\n\n**질문:** {query_text}\n\n"
    
    print("\n[검색된 의미 있는 상위 3개 식당 데이터]")
    for i in range(len(results['ids'][0])):
        res_id = results['ids'][0][i]
        meta = results['metadatas'][0][i]
        dist = results['distances'][0][i]
        doc = results['documents'][0][i]
        
        print(f"\n--- Rank {i+1} ---")
        print(f"식당 이름: {meta['restaurant_name']} (거리: {dist:.4f})")
        
        preview = doc[:300] + "..." if len(doc) > 300 else doc
        print(f"데이터 요약: {preview}")
        
        result_md += f"## Rank {i+1} : {meta['restaurant_name']}\n"
        result_md += f"- **주소:** {meta['address']}\n"
        result_md += f"- **유사도 거리(Distance):** {dist:.4f}\n"
        result_md += f"- **데이터 전체 요약:** \n{doc}\n\n"
        
    md_path = "./vectorDB/rag_query_result.md"
    with open(md_path, "w", encoding="utf-8") as f:
        f.write(result_md)
    print(f"\n✅ 검색 결과가 '{md_path}' 파일로 저장되었습니다.")

if __name__ == "__main__":
    col = build_vector_db()
    query_vector_db(col, "강남역 단체 회식 삼겹살집 추천해줘")
