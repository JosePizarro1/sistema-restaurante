import os

import pusher


def trigger_pusher_event(event_name, data=None):
    """Dispara un evento en Pusher al canal 'cocina-channel'.

    Falla de forma silenciosa para no bloquear las solicitudes HTTP de la app si hay error de red.
    """
    app_id = os.environ.get('PUSHER_APP_ID')
    key = os.environ.get('PUSHER_KEY')
    secret = os.environ.get('PUSHER_SECRET')
    cluster = os.environ.get('PUSHER_CLUSTER', 'us2')

    if not app_id or not key or not secret:
        return

    try:
        pusher_client = pusher.Pusher(
            app_id=app_id,
            key=key,
            secret=secret,
            cluster=cluster,
            ssl=True
        )
        pusher_client.trigger('cocina-channel', event_name, data or {})
    except Exception as e:  # noqa: BLE001
        print(f"Error al disparar evento Pusher '{event_name}': {e}")

