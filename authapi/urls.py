
from django.contrib import admin
from django.urls import path, include
from account.views import *
from django.conf import settings
from django.conf.urls.static import static


urlpatterns = [
    path('', signup_page, name="signup_page"),
    path('admin/', admin.site.urls),
    path('api/user/', include('account.urls')),
    path("login/", login_page, name="login_page"),
    path("signup/", signup_page, name="signup_page"),
    path("qna/", qna_page, name="qna_page"),
    
    path("api/rag/", include("rag.api_urls")),
    path("rag/", include("rag.urls")),
]

if settings.DEBUG:
    urlpatterns += static(settings.MEDIA_URL, document_root=settings.MEDIA_ROOT)

