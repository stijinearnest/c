from django.http import HttpResponse
from django.utils import timezone
import datetime
from reportlab.platypus import SimpleDocTemplate, Paragraph, Spacer, Table
from reportlab.lib import colors
from reportlab.lib.styles import getSampleStyleSheet
from django.db.models import Count
from django.utils.timezone import now
from datetime import timedelta
from django.db.models import Count, Q
from django.utils import timezone
from django.core.mail import send_mail
from django.conf import settings
from .models import StudentProfile
from django.contrib.auth.models import Group
from django.contrib.auth.models import User, Group
from django.db.models import Count
from django.contrib.auth.decorators import user_passes_test
from django.utils import timezone
import datetime
from datetime import time as dtime, timedelta
from django.core.mail import send_mail
from django.conf import settings
from django.shortcuts import render, redirect, get_object_or_404
from django.contrib.auth import authenticate, login, logout
from django.contrib.auth.decorators import login_required
from .forms import CounselorLoginForm, SlotCreateForm, StudentLoginForm, BookingForm
from .models import Slot, Booking
from django.contrib import messages

from django.contrib.auth.decorators import login_required
from django.core.exceptions import PermissionDenied
def is_principal(user):
    return user.is_authenticated and user.groups.filter(name="Principal").exists()

def principal_required(view_func):
    @login_required
    def wrapper(request, *args, **kwargs):
        if not is_principal(request.user):
            raise PermissionDenied
        return view_func(request, *args, **kwargs)
    return wrapper

def home(request):
    return render(request, 'booking/unified_login.html')

# ----------------- Student flows -----------------
def student_login_view(request):
    if request.method == 'POST':
        form = StudentLoginForm(request.POST)
        if form.is_valid():
            # store student info in session
            request.session['student'] = {
                'name': form.cleaned_data['student_name'],
                'email': form.cleaned_data['student_email'],
            }
            return redirect('booking:student_dashboard')
    else:
        form = StudentLoginForm()
    return render(request, 'booking/student_login.html', {'form': form})

def student_logout(request):
    request.session.pop('student', None)
    return redirect('booking:home')

def get_all_future_sessions():
    sessions = []
    now = timezone.now()

    slots = Slot.objects.filter(
        date__gte=datetime.date.today()
    ).order_by('date', 'start_time')

    for slot in slots:
        for sstart, send in slot.generate_sessions():

            # 🔥 Create datetime
            session_datetime = datetime.datetime.combine(slot.date, sstart)

            # 🔥 Convert to timezone-aware
            session_datetime = timezone.make_aware(session_datetime)

            # 🔥 Skip past sessions
            if session_datetime <= now:
                continue

            sessions.append({
                'slot': slot,
                'session_start': sstart,
                'session_end': send,
                'datetime': session_datetime
            })

    return sorted(sessions, key=lambda x: x['datetime'])

    
def student_dashboard(request):
    student = request.session.get('student')
    if not student:
        return redirect('booking:student_login')

    slots = Slot.objects.filter(date__gte=datetime.date.today()).order_by('date', 'start_time')

    available = []

    now = timezone.now()

    for slot in slots:
        for sstart, send in slot.generate_sessions():

            session_datetime = datetime.datetime.combine(slot.date, sstart)

        # 🔥 MAKE AWARE (THIS IS WHAT YOU MISSED)
            session_datetime = timezone.make_aware(session_datetime)

        # 🔥 SKIP PAST SESSIONS
            if session_datetime <= now:
                continue

            booked = Booking.objects.filter(slot=slot, session_start=sstart).exists()

            if not booked:
                available.append({
                'slot': slot,
                'session_start': sstart.strftime('%H:%M:%S'),
                'session_end': send.strftime('%H:%M:%S'),
            })

    # 🔥 NEW: FIND EMERGENCY SLOT
    all_sessions = get_all_future_sessions()
    emergency_slot = None

    for session in all_sessions:
        existing = Booking.objects.filter(
            slot=session['slot'],
            session_start=session['session_start']
        ).first()

        # ✅ FREE SLOT
        if not existing:
            emergency_slot = session
            break

        # ❌ Skip if already emergency
        if existing.is_emergency:
            continue

        # 🔁 Can displace normal booking
        emergency_slot = session
        break

    return render(request, 'booking/student_dashboard.html', {
        'student': student,
        'available': available,
        'emergency_slot': emergency_slot   # 🔥 PASS THIS
    })
