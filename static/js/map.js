const initialLocation = {
  name: "幕張メッセ",
  lat: 35.64709538816071,
  lng: 140.03399365894265,
  zoom: 16,
};
const weekdayLabels = ["月", "火", "水", "木", "金", "土", "日"];
const categoryIconNames = new Set([
  "place",
  "restaurant",
  "cafe",
  "shop",
  "sightseeing",
  "park",
  "museum",
]);

const map = L.map("map").setView(
  [initialLocation.lat, initialLocation.lng],
  initialLocation.zoom
);
const placeMarkers = L.layerGroup().addTo(map);
const openNowFilter = document.querySelector("#open-now-filter");
const placeSort = document.querySelector("#place-sort");
const categoryFilter = document.querySelector("#category-filter");
const categoryFilterLabel = document.querySelector("#category-filter-label");
const categoryCheckboxes = [...document.querySelectorAll(".category-checkbox")];
const clearCategoryFilter = document.querySelector("#clear-category-filter");
const placeCount = document.querySelector("#place-count");
const placeList = document.querySelector("#place-list");
const placeListPanel = document.querySelector("#place-list-panel");
const placeListToggle = document.querySelector("#place-list-toggle");
const placeListToggleIcon = placeListToggle.querySelector(".place-list-toggle-icon");
const mapMessage = document.querySelector("#map-message");
const placeListItems = new Map();
const placeMarkersById = new Map();
let activePlaceButton = null;
let latestPlacesRequest = 0;

function createElement(tagName, className, textContent) {
  const element = document.createElement(tagName);
  if (className) {
    element.className = className;
  }
  if (textContent !== undefined) {
    element.textContent = textContent;
  }
  return element;
}

function getCategoryIconName(iconName) {
  return categoryIconNames.has(iconName) ? iconName : "place";
}

function createCategoryIconElement(iconName, className) {
  const icon = document.createElementNS("http://www.w3.org/2000/svg", "svg");
  const use = document.createElementNS("http://www.w3.org/2000/svg", "use");

  icon.setAttribute("class", `category-icon ${className}`);
  icon.setAttribute("aria-hidden", "true");
  use.setAttribute("href", `#category-icon-${getCategoryIconName(iconName)}`);
  icon.append(use);

  return icon;
}

function createCategoryLabel(place) {
  const category = createElement("span", "place-category-label");
  const icon = createCategoryIconElement(
    place.category_icon,
    "place-category-icon"
  );
  const text = createElement(
    "span",
    "",
    place.category_name || place.category
  );

  icon.style.color = place.category_color || "#315f73";
  category.append(icon, text);

  return category;
}

function updateCategoryFilterLabel() {
  const selected = categoryCheckboxes.filter((checkbox) => checkbox.checked);

  if (selected.length === 0) {
    categoryFilterLabel.textContent = "すべて";
  } else if (selected.length === 1) {
    categoryFilterLabel.textContent = selected[0].dataset.label;
  } else {
    categoryFilterLabel.textContent = `${selected.length}件選択`;
  }
}

L.tileLayer("https://tile.openstreetmap.org/{z}/{x}/{y}.png", {
  maxZoom: 19,
  attribution: '&copy; <a href="https://www.openstreetmap.org/copyright">OpenStreetMap</a>',
}).addTo(map);

const venueIcon = L.divIcon({
  className: "custom-map-icon",
  html: '<span class="venue-marker">会場</span>',
  iconSize: [48, 30],
  iconAnchor: [24, 15],
  popupAnchor: [0, -17],
});

function createVenuePopup() {
  const popup = createElement("article", "place-popup");
  const heading = createElement("div", "place-popup-heading");
  const name = createElement("strong", "place-popup-name", initialLocation.name);
  const type = createElement("div", "place-popup-meta", "イベント会場");

  heading.append(name, type);
  popup.append(heading);

  return popup;
}

