import os
import re
import google.generativeai as genai
from flask import Flask, request, jsonify

# Render 환경 변수에서 Gemini API 키 가져오기
GEMINI_API_KEY = os.environ.get("GEMINI_API_KEY")

# API 키 유효성 검사 (빠른 실패)
if not GEMINI_API_KEY:
    raise ValueError("GEMINI_API_KEY 환경 변수가 설정되지 않았습니다.")

# --- Gemini 설정 (글로벌 변수) ---
# API 클라이언트 초기화는 환경 변수 적용을 위해 라우트 함수 내부로 이동됨.
SYSTEM_INSTRUCTION = "당신은 사용자의 마음을 편안하게 해주는 마음챙김 전문가 '챗버디'입니다. 따뜻하고 공감적인 태도로 사용자의 고민을 들어주고, 긍정적이고 차분한 조언을 제공합니다. 질문에 직접적인 답을 주기보다는, 사용자가 스스로 답을 찾을 수 있도록 돕는 방식으로 대화해주세요. 대화는 짧고 명확하게 유지합니다."
MODEL_NAME = "gemini-1.5-flash"

app = Flask(__name__)

# --- 안전 및 길이 제한 설정 ---
DANGER_KEYWORDS_PATTERN = re.compile(r"죽(고|을)? ?(싶|것|까)?|자살|살기 ?싫|끝내고 ?싶|힘들어 ?죽|우울증|극단적 선택", re.IGNORECASE)
EMERGENCY_MESSAGE = "당신의 힘든 마음에 깊이 공감합니다. 하지만 당신은 혼자가 아닙니다. 지금 바로 전문가의 도움을 받는 것이 중요해요. 정신건강위기상담전화 1577-0199 (24시간, 연중무휴) 또는 자살예방 상담전화 1393으로 전화해보세요. 당신의 이야기를 들어줄 준비가 되어 있습니다."
MAX_RESPONSE_LENGTH = 900 # 카카오톡 simpleText 길이 제한 (1,000자 내외)
KAKAO_TIMEOUT_SECONDS = 4.5 # 카카오톡 기본 타임아웃(5초)보다 짧게 설정

def normalize_text(text):
    """카카오톡 메시지의 제어 문자 및 연속 공백을 처리합니다."""
    return re.sub(r'[\r\n\t]+', ' ', text).strip()

@app.route("/healthz", methods=["GET"])
def healthz():
    """Render 헬스체크용 라우트"""
    return "OK", 200

@app.route("/chatbuddy", methods=["POST"])
def chatbuddy():
    try:
        # --- API 클라이언트 초기화 (요청 시점) ---
        # GOOGLE_API_BASE 환경 변수가 확실히 적용되도록 함수 내부에서 설정
        genai.configure(api_key=GEMINI_API_KEY)
        
        # 모델 인스턴스 정의
        model_instance = genai.GenerativeModel(
            MODEL_NAME,
            system_instruction=SYSTEM_INSTRUCTION
        )
        
        # --- 카카오톡 요청 처리 ---
        payload = request.json or {}
        user_request = payload.get("userRequest", {})
        user_message = normalize_text(user_request.get("utterance", ""))
        user_id = user_request.get("user", {}).get("id")

        if not user_message:
            return jsonify({
                "version": "2.0",
                "template": {
                    "outputs": [{"simpleText": {"text": "메시지가 비어있습니다. 다시 시도해주세요."}}]
                }
            })

        print(f"[{user_id}] 사용자 메시지: {user_message}")

        # --- 위험 키워드 감지 및 응급 메시지 전송 ---
        if DANGER_KEYWORDS_PATTERN.search(user_message):
            reply = EMERGENCY_MESSAGE
            print(f"[{user_id}] -> 위험 키워드 감지. 긴급 메시지 전송.")
        else:
            # Gemini API 호출 및 응답 생성 (4.5초 타임아웃 설정 추가)
            response = model_instance.generate_content(
                user_message,
                request_options={"timeout": KAKAO_TIMEOUT_SECONDS} # 카카오톡 타임아웃 방어
            )
            
            print(f"[{user_id}] -> Gemini 응답 종료 사유: {response.candidates[0].finish_reason}")
            
            # 응답 텍스트 추출 및 길이 제한
            reply = response.text.strip()
            if len(reply) > MAX_RESPONSE_LENGTH:
                reply = reply[:MAX_RESPONSE_LENGTH] + "..."
        
    except Exception as e:
        # API 오류 (404) 또는 타임아웃 발생 시 대체 메시지 반환
        print(f"[{user_id}] 오류 발생: {e}")
        reply = "서비스에 문제가 발생했습니다. 잠시 후 다시 시도해주세요."
        
    # --- 카카오톡 응답 포맷 반환 ---
    return jsonify({
        "version": "2.0",
        "template": {
            "outputs": [{"simpleText": {"text": reply}}]
        }
    })

if __name__ == "__main__":
    # Flask 앱 실행 (Render는 PORT 환경 변수를 제공)
    app.run(host="0.0.0.0", port=int(os.environ.get("PORT", 5000)))