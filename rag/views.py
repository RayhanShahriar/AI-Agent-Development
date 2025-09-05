from django.shortcuts import render, redirect
from django.views import View
import markdown   # ✅ NEW: For converting model output (Markdown) to clean HTML

from .forms import LLMConfigForm, QuestionForm
from .rag_core import llm_options, set_default_llm, answer_question, build_retriever

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

        llm_form = LLMConfigForm(initial={
            "llm_provider": cur_provider,
            "model_name": current.get("model", providers.get(cur_provider, {}).get("default", "")),
        })
        ask_form = QuestionForm()

        chat = request.session.get(SESSION_KEY, [])

        ctx = {
            "status_msg": status_msg,
            "providers": providers,
            "current": current,
            "provider_models": provider_models,
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
