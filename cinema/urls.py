from django.urls import path
from . import views

app_name = 'cinema'

urlpatterns = [
    path('', views.index, name='index'),

    path('movies/', views.movies_list, name='movies_list'),
    path('movies/<int:movie_id>/', views.movie_detail, name='movie_detail'),

    path('sessions/<int:session_id>/seats/', views.seat_selection, name='seat_selection'),
    path('sessions/<int:session_id>/booking/create/', views.create_booking, name='create_booking'),

    path('profile/', views.profile, name='profile'),

    path('register/', views.register_view, name='register'),
    path('login/', views.login_view, name='login'),
    path('logout/', views.logout_view, name='logout'),
    path('bookings/<int:booking_id>/cancel/', views.cancel_booking, name='cancel_booking'),
]