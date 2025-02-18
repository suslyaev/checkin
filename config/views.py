# config/views.py (или где у вас home)
from django.shortcuts import render, redirect
from django.contrib.auth.forms import AuthenticationForm
from django.contrib.auth import login, authenticate
from django.db.models import Q
from django.db.models.functions import Lower
from django.contrib.auth.decorators import login_required
from django.contrib.auth import logout

from event.models import ModuleInstance

def home(request):
    if request.user.is_authenticated:
        qs = ModuleInstance.objects.all()

        # Ограничения по ролям (как в админке)
        if not request.user.is_superuser:
            # Если проверяющий - фильтруем
            if request.user.groups.filter(name='Проверяющий').exists():
                qs = qs.filter(checkers=request.user)
            # Если менеджер - возможно оставляем всё, 
            #   или фильтруем managers=request.user (зависит от вашей логики)

        # --- Добавляем поиск ---
        search_term = request.GET.get('q', '')
        if search_term:
            term_lower = search_term.lower()
            qs = qs.annotate(
                name_lower=Lower('name'),
                address_lower=Lower('address')
            ).filter(
                Q(name_lower__contains=term_lower) | Q(address_lower__contains=term_lower)
            )
        else:
            search_term = ''  # пустая строка, если нет поиска

        return render(request, 'front/home.html', {
            'user': request.user,
            'instances': qs,
            'search_term': search_term,
        })
    else:
        # Если не авторизован -> логин
        if request.method == "POST":
            form = AuthenticationForm(request, data=request.POST)
            if form.is_valid():
                username = form.cleaned_data.get('username')
                password = form.cleaned_data.get('password')
                user = authenticate(username=username, password=password)
                if user is not None:
                    login(request, user)
                    return redirect('home')
        else:
            form = AuthenticationForm()
        return render(request, 'front/login.html', {'form': form})

def custom_logout(request):
    logout(request)  # «Разлогинить» пользователя
    return redirect('home')  # На главную