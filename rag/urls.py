# rag/urls.py
from django.urls import path
from .views import QnAPage, ConfigureLLM, ClearChat, UploadPDF, QnAPage_admin, ConfigureLLM_admin, ClearChat_admin

urlpatterns = [
    path("qna/", QnAPage.as_view(), name="rag_qna_page"),
    path("configure-llm/", ConfigureLLM.as_view(), name="configure_llm"),
    path("configure-llm/admin", ConfigureLLM_admin.as_view(), name="configure_llm_admin"),
    path("clear-chat/", ClearChat.as_view(), name="clear_chat"),
    path("clear-chat/admin", ClearChat_admin.as_view(), name="clear_chat_admin"),
    path("upload-pdf/", UploadPDF.as_view(), name="upload_pdf"),
    path("qna/admin/", QnAPage_admin.as_view(), name = "rag_qna_page_admin")
   
]