def book_session(request, slot_id, session_start):

    student_in_session = request.session.get('student')

    # 🔥 Detect emergency booking
    is_emergency_request = request.GET.get("emergency") == "true"

    slot = None
    sstart = None

    # ================================
    # 🟢 NORMAL BOOKING
    # ================================
    if not is_emergency_request:
        slot = get_object_or_404(Slot, id=slot_id)
        sstart = datetime.datetime.strptime(session_start, '%H:%M:%S').time()

    # ================================
    # 🚨 EMERGENCY BOOKING (PREVIEW SLOT)
    # ================================
    else:
        all_sessions = get_all_future_sessions()

        for session in all_sessions:
            existing = Booking.objects.filter(
                slot=session['slot'],
                session_start=session['session_start']
            ).first()

            # Take first free OR replaceable slot
            if not existing or not existing.is_emergency:
                slot = session['slot']
                sstart = session['session_start']
                break

    # ================================
    # 📩 FORM SUBMISSION
    # ================================
    if request.method == 'POST':
        form = BookingForm(request.POST)

        if form.is_valid():
            b = form.save(commit=False)

            # 🔥 FORCE emergency mode (NO checkbox dependency)
            b.is_emergency = is_emergency_request

            # -----------------------------------------
            # 🔹 CREATE OR UPDATE STUDENT PROFILE
            # -----------------------------------------
            student_name = form.cleaned_data['student_name']
            student_email = form.cleaned_data['student_email']

            student, created = StudentProfile.objects.get_or_create(
                email=student_email,
                defaults={'name': student_name}
            )

            if not created and student.name != student_name:
                student.name = student_name
                student.save()

            b.student = student

            # =========================================
            # 🚨 EMERGENCY BOOKING LOGIC
            # =========================================
            if b.is_emergency:

                all_sessions = get_all_future_sessions()
                assigned = False

                for session in all_sessions:

                    slot_obj = session['slot']
                    start_time = session['session_start']
                    end_time = session['session_end']

                    existing_booking = Booking.objects.filter(
                        slot=slot_obj,
                        session_start=start_time
                    ).first()

                    # ✅ FREE SLOT
                    if not existing_booking:
                        b.slot = slot_obj
                        b.session_start = start_time
                        b.session_end = end_time
                        assigned = True
                        break

                    # ❌ Skip emergency
                    if existing_booking.is_emergency:
                        continue

                    # 🔁 Displace normal booking
                    displaced = existing_booking

                    next_free = None

                    for future in all_sessions:
                        if future['datetime'] <= session['datetime']:
                            continue

                        is_taken = Booking.objects.filter(
                            slot=future['slot'],
                            session_start=future['session_start']
                        ).exists()

                        if not is_taken:
                            next_free = future
                            break

                    if next_free:
                        # 🔥 Save old details
                        old_date = displaced.slot.date
                        old_time = displaced.session_start

                        # 🔁 Move booking
                        displaced.slot = next_free['slot']
                        displaced.session_start = next_free['session_start']
                        displaced.session_end = next_free['session_end']
                        displaced.save()

                        # 📧 SEND EMAIL (RESTORED)
                        send_mail(
                            "Your Counseling Appointment Has Been Rescheduled",
                            f"""
Dear {displaced.student.name},

Your appointment on {old_date} at {old_time}
was rescheduled due to an emergency booking.

New Date: {next_free['slot'].date}
New Time: {next_free['session_start']}

Regards,
Counseling Team
""",
                            settings.DEFAULT_FROM_EMAIL,
                            [displaced.student.email],
                            fail_silently=True,
                        )

                        # 🚨 Assign emergency slot
                        b.slot = slot_obj
                        b.session_start = start_time
                        b.session_end = end_time
                        assigned = True
                        break

                if not assigned:
                    messages.error(request, "No available slots for emergency booking.")
                    return redirect('booking:student_dashboard')

            # =========================================
            # 🟢 NORMAL BOOKING LOGIC
            # =========================================
            else:
                if Booking.objects.filter(slot=slot, session_start=sstart).exists():
                    messages.error(request, "Sorry, this session was just booked.")
                    return redirect('booking:student_dashboard')

                b.slot = slot
                b.session_start = sstart
                b.session_end = (
                    datetime.datetime.combine(slot.date, sstart)
                    + datetime.timedelta(minutes=60)
                ).time()

            # 💾 SAVE BOOKING
            b.save()

            messages.success(
                request,
                "Emergency booking successful!" if b.is_emergency else "Booking successful!"
            )

            return redirect('booking:student_dashboard')

    # ================================
    # 🧾 FORM LOAD (GET)
    # ================================
    else:
        initial = {}
        if student_in_session:
            initial['student_name'] = student_in_session.get('name')
            initial['student_email'] = student_in_session.get('email')

        form = BookingForm(initial=initial)

    return render(
        request,
        'booking/book_session.html',
        {
            'form': form,
            'slot': slot,
            'session_start': sstart,
            'is_emergency': is_emergency_request
        }
    )