L.marker([initialLocation.lat, initialLocation.lng], { icon: venueIcon })
  .addTo(map)
  .bindPopup(createVenuePopup(), {
    className: "place-leaflet-popup",
    minWidth: 220,
    maxWidth: 280,
  })
  .openPopup();

function setPlaceListVisibility(isVisible) {
  placeListPanel.hidden = !isVisible;
  placeListToggle.setAttribute("aria-expanded", String(isVisible));
  placeListToggle.setAttribute("aria-label", isVisible ? "一覧を隠す" : "一覧を表示");
  placeListToggle.title = isVisible ? "一覧を隠す" : "一覧を表示";
  placeListToggle.classList.toggle("place-list-toggle-collapsed", !isVisible);
  placeListToggleIcon.textContent = isVisible ? "›" : "‹";

  // 一覧の幅が変わった後に地図を描き直す
  requestAnimationFrame(() => map.invalidateSize());
}

setPlaceListVisibility(true);

placeListToggle.addEventListener("click", () => {
  setPlaceListVisibility(placeListPanel.hidden);
});

function createPlaceIcon(label, markerColor, categoryIcon) {
  const iconName = getCategoryIconName(categoryIcon);
  const markerContent = label
    ? `<span>${label}</span>`
    : `<svg class="category-icon place-marker-category-icon" aria-hidden="true"><use href="#category-icon-${iconName}"></use></svg>`;

  return L.divIcon({
    className: "custom-map-icon",
    html: `<span class="place-marker" style="--marker-color: ${markerColor}">${markerContent}</span>`,
    iconSize: [30, 30],
    iconAnchor: [15, 30],
    popupAnchor: [0, -30],
  });
}

function formatPrice(place) {
  const minimum = place.price_min?.toLocaleString("ja-JP");
  const maximum = place.price_max?.toLocaleString("ja-JP");

  if (place.price_min === null && place.price_max === null) {
    return "金額未設定";
  }
  if (place.price_min === place.price_max) {
    return `${minimum}円`;
  }
  if (place.price_min === null) {
    return `〜${maximum}円`;
  }
  if (place.price_max === null) {
    return `${minimum}円〜`;
  }
  return `${minimum}〜${maximum}円`;
}

function createOpeningHours(openingHours) {
  const section = createElement("section", "place-popup-section");
  const heading = createElement("h3", "", "営業時間");
  const list = createElement("dl", "place-hours-list");
  const hoursByDay = Array.from({ length: 7 }, () => []);

  openingHours.forEach((hours) => {
    hoursByDay[hours.day_of_week].push(hours);
  });

  hoursByDay.forEach((dayHours, dayOfWeek) => {
    if (!dayHours.length) {
      return;
    }

    const row = createElement("div", "place-hours-row");
    const day = createElement("dt", "", weekdayLabels[dayOfWeek]);
    const times = createElement("dd");

    if (dayHours.some((hours) => hours.is_closed)) {
      times.textContent = "定休";
      times.className = "place-hours-closed";
    } else {
      dayHours.forEach((hours) => {
        const period = createElement(
          "span",
          "",
          `${hours.opens_at}〜${hours.closes_at}`
        );
        times.append(period);
      });
    }

    row.append(day, times);
    list.append(row);
  });

  section.append(heading, list);
  return section;
}

function createClosureInfo(place) {
  const closedDates = place.closed_dates || [];
  const annualClosedDates = place.annual_closed_dates || [];
  const recurringClosedDays = place.recurring_closed_days || [];

  if (!closedDates.length && !annualClosedDates.length && !recurringClosedDays.length) {
    return null;
  }

  const section = createElement("section", "place-popup-section");
  const heading = createElement("h3", "", "休業日");
  const list = createElement("ul", "place-closure-list");

  if (closedDates.length) {
    const labels = closedDates.map((value) => {
      const [year, month, day] = value.split("-").map(Number);
      return `${year}年${month}月${day}日`;
    });
    list.append(createElement("li", "", `臨時：${labels.join("、")}`));
  }

  if (annualClosedDates.length) {
    const labels = annualClosedDates.map(
      (rule) => `${rule.month}月${rule.day}日`
    );
    list.append(createElement("li", "", `毎年：${labels.join("、")}`));
  }

  if (recurringClosedDays.length) {
    const labels = recurringClosedDays.map(
      (rule) => `第${rule.week_of_month}${weekdayLabels[rule.day_of_week]}曜日`
    );
    list.append(createElement("li", "", `毎月：${labels.join("、")}`));
  }

  section.append(heading, list);
  return section;
}

