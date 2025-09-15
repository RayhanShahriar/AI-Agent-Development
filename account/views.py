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
from django.contrib.auth import get_user_model
from django.contrib.auth import authenticate, login, logout



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
            username = serializer.data.get('username')
            password = serializer.data.get('password')
            user = authenticate(username = username, password = password)
            if user is not None:
                token= get_tokens_for_user(user)
                return Response({'token': token,'msg':'Login Successful'}, status = status.HTTP_200_OK)
            
            else:
                return Response({'errors': {'non_field_errors': ['Username or password is not valid']}}, status= status.HTTP_404_NOT_FOUND)
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
            username = form.cleaned_data["username"]
            password = form.cleaned_data["password"]

            user = authenticate(request, username=username, password=password)
            if user is not None:
                login(request, user)  # logs in the user
                messages.success(request, "✅ Logged in successfully!")

                # Redirect based on role
                if getattr(user, "is_staff", False) or getattr(user, "is_superuser", False):
                    return redirect("rag_qna_page_admin")
                else:
                    return redirect("rag_qna_page")
            else:
                messages.error(request, "❌ Invalid username or password")
    else:
        form = LoginForm()

    return render(request, "login.html", {"form": form})




#####Sign Up####

User = get_user_model()  # Use custom user model

def signup_page(request):
    if request.method == "POST":
        form = SignUpForm(request.POST)
        if form.is_valid():
            username = form.cleaned_data["username"]
            email = form.cleaned_data["email"]
            password = form.cleaned_data["password"]
            password2 = form.cleaned_data["password2"]

            if password != password2:
                messages.error(request, "Passwords do not match ❌")
                return render(request, "signup.html", {"form": form})

            # Check if username or email already exists
            if User.objects.filter(username=username).exists():
                messages.error(request, "Username already exists ❌")
                return render(request, "signup.html", {"form": form})
            
            if User.objects.filter(email=email).exists():
                messages.error(request, "Email already exists ❌")
                return render(request, "signup.html", {"form": form})

            # Create Django user using custom model
            User.objects.create_user(username=username, email=email, password=password)
            messages.success(request, "✅ Registration successful, please login!")
            return redirect("login_page")
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



@login_required
def admin_page(request):
    return render(request, "admin_dashboard.html")
