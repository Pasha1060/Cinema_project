import json
from .seat_locks import (
    clear_expired_locks,
    get_locked_seat_ids,
    release_booked_seats,
    release_seats_by_client,
)
from datetime import timedelta

from django.utils import timezone
from django.contrib import messages
from django.contrib.auth import authenticate, login, logout
from django.contrib.auth.decorators import login_required
from django.contrib.auth.forms import UserCreationForm, AuthenticationForm
from django.db import transaction
from django.http import JsonResponse
from django.shortcuts import get_object_or_404, redirect, render
from django.views.decorators.http import require_POST
from asgiref.sync import async_to_sync
from channels.layers import get_channel_layer
from .models import Movie, Session, Seat, Booking, BookingSeat

def index(request):
    movies = Movie.objects.all()[:4]

    sessions = Session.objects.select_related('movie', 'hall').filter(
        start_time__gt=timezone.now()
    ).order_by('start_time')[:5]

    context = {
        'movies': movies,
        'sessions': sessions,
    }

    return render(request, 'index.html', context)


def movies_list(request):
    movies = Movie.objects.prefetch_related('genres').all()

    context = {
        'movies': movies,
    }

    return render(request, 'movies.html', context)


def movie_detail(request, movie_id):
    movie = get_object_or_404(
        Movie.objects.prefetch_related('genres'),
        id=movie_id
    )

    sessions = Session.objects.filter(
        movie=movie,
        start_time__gt=timezone.now()
    ).order_by('start_time')

    context = {
        'movie': movie,
        'sessions': sessions,
    }

    return render(request, 'movie_detail.html', context)


def seat_selection(request, session_id):
    session = get_object_or_404(
        Session.objects.select_related('movie', 'hall'),
        id=session_id
    )
    expired_locks = clear_expired_locks(session.id)

    booking_available = session.start_time > timezone.now()

    if expired_locks:
        channel_layer = get_channel_layer()

        for lock_data in expired_locks:
            async_to_sync(channel_layer.group_send)(
                f'session_{session.id}',
                {
                    'type': 'seat_status_message',
                    'event_type': 'seat_released',
                    'seat_id': lock_data.get('seat_id'),
                    'row': lock_data.get('row'),
                    'number': lock_data.get('number'),
                    'status': 'free',
                    'sender_channel_name': None,
                }
            )
    client_id = request.GET.get('client_id')

    if client_id:
        released_locks = release_seats_by_client(session.id, client_id)

        if released_locks:
            channel_layer = get_channel_layer()

            for lock_data in released_locks:
                async_to_sync(channel_layer.group_send)(
                    f'session_{session.id}',
                    {
                        'type': 'seat_status_message',
                        'event_type': 'seat_released',
                        'seat_id': lock_data.get('seat_id'),
                        'row': lock_data.get('row'),
                        'number': lock_data.get('number'),
                        'status': 'free',
                        'sender_channel_name': None,
                    }
                )

    seats = Seat.objects.filter(
        hall=session.hall
    ).order_by('row_number', 'seat_number')

    booked_seat_ids = BookingSeat.objects.filter(
        booking__session=session,
        booking__status='active'
    ).values_list('seat_id', flat=True)

    temporary_locked_seat_ids = get_locked_seat_ids(session.id)

    context = {
        'session': session,
        'seats': seats,
        'booked_seat_ids': list(booked_seat_ids),
        'temporary_locked_seat_ids': temporary_locked_seat_ids,
        'booking_available': booking_available,
    }

    return render(request, 'seat_selection.html', context)
