from django.contrib import admin

from django.contrib import admin
from .models import Genre, Movie, Hall, Seat, Session, Booking, BookingSeat


@admin.register(Genre)
class GenreAdmin(admin.ModelAdmin):
    list_display = ('id', 'name')
    search_fields = ('name',)


@admin.register(Movie)
class MovieAdmin(admin.ModelAdmin):
    list_display = ('id', 'title', 'duration', 'age_limit')
    search_fields = ('title',)
    list_filter = ('genres',)

class SeatInline(admin.TabularInline):
    model = Seat
    extra = 0
    readonly_fields = ('row_number', 'seat_number')
    can_delete = False
@admin.register(Hall)
class HallAdmin(admin.ModelAdmin):
    list_display = ('id', 'name', 'rows_count', 'seats_per_row')
    inlines = [SeatInline]


@admin.register(Seat)
class SeatAdmin(admin.ModelAdmin):
    list_display = ('id', 'hall', 'row_number', 'seat_number')
    list_filter = ('hall', 'row_number')
    search_fields = ('hall__name',)
    ordering = ('hall', 'row_number', 'seat_number')

@admin.register(Session)
class SessionAdmin(admin.ModelAdmin):
    list_display = ('id', 'movie', 'hall', 'start_time', 'price')
    list_filter = ('hall', 'start_time')
    search_fields = ('movie__title',)


class BookingSeatInline(admin.TabularInline):
    model = BookingSeat
    extra = 0


@admin.register(Booking)
class BookingAdmin(admin.ModelAdmin):
    list_display = ('id', 'user', 'session', 'status', 'created_at')
    list_filter = ('status', 'created_at')
    inlines = [BookingSeatInline]


@admin.register(BookingSeat)
class BookingSeatAdmin(admin.ModelAdmin):
    list_display = ('id', 'booking', 'seat')
