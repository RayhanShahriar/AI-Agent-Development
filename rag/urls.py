# rag/urls.py
from django.urls import path
from .views import QnAPage, ConfigureLLM, ClearChat

urlpatterns = [
    path("qna/", QnAPage.as_view(), name="rag_qna_page"),
    path("configure-llm/", ConfigureLLM.as_view(), name="configure_llm"),
    path("clear-chat/", ClearChat.as_view(), name="clear_chat"),
]
