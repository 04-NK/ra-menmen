const copyButton = document.querySelector("#copy-json-template");
const jsonTemplate = document.querySelector("#json-template");
const copyResult = document.querySelector("#copy-result");
const deleteForm = document.querySelector("#delete-places-form");
const deleteButton = document.querySelector("#delete-places-button");
const selectAll = document.querySelector("#select-all-places");
const placeCheckboxes = [...document.querySelectorAll(".place-checkbox")];
const hoursRows = [...document.querySelectorAll(".hours-row")];
const bulkDayCheckboxes = [...document.querySelectorAll(".bulk-day")];
const bulkOpenTime = document.querySelector("#bulk-open-time");
const bulkCloseTime = document.querySelector("#bulk-close-time");
const applyHoursButton = document.querySelector("#apply-hours");
const applyClosedButton = document.querySelector("#apply-closed");
const hoursBulkResult = document.querySelector("#hours-bulk-result");

// JSONテンプレートをクリップボードにコピーする
copyButton?.addEventListener("click", async () => {
  try {
    await navigator.clipboard.writeText(jsonTemplate.textContent.trim());
    copyResult.textContent = "コピーしました。";
  } catch (error) {
    console.warn("JSONテンプレートをコピーできませんでした", error);
    copyResult.textContent = "コピーできませんでした。";
  }
});

// 選択状態に合わせて削除ボタンを切り替える
function updateSelection() {
  const selectedCount = placeCheckboxes.filter((checkbox) => checkbox.checked).length;

  deleteButton.disabled = selectedCount === 0;
  deleteButton.textContent = selectedCount
    ? `選択した場所を削除（${selectedCount}件）`
    : "選択した場所を削除";

  selectAll.checked = selectedCount === placeCheckboxes.length;
  selectAll.indeterminate = selectedCount > 0 && selectedCount < placeCheckboxes.length;
}

selectAll?.addEventListener("change", () => {
  placeCheckboxes.forEach((checkbox) => {
    checkbox.checked = selectAll.checked;
  });
  updateSelection();
});

placeCheckboxes.forEach((checkbox) => {
  checkbox.addEventListener("change", updateSelection);
});

deleteForm?.addEventListener("submit", (event) => {
  const selectedCount = placeCheckboxes.filter((checkbox) => checkbox.checked).length;
  const shouldDelete = window.confirm(`${selectedCount}件の場所を削除しますか？`);

  if (!shouldDelete) {
    event.preventDefault();
  }
});

// 定休日を選んだ曜日は時刻入力を無効にする
hoursRows.forEach((row) => {
  const closed = row.querySelector(".hours-closed");
  const timeInputs = [...row.querySelectorAll('input[type="time"]')];

  closed.addEventListener("change", () => {
    timeInputs.forEach((input) => {
      input.disabled = closed.checked;
    });
  });
});

function getSelectedDays() {
  return bulkDayCheckboxes
    .filter((checkbox) => checkbox.checked)
    .map((checkbox) => checkbox.value);
}

function getHoursRow(day) {
  return hoursRows.find((row) => row.dataset.day === day);
}

// 全曜日・平日・土日をすぐ選べるようにする
document.querySelectorAll("[data-days]").forEach((button) => {
  button.addEventListener("click", () => {
    const preset = button.dataset.days;

    bulkDayCheckboxes.forEach((checkbox, index) => {
      checkbox.checked =
        preset === "all" ||
        (preset === "weekday" && index < 5) ||
        (preset === "weekend" && index >= 5);
    });
  });
});

applyHoursButton?.addEventListener("click", () => {
  const selectedDays = getSelectedDays();

  if (!selectedDays.length) {
    hoursBulkResult.textContent = "反映する曜日を選択してください。";
    return;
  }
  if (!bulkOpenTime.value || !bulkCloseTime.value) {
    hoursBulkResult.textContent = "開店時刻と閉店時刻を入力してください。";
    return;
  }

  selectedDays.forEach((day) => {
    const row = getHoursRow(day);
    const [openInput, closeInput] = row.querySelectorAll('input[type="time"]');
    const closed = row.querySelector(".hours-closed");

    openInput.value = bulkOpenTime.value;
    closeInput.value = bulkCloseTime.value;
    openInput.disabled = false;
    closeInput.disabled = false;
    closed.checked = false;
  });
  hoursBulkResult.textContent = `${selectedDays.length}日分に時刻を反映しました。`;
});

applyClosedButton?.addEventListener("click", () => {
  const selectedDays = getSelectedDays();

  if (!selectedDays.length) {
    hoursBulkResult.textContent = "定休日にする曜日を選択してください。";
    return;
  }

  selectedDays.forEach((day) => {
    const row = getHoursRow(day);
    const timeInputs = [...row.querySelectorAll('input[type="time"]')];
    const closed = row.querySelector(".hours-closed");

    closed.checked = true;
    timeInputs.forEach((input) => {
      input.disabled = true;
    });
  });
  hoursBulkResult.textContent = `${selectedDays.length}日分を定休日にしました。`;
});
