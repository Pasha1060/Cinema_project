const pageData = document.getElementById('seat-page-data');
const bookingAvailable = pageData.dataset.bookingAvailable === 'true';
const sessionId = pageData.dataset.sessionId;
const isAuthenticated = pageData.dataset.isAuthenticated === 'true';
const ticketPrice = Number(pageData.dataset.ticketPrice.replace(',', '.'));
const loginUrl = pageData.dataset.loginUrl;
const currentPath = pageData.dataset.currentPath;
const createBookingUrl = pageData.dataset.createBookingUrl;

let clientId = sessionStorage.getItem('seat_client_id');

if (!clientId) {
    clientId = crypto.randomUUID();
    sessionStorage.setItem('seat_client_id', clientId);
}

const currentUrl = new URL(window.location.href);

if (!currentUrl.searchParams.get('client_id')) {
    currentUrl.searchParams.set('client_id', clientId);
    window.location.replace(currentUrl.toString());
}
const selectedSeats = new Map();
const selectedSeatsText = document.getElementById('selected-seats-text');
const totalPriceElement = document.getElementById('total-price');
const bookingButton = document.getElementById('booking-button');

const temporaryLockTime = 5 * 60 * 1000;
let selectionTimer = null;
let selectionStartedAt = null;

const protocol = window.location.protocol === 'https:' ? 'wss' : 'ws';
const seatSocket = new WebSocket(
    `${protocol}://${window.location.host}/ws/sessions/${sessionId}/seats/?client_id=${clientId}`
);
function getCookie(name) {
    let cookieValue = null;

    if (document.cookie && document.cookie !== '') {
        const cookies = document.cookie.split(';');

        for (let i = 0; i < cookies.length; i++) {
            const cookie = cookies[i].trim();

            if (cookie.substring(0, name.length + 1) === (name + '=')) {
                cookieValue = decodeURIComponent(cookie.substring(name.length + 1));
                break;
            }
        }
    }

    return cookieValue;
}

function updateBookingInfo() {
    if (selectedSeats.size === 0) {
        selectedSeatsText.textContent = 'не выбраны';
        totalPriceElement.textContent = '0';
        updateSelectionTimerState();
        return;
    }

    const selectedSeatsLabels = Array.from(selectedSeats.values()).map(seat => {
        return `ряд ${seat.row}, место ${seat.number}`;
    });

    selectedSeatsText.textContent = selectedSeatsLabels.join('; ');

    const totalPrice = selectedSeats.size * ticketPrice;
    totalPriceElement.textContent = totalPrice.toFixed(2);

    updateSelectionTimerState();
}
function releaseAllSelectedSeatsByTimer() {
    selectedSeats.forEach((seat, seatId) => {
        const button = document.querySelector(`[data-seat-id="${seatId}"]`);

        if (button) {
            button.classList.remove('selected');
            button.classList.add('free');
            button.disabled = false;
            button.title = 'Место свободно';
        }

        if (seatSocket.readyState === WebSocket.OPEN) {
            seatSocket.send(JSON.stringify({
                type: 'seat_released',
                seat_id: seatId,
                row: seat.row,
                number: seat.number,
                status: 'free',
                client_id: clientId,
            }));
        }
    });

    selectedSeats.clear();
    updateBookingInfo();
    stopSelectionTimer();

    alert('Время временного выбора мест истекло. Места освобождены.');
}


function startSelectionTimer() {
    if (selectionTimer) {
        return;
    }

    selectionStartedAt = Date.now();

    selectionTimer = setTimeout(() => {
        releaseAllSelectedSeatsByTimer();
    }, temporaryLockTime);
}


function stopSelectionTimer() {
    if (selectionTimer) {
        clearTimeout(selectionTimer);
        selectionTimer = null;
        selectionStartedAt = null;
    }
}


function updateSelectionTimerState() {
    if (selectedSeats.size > 0) {
        startSelectionTimer();
    } else {
        stopSelectionTimer();
    }
}
function removeSeatFromSelection(seatId) {
    const seatIdString = String(seatId);

    selectedSeats.delete(seatIdString);

    const button = document.querySelector(`[data-seat-id="${seatIdString}"]`);

    if (button) {
        button.classList.remove('free');
        button.classList.remove('selected');
        button.classList.remove('temporary-selected');
        button.classList.add('booked');

        button.disabled = true;
        button.title = 'Место забронировано';
    }

    updateBookingInfo();
}


function markSeatTemporarySelected(seatId) {
    const seatIdString = String(seatId);
    const button = document.querySelector(`[data-seat-id="${seatIdString}"]`);

    if (!button || button.classList.contains('booked')) {
        return;
    }

    // Если это место было выбрано текущим пользователем, снимаем его из выбора
    if (selectedSeats.has(seatIdString)) {
        selectedSeats.delete(seatIdString);
    }

    button.classList.remove('free');
    button.classList.remove('selected');
    button.classList.add('temporary-selected');

    button.disabled = true;
    button.title = 'Место временно выбрано другим пользователем';

    updateBookingInfo();
}


