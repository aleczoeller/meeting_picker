from django.urls import path

from .views import picker 

app_name = 'na_picker'

urlpatterns = [
    path('<str:day>/<str:venue>/<str:region>/', picker, name='picker'),
]