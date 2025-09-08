from django.shortcuts import render, redirect
from django.views import View
import markdown   # ✅ NEW: For converting model output (Markdown) to clean HTML

from .forms import LLMConfigForm, QuestionForm
from .rag_core import llm_options, set_default_llm, answer_question, build_retriever
from django.utils.decorators import method_decorator
from django.contrib.admin.views.decorators import staff_member_required
from .forms import *
from .rag_core import build_retriever, PDF_DIR
from . import rag_core
from django.contrib import messages
from django.utils.text import get_valid_filename
import os

SESSION_KEY = "rag_chat_history"

class QnAPage(View):
    template_name = "QnA.html"

    def get(self, request):
        # Ensure retriever is ready, show simple status message
        status_msg = "RAG ready"
        try:
            build_retriever()
        except Exception as e:
            status_msg = f"RAG not ready: {e}"

        options = llm_options()
        providers = options["providers"]
        current = options["current"]

        cur_provider = current.get("provider", "google")
        provider_models = providers.get(cur_provider, {}).get("models", [])
        
        # Ensure provider_models is never empty - provide a fallback
        if not provider_models:
            provider_models = ["default-model"]

        # Get default model name
        default_model = current.get("model", "")
        if not default_model and provider_models:
            default_model = provider_models[0]

        llm_form = LLMConfigForm(initial={
            "llm_provider": cur_provider,
            "model_name": default_model,
        })
        ask_form = QuestionForm()

        chat = request.session.get(SESSION_KEY, [])

        ctx = {
            "status_msg": status_msg,
            "providers": providers,
            "current": current,
            "provider_models": provider_models,  # ✅ This is now guaranteed to be in context
            "default_model": default_model,      # ✅ Safe default model name
            "llm_form": llm_form,
            "ask_form": ask_form,
            "chat": chat,
        }
        return render(request, self.template_name, ctx)

    def post(self, request):
        # Handle question submission
        ask_form = QuestionForm(request.POST)
        if not ask_form.is_valid():
            # Instead of showing error, just reload page
            return redirect("rag_qna_page")

        q = ask_form.cleaned_data["question"]

        try:
            answer, llm_used = answer_question(q, provider=None, model_name=None)
            answer_html = markdown.markdown(answer)  # ✅ Converts markdown (*, **, etc.) to clean HTML
        except Exception:
            return redirect("rag_qna_page")

        chat = request.session.get(SESSION_KEY, [])
        chat.append({"who": "user", "text": q})
        chat.append({"who": "bot", "text": answer_html, "llm": llm_used})
        request.session[SESSION_KEY] = chat
        request.session.modified = True

        return redirect("rag_qna_page")


class ConfigureLLM(View):
    def post(self, request):
        form = LLMConfigForm(request.POST)
        if not form.is_valid():
            return redirect("rag_qna_page")

        data = form.cleaned_data
        try:
            set_default_llm(data["llm_provider"], data["model_name"])
        except Exception:
            pass  # silently ignore errors

        return redirect("rag_qna_page")


class ClearChat(View):
    def post(self, request):
        request.session[SESSION_KEY] = []
        request.session.modified = True
        return redirect("rag_qna_page")



@method_decorator(staff_member_required, name="dispatch") #before you run dispatch(), first run staff_member_required
class UploadPDF(View):
    template_name = "uploadPDF.html"

    def get(self, request):
        form = PDFUploadForm()

        return render(request, self.template_name, {'form': form})
    
    def post(self, request):
        # Bind form with uploaded data
        form = PDFUploadForm(request.POST, request.FILES)

        # If invalid (wrong type/size), re-render the page with errors
        if not form.is_valid():
            return render(request, self.template_name, {"form": form})

        # Get the validated file
        pdf_file = form.cleaned_data["pdf_file"]

        # Ensure target directory exists
        PDF_DIR.mkdir(parents=True, exist_ok=True)

        # Sanitize filename and prevent overwriting existing files
        base_name, ext = os.path.splitext(pdf_file.name)
        base_name = get_valid_filename(base_name) or "document"
        ext = ".pdf"
        candidate = PDF_DIR / f"{base_name}{ext}"
        i = 1
        while candidate.exists():
            candidate = PDF_DIR / f"{base_name}_{i}{ext}"
            i += 1

        # Save file in chunks to avoid memory issues
        with open(candidate, "wb+") as destination:
            for chunk in pdf_file.chunks():
                destination.write(chunk)

        # Reset retriever so it indexes the new file
        rag_core.retriever = None
        try:
            build_retriever()
            messages.success(request, f"Uploaded and indexed: {candidate.name}")
        except Exception as e:
            messages.warning(
                request,
                f"Uploaded {candidate.name}, but indexing failed: {e}"
            )

        return redirect("upload_pdf")