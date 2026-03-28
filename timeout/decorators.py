from functools import wraps

from django.http import JsonResponse, HttpResponseForbidden


def staff_required(view_func):
    """Decorator: allow only staff users. Returns 403 JSON for AJAX, HttpResponseForbidden otherwise."""
    @wraps(view_func)
    def wrapper(request, *args, **kwargs):
        if not request.user.is_staff:
            if request.headers.get('X-Requested-With') == 'XMLHttpRequest':
                return JsonResponse({'error': 'Staff access required.'}, status=403)
            return HttpResponseForbidden('Staff access required.')
        return view_func(request, *args, **kwargs)
    return wrapper