@login_required
def counselor_logout(request):
    logout(request)
    return redirect('booking:login')

@login_required
def counselor_dashboard(request):
    # basic summary: upcoming slots & bookings
    slots = Slot.objects.filter(counselor=request.user, date__gte=datetime.date.today()).order_by('date')
    return render(request, 'booking/counselor_dashboard.html', {
    'slots': slots,
    'today': datetime.date.today()
})

@login_required
def add_slot(request):
    if request.method == 'POST':
        form = SlotCreateForm(request.POST)
        if form.is_valid():
            slot = form.save(commit=False)
            slot.counselor = request.user
            slot.save()
            messages.success(request, "Slot added. 15-min sessions generated automatically for booking.")
            return redirect('booking:counselor_dashboard')
    else:
        form = SlotCreateForm()
    return render(request, 'booking/add_slot.html', {'form': form})

@login_required
def counselor_bookings(request):
    # show bookings for upcoming slots
    bookings = Booking.objects.filter(slot__counselor=request.user, slot__date__gte=datetime.date.today()).order_by('slot__date', 'session_start')
  # Your bookings queryset
    
    context = {
        'bookings': bookings,
        'pending_count': bookings.filter(attended=False).count(),
        'emergency_count': bookings.filter(is_emergency=True).count(),
    }
  
    return render(request, 'booking/counselor_bookings.html', context)


@login_required
def counselor_history(request):

    selected_date = request.GET.get("date")

    # 🎯 Default = TODAY
    if selected_date:
        bookings = Booking.objects.filter(
            slot__counselor=request.user,
            slot__date=selected_date
        )
    else:
        today = timezone.now().date()
        bookings = Booking.objects.filter(
            slot__counselor=request.user,
            slot__date=today
        )
        selected_date = today  # for template

    bookings = bookings.order_by('-session_start')
    context = {
        'bookings': bookings,
        'selected_date': selected_date,
        'attended_count': bookings.filter(attended=True).count(),
        'pending_count': bookings.filter(attended=False).count(),
        'bookings_with_remarks': bookings.exclude(counselor_remark__isnull=True).exclude(counselor_remark__exact='').count(),
    }
    return render(request, 'booking/counselor_history.html', context)

   
@login_required
def add_remark(request, booking_id):
    booking = get_object_or_404(Booking, id=booking_id, slot__counselor=request.user)
    if request.method == 'POST':
        remark = request.POST.get('remark', '').strip()
        booking.counselor_remark = remark
        booking.attended = True if request.POST.get('attended') == 'on' else booking.attended
        booking.save()
        messages.success(request, "Remark saved.")
        return redirect('booking:counselor_history')
    return render(request, 'booking/add_remark.html', {'booking': booking})

def staff_login_view(request):

    # 🟢 If already logged in → redirect to dashboard (DON'T logout)
    if request.method == "GET" and request.user.is_authenticated:
        if request.user.groups.filter(name="Principal").exists():
            return redirect('booking:principal_dashboard')
        elif request.user.groups.filter(name="Counselor").exists():
            return redirect('booking:counselor_dashboard')

    # 🔵 Handle login form
    if request.method == 'POST':
        form = CounselorLoginForm(data=request.POST)

        if form.is_valid():

            # 🔥 Logout existing user ONLY when switching accounts
            if request.user.is_authenticated:
                logout(request)

            user = form.get_user()
            login(request, user)

            # 🎯 Redirect based on role
            if user.groups.filter(name="Principal").exists():
                return redirect('booking:principal_dashboard')

            elif user.groups.filter(name="Counselor").exists():
                return redirect('booking:counselor_dashboard')

            else:
                logout(request)
                messages.error(request, "Unauthorized account.")
                return redirect('booking:home')

        else:
            messages.error(request, "Invalid credentials.")
            return redirect('booking:home')

    # 🧾 Show login page
    return render(request, 'booking/unified_login.html')
