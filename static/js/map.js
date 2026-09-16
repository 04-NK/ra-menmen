// 最初に表示する場所
const initialLocation = {
  name: "幕張メッセ",
  lat: 35.6476856,
  lng: 140.0354964,
  zoom: 13,
};

const map = L.map("map").setView(
  [initialLocation.lat, initialLocation.lng],
  initialLocation.zoom
);

// OpenStreetMapの地図画像を重ねる。出典表示は残す。
L.tileLayer("https://tile.openstreetmap.org/{z}/{x}/{y}.png", {
  maxZoom: 19,
  attribution: '&copy; <a href="https://www.openstreetmap.org/copyright">OpenStreetMap</a>',
}).addTo(map);

// 初期地点にマーカーを置く
L.marker([initialLocation.lat, initialLocation.lng])
  .addTo(map)
  .bindPopup(initialLocation.name)
  .openPopup();

// 登録済みスポットのポップアップを作る
function createPlacePopup(place) {
  const popup = document.createElement("div");
  const name = document.createElement("strong");
  const category = document.createElement("p");

  name.textContent = place.name;
  category.textContent = place.category;
  popup.append(name, category);

  if (place.description) {
    const description = document.createElement("p");
    description.textContent = place.description;
    popup.append(description);
  }

  return popup;
}

// Neonに登録されたスポットを地図に表示する
async function loadPlaces() {
  try {
    const response = await fetch("/api/places");

    if (!response.ok) {
      throw new Error("スポット情報を取得できませんでした");
    }

    const data = await response.json();

    data.places.forEach((place) => {
      L.marker([place.latitude, place.longitude])
        .addTo(map)
        .bindPopup(createPlacePopup(place));
    });
  } catch (error) {
    console.warn(error.message);
  }
}

loadPlaces();
