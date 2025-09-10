# rag/api_views.py
import requests
from rest_framework.views import APIView
from rest_framework.response import Response
from rest_framework import status
from django.conf import settings

# URL of FastAPI backend
FASTAPI_URL = getattr(settings, "FASTAPI_URL", "http://127.0.0.1:8000")

# Default headers if needed (e.g., for admin token)
FASTAPI_HEADERS = {
    # "Authorization": "Bearer admin_secret_token_2024"  # uncomment if needed
}


class StatusView(APIView):
    """Check if RAG system is ready"""
    def get(self, request):
        try:
            resp = requests.get(f"{FASTAPI_URL}/status/", headers=FASTAPI_HEADERS, timeout=10)
            resp.raise_for_status()
            return Response(resp.json())
        except requests.RequestException as e:
            return Response(
                {"status": "error", "detail": str(e)},
                status=status.HTTP_500_INTERNAL_SERVER_ERROR
            )


class AskView(APIView):
    """Send a question to FastAPI and get answer"""
    def post(self, request):
        question = request.data.get("question")
        llm_provider = request.data.get("llm_provider")
        model_name = request.data.get("model_name")
        use_reranker = request.data.get("use_reranker", True)
        max_chunks = request.data.get("max_chunks", 10)

        if not question:
            return Response({"error": "Question is required"}, status=status.HTTP_400_BAD_REQUEST)

        payload = {
            "question": question,
            "llm_provider": llm_provider or "openai",
            "model_name": model_name,
            "use_reranker": use_reranker,
            "max_chunks": max_chunks
        }

        try:
            resp = requests.post(f"{FASTAPI_URL}/ask", json=payload, headers=FASTAPI_HEADERS, timeout=20)
            resp.raise_for_status()
            data = resp.json()
            return Response({
                "answer": data.get("answer", "No answer"),
                "llm_used": data.get("llm_used", ""),
                "status": "success"
            })
        except requests.RequestException as e:
            return Response({"error": str(e)}, status=status.HTTP_500_INTERNAL_SERVER_ERROR)


class LLMOptionsView(APIView):
    """Get available LLM options from FastAPI"""
    def get(self, request):
        try:
            resp = requests.get(f"{FASTAPI_URL}/llm-options/", headers=FASTAPI_HEADERS, timeout=10)
            resp.raise_for_status()
            return Response(resp.json())
        except requests.RequestException as e:
            return Response({"error": str(e)}, status=status.HTTP_500_INTERNAL_SERVER_ERROR)


class ConfigureLLMView(APIView):
    """Set default LLM via FastAPI (admin only)"""
    def post(self, request):
        provider = request.data.get("llm_provider")
        model_name = request.data.get("model_name")

        if not provider or not model_name:
            return Response({"error": "Provider and model_name are required"}, status=status.HTTP_400_BAD_REQUEST)

        payload = {
            "llm_provider": provider,
            "model_name": model_name
        }

        try:
            resp = requests.post(f"{FASTAPI_URL}/configure-llm/", json=payload, headers=FASTAPI_HEADERS, timeout=10)
            resp.raise_for_status()
            return Response(resp.json())
        except requests.RequestException as e:
            return Response({"error": str(e)}, status=status.HTTP_500_INTERNAL_SERVER_ERROR)
