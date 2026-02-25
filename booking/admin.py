

from django.contrib import admin
from .models import Booking, StudentProfile,CounselorProfile


@admin.register(StudentProfile)
class StudentProfileAdmin(admin.ModelAdmin):
    list_display = ('unique_id', 'name', 'email')
    search_fields = ('unique_id', 'name', 'email')


@admin.register(Booking)
class BookingAdmin(admin.ModelAdmin):
    list_display = ('student', 'slot', 'session_start', 'attended')
    list_filter = ('attended', 'slot__date')
    search_fields = ('student__name', 'student__email')

@admin.register(CounselorProfile)
class CounselorProfileAdmin(admin.ModelAdmin):
    list_display = ('user',)
