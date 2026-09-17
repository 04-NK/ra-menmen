// 最初に表示する場所
const initialLocation = {
  name: "幕張メッセ",
  lat: 35.64709538816071,
  lng: 140.03399365894265,
  zoom: 16,
};
const weekdayLabels = ["月", "火", "水", "木", "金", "土", "日"];

const map = L.map("map").setView(
  [initialLocation.lat, initialLocation.lng],
  initialLocation.zoom
);
const placeMarkers = L.layerGroup().addTo(map);
const openNowFilter = document.querySelector("#open-now-filter");
const placeSort = document.querySelector("#place-sort");
const placeCount = document.querySelector("#place-count");
const placeList = document.querySelector("#place-list");
const placeListPanel = document.querySelector("#place-list-panel");
const placeListToggle = document.querySelector("#place-list-toggle");
const placeListToggleIcon = placeListToggle.querySelector(".place-list-toggle-icon");
const mapMessage = document.querySelector("#map-message");
const placeListItems = new Map();
const placeMarkersById = new Map();
let activePlaceButton = null;

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

// OpenStreetMapの地図画像を重ねる。出典表示は残す。
L.tileLayer("https://tile.openstreetmap.org/{z}/{x}/{y}.png", {
  maxZoom: 19,
  attribution: '&copy; <a href="https://www.openstreetmap.org/copyright">OpenStreetMap</a>',
}).addTo(map);

// 会場は店舗と見分けられるラベル付きマーカーにする
const venueIcon = L.divIcon({
  className: "custom-map-icon",
  html: '<span class="venue-marker">会場</span>',
  iconSize: [48, 30],
  iconAnchor: [24, 15],
  popupAnchor: [0, -17],
});

// 会場も店舗と同じ見た目の吹き出しにする
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

// 画面幅にかかわらず、一覧を開いた状態から始める
setPlaceListVisibility(true);

placeListToggle.addEventListener("click", () => {
  setPlaceListVisibility(placeListPanel.hidden);
});

// カテゴリごとに店舗マーカーの色を固定する
function getMarkerColor(category) {
  const text = category || "other";
  let total = 0;

  for (const character of text) {
    total += character.codePointAt(0);
  }

  return total % 4;
}

function createPlaceIcon(label, markerColor) {
  return L.divIcon({
    className: "custom-map-icon",
    html: `<span class="place-marker place-marker-color-${markerColor}"><span>${label}</span></span>`,
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

// 登録済みスポットのポップアップを作る
function createPlacePopup(place) {
  const popup = createElement("article", "place-popup");
  const heading = createElement("div", "place-popup-heading");
  const name = createElement("strong", "place-popup-name", place.name);
  const meta = createElement("div", "place-popup-meta");
  const category = createElement(
    "span",
    "",
    place.category_name || place.category
  );
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
  const rank = createElement(
    "span",
    `map-place-rank place-marker-color-${markerColor}`,
    label
  );
  const main = createElement("span", "map-place-card-main");
  const name = createElement("strong", "map-place-name", place.name);
  const details = createElement("span", "map-place-details");
  const category = createElement(
    "span",
    "",
    place.category_name || place.category
  );
  const price = createElement("span", "map-place-price", formatPrice(place));
  const status = createElement("span", "", place.open_status);
  const placeId = String(place.id);

  button.type = "button";
  button.dataset.placeId = placeId;
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

// 一覧を押したら対応するマーカーを地図の中央に表示する
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

// 選択中の条件でNeonからスポットを読み込む
async function loadPlaces() {
  const query = new URLSearchParams();
  query.set("sort", placeSort.value);
  if (openNowFilter.checked) {
    query.set("open_now", "1");
  }

  placeCount.textContent = "場所を読み込み中";
  showMapMessage("");

  try {
    const response = await fetch(`/api/places?${query.toString()}`);
    if (!response.ok) {
      throw new Error("場所を読み込めませんでした");
    }

    const data = await response.json();
    const placeListFragment = document.createDocumentFragment();
    const placeLabels = createPlaceLabels(data.places);
    clearPlaces();

    data.places.forEach((place, index) => {
      const label = placeLabels[index];
      const markerColor = getMarkerColor(place.category);
      const placeId = String(place.id);
      const marker = L.marker([place.latitude, place.longitude], {
        icon: createPlaceIcon(label, markerColor),
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
    clearPlaces();
    placeCount.textContent = "読み込みに失敗しました";
    showMapMessage(error.message);
  }
}

openNowFilter.addEventListener("change", loadPlaces);
placeSort.addEventListener("change", loadPlaces);
loadPlaces();
