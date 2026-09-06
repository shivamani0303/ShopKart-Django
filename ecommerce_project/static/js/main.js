document.addEventListener("DOMContentLoaded", () => {
    document.querySelectorAll(".alert").forEach((alert) => {
        setTimeout(() => {
            const close = alert.querySelector(".btn-close");
            if (close) close.click();
        }, 5000);
    });
});