@principal_required
def principal_dashboard(request):
    total_bookings = Booking.objects.count()
    attended = Booking.objects.filter(attended=True).count()
    not_attended = total_bookings - attended

    counselors = User.objects.filter(groups__name="Counselor")
    per_counselor = []
    for counselor in counselors:
        bookings = Booking.objects.filter(slot__counselor=counselor)
        per_counselor.append({
            'slot__counselor__username': counselor.username,
            'total': bookings.count(),
            'attended': bookings.filter(attended=True).count(),
            'pending': bookings.filter(attended=False).count(),
            'first_booking_date': bookings.order_by('slot__date').first().slot.date if bookings.exists() else None,
        })
    
    context = {
        'total_bookings': total_bookings,
        'attended': attended,
        'not_attended': not_attended,
        'per_counselor': per_counselor,
    }
    return render(request, 'booking/principal_dashboard.html', context)

@principal_required

def add_counselor(request):
    if request.method == 'POST':
        username = request.POST.get('username', '').strip()
        email = request.POST.get('email', '').strip()
        password = request.POST.get('password', '').strip()

        if not username or not email or not password:
            messages.error(request, "All fields are required.")
            return redirect('booking:add_counselor')

        if User.objects.filter(username=username).exists():
            messages.error(request, "Username already exists.")
            return redirect('booking:add_counselor')

        if User.objects.filter(email=email).exists():
            messages.error(request, "Email already in use.")
            return redirect('booking:add_counselor')

        user = User.objects.create_user(
            username=username,
            email=email,
            password=password,
            is_active=True
        )

        Group.objects.get(name="Counselor").user_set.add(user)

        messages.success(request, "Counselor added successfully.")
        return redirect('booking:principal_dashboard')

    return render(request, 'booking/add_counselor.html')


@principal_required
def delete_counselor(request, user_id):
    counselor = get_object_or_404(User, id=user_id)

    # Safety: ensure user is actually a counselor
    if not counselor.groups.filter(name="Counselor").exists():
        messages.error(request, "This user is not a counselor.")
        return redirect('booking:principal_dashboard')

    # Optional safety: prevent deletion if bookings exist
    has_bookings = Booking.objects.filter(
        slot__counselor=counselor
    ).exists()

    if has_bookings:
        messages.error(
            request,
            "Cannot delete counselor with existing bookings."
        )
        return redirect('booking:principal_dashboard')

    counselor.delete()
    messages.success(request, "Counselor deleted successfully.")
    return redirect('booking:principal_dashboard')




@login_required
def student_search(request):

    students = None
    query = None

    if request.method == "POST":
        query = request.POST.get("name", "").strip()

        if query:
            students = StudentProfile.objects.filter(
                name__icontains=query
            ).order_by("name")

    return render(request, "booking/student_search.html", {
        "students": students,
        "query": query
    })

@login_required
def student_detail(request, student_id):

    student = get_object_or_404(StudentProfile, id=student_id)

    bookings = student.bookings.select_related("slot").order_by(
        "-slot__date",
        "-session_start"
    )
    context = {
        'student': student,
        'bookings': bookings,
        'attended_count': bookings.filter(attended=True).count(),
        'pending_count': bookings.filter(attended=False).count(),
    }
    return render(request, 'booking/student_detail.html', context)
   

@principal_required
def principal_analytics(request):

    counselors = User.objects.filter(groups__name="Counselor")

    counselor_id = request.GET.get("counselor")
    start_date = request.GET.get("start")
    end_date = request.GET.get("end")

    bookings = Booking.objects.all()

    if counselor_id:
        bookings = bookings.filter(slot__counselor_id=counselor_id)

    if start_date:
        bookings = bookings.filter(slot__date__gte=start_date)

    if end_date:
        bookings = bookings.filter(slot__date__lte=end_date)

    total = bookings.count()
    attended = bookings.filter(attended=True).count()
    not_attended = total - attended
    emergency = bookings.filter(is_emergency=True).count()
    regular = total - emergency   # 👈 ADD THIS

    context = {
        "counselors": counselors,
        "total": total,
        "attended": attended,
        "not_attended": not_attended,
        "emergency": emergency,
        "regular": regular,   # 👈 PASS IT
        "selected_counselor": counselor_id,
        "start_date": start_date,
        "end_date": end_date,
    }

    return render(request, "booking/principal_analytics.html", context)



