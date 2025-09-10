# rag/api_urls.py
from django.urls import path
from .api_views import StatusView, AskView, LLMOptionsView, ConfigureLLMView

urlpatterns = [
    path("status/", StatusView.as_view(), name="rag_status"),
    path("ask/", AskView.as_view(), name="rag_ask"),
    path("llm-options/", LLMOptionsView.as_view(), name="rag_llm_options"),
    path("configure-llm/", ConfigureLLMView.as_view(), name="rag_configure_llm"),
    
    
]
