from django.contrib.auth.decorators import login_required
from django.http import JsonResponse
from django.shortcuts import render, redirect, get_object_or_404
from django.views.decorators.http import require_POST
from django.db.models import Q

from timeout.models import User, Conversation, Message
from timeout.models.notification import Notification


@login_required
def inbox(request):
    """Show all conversations for the current user."""
    conversations = request.user.conversations.prefetch_related(
        'participants', 'messages'
    ).order_by('-updated_at')

    conversation_data = []
    for conv in conversations:
        conversation_data.append({
            'conv': conv,
            'other': conv.get_other_participant(request.user),
            'last': conv.get_last_message(),
        })

    context = {'conversations': conversation_data}
    return render(request, 'messaging/inbox.html', context)


@login_required
def start_conversation(request, username):
    """Start a conversation with a user, or resume existing one."""
    other_user = get_object_or_404(User, username=username)

    if other_user == request.user:
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

    conv.messages.exclude(sender=request.user).update(is_read=True)

    messages = conv.messages.select_related('sender').order_by('created_at')
    other_user = conv.get_other_participant(request.user)

    context = {
        'conversation': conv,
        'messages': messages,
        'other_user': other_user,
    }
    return render(request, 'messaging/conversation.html', context)


@login_required
@require_POST
def send_message(request, conversation_id):
    """Send a message in a conversation."""
    conv = get_object_or_404(
        Conversation,
        id=conversation_id,
        participants=request.user
    )

    content = request.POST.get('content', '').strip()
    if not content:
        return JsonResponse({'error': 'Empty message'}, status=400)

    message = Message.objects.create(
        conversation=conv,
        sender=request.user,
        content=content,
    )

    conv.save()

    receiver = conv.get_other_participant(request.user)

    if receiver:
        Notification.objects.create(
            user=receiver,
            title=f"💬 {request.user.username} sent you a message",
            message=content[:80],
            type=Notification.Type.MESSAGE,
            conversation=conv,
        )    

    return JsonResponse({
        'id': message.id,
        'content': message.content,
        'sender': message.sender.username,
        'created_at': message.created_at.strftime('%H:%M'),
        'is_me': True,
    })


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