@login_required
@require_POST
def create_booking(request, session_id):
    session = get_object_or_404(
        Session.objects.select_related('movie', 'hall'),
        id=session_id
    )
    if session.start_time <= timezone.now():
        return JsonResponse(
            {
                'success': False,
                'message': 'Нельзя забронировать места на сеанс, который уже начался или прошел.'
            },
            status=400
        )
    try:
        data = json.loads(request.body)
        seat_ids = data.get('seat_ids', [])
    except json.JSONDecodeError:
        return JsonResponse(
            {'success': False, 'message': 'Некорректный формат данных.'},
            status=400
        )

    if not seat_ids:
        MAX_SEATS_PER_BOOKING = 4

        if len(seat_ids) > MAX_SEATS_PER_BOOKING:
            return JsonResponse(
                {
                    'success': False,
                    'message': f'За одно бронирование можно выбрать не более {MAX_SEATS_PER_BOOKING} мест.'
                },
                status=400
            )
        return JsonResponse(
            {'success': False, 'message': 'Не выбрано ни одного места.'},
            status=400
        )

    seats = list(
        Seat.objects.filter(
            id__in=seat_ids,
            hall=session.hall
        )
    )

    if len(seats) != len(seat_ids):
        return JsonResponse(
            {'success': False, 'message': 'Одно или несколько мест не найдены в выбранном зале.'},
            status=400
        )

    with transaction.atomic():
        clear_expired_locks(session.id)
        already_booked_seat_ids = set(
            BookingSeat.objects.select_for_update().filter(
                booking__session=session,
                booking__status='active',
                seat_id__in=seat_ids
            ).values_list('seat_id', flat=True)
        )

        if already_booked_seat_ids:
            return JsonResponse(
                {
                    'success': False,
                    'message': 'Одно или несколько выбранных мест уже забронированы.',
                    'booked_seat_ids': list(already_booked_seat_ids),
                },
                status=409
            )

        booking = Booking.objects.create(
            user=request.user,
            session=session,
            status='active'
        )

        BookingSeat.objects.bulk_create([
            BookingSeat(booking=booking, seat=seat)
            for seat in seats
        ])

        release_booked_seats(session.id, seat_ids)

        channel_layer = get_channel_layer()

        for seat in seats:
            async_to_sync(channel_layer.group_send)(
                f'session_{session.id}',
                {
                    'type': 'seat_status_message',
                    'event_type': 'seat_booked',
                    'seat_id': seat.id,
                    'row': seat.row_number,
                    'number': seat.seat_number,
                    'status': 'booked',
                    'sender_channel_name': None,
                }
            )

    return JsonResponse({
        'success': True,
        'message': 'Бронирование успешно создано.',
        'booking_id': booking.id,
        'redirect_url': '/profile/',
    })

@login_required
def profile(request):
    bookings = request.user.bookings.select_related(
        'session',
        'session__movie',
        'session__hall'
    ).prefetch_related(
        'booking_seats',
        'booking_seats__seat'
    ).order_by('-created_at')

    now = timezone.now()

    for booking in bookings:
        time_until_session = booking.session.start_time - now

        booking.can_cancel = (
            booking.status == 'active'
            and time_until_session >= timedelta(hours=24)
        )

    context = {
        'bookings': bookings,
    }

    return render(request, 'profile.html', context)

def register_view(request):
    """
    Регистрация нового пользователя.
    """
    if request.user.is_authenticated:
        return redirect('cinema:index')

    if request.method == 'POST':
        form = UserCreationForm(request.POST)

        if form.is_valid():
            user = form.save()
            login(request, user)
            messages.success(request, 'Регистрация выполнена успешно.')
            return redirect('cinema:index')
    else:
        form = UserCreationForm()

    return render(request, 'register.html', {'form': form})


def login_view(request):
    """
    Авторизация пользователя.
    """
    if request.user.is_authenticated:
        return redirect('cinema:index')

    if request.method == 'POST':
        form = AuthenticationForm(request, data=request.POST)

        if form.is_valid():
            user = form.get_user()
            login(request, user)
            messages.success(request, 'Вход выполнен успешно.')

            next_url = request.GET.get('next')
            if next_url:
                return redirect(next_url)

            return redirect('cinema:index')
    else:
        form = AuthenticationForm()

    return render(request, 'login.html', {'form': form})


def logout_view(request):
    """
    Выход пользователя из системы.
    """
    logout(request)
    messages.info(request, 'Вы вышли из системы.')
    return redirect('cinema:index')
@login_required
@require_POST
def cancel_booking(request, booking_id):
    booking = get_object_or_404(
        Booking.objects.select_related('session'),
        id=booking_id,
        user=request.user
    )

    if booking.status == 'cancelled':
        messages.info(request, 'Бронирование уже было отменено.')
        return redirect('cinema:profile')

    now = timezone.now()
    time_until_session = booking.session.start_time - now

    if time_until_session < timedelta(hours=24):
        messages.error(
            request,
            'Отмена бронирования недоступна, так как до начала сеанса осталось менее суток.'
        )
        return redirect('cinema:profile')

    booking.status = 'cancelled'
    booking.save(update_fields=['status'])

    messages.success(request, 'Бронирование успешно отменено.')
    return redirect('cinema:profile')