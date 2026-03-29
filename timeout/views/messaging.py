"""
Views for the messaging system, allowing users to have private conversations with each other.
"""

from django.contrib.auth.decorators import login_required
from django.http import JsonResponse
from django.shortcuts import render, redirect, get_object_or_404
from django.views.decorators.http import require_POST

from timeout.models import User, Conversation, Message
from timeout.services.social_service import are_blocked
from timeout.services.notification_service import NotificationService


@login_required
def inbox(request):
    """Show all conversations for the current user."""
    conversations = request.user.conversations.prefetch_related(
        'participants', 'messages'
    ).order_by('-updated_at')

    conversation_data = []
    for conv in conversations:
        unread_count = conv.messages.filter(
            is_read=False
        ).exclude(sender=request.user).count()
        conversation_data.append({
            'conv': conv,
            'other': conv.get_other_participant(request.user),
            'last': conv.get_last_message(),
            'unread_count': unread_count,
        })

    context = {'conversations': conversation_data}
    return render(request, 'messaging/inbox.html', context)


@login_required
def start_conversation(request, username):
    """Start a conversation with a user, or resume existing one."""
    other_user = get_object_or_404(User, username=username)

    if other_user == request.user:
        return redirect('inbox')
    
    if are_blocked(request.user, other_user):
        return redirect('inbox')

    # Check if conversation already exists between these two users
    conversation = Conversation.objects.filter(
        participants=request.user
    ).filter(
        participants=other_user
    ).first()

    if not conversation:
        conversation = Conversation.objects.create()
        conversation.participants.add(request.user, other_user)

    return redirect('conversation', conversation_id=conversation.id)


@login_required
def conversation(request, conversation_id):
    """View a conversation thread."""
    conv = get_object_or_404(
        Conversation,
        id=conversation_id,
        participants=request.user
    )

    other_user = conv.get_other_participant(request.user)
    if are_blocked(request.user, other_user):
        return redirect('inbox')

    conv.messages.exclude(sender=request.user).update(is_read=True)

    messages = conv.messages.select_related('sender').order_by('created_at')

    context = {
        'conversation': conv,
        'messages': messages,
        'other_user': other_user,
    }
    return render(request, 'messaging/conversation.html', context)




def _notify_receiver(receiver, sender, content, conv):
    """Create a message notification for the receiver."""
    if receiver:
        NotificationService.notify_new_message(receiver, sender, content, conv)


def _serialize_message(message):
    """Return a JSON-serializable dict for a sent message."""
    return {
        'id': message.id,
        'content': message.content,
        'sender': message.sender.username,
        'created_at': message.created_at.strftime('%H:%M'),
        'is_me': True,
    }


@login_required
@require_POST
def send_message(request, conversation_id):
    """Send a message in a conversation."""
    conv = get_object_or_404(
        Conversation, id=conversation_id, participants=request.user)
    receiver = conv.get_other_participant(request.user)
    if are_blocked(request.user, receiver):
        return JsonResponse({'error': 'Cannot message a blocked user'}, status=403)
    content = request.POST.get('content', '').strip()
    if not content:
        return JsonResponse({'error': 'Empty message'}, status=400)
    message = Message.objects.create(
        conversation=conv, sender=request.user, content=content)
    conv.save()
    _notify_receiver(receiver, request.user, content, conv)
    return JsonResponse(_serialize_message(message))


@login_required
@require_POST
def mark_conversation_unread(request, conversation_id):
    """Mark the most recent received message in a conversation as unread."""
    conv = get_object_or_404(
        Conversation, id=conversation_id, participants=request.user
    )
    last_received = (
        conv.messages
        .exclude(sender=request.user)
        .order_by('-created_at', '-pk')
        .first()
    )
    if last_received:
        last_received.is_read = False
        last_received.save(update_fields=['is_read'])
    return JsonResponse({'success': True})


@login_required
@require_POST
def delete_message(request, message_id):
    """Permanently delete a message (staff only)."""
    if not request.user.is_staff:
        return JsonResponse({'error': 'Staff access required.'}, status=403)
    message = get_object_or_404(Message, id=message_id)
    message.delete()
    return JsonResponse({'success': True})


@login_required
def poll_messages(request, conversation_id):
    """Return messages newer than a given message ID for polling."""
    conv = get_object_or_404(
        Conversation,
        id=conversation_id,
        participants=request.user
    )

    last_id = request.GET.get('last_id', 0)

    new_messages = conv.messages.filter(
        id__gt=last_id
    ).select_related('sender').order_by('created_at')

    new_messages.exclude(sender=request.user).update(is_read=True)

    data = [{
        'id': m.id,
        'content': m.content,
        'sender': m.sender.username,
        'created_at': m.created_at.strftime('%H:%M'),
        'is_me': m.sender == request.user,
    } for m in new_messages]

    return JsonResponse({'messages': data})