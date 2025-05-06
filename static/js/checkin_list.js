document.addEventListener("DOMContentLoaded", function () {
    const buttonsInvited = document.querySelectorAll(".button-invited");
    const buttonsRegistered = document.querySelectorAll(".button-registered");
    const buttonsCancelled = document.querySelectorAll(".button-cancelled");
    const buttonsVisited = document.querySelectorAll(".button-visited");
    const buttonsCancelCheckin = document.querySelectorAll(".button-cancel-checkin");

    function sendAction(url, element, statusText) {
        fetch(url, { method: "GET", headers: { "X-Requested-With": "XMLHttpRequest" } })
            .then(response => {
                if (response.ok) {
                    element.textContent = statusText;
                    element.style.color = 'gray';
                    element.style.borderColor = 'gray';
                    element.className = 'button-cancel';
                } else {
                    alert("Ошибка при выполнении действия");
                }
            })
            .catch(error => {
                console.error("Ошибка:", error);
                alert("Не удалось выполнить действие");
            });
    }

    buttonsInvited.forEach(button => {
        button.addEventListener("click", function () {
            const url = this.dataset.url;
            sendAction(url, this, "Приглашён");
        });
    });
    buttonsRegistered.forEach(button => {
        button.addEventListener("click", function () {
            const url = this.dataset.url;
            sendAction(url, this, "Подтвердил");
        });
    });
    buttonsCancelled.forEach(button => {
        button.addEventListener("click", function () {
            const url = this.dataset.url;
            sendAction(url, this, "Отклонил");
        });
    });
    buttonsVisited.forEach(button => {
        button.addEventListener("click", function () {
            const url = this.dataset.url;
            sendAction(url, this, "Зачекинен");
        });
    });
    buttonsCancelCheckin.forEach(button => {
        button.addEventListener("click", function () {
            const url = this.dataset.url;
            sendAction(url, this, "Чекин отменен");
        });
    });
});
