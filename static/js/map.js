// 最初に表示する場所
const initialLocation = {
  name: "幕張メッセ",
  lat: 35.6476856,
  lng: 140.0354964,
  zoom: 13,
};
const weekdayLabels = ["月", "火", "水", "木", "金", "土", "日"];

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
  category.textContent = place.category_name || place.category;
  popup.append(name, category);

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

  if (place.price_min !== null || place.price_max !== null) {
    const price = document.createElement("p");
    const minimum = place.price_min?.toLocaleString("ja-JP");
    const maximum = place.price_max?.toLocaleString("ja-JP");

    if (place.price_min === place.price_max) {
      price.textContent = `価格の目安：${minimum}円`;
    } else if (place.price_min === null) {
      price.textContent = `価格の目安：〜${maximum}円`;
    } else if (place.price_max === null) {
      price.textContent = `価格の目安：${minimum}円〜`;
    } else {
      price.textContent = `価格の目安：${minimum}〜${maximum}円`;
    }

    popup.append(price);
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
