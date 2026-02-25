# booking/urls.py
from django.urls import path
from . import views


app_name = 'booking'

urlpatterns = [

    # Home (Unified Login Page)
    path('', views.home, name='home'),

    # Student
    path('student/login/', views.student_login_view, name='student_login'),
    path('student/dashboard/', views.student_dashboard, name='student_dashboard'),
    path('student/book/<int:slot_id>/<str:session_start>/', views.book_session, name='book_session'),
    path('student/logout/', views.student_logout, name='student_logout'),

    # Staff (Counselor + Principal login)
   path('staff/login/', views.staff_login_view, name='login'),

    # Counselor
    path('counselor/dashboard/', views.counselor_dashboard, name='counselor_dashboard'),
    path('counselor/slots/add/', views.add_slot, name='add_slot'),
    path('counselor/bookings/', views.counselor_bookings, name='counselor_bookings'),
    path('counselor/history/', views.counselor_history, name='counselor_history'),
    path('counselor/booking/<int:booking_id>/remark/', views.add_remark, name='add_remark'),
    path('counselor/logout/', views.counselor_logout, name='counselor_logout'),

    # Principal
    path('principal/dashboard/', views.principal_dashboard, name='principal_dashboard'),
    path('principal/add-counselor/', views.add_counselor, name='add_counselor'),
    path('principal/delete-counselor/<int:user_id>/', views.delete_counselor, name='delete_counselor'),
    path('counselor/student-search/', views.student_search, name='student_search'),
path('counselor/student/<int:student_id>/', views.student_detail, name='student_detail'),
path('principal/analytics/', views.principal_analytics, name='principal_analytics'),
path('principal/insights/', views.principal_insights, name='principal_insights'),

]