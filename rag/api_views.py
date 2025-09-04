# rag/api_views.py
from rest_framework.views import APIView
from rest_framework.response import Response
from rest_framework import status
from .rag_core import build_retriever, answer_question, llm_options, set_default_llm


class StatusView(APIView):
    def get(self, request):
        try:
            build_retriever()
            return Response({"status": "ready"})
        except Exception as e:
            return Response({"status": "error", "detail": str(e)}, status=status.HTTP_500_INTERNAL_SERVER_ERROR)


class AskView(APIView):
    def post(self, request):
        question = request.data.get("question")
        provider = request.data.get("provider")
        model_name = request.data.get("model_name")

        if not question:
            return Response({"error": "Question is required"}, status=status.HTTP_400_BAD_REQUEST)

        try:
            answer, llm_used = answer_question(question, provider, model_name)
            return Response({"answer": answer, "llm_used": llm_used})
        except Exception as e:
            return Response({"error": str(e)}, status=status.HTTP_500_INTERNAL_SERVER_ERROR)


class LLMOptionsView(APIView):
    def get(self, request):
        try:
            options = llm_options()
            return Response(options)
        except Exception as e:
            return Response({"error": str(e)}, status=status.HTTP_500_INTERNAL_SERVER_ERROR)


class ConfigureLLMView(APIView):
    def post(self, request):
        provider = request.data.get("llm_provider")
        model = request.data.get("model_name")

        if not provider or not model:
            return Response({"error": "Provider and model_name are required"}, status=status.HTTP_400_BAD_REQUEST)

        try:
            desc = set_default_llm(provider, model)
            return Response({"message": f"Default LLM set to {desc['description']}"})
        except Exception as e:
            return Response({"error": str(e)}, status=status.HTTP_500_INTERNAL_SERVER_ERROR)
