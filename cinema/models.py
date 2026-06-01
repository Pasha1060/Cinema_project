from django.conf import settings
from django.db import models
from django.db.models.signals import post_save
from django.dispatch import receiver

class Genre(models.Model):
    name = models.CharField('Название', max_length=100, unique=True)

    class Meta:
        verbose_name = 'Жанр'
        verbose_name_plural = 'Жанры'

    def __str__(self):
        return self.name


class Movie(models.Model):
    title = models.CharField('Название', max_length=255)
    description = models.TextField('Описание')
    duration = models.PositiveIntegerField('Длительность, мин')
    age_limit = models.CharField('Возрастное ограничение', max_length=10)
    poster = models.ImageField('Постер', upload_to='posters/', blank=True, null=True)
    genres = models.ManyToManyField(Genre, verbose_name='Жанры', related_name='movies')

    class Meta:
        verbose_name = 'Фильм'
        verbose_name_plural = 'Фильмы'

    def __str__(self):
        return self.title


class Hall(models.Model):
    name = models.CharField('Название', max_length=100, unique=True)
    rows_count = models.PositiveIntegerField('Количество рядов')
    seats_per_row = models.PositiveIntegerField('Мест в ряду')

    class Meta:
        verbose_name = 'Зал'
        verbose_name_plural = 'Залы'

    def __str__(self):
        return self.name


class Seat(models.Model):
    hall = models.ForeignKey(Hall, verbose_name='Зал', on_delete=models.CASCADE, related_name='seats')
    row_number = models.PositiveIntegerField('Ряд')
    seat_number = models.PositiveIntegerField('Номер места')

    class Meta:
        verbose_name = 'Место'
        verbose_name_plural = 'Места'
        unique_together = ('hall', 'row_number', 'seat_number')

    def __str__(self):
        return f'{self.hall.name}, ряд {self.row_number}, место {self.seat_number}'


class Session(models.Model):
    movie = models.ForeignKey(Movie, verbose_name='Фильм', on_delete=models.CASCADE, related_name='sessions')
    hall = models.ForeignKey(Hall, verbose_name='Зал', on_delete=models.CASCADE, related_name='sessions')
    start_time = models.DateTimeField('Дата и время начала')
    price = models.DecimalField('Цена', max_digits=8, decimal_places=2)

    class Meta:
        verbose_name = 'Сеанс'
        verbose_name_plural = 'Сеансы'
        ordering = ['start_time']

    def __str__(self):
        return f'{self.movie.title} — {self.start_time}'


class Booking(models.Model):
    STATUS_CHOICES = [
        ('active', 'Активно'),
        ('cancelled', 'Отменено'),
    ]

    user = models.ForeignKey(settings.AUTH_USER_MODEL, verbose_name='Пользователь', on_delete=models.CASCADE, related_name='bookings')
    session = models.ForeignKey(Session, verbose_name='Сеанс', on_delete=models.CASCADE, related_name='bookings')
    status = models.CharField('Статус', max_length=20, choices=STATUS_CHOICES, default='active')
    created_at = models.DateTimeField('Дата создания', auto_now_add=True)

    class Meta:
        verbose_name = 'Бронирование'
        verbose_name_plural = 'Бронирования'

    def __str__(self):
        return f'Бронирование #{self.id} — {self.user}'


class BookingSeat(models.Model):
    booking = models.ForeignKey(Booking, verbose_name='Бронирование', on_delete=models.CASCADE, related_name='booking_seats')
    seat = models.ForeignKey(Seat, verbose_name='Место', on_delete=models.CASCADE, related_name='booking_seats')

    class Meta:
        verbose_name = 'Место в бронировании'
        verbose_name_plural = 'Места в бронировании'
        unique_together = ('booking', 'seat')

    def __str__(self):
        return f'{self.booking} — {self.seat}'

@receiver(post_save, sender=Hall)
def create_seats_for_hall(sender, instance, created, **kwargs):
    """
    Автоматическое создание мест для зала после его сохранения.
    Если места уже существуют, повторно они не создаются.
    """
    for row_number in range(1, instance.rows_count + 1):
        for seat_number in range(1, instance.seats_per_row + 1):
            Seat.objects.get_or_create(
                hall=instance,
                row_number=row_number,
                seat_number=seat_number
            )