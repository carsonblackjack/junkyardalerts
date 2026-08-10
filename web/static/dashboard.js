// Keep Year From / Year To from crossing each other: disabling the
// out-of-range options (rather than just validating on submit) also
// stops the browser's scroll-wheel-on-a-select behavior from landing on
// an invalid year.
const yearFromSelect = document.getElementById("year-from-select");
const yearToSelect = document.getElementById("year-to-select");

function constrainYearRange() {
    const fromValue = yearFromSelect.value;
    const toValue = yearToSelect.value;

    for (const option of yearToSelect.options) {
        if (!option.value) continue;
        option.disabled = fromValue !== "" && option.value < fromValue;
    }

    for (const option of yearFromSelect.options) {
        if (!option.value) continue;
        option.disabled = toValue !== "" && option.value > toValue;
    }
}

yearFromSelect.addEventListener("change", constrainYearRange);
yearToSelect.addEventListener("change", constrainYearRange);

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
