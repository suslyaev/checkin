from django.shortcuts import render
from django.contrib.auth.forms import AuthenticationForm
from django.contrib.auth import login, authenticate


def home(request):
    if request.user.is_authenticated:
        # Если пользователь авторизован, показываем приветствие
        return render(request, 'front/home.html', {'user': request.user})
    else:
        # Если пользователь не авторизован, показываем форму для входа
        if request.method == "POST":
            form = AuthenticationForm(request, data=request.POST)
            if form.is_valid():
                username = form.cleaned_data.get('username')
                password = form.cleaned_data.get('password')
                user = authenticate(username=username, password=password)
                if user is not None:
                    login(request, user)
                    return render(request, 'front/home.html', {'user': user})
        else:
            form = AuthenticationForm()
        return render(request, 'front/login.html', {'form': form})
