// 初期表示。[緯度, 経度]とズーム倍率を指定する。
const map = L.map("map").setView([35.64768559999999, 140.0354964134909], 13);
// OpenStreetMapの地図画像を重ねる。出典表示は残す。
L.tileLayer("https://tile.openstreetmap.org/{z}/{x}/{y}.png", {
  maxZoom: 19,
  attribution: '&copy; <a href="https://www.openstreetmap.org/copyright">OpenStreetMap</a>',
}).addTo(map);

// マーカーやルートの描画は、ここから追加する。