function createPlacePopup(place) {
  const popup = createElement("article", "place-popup");
  const heading = createElement("div", "place-popup-heading");
  const name = createElement("strong", "place-popup-name", place.name);
  const meta = createElement("div", "place-popup-meta");
  const category = createCategoryLabel(place);
  const status = createElement("span", "place-popup-status", place.open_status);
  const price = createElement(
    "p",
    "place-popup-price",
    `予算 ${formatPrice(place)}`
  );

  if (place.is_open_now) {
    status.classList.add("place-popup-status-open");
  }
  meta.append(category, status);
  heading.append(name, meta);
  popup.append(heading, price);

  if (place.address) {
    popup.append(createElement("p", "place-popup-address", place.address));
  }

  if (place.description) {
    popup.append(
      createElement("p", "place-popup-description", place.description)
    );
  }

  if (place.opening_hours.length) {
    popup.append(createOpeningHours(place.opening_hours));
  }

  const closureInfo = createClosureInfo(place);
  if (closureInfo) {
    popup.append(closureInfo);
  }

  if (place.website_url) {
    const website = createElement("a", "place-popup-link", "公式サイトを見る");
    website.href = place.website_url;
    website.target = "_blank";
    website.rel = "noopener noreferrer";
    popup.append(website);
  }

  return popup;
}

function activatePlace(placeId, shouldScroll = true) {
  activePlaceButton?.classList.remove("map-place-card-active");

  activePlaceButton = placeListItems.get(String(placeId)) || null;
  if (!activePlaceButton) {
    return;
  }

  activePlaceButton.classList.add("map-place-card-active");
  if (shouldScroll) {
    activePlaceButton.scrollIntoView({ behavior: "smooth", block: "nearest" });
  }
}

function createPlaceListItem(place, label, markerColor) {
  const item = createElement("li");
  const button = createElement("button", "map-place-card");
  const rank = createElement("span", "map-place-rank", label || undefined);
  const main = createElement("span", "map-place-card-main");
  const name = createElement("strong", "map-place-name", place.name);
  const details = createElement("span", "map-place-details");
  const category = createCategoryLabel(place);
  const price = createElement("span", "map-place-price", formatPrice(place));
  const status = createElement("span", "", place.open_status);
  const placeId = String(place.id);

  button.type = "button";
  button.dataset.placeId = placeId;
  rank.style.backgroundColor = markerColor;
  if (!label) {
    rank.append(
      createCategoryIconElement(place.category_icon, "map-place-rank-icon")
    );
  }
  if (place.is_open_now) {
    status.className = "map-place-open";
  }

  details.append(category, price, status);
  main.append(name, details);
  button.append(rank, main);
  item.append(button);
  placeListItems.set(placeId, button);

  return item;
}

placeList.addEventListener("click", (event) => {
  const button = event.target.closest(".map-place-card");
  if (!button) {
    return;
  }

  const placeId = button.dataset.placeId;
  const marker = placeMarkersById.get(placeId);
  if (!marker) {
    return;
  }

  map.setView(marker.getLatLng(), Math.max(map.getZoom(), initialLocation.zoom));
  marker.openPopup();
  activatePlace(placeId, false);
});

function showMapMessage(message) {
  mapMessage.textContent = message;
  mapMessage.hidden = !message;
}

function clearPlaces() {
  placeMarkers.clearLayers();
  placeList.replaceChildren();
  placeListItems.clear();
  placeMarkersById.clear();
  activePlaceButton = null;
}

