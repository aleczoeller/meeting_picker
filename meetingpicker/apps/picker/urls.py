from django.urls import path, re_path, include

from .views import picker

app_name = 'na_picker'

urlpatterns = [
        path('<str:venue>/<str:region>/<str:day>/', picker, name='picker'),
]
