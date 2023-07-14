from django.urls import path

from .views import picker 

urlpatterns = [
    path('', picker, name='apps.picker'),
    path('<str:day>/<str:venue>/<str:region>', picker, name='apps.picker'),
]