function getPriceCenterTwice(place) {
  if (place.price_min !== null && place.price_max !== null) {
    return place.price_min + place.price_max;
  }
  if (place.price_min !== null) {
    return place.price_min * 2;
  }
  if (place.price_max !== null) {
    return place.price_max * 2;
  }
  return null;
}

function createPlaceLabels(places) {
  if (placeSort.value !== "price_asc") {
    return places.map((_, index) => String(index + 1));
  }

  let previousPriceCenter = null;
  let previousRank = 0;

  return places.map((place) => {
    // サーバーと同じ中央額を使い、同じ金額は同順位にする。
    const priceCenter = getPriceCenterTwice(place);
    if (priceCenter === null) {
      return "";
    }

    if (priceCenter !== previousPriceCenter) {
      previousPriceCenter = priceCenter;
      previousRank += 1;
    }

    return String(previousRank);
  });
}

async function loadPlaces() {
  const requestId = ++latestPlacesRequest;
  const query = new URLSearchParams();
  query.set("sort", placeSort.value);
  if (openNowFilter.checked) {
    query.set("open_now", "1");
  }
  categoryCheckboxes
    .filter((checkbox) => checkbox.checked)
    .forEach((checkbox) => query.append("category", checkbox.value));

  placeCount.textContent = "場所を読み込み中";
  showMapMessage("");

  try {
    const response = await fetch(`/api/places?${query.toString()}`);
    if (!response.ok) {
      throw new Error("場所を読み込めませんでした");
    }

    const data = await response.json();
    if (requestId !== latestPlacesRequest) {
      return;
    }

    const placeListFragment = document.createDocumentFragment();
    const placeLabels = createPlaceLabels(data.places);
    clearPlaces();

    data.places.forEach((place, index) => {
      const label = placeLabels[index];
      const markerColor = place.category_color || "#315f73";
      const placeId = String(place.id);
      const marker = L.marker([place.latitude, place.longitude], {
        icon: createPlaceIcon(label, markerColor, place.category_icon),
      });
      marker
        .addTo(placeMarkers)
        .bindPopup(createPlacePopup(place), {
          className: "place-leaflet-popup",
          minWidth: 270,
          maxWidth: 320,
        });
      marker.on("click", () => activatePlace(placeId));
      placeMarkersById.set(placeId, marker);
      placeListFragment.append(
        createPlaceListItem(place, label, markerColor)
      );
    });
    placeList.append(placeListFragment);

    placeCount.textContent = `${data.places.length}件を表示`;
    if (data.places.length === 0) {
      const message = openNowFilter.checked
        ? "現在営業中の場所は見つかりませんでした"
        : "表示できる場所がありません";
      showMapMessage(message);

      const emptyItem = document.createElement("li");
      emptyItem.className = "map-list-empty";
      emptyItem.textContent = message;
      placeList.append(emptyItem);
    }
  } catch (error) {
    if (requestId !== latestPlacesRequest) {
      return;
    }

    clearPlaces();
    placeCount.textContent = "読み込みに失敗しました";
    showMapMessage(error.message);
  }
}

openNowFilter.addEventListener("change", loadPlaces);
placeSort.addEventListener("change", loadPlaces);
categoryFilter.addEventListener("change", (event) => {
  if (!event.target.classList.contains("category-checkbox")) {
    return;
  }

  updateCategoryFilterLabel();
  loadPlaces();
});

clearCategoryFilter.addEventListener("click", () => {
  categoryCheckboxes.forEach((checkbox) => {
    checkbox.checked = false;
  });
  updateCategoryFilterLabel();
  loadPlaces();
});

document.addEventListener("click", (event) => {
  if (!categoryFilter.contains(event.target)) {
    categoryFilter.removeAttribute("open");
  }
});

categoryFilter.addEventListener("keydown", (event) => {
  if (event.key === "Escape") {
    categoryFilter.removeAttribute("open");
    categoryFilter.querySelector("summary").focus();
  }
});

updateCategoryFilterLabel();
loadPlaces();
