const copyButton = document.querySelector("#copy-json-template");
const jsonTemplate = document.querySelector("#json-template");
const copyResult = document.querySelector("#copy-result");
const deleteForm = document.querySelector("#delete-places-form");
const deleteButton = document.querySelector("#delete-places-button");
const selectAll = document.querySelector("#select-all-places");
const placeCheckboxes = [...document.querySelectorAll(".place-checkbox")];

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
