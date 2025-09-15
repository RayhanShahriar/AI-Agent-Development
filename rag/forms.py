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

class PDFUploadForm(forms.Form):
    pdf_file = forms.FileField()

    def clean_pdf_file(self):
        file = self.cleaned_data["pdf_file"]
        name = file.name.lower()
        if not name.endswith(".pdf"):
            raise forms.ValidationError("Only .pdf files are allowed")
        if file.size and file.size > 20 * 1024 *1024:
            raise forms.ValidationError("Pdf too large (Max 20 MB)")
        return file
