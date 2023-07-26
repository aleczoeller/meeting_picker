from django.urls import path

from .views import picker, redirect_view

app_name = 'na_picker'

urlpatterns = [
    path('', redirect_view, name='redirect'),
    path('<str:venue>/<str:region>/<str:day>/', picker, name='picker'),
]