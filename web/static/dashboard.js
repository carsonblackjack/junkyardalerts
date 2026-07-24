// When a make is picked, fetch the models we've seen for it and fill in
// the model dropdown.
document.getElementById("make-select").addEventListener("change", function () {
    const make = this.value;
    const modelSelect = document.getElementById("model-select");

    modelSelect.innerHTML = '<option value="">Any model</option>';

    if (!make) {
        return;
    }

    fetch(`/api/models/${encodeURIComponent(make)}`)
        .then((response) => response.json())
        .then((models) => {
            models.forEach((model) => {
                const option = document.createElement("option");
                option.value = model;
                option.textContent = model;
                modelSelect.appendChild(option);
            });
        });
});
