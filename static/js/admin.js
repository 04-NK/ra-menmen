const copyButton = document.querySelector("#copy-json-template");
const jsonTemplate = document.querySelector("#json-template");
const copyResult = document.querySelector("#copy-result");
const deleteForm = document.querySelector("#delete-places-form");
const deleteButton = document.querySelector("#delete-places-button");
const selectAll = document.querySelector("#select-all-places");
const placeCheckboxes = [...document.querySelectorAll(".place-checkbox")];
const hoursList = document.querySelector(".hours-list");
const hoursRows = [...document.querySelectorAll(".hours-row")];
const hoursRowsByDay = new Map(hoursRows.map((row) => [row.dataset.day, row]));
const bulkDayCheckboxes = [...document.querySelectorAll(".bulk-day")];
const bulkOpenTime = document.querySelector("#bulk-open-time");
const bulkCloseTime = document.querySelector("#bulk-close-time");
const applyHoursButton = document.querySelector("#apply-hours");
const addHoursButton = document.querySelector("#add-hours");
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

deleteForm?.addEventListener("change", (event) => {
  if (event.target.classList.contains("place-checkbox")) {
    updateSelection();
  }
});

deleteForm?.addEventListener("submit", (event) => {
  const selectedCount = placeCheckboxes.filter((checkbox) => checkbox.checked).length;
  const shouldDelete = window.confirm(`${selectedCount}件の場所を削除しますか？`);

  if (!shouldDelete) {
    event.preventDefault();
  }
});

function createHoursPeriod(row, opensAt = "", closesAt = "") {
  const day = row.dataset.day;
  const dayLabel = row.dataset.dayLabel;
  const period = document.createElement("div");
  const openInput = document.createElement("input");
  const separator = document.createElement("span");
  const closeInput = document.createElement("input");
  const removeButton = document.createElement("button");

  period.className = "hours-period";
  openInput.type = "time";
  openInput.name = `hours_${day}_open`;
  openInput.value = opensAt;
  openInput.setAttribute("aria-label", `${dayLabel}の開店時刻`);
  separator.className = "hours-separator";
  separator.textContent = "〜";
  closeInput.type = "time";
  closeInput.name = `hours_${day}_close`;
  closeInput.value = closesAt;
  closeInput.setAttribute("aria-label", `${dayLabel}の閉店時刻`);
  removeButton.type = "button";
  removeButton.className = "remove-hours-period";
  removeButton.textContent = "削除";
  period.append(openInput, separator, closeInput, removeButton);

  return period;
}

function setClosedState(row) {
  const closed = row.querySelector(".hours-closed");
  row.querySelectorAll('input[type="time"], .add-hours-period, .remove-hours-period')
    .forEach((control) => {
      control.disabled = closed.checked;
    });
}

// 曜日ごとの操作は親要素でまとめて受け取る
hoursList?.addEventListener("change", (event) => {
  if (event.target.classList.contains("hours-closed")) {
    setClosedState(event.target.closest(".hours-row"));
  }
});

hoursList?.addEventListener("click", (event) => {
  const row = event.target.closest(".hours-row");
  if (!row) {
    return;
  }

  if (event.target.classList.contains("add-hours-period")) {
    row.querySelector(".hours-closed").checked = false;
    row.querySelector(".hours-periods").append(createHoursPeriod(row));
    setClosedState(row);
  } else if (event.target.classList.contains("remove-hours-period")) {
    const periods = row.querySelectorAll(".hours-period");
    if (periods.length === 1) {
      periods[0].querySelectorAll('input[type="time"]').forEach((input) => {
        input.value = "";
      });
    } else {
      event.target.closest(".hours-period").remove();
    }
  }
});

hoursRows.forEach(setClosedState);

function getBulkSelection(emptyMessage, needsTimes = false) {
  const rows = bulkDayCheckboxes
    .filter((checkbox) => checkbox.checked)
    .map((checkbox) => hoursRowsByDay.get(checkbox.value));

  if (!rows.length) {
    hoursBulkResult.textContent = emptyMessage;
    return null;
  }
  if (needsTimes && (!bulkOpenTime.value || !bulkCloseTime.value)) {
    hoursBulkResult.textContent = "開店時刻と閉店時刻を入力してください。";
    return null;
  }

  return {
    rows,
    opensAt: bulkOpenTime.value,
    closesAt: bulkCloseTime.value,
  };
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
  const selection = getBulkSelection("反映する曜日を選択してください。", true);
  if (!selection) {
    return;
  }

  selection.rows.forEach((row) => {
    const closed = row.querySelector(".hours-closed");

    row.querySelector(".hours-periods").replaceChildren(
      createHoursPeriod(row, selection.opensAt, selection.closesAt)
    );
    closed.checked = false;
    setClosedState(row);
  });
  hoursBulkResult.textContent = `${selection.rows.length}日分に時刻を反映しました。`;
});

addHoursButton?.addEventListener("click", () => {
  const selection = getBulkSelection("追加する曜日を選択してください。", true);
  if (!selection) {
    return;
  }

  selection.rows.forEach((row) => {
    const periods = row.querySelector(".hours-periods");
    const firstInputs = periods.querySelectorAll('input[type="time"]');
    const firstPeriodIsEmpty =
      periods.children.length === 1 &&
      [...firstInputs].every((input) => !input.value);

    if (firstPeriodIsEmpty) {
      periods.replaceChildren(
        createHoursPeriod(row, selection.opensAt, selection.closesAt)
      );
    } else {
      periods.append(
        createHoursPeriod(row, selection.opensAt, selection.closesAt)
      );
    }
    row.querySelector(".hours-closed").checked = false;
    setClosedState(row);
  });
  hoursBulkResult.textContent = `${selection.rows.length}日分に時間帯を追加しました。`;
});

applyClosedButton?.addEventListener("click", () => {
  const selection = getBulkSelection("定休日にする曜日を選択してください。");
  if (!selection) {
    return;
  }

  selection.rows.forEach((row) => {
    const closed = row.querySelector(".hours-closed");

    closed.checked = true;
    setClosedState(row);
  });
  hoursBulkResult.textContent = `${selection.rows.length}日分を定休日にしました。`;
});
