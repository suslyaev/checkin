document.addEventListener("DOMContentLoaded", function () {
    const buttonsConfirm = document.querySelectorAll(".button-confirm");
    const buttonsCancel = document.querySelectorAll(".button-cancel");

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

    buttonsConfirm.forEach(button => {
        button.addEventListener("click", function () {
            const url = this.dataset.url;
            sendAction(url, this, "Подтверждено");
        });
    });

    buttonsCancel.forEach(button => {
        button.addEventListener("click", function () {
            const url = this.dataset.url;
            sendAction(url, this, "Отменено");
        });
    });
});
