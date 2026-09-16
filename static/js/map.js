// 最初に表示する場所
const initialLocation = {
  name: "幕張メッセ",
  lat: 35.6476856,
  lng: 140.0354964,
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
const mapMessage = document.querySelector("#map-message");
const placeListItems = new Map();
let activePlaceButton = null;

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

L.marker([initialLocation.lat, initialLocation.lng], { icon: venueIcon })
  .addTo(map)
  .bindPopup(initialLocation.name)
  .openPopup();

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

// 登録済みスポットのポップアップを作る
function createPlacePopup(place) {
  const popup = document.createElement("div");
  const name = document.createElement("strong");
  const category = document.createElement("p");
  const status = document.createElement("p");

  popup.className = "place-popup";
  name.textContent = place.name;
  category.textContent = place.category_name || place.category;
  status.className = "place-popup-status";
  status.textContent = place.open_status;
  if (place.is_open_now) {
    status.classList.add("place-popup-status-open");
  }
  popup.append(name, category, status);

  if (place.description) {
    const description = document.createElement("p");
    description.textContent = place.description;
    popup.append(description);
  }

  if (place.opening_hours.length) {
    const openingHours = document.createElement("p");
    const schedule = place.opening_hours.map((hours) => {
      const day = weekdayLabels[hours.day_of_week];

      if (hours.is_closed) {
        return `${day} 定休`;
      }

      return `${day} ${hours.opens_at}〜${hours.closes_at}`;
    });

    openingHours.textContent = `営業時間：${schedule.join(" / ")}`;
    popup.append(openingHours);
  }

  const price = document.createElement("p");
  price.textContent = `価格の目安：${formatPrice(place)}`;
  popup.append(price);

  return popup;
}

function activatePlace(placeId, shouldScroll = true) {
  activePlaceButton?.classList.remove("map-place-card-active");

  activePlaceButton = placeListItems.get(placeId) || null;
  if (!activePlaceButton) {
    return;
  }

  activePlaceButton.classList.add("map-place-card-active");
  if (shouldScroll) {
    activePlaceButton.scrollIntoView({ behavior: "smooth", block: "nearest" });
  }
}

// 一覧を押したら対応するマーカーを地図の中央に表示する
function createPlaceListItem(place, label, marker, markerColor) {
  const item = document.createElement("li");
  const button = document.createElement("button");
  const rank = document.createElement("span");
  const main = document.createElement("span");
  const name = document.createElement("strong");
  const details = document.createElement("span");
  const category = document.createElement("span");
  const price = document.createElement("span");
  const status = document.createElement("span");

  button.type = "button";
  button.className = "map-place-card";
  rank.className = `map-place-rank place-marker-color-${markerColor}`;
  rank.textContent = label;
  main.className = "map-place-card-main";
  name.className = "map-place-name";
  name.textContent = place.name;
  details.className = "map-place-details";
  category.textContent = place.category_name || place.category;
  price.className = "map-place-price";
  price.textContent = formatPrice(place);
  status.textContent = place.open_status;
  if (place.is_open_now) {
    status.className = "map-place-open";
  }

  details.append(category, price, status);
  main.append(name, details);
  button.append(rank, main);
  item.append(button);
  placeListItems.set(place.id, button);

  button.addEventListener("click", () => {
    map.setView(
      [place.latitude, place.longitude],
      Math.max(map.getZoom(), initialLocation.zoom)
    );
    marker.openPopup();
    activatePlace(place.id, false);
  });
  marker.on("click", () => activatePlace(place.id));

  return item;
}

function showMapMessage(message) {
  mapMessage.textContent = message;
  mapMessage.hidden = !message;
}

function clearPlaces() {
  placeMarkers.clearLayers();
  placeList.replaceChildren();
  placeListItems.clear();
  activePlaceButton = null;
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
    clearPlaces();

    data.places.forEach((place, index) => {
      const hasPrice = place.price_min !== null || place.price_max !== null;
      const isPriceOrder = placeSort.value === "price_asc";
      const label = isPriceOrder && !hasPrice ? "-" : String(index + 1);
      const markerColor = getMarkerColor(place.category);
      const marker = L.marker([place.latitude, place.longitude], {
        icon: createPlaceIcon(label, markerColor),
      });
      marker
        .addTo(placeMarkers)
        .bindPopup(createPlacePopup(place));
      placeListFragment.append(
        createPlaceListItem(place, label, marker, markerColor)
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
