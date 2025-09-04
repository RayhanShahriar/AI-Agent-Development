from rest_framework.response import Response
from rest_framework import status
from rest_framework.views import APIView
from account.serializers import *
from django.contrib.auth import authenticate
from account.renderers import *
from rest_framework_simplejwt.tokens import RefreshToken
from rest_framework_simplejwt.exceptions import AuthenticationFailed
from rest_framework.permissions import IsAuthenticated
from django.shortcuts import render
import requests
from django.shortcuts import render, redirect
from django.contrib import messages
from .forms import *
from django.contrib.auth.decorators import login_required
from django.shortcuts import render, redirect
from django.contrib import messages




#Generating tokens manually
def get_tokens_for_user(user):
    if not user.is_active:
      raise AuthenticationFailed("User is not active")

    refresh = RefreshToken.for_user(user)

    return {
        'refresh': str(refresh),
        'access': str(refresh.access_token),
    }


class UserRegistrationView(APIView):
    renderer_classes = [UserRenderer]
    def post(self,request, format = None):
        serializer = UserRegistrationSerializer(data = request.data)
        if serializer.is_valid(raise_exception = True):
            user = serializer.save()
            token= get_tokens_for_user(user)
            return Response({'token': token, 'msg':'Registration Successful'}, status = status.HTTP_201_CREATED)
        return Response(serializer.errors, status= status.HTTP_400_BAD_REQUEST)
        

class UserLoginView(APIView):
    renderer_classes = [UserRenderer]
    def post(self,request, format = None):
        serializer = UserLoginSerializer(data = request.data)
        if serializer.is_valid(raise_exception = True):
            email = serializer.data.get('email')
            password = serializer.data.get('password')
            user = authenticate(email = email, password = password)
            if user is not None:
                token= get_tokens_for_user(user)
                return Response({'token': token,'msg':'Login Successful'}, status = status.HTTP_200_OK)
            
            else:
                return Response({'errors': {'non_field_errors': ['Email or password is not valid']}}, status= status.HTTP_404_NOT_FOUND)
        return Response(serializer.errors, status= status.HTTP_400_BAD_REQUEST)
    

class UserProfileView(APIView):
    renderer_classes = [UserRenderer]
    permission_classes =[IsAuthenticated]
    def get(self,request, format = None):
        serializer = UserProfileSerializer(request.user)
        return Response(serializer.data, status= status.HTTP_200_OK)
    




#Frontend

def login_page(request):
    return render(request, "login.html")

def signup_page(request):
    return render(request, "signup.html")





def login_page(request):
    if request.method == "POST":
        form = LoginForm(request.POST)
        if form.is_valid():
            email = form.cleaned_data["email"]
            password = form.cleaned_data["password"]

            # Call your API endpoint
            response = requests.post("http://127.0.0.1:8000/api/user/login/", json={
                "email": email,
                "password": password
            })

            if response.status_code == 200: ##HTTP_200_OK
                data = response.json()
                # Save token in session
                request.session["access"] = data["token"]["access"]
                request.session["refresh"] = data["token"]["refresh"]
                messages.success(request, "Login successful ✅")
                return redirect("qna_page")  # send user to homepage
            else:
                messages.error(request, "Invalid email or password ❌")
    else:
        form = LoginForm()

    return render(request, "login.html", {"form": form})




#####Sign Up####

def signup_page(request):
    if request.method == "POST":
        form = SignUpForm(request.POST)
        if form.is_valid():
            name = form.cleaned_data["name"]
            email = form.cleaned_data["email"]
            password = form.cleaned_data["password"]
            password2 = form.cleaned_data["password2"]
            tc = form.cleaned_data["tc"]

            if password != password2:
                messages.error(request, "Passwords do not match ❌")
                return render(request, "signup.html", {"form": form})

            if not tc:
                messages.error(request, "You must accept Terms & Conditions ❌")
                return render(request, "signup.html", {"form": form})

            # Call API for registration
            response = requests.post("http://127.0.0.1:8000/api/user/register/", json={
                "name": name,
                "email": email,
                "password": password,
                "password2": password2,
                "tc": tc
            })

            if response.status_code == 201:
                messages.success(request, "✅ Registration successful, please login!")
                return redirect("login_page")
            else:
                messages.error(request, "❌ Registration failed: " + str(response.json()))
                return render(request, "signup.html", {"form": form})
    else:
        form = SignUpForm()

    return render(request, "signup.html", {"form": form})



@login_required
def qna_page(request):
    if request.method == "POST":
        question = request.POST.get("question")
        if question:
            # You can save this question to your database
            messages.success(request, f"✅ Question submitted: {question}")
        else:
            messages.error(request, "❌ Please enter a question")
    return render(request, "QnA.html")
