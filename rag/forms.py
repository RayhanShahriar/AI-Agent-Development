from django import forms

PROVIDERS = (
    ("openai", "openai"), #Value, label
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
        file = self.cleaned_data["pdf_file"] # we extract the uploaded file object from the pdf_file field and store it in file

        #In Django, cleaned_data is a dictionary attribute of a Form instance that holds the validated and normalized data submitted through a form. After a form's is_valid() method is called and returns True, all the valid data from the form fields are available in cleaned_data.
        
        name = file.name.lower() #converts it to lowercase so that checking the file extension is case-insensitive

        if not name.endswith(".pdf"):
            raise forms.ValidationError("Only .pdf files are allowed")
        
        if file.size and file.size > 20 * 1024 *1024 :   # if file exists and if the file's within 20 MB
            raise forms.ValidationError("Pdf too large (Max 20 MB)")
        
        return file

