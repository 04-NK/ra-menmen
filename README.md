# ra-menmen
# ヨリタビ（チーム：ラーメンメン）

## サービス概要
- **サービス名**：ヨリタビ
- **チーム名**：ラーメンメン
- **アプリURL**：[https://ra-menmen.vercel.app/](https://ra-menmen.vercel.app/)

---

## チームメンバー
- [@04-NK](https://github.com/04-NK)
- [@tamasyun](https://github.com/tamasyun)
- [@DaichiMatsu](https://github.com/DaichiMatsu)
- [@YutoUchima](https://github.com/YutoUchima)

---

## エレベーターピッチ

**[フェスやライブのついでに寄り道で観光も楽しみたい]** \
**[都心に来た旅行者]** 向けの、\
**[ヨリタビ]** というプロダクトは、\
**[旅行サポートマップアプリ]** です。\
これは **[メインイベントの​場所や​ホテルの​位置から​コスパよく​回れる​周辺の​おすすめスポットを​提案し、​最適ルートを​作成すること]** ができ、\
**[Google Map]** とは違って、\
**[安く楽しめる観光地のみを提案し、時間に合わせてルートを作成する機能]** が備わっている。

## 開発環境
- **フロントエンド** : html , css , Leaflet , JavaScript
- **バックエンド** : flask
- **データベース** : Neon PostgreSQL
- **タスク管理** : GitHub
- **マップ** : OpenStreetMap , Leaflet
- **距離計算** : OSRM

## 場所の管理

`/admin/places` から、場所の追加・JSONでの一括追加・一覧確認・削除ができる。
ブラウザの認証画面では、ユーザー名に `ramenmen`、パスワードに環境変数
`ADMIN_PASSWORD` の値を入力する。

JSONは画面内のテンプレートをコピーして作成する。一度に100件まで登録できる。
一覧では複数の場所を選択してまとめて削除できる。
