// Toggle a "spotted" checkmark without reloading the page.
document.querySelectorAll(".spotted-checkbox").forEach((checkbox) => {
    checkbox.addEventListener("change", function () {
        const vehicleId = this.dataset.vehicleId;
        const wasChecked = this.checked;

        fetch(`/spotted/toggle/${vehicleId}`, { method: "POST" })
            .then((response) => response.json())
            .then((data) => {
                this.checked = data.spotted;
            })
            .catch(() => {
                // If the request failed, put the checkbox back how it was.
                this.checked = !wasChecked;
            });
    });
});
