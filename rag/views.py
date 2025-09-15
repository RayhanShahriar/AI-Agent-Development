from django.shortcuts import render, redirect
from django.views import View
from .forms import LLMConfigForm, QuestionForm, PDFUploadForm
from django.contrib import messages
from django.conf import settings
import requests
from django.utils.text import get_valid_filename
import os
from pathlib import Path
import markdown
from django.conf import settings

FASTAPI_URL = "http://127.0.0.1:8000"  # FastAPI backend URL
SESSION_KEY = "rag_chat_history"
PDF_DIR = settings.MEDIA_ROOT / "pdfs"


class QnAPage(View):
    template_name = "QnA.html"

    def get(self, request):
        try:
            resp = requests.get(f"{FASTAPI_URL}/llm-options/")
            options = resp.json()
        except Exception as e:
            options = {"providers": {}, "current": {}}
            messages.warning(request, f"Could not reach backend: {e}")

        providers_list = []
        for key, val in options.get("providers", {}).items():
            providers_list.append({"name": key, "models": val.get("models", ["default-model"])})

        current_provider = request.session.get("current_provider") or options.get("current", {}).get("provider")
        if not current_provider or current_provider not in [p["name"] for p in providers_list]:
            current_provider = providers_list[0]["name"] if providers_list else "openai"

        provider_models = next((p["models"] for p in providers_list if p["name"] == current_provider), ["default-model"])
        current_model = request.session.get("current_model") or options.get("current", {}).get("model")
        if current_model not in provider_models:
            current_model = provider_models[0]

        llm_form = LLMConfigForm(initial={"llm_provider": current_provider, "model_name": current_model})
        ask_form = QuestionForm()
        chat = request.session.get(SESSION_KEY, [])

        return render(request, self.template_name, {
            "providers": providers_list,
            "current_provider": current_provider,
            "provider_models": provider_models,
            "default_model": current_model,
            "llm_form": llm_form,
            "ask_form": ask_form,
            "chat": chat,
            "status_msg": "Backend ready"
        })

    def post(self, request):
        ask_form = QuestionForm(request.POST)
        if not ask_form.is_valid():
            messages.error(request, "Invalid question.")
            return redirect("rag_qna_page")

        question = ask_form.cleaned_data["question"]

        provider = request.session.get("current_provider", "openai")
        model_name = request.session.get("current_model", "gpt-4o-mini")

        try:
            resp = requests.post(f"{FASTAPI_URL}/ask/", json={
                "question": question,
                "llm_provider": provider,
                "model_name": model_name
            })
            resp.raise_for_status()
            data = resp.json()
            answer = data.get("answer", "No answer")
            llm_used = data.get("llm_used", "")

            # ✅ Convert Markdown to HTML
            answer_html = markdown.markdown(answer)

        except Exception as e:
            messages.error(request, f"Backend error: {e}")
            return redirect("rag_qna_page")

        chat = request.session.get(SESSION_KEY, [])
        chat.append({"who": "user", "text": question})
        chat.append({"who": "bot", "text": answer_html, "llm": llm_used})
        request.session[SESSION_KEY] = chat
        request.session.modified = True

        return redirect("rag_qna_page")


# -----------------------------
# Admin QnA Page
# -----------------------------
class QnAPage_admin(View):
    template_name = "QnA_admin.html"

    def get(self, request):
        try:
            resp = requests.get(f"{FASTAPI_URL}/llm-options/")
            options = resp.json()
        except Exception as e:
            options = {"providers": {}, "current": {}}
            messages.warning(request, f"Could not reach backend: {e}")

        providers_list = []
        for key, val in options.get("providers", {}).items():
            providers_list.append({"name": key, "models": val.get("models", ["default-model"])})

        current_provider = request.session.get("current_provider") or options.get("current", {}).get("provider")
        if not current_provider or current_provider not in [p["name"] for p in providers_list]:
            current_provider = providers_list[0]["name"] if providers_list else "openai"

        provider_models = next((p["models"] for p in providers_list if p["name"] == current_provider), ["default-model"])
        current_model = request.session.get("current_model") or options.get("current", {}).get("model")
        if current_model not in provider_models:
            current_model = provider_models[0]

        llm_form = LLMConfigForm(initial={"llm_provider": current_provider, "model_name": current_model})
        ask_form = QuestionForm()
        chat = request.session.get(SESSION_KEY, [])

        return render(request, self.template_name, {
            "providers": providers_list,
            "current_provider": current_provider,
            "provider_models": provider_models,
            "default_model": current_model,
            "llm_form": llm_form,
            "ask_form": ask_form,
            "chat": chat,
            "status_msg": "Backend ready"
        })

    def post(self, request):
        ask_form = QuestionForm(request.POST)
        if not ask_form.is_valid():
            messages.error(request, "Invalid question.")
            return redirect("rag_qna_page_admin")

        question = ask_form.cleaned_data["question"]

        provider = request.session.get("current_provider", "openai")
        model_name = request.session.get("current_model", "gpt-4o-mini")

        try:
            resp = requests.post(f"{FASTAPI_URL}/ask/", json={
                "question": question,
                "llm_provider": provider,
                "model_name": model_name
            })
            resp.raise_for_status()
            data = resp.json()
            answer = data.get("answer", "No answer")
            llm_used = data.get("llm_used", "")

            # ✅ Convert Markdown to HTML
            answer_html = markdown.markdown(answer)

        except Exception as e:
            messages.error(request, f"Backend error: {e}")
            return redirect("rag_qna_page_admin")

        chat = request.session.get(SESSION_KEY, [])
        chat.append({"who": "user", "text": question})
        chat.append({"who": "bot", "text": answer_html, "llm": llm_used})
        request.session[SESSION_KEY] = chat
        request.session.modified = True

        return redirect("rag_qna_page_admin")





