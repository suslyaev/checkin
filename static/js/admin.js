document.addEventListener("DOMContentLoaded", function () {
    console.log('q1');
    document.querySelectorAll(".deletelink").forEach((button) => {
        if (button.textContent.trim() === "Удалено") {
            button.textContent = "Удалить";
        }
    });
});