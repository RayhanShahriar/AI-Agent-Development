from django import forms

PROVIDERS = (
    ("openai", "openai"),
    ("groq", "groq"),
    ("google", "google"),
)

class LLMConfigForm(forms.Form):
    llm_provider = forms.ChoiceField(choices=PROVIDERS)
    model_name   = forms.CharField()

class QuestionForm(forms.Form):
    question = forms.CharField(
        widget=forms.TextInput(attrs={
            "placeholder": "Type your question…",
            "autocomplete": "off"
        })
    )