class ConfigureLLM(View):
    def post(self, request):
        form = LLMConfigForm(request.POST)
        if not form.is_valid():
            messages.error(request, "Invalid configuration.")
            return redirect("rag_qna_page")

        provider = form.cleaned_data["llm_provider"]
        model_name = form.cleaned_data["model_name"]

        try:
            headers = {"Authorization": "Bearer admin_secret_token_2024"}
            resp = requests.post(
                f"{FASTAPI_URL}/configure-llm/",
                json={"llm_provider": provider, "model_name": model_name},
                headers=headers,
                timeout=5
            )
            resp.raise_for_status()
            messages.success(request, f"LLM configured: {provider.title()} ({model_name})")

            # Save in session
            request.session["current_provider"] = provider
            request.session["current_model"] = model_name
            request.session.modified = True

        except requests.RequestException as e:
            messages.warning(request, f"Could not configure LLM: {e}")

        return redirect("rag_qna_page")
    
    
class ConfigureLLM_admin(View):
    def post(self, request):
        form = LLMConfigForm(request.POST)
        if not form.is_valid():
            messages.error(request, "Invalid configuration.")
            return redirect("rag_qna_page")

        provider = form.cleaned_data["llm_provider"]
        model_name = form.cleaned_data["model_name"]

        try:
            headers = {"Authorization": "Bearer admin_secret_token_2024"}
            resp = requests.post(
                f"{FASTAPI_URL}/configure-llm/",
                json={"llm_provider": provider, "model_name": model_name},
                headers=headers,
                timeout=5
            )
            resp.raise_for_status()
            messages.success(request, f"LLM configured: {provider.title()} ({model_name})")

            # Save in session
            request.session["current_provider"] = provider
            request.session["current_model"] = model_name
            request.session.modified = True

        except requests.RequestException as e:
            messages.warning(request, f"Could not configure LLM: {e}")

        return redirect("rag_qna_page_admin")


class ClearChat(View):
    def post(self, request):
        request.session[SESSION_KEY] = []
        request.session.modified = True
        messages.info(request, "Conversation cleared.")
        return redirect("rag_qna_page")

class ClearChat_admin(View):
    def post(self, request):
        request.session[SESSION_KEY] = []
        request.session.modified = True
        messages.info(request, "Conversation cleared.")
        return redirect("rag_qna_page_admin")


RAG_PDF_DIR = settings.RAG_PDF_DIR

class UploadPDF(View):
    template_name = "uploadPDF.html"
   

    def get(self, request):
        form = PDFUploadForm()
        RAG_PDF_DIR.mkdir(parents=True, exist_ok=True)

        pdf_files = []
        for pdf_path in RAG_PDF_DIR.glob("*.pdf"):
            pdf_files.append({
                "name": pdf_path.name,
                "url": f"{settings.MEDIA_URL}pdfs/{pdf_path.name}"
            })

        return render(request, self.template_name, {
            "form": form,
            "pdf_files": pdf_files
        })

    def post(self, request):
        form = PDFUploadForm(request.POST, request.FILES)
        if not form.is_valid():
            return render(request, self.template_name, {"form": form})

        pdf_file = form.cleaned_data["pdf_file"]
        
        RAG_PDF_DIR.mkdir(parents=True, exist_ok=True)

        base_name, ext = os.path.splitext(pdf_file.name)
        base_name = get_valid_filename(base_name) or "document"
        ext = ".pdf"
        candidate = RAG_PDF_DIR / f"{base_name}{ext}"
        i = 1
        while candidate.exists():
            candidate = RAG_PDF_DIR / f"{base_name}_{i}{ext}"
            i += 1

        with open(candidate, "wb+") as f:
            for chunk in pdf_file.chunks():
                f.write(chunk)

        messages.success(request, f"PDF uploaded: {candidate.name}")
        return redirect("upload_pdf")