function blockSeatAsTemporarySelected(seatId) {
    const seatIdString = String(seatId);

    selectedSeats.delete(seatIdString);

    const button = document.querySelector(`[data-seat-id="${seatIdString}"]`);

    if (button) {
        button.classList.remove('free');
        button.classList.remove('selected');
        button.classList.add('temporary-selected');
        button.disabled = true;
        button.title = 'Место временно выбрано другим пользователем';
    }

    updateBookingInfo();
}
function unmarkSeatTemporarySelected(seatId) {
    const seatIdString = String(seatId);
    const button = document.querySelector(`[data-seat-id="${seatIdString}"]`);

    if (!button || button.classList.contains('booked')) {
        return;
    }

    button.classList.remove('temporary-selected');
    button.classList.remove('selected');
    button.classList.add('free');

    button.disabled = false;
    button.title = 'Место свободно';

    selectedSeats.delete(seatIdString);
    updateBookingInfo();
}
seatSocket.onmessage = function(event) {
    const data = JSON.parse(event.data);

    if (data.type === 'initial_locked_seats') {
        data.locked_seats.forEach(seat => {
            markSeatTemporarySelected(seat.seat_id);
        });
        return;
    }

    if (data.type === 'seat_selected') {
        markSeatTemporarySelected(data.seat_id);
    }

    if (data.type === 'seat_released') {
        unmarkSeatTemporarySelected(data.seat_id);
    }

    if (data.type === 'seat_booked') {
        removeSeatFromSelection(data.seat_id);
    }

    if (data.type === 'seat_lock_failed') {
        alert(data.message || 'Место уже выбрано другим пользователем.');
        blockSeatAsTemporarySelected(data.seat_id);
    }
};

seatSocket.onclose = function() {
    console.log('WebSocket-соединение закрыто.');
};
const seatMap = document.querySelector('.seat-map');

seatMap.addEventListener('click', (event) => {
    const button = event.target.closest('.seat');

    if (!button) {
        return;
    }

    if (button.disabled || button.classList.contains('booked') || button.classList.contains('temporary-selected')) {
        return;
    }

    const seatId = button.dataset.seatId;
    const row = button.dataset.row;
    const number = button.dataset.number;

    if (selectedSeats.has(seatId)) {
        selectedSeats.delete(seatId);
        button.classList.remove('selected');

        if (seatSocket.readyState === WebSocket.OPEN) {
            seatSocket.send(JSON.stringify({
                type: 'seat_released',
                seat_id: seatId,
                row: row,
                number: number,
                status: 'free',
                client_id: clientId,
            }));
        }
    } else {
        const maxSeatsPerBooking = 4;

        if (selectedSeats.size >= maxSeatsPerBooking) {
            alert(`За одно бронирование можно выбрать не более ${maxSeatsPerBooking} мест.`);
            return;
        }
        selectedSeats.set(seatId, {
            row: row,
            number: number,
        });

        button.classList.add('selected');

        if (seatSocket.readyState === WebSocket.OPEN) {
            seatSocket.send(JSON.stringify({
                type: 'seat_selected',
                seat_id: seatId,
                row: row,
                number: number,
                status: 'selected',
                client_id: clientId,
            }));
        }
    }

    updateBookingInfo();
});

bookingButton.addEventListener('click', () => {
    if (!bookingAvailable) {
        alert('Нельзя забронировать места на сеанс, который уже начался или прошел.');
        return;
    }
    if (!isAuthenticated) {
        window.location.href = `${loginUrl}?next=${currentPath}`;
        return;
    }

    if (selectedSeats.size === 0) {
        alert('Выберите хотя бы одно место.');
        return;
    }

    bookingButton.disabled = true;
    bookingButton.textContent = 'Создание бронирования...';

    fetch(createBookingUrl, {
        method: 'POST',
        headers: {
            'Content-Type': 'application/json',
            'X-CSRFToken': getCookie('csrftoken'),
        },
        body: JSON.stringify({
            seat_ids: Array.from(selectedSeats.keys()),
        }),
    })
    .then(response => response.json().then(data => ({
        status: response.status,
        body: data,
    })))
    .then(result => {
        if (result.body.success) {
            stopSelectionTimer();
            selectedSeats.clear();
            alert(result.body.message);
            window.location.href = result.body.redirect_url;
            return;
        }

        alert(result.body.message || 'Ошибка при создании бронирования.');

        if (result.body.booked_seat_ids) {
            result.body.booked_seat_ids.forEach(seatId => {
                removeSeatFromSelection(seatId);
            });

            updateBookingInfo();
        }
    })
    .catch(error => {
        console.error(error);
        alert('Ошибка соединения с сервером.');
    })
    .finally(() => {
        bookingButton.disabled = false;

        if (isAuthenticated) {
            bookingButton.textContent = 'Забронировать';
        } else {
            bookingButton.textContent = 'Войти для бронирования';
        }
    });
});
