# simbrief-to-rfs

Simbriefで生成されたフライトプランを、RFS(Real Flight Simulator)で使用できるように変換する

## 使い方

1. Simbriefでフライトプランを作成する。
2. STARルートの高度を詳細に設定する場合は、star_data.jsonに直接記入しておく。
   - 例:

     ```json

     {
      "airport_ident": "YSSY",
      "star_ident": "BORE4A",
      "data": [
        {
          "name": "BOREE",
          "upper": null,
          "lower": 9000
        },
        {
          "name": "VASRA",
          "upper": null,
          "lower": 8000
        },
        {
          "name": "BEROW",
          "upper": 9000,
          "lower": null
        },
        {
          "name": "ZONKA",
          "upper": null,
          "lower": 6000
        }
      ]
    }

     ```json

3. `python app.py`を実行する。
