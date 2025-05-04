from django.urls import path
from .views import *

app_name = 'geral'

urlpatterns = [
    # path('forms/', all_forms, name='all_forms'),
    path('', render_ranking, name='ranking'),
]

