# Pequeño helper para lanzar tareas asyncio sin bloquear la UI.
import asyncio
from typing import Coroutine, Any

def run_task(coro: Coroutine[Any, Any, Any]) -> asyncio.Task:
    """
    Lanza `coro` como tarea en el loop actual (o crea uno si no hay),
    y devuelve la Task. Útil para "fire-and-forget".
    """
    try:
        loop = asyncio.get_running_loop()
    except RuntimeError:
        # No hay loop activo (p.ej. hilo principal sin loop): creamos uno.
        loop = asyncio.new_event_loop()
        asyncio.set_event_loop(loop)
    return loop.create_task(coro)
