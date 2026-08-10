function loadYears(make, model) {
    const yearFromSelect = document.getElementById("year-from-select");
    const yearToSelect = document.getElementById("year-to-select");

    yearFromSelect.innerHTML = '<option value="">No limit</option>';
    yearToSelect.innerHTML = '<option value="">No limit</option>';

    if (!make) {
        return;
    }

    const url = `/api/years/${encodeURIComponent(make)}` + (model ? `?model=${encodeURIComponent(model)}` : "");

    fetch(url)
        .then((response) => response.json())
        .then((years) => {
            years.forEach((year) => {
                const fromOption = document.createElement("option");
                fromOption.value = year;
                fromOption.textContent = year;
                yearFromSelect.appendChild(fromOption);

                const toOption = document.createElement("option");
                toOption.value = year;
                toOption.textContent = year;
                yearToSelect.appendChild(toOption);
            });
        });
}

// When a make is picked, fetch the models we've seen for it and fill in
// the model dropdown (and refresh the year options for the make alone).
document.getElementById("make-select").addEventListener("change", function () {
    const make = this.value;
    const modelSelect = document.getElementById("model-select");

    modelSelect.innerHTML = '<option value="">Any model</option>';

    loadYears(make, "");

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

// When a model is picked, narrow the year options to that specific model.
document.getElementById("model-select").addEventListener("change", function () {
    const make = document.getElementById("make-select").value;
    loadYears(make, this.value);
});
