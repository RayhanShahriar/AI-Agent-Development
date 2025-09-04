from django.shortcuts import render, redirect
from django.views import View
from django.contrib import messages

from .forms import LLMConfigForm, QuestionForm
from .rag_core import llm_options, set_default_llm, answer_question, build_retriever

SESSION_KEY = "rag_chat_history"

class QnAPage(View):
    template_name = "QnA.html"

    def get(self, request):
        # Ensure retriever is ready; surface any error up top
        status_msg = "RAG ready"
        try:
            build_retriever()
        except Exception as e:
            status_msg = f"RAG not ready: {e}"

        # Options for selects
        options = llm_options()
        providers = options["providers"]
        current   = options["current"]

        # Build choices for models of the current/default provider
        cur_provider = current.get("provider", "google")
        provider_models = providers.get(cur_provider, {}).get("models", [])

        # Forms
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
            messages.error(request, "Please enter a question.")
            return redirect("rag_qna_page")

        q = ask_form.cleaned_data["question"]

        # Keep using the default model unless user changed it on the config page
        try:
            answer, llm_used = answer_question(q, provider=None, model_name=None)
        except Exception as e:
            messages.error(request, f"Error: {e}")
            return redirect("rag_qna_page")

        # Persist chat in session (simple list of dicts)
        chat = request.session.get(SESSION_KEY, [])
        chat.append({"who": "user", "text": q})
        chat.append({"who": "bot", "text": answer, "llm": llm_used})
        request.session[SESSION_KEY] = chat
        request.session.modified = True

        return redirect("rag_qna_page")


class ConfigureLLM(View):
    def post(self, request):
        form = LLMConfigForm(request.POST)
        if not form.is_valid():
            messages.error(request, "Invalid LLM settings.")
            return redirect("rag_qna_page")

        data = form.cleaned_data
        try:
            desc = set_default_llm(data["llm_provider"], data["model_name"])
            messages.success(request, f"Default LLM set to {desc['description']}")
        except Exception as e:
            messages.error(request, f"Failed to set LLM: {e}")

        return redirect("rag_qna_page")


class ClearChat(View):
    def post(self, request):
        request.session[SESSION_KEY] = []
        request.session.modified = True
        messages.success(request, "Chat cleared.")
        return redirect("rag_qna_page")
