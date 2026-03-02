from django.shortcuts import get_object_or_404, redirect, render
from django.contrib import messages
from timeout.models import Event
from django.core.exceptions import ValidationError

def event_edit(request, pk):
    """Edit an existing event."""
    event = get_object_or_404(Event, pk=pk, creator=request.user)

    if request.method == "POST":

        is_all_day = request.POST.get("is_all_day") == "on"

        start_datetime = request.POST.get("start_datetime")
        end_datetime = request.POST.get("end_datetime")

        if is_all_day and start_datetime:
            date_part = start_datetime.split("T")[0]
            start_datetime = f"{date_part}T00:00"
            end_datetime = f"{date_part}T23:59"

        event.title = request.POST.get("title", event.title)
        event.start_datetime = start_datetime
        event.end_datetime = end_datetime
        event.description = request.POST.get("description", "")
        event.location = request.POST.get("location", "")
        event.event_type = request.POST.get("event_type", "other")
        event.visibility = request.POST.get("visibility", "public")
        event.allow_conflict = request.POST.get("allow_conflict") == "on"
        event.is_all_day = is_all_day
        event.recurrence = request.POST.get("recurrence", "none")

        try:
            event.full_clean()  
            event.save()
            messages.success(request, f'Event "{event.title}" updated successfully.')
            return redirect("calendar")  
        except ValidationError as e:
            messages.error(request, "Error updating event: " + str(e))
        except Exception as e:
            messages.error(request, "Unexpected error: " + str(e))

    return render(request, "pages/event_form.html", {"event": event})