from django.urls import path
from . import views

urlpatterns = [

      path('contact/', views.contact, name='contact'),
      path('index/', views.index, name='index'),
      path('blog_1/', views.blog_1, name='blog_1'),
      path('login/', views.login, name='login'),
      path('map/', views.map, name='map'),

]

