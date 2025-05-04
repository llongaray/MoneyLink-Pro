from django.shortcuts import render
from django.contrib import messages

# Create your views here.


def get_all_forms(request):
    pass

def all_forms(request):
    pass

def get_ranking(request):
    pass

def render_ranking(request):
    context = {}
    # Se houver uma mensagem na sessão, adiciona ao contexto
    if messages.get_messages(request):
        context['mensagem'] = {
            'texto': list(messages.get_messages(request))[-1].message,
            'classe': 'error'  # ou 'success', dependendo do tipo de mensagem
        }
    return render(request, 'partials/_developing.html', context)
