import time

from django.core.cache import cache


LOCK_TIMEOUT = 300  # 5 минут


def _session_locks_key(session_id):
    return f'session_{session_id}_temporary_selected_seats'


def _now():
    return int(time.time())


def get_session_locks(session_id):
    locks = cache.get(_session_locks_key(session_id), {})
    locks, _ = clear_expired_locks_from_dict(locks)
    save_session_locks(session_id, locks)
    return locks


def save_session_locks(session_id, locks):
    cache.set(_session_locks_key(session_id), locks, timeout=LOCK_TIMEOUT + 60)


def clear_expired_locks_from_dict(locks):
    current_time = _now()
    expired_locks = []

    for seat_id, lock_data in list(locks.items()):
        expires_at = lock_data.get('expires_at', 0)

        if expires_at <= current_time:
            expired_locks.append(lock_data)
            locks.pop(seat_id, None)

    return locks, expired_locks


def clear_expired_locks(session_id):
    locks = cache.get(_session_locks_key(session_id), {})
    locks, expired_locks = clear_expired_locks_from_dict(locks)
    save_session_locks(session_id, locks)
    return expired_locks


def lock_seat(session_id, seat_id, client_id, row=None, number=None):
    seat_id = str(seat_id)
    locks = get_session_locks(session_id)

    current_lock = locks.get(seat_id)

    if current_lock and current_lock.get('owner') != client_id:
        return False

    current_time = _now()

    locks[seat_id] = {
        'seat_id': seat_id,
        'owner': client_id,
        'row': row,
        'number': number,
        'created_at': current_time,
        'expires_at': current_time + LOCK_TIMEOUT,
    }

    save_session_locks(session_id, locks)
    return True


def release_seat(session_id, seat_id, client_id=None):
    seat_id = str(seat_id)
    locks = get_session_locks(session_id)

    current_lock = locks.get(seat_id)

    if not current_lock:
        return None

    if client_id and current_lock.get('owner') != client_id:
        return None

    released_lock = locks.pop(seat_id)
    save_session_locks(session_id, locks)

    return released_lock


def release_seats_by_client(session_id, client_id):
    locks = get_session_locks(session_id)
    released_locks = []

    for seat_id, lock_data in list(locks.items()):
        if lock_data.get('owner') == client_id:
            released_locks.append(lock_data)
            locks.pop(seat_id, None)

    save_session_locks(session_id, locks)
    return released_locks


def get_locked_seat_ids(session_id):
    locks = get_session_locks(session_id)
    return [int(seat_id) for seat_id in locks.keys()]


def get_locked_seats(session_id):
    locks = get_session_locks(session_id)
    return list(locks.values())


def release_booked_seats(session_id, seat_ids):
    locks = get_session_locks(session_id)

    for seat_id in seat_ids:
        locks.pop(str(seat_id), None)

    save_session_locks(session_id, locks)