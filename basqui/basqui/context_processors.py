from maps.models import MessageHistory

def loadMessages(request):
    try:
        messages = MessageHistory.objects.filter(created_by=request.user).order_by('-date_created')[:25]
    except:
        messages = None
    return {'messagesLog': messages,}