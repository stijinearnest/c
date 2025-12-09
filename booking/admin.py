# booking/admin.py
from django.contrib import admin
from .models import Slot, Booking, CounselorProfile

@admin.register(Slot)
class SlotAdmin(admin.ModelAdmin):
    list_display = ('counselor', 'date', 'start_time', 'end_time')

@admin.register(Booking)
class BookingAdmin(admin.ModelAdmin):
    list_display = ('student_name', 'slot', 'session_start', 'created_at', 'attended')

@admin.register(CounselorProfile)
class CounselorProfileAdmin(admin.ModelAdmin):
    list_display = ('user',)
