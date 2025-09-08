# In your forms.py
from django import forms

class LoginForm(forms.Form):
    LOGIN_TYPE_CHOICES = [
        ('user', 'User'),
        ('admin', 'Admin'),
    ]
    
    login_type = forms.ChoiceField(
        choices=LOGIN_TYPE_CHOICES,
        widget=forms.RadioSelect,
        initial='user',
        required=True
    )
    email = forms.EmailField(
        widget=forms.EmailInput(attrs={
            'placeholder': 'Enter your email address',
            'class': 'form-control'
        })
    )
    password = forms.CharField(
        widget=forms.PasswordInput(attrs={
            'placeholder': 'Enter your password',
            'class': 'form-control'
        })
    )

class SignUpForm(forms.Form):
    name = forms.CharField(
        max_length=100,
        widget=forms.TextInput(attrs={
            'placeholder': 'Enter your full name',
            'class': 'form-control'
        })
    )
    email = forms.EmailField(
        widget=forms.EmailInput(attrs={
            'placeholder': 'Enter your email address',
            'class': 'form-control'
        })
    )
    password = forms.CharField(
        widget=forms.PasswordInput(attrs={
            'placeholder': 'Create a password',
            'class': 'form-control'
        })
    )
    password2 = forms.CharField(
        widget=forms.PasswordInput(attrs={
            'placeholder': 'Confirm your password',
            'class': 'form-control'
        })
    )
    tc = forms.BooleanField(
        required=True,
        widget=forms.CheckboxInput(attrs={
            'class': 'form-check-input'
        }),
        label="I agree to the Terms and Conditions"
    )