@principal_required
def principal_insights(request):

    insights = []

    today = now().date()
    first_day_this_month = today.replace(day=1)

    last_month = first_day_this_month - timedelta(days=1)
    first_day_last_month = last_month.replace(day=1)

    current_month = Booking.objects.filter(
        slot__date__gte=first_day_this_month
    )

    last_month_qs = Booking.objects.filter(
        slot__date__gte=first_day_last_month,
        slot__date__lt=first_day_this_month
    )

    current_count = current_month.count()
    last_count = last_month_qs.count()

    # 📈 Booking Trend Insight
    if last_count > 0:
        change = ((current_count - last_count) / last_count) * 100
        if change > 10:
            insights.append({
                "type": "positive",
                "message": f"Bookings increased by {round(change,1)}% compared to last month."
            })
        elif change < -10:
            insights.append({
                "type": "negative",
                "message": f"Bookings decreased by {abs(round(change,1))}% compared to last month."
            })

    # ⚠ Attendance Insight
    total = Booking.objects.count()
    attended = Booking.objects.filter(attended=True).count()

    if total > 0:
        rate = (attended / total) * 100
        if rate < 70:
            insights.append({
                "type": "warning",
                "message": "Attendance rate is below 70%."
            })

    # 🚨 Emergency Spike
    emergency = Booking.objects.filter(is_emergency=True).count()
    if total > 0:
        emergency_rate = (emergency / total) * 100
        if emergency_rate > 30:
            insights.append({
                "type": "critical",
                "message": "High emergency booking rate detected."
            })

    # 🔥 Top Counselor
    top = (
        Booking.objects
        .values('slot__counselor__username')
        .annotate(total=Count('id'))
        .order_by('-total')                                                  
        .first()
    )

    if top:
        insights.append({
            "type": "info",
            "message": f"{top['slot__counselor__username']} handled the highest number of bookings."
        })

    return render(request, "booking/principal_insights.html", {
        "insights": insights
    })                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                  

@principal_required
def download_analytics_pdf(request):

    counselor_id = request.GET.get("counselor")
    start_date = request.GET.get("start")
    end_date = request.GET.get("end")

    bookings = Booking.objects.all()

# ✅ Only apply filters if valid values exist
    if counselor_id and counselor_id != "None":
        bookings = bookings.filter(slot__counselor_id=counselor_id)

    if start_date and start_date != "None":
        bookings = bookings.filter(slot__date__gte=start_date)

    if end_date and end_date != "None":
        bookings = bookings.filter(slot__date__lte=end_date)
    total = bookings.count()
    attended = bookings.filter(attended=True).count()
    not_attended = total - attended
    emergency = bookings.filter(is_emergency=True).count()
    regular = total - emergency

    # 📄 Create response
    response = HttpResponse(content_type='application/pdf')
    response['Content-Disposition'] = 'attachment; filename="analytics_report.pdf"'

    doc = SimpleDocTemplate(response)
    styles = getSampleStyleSheet()

    # 🎯 Make labels user-friendly
    counselor_label = "All Counselors" if not counselor_id else counselor_id
    date_label = f"{start_date or 'Beginning'} to {end_date or 'Today'}"

    elements = []

    # Title
    elements.append(Paragraph("Counseling Analytics Report", styles['Title']))
    elements.append(Spacer(1, 20))

    # Filters
    elements.append(Paragraph("Filters Applied:", styles['Heading3']))
    elements.append(Paragraph(f"Counselor: {counselor_label}", styles['Normal']))
    elements.append(Paragraph(f"Date Range: {date_label}", styles['Normal']))
    elements.append(Spacer(1, 20))

    # Table Data
    data = [
        ["Metric", "Value"],
        ["Total Bookings", total],
        ["Attended", attended],
        ["Not Attended", not_attended],
        ["Emergency", emergency],
        ["Regular", regular],
    ]

    table = Table(data)
    table.setStyle([
        ('BACKGROUND', (0, 0), (-1, 0), colors.grey),
        ('TEXTCOLOR', (0, 0), (-1, 0), colors.white),
        ('GRID', (0, 0), (-1, -1), 1, colors.black),
    ])

    elements.append(table)

    doc.build(elements)

    return response