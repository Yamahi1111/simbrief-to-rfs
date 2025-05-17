import requests
import xml.etree.ElementTree as ET
import json

# Adjusts the altitude (in feet) of a waypoint based on STAR data conditions.
# 'star_data' is expected to be a list of dicts with keys: 'name', 'upper', 'lower'.
def adjust_star(altitude_ft, ident, star_data):
    for star in star_data:
        if star["name"] == ident:
            upper = star.get("upper")  # Upper altitude limit in feet
            lower = star.get("lower")  # Lower altitude limit in feet
            if upper is not None and lower is None:
                if altitude_ft > upper:
                    altitude_ft = upper
            elif lower is not None and upper is None:
                if altitude_ft < lower:
                    altitude_ft = lower
            elif upper is not None and lower is not None:
                if altitude_ft < lower or altitude_ft > upper:
                    altitude_ft = (upper + lower) / 2.0
            break
    return altitude_ft

def main():
    # === (1) SimBrief からデータ取得 & パース ===
    url = "https://www.simbrief.com/api/xml.fetcher.php?username=yamahi"
    response = requests.get(url)
    xml_data = response.text
    root = ET.fromstring(xml_data)

    with open("/Users/yzhy/Downloads/SimbriefToRFS/xml_data.xml", "w", encoding="utf-8") as xml_file:
        xml_file.write(xml_data)

    # STARデータの読み込み
    star_file_path = "/Users/yzhy/Downloads/SimbriefToRFS/star_data.json"
    try:
        with open(star_file_path, "r", encoding="utf-8") as sf:
            star_all = json.load(sf)
    except Exception as e:
        print("STARデータファイルが読み込めませんでした:", e)
        star_all = None

    # XMLからSTARの識別子を取得（.//general/star_ident を使用）
    star_ident = root.findtext('.//general/star_ident')
    # STARコードが見つからない場合、ユーザーに確認して入力を促す
    if not star_ident:
        answer = input("XMLにSTARコードが存在しません。STARコードはありますか？ (y/n): ")
        if answer.lower().startswith("y"):
            star_ident = input("STARコードを入力してください: ")

    star_data = None
    if star_all is not None and star_ident:
        for star_entry in star_all:
            if star_entry.get("star_ident") == star_ident:
                star_data = star_entry.get("data")
                break
        if star_data is None:
            print("STARデータがありませんでした")
    else:
        print("STARデータがありませんでした")

    # 必要そうなデータを取得（例）
    origin_icao = root.findtext('.//origin/icao_code')      # 'MMMX' など
    origin_runway = root.findtext('.//origin/plan_rwy')     # '05R' など
    origin_lat = root.findtext('.//origin/pos_lat')             # '19.4363' など
    origin_long = root.findtext('.//origin/pos_long')           # '-99.0721' など

    dest_icao = root.findtext('.//destination/icao_code')   # 'MSLP' など
    dest_runway = root.findtext('.//destination/plan_rwy')  # '07' など

    aircraft = root.findtext('.//aircraft/icaocode')        # 'B737', 'B767' など
    aircraftBaseType = root.findtext('.//aircraft/base_type')
    if (aircraft == "A21N"):
        aircraft = "A321N"
    if (aircraft == "A359"):
        aircraft = "A350"
    if (aircraft == "A35K"):
        aircraft = "A3501"
    if (aircraft == "B763"):
        aircraft = "B767"
    if (aircraft == "B789"):
        aircraft = "B7879"
    if (aircraft == "B772"):
        aircraft = "B777"
    if (aircraft == "B77W"):
        aircraft = "B7773"
    if (aircraft == "B788"):
        aircraft = "B787"
    if (aircraft == "A388"):
        aircraft = "A380"
    if (aircraft == "C5M"):
        aircraft = "C5G"
    if (aircraftBaseType == "B76F"):
        aircraft = "B767F"
    if (aircraft == "B38M"):
        aircraft = "B737M"
    if (aircraft == "B78X"):
        aircraft = "B7871"
    if (aircraft == "B738"):
        aircraft = "B737"
    if (aircraft == "A20N"):
        aircraft = "A320N"
    if (aircraft == "B77L"):
        aircraft = "B7772L"
    if (aircraft == "B764"):
        aircraft = "B7674"
    fuel = root.findtext('.//fuel/plan_ramp')               # Ramp fuel
    payload = root.findtext('.//weights/payload')           # '10000' など

    # navlog の fix からウェイポイント一覧を作成
    fix_list = root.findall('.//navlog/fix')
    waypoints = []
    for fix in fix_list[:-1]:
        ident = fix.findtext('ident', default="N/A")
        latitude = fix.findtext('pos_lat', default="0.0")
        longitude = fix.findtext('pos_long', default="0.0")

        # XMLから取得した元の高度(フィート)を保持
        orig_altitude_ft = float(fix.findtext('altitude_feet', default="0"))
        altitude_ft = orig_altitude_ft

        # STARによる高度調整（STARデータが存在する場合）
        if star_data:
            altitude_ft = adjust_star(altitude_ft, ident, star_data)
        altitude_m = altitude_ft / 3.28084

        # XMLから取得した元のTAS (knots→m/s) を保持
        orig_tas = float(fix.findtext('true_airspeed', default="0")) * 0.5139534884
        tas = orig_tas

        # fix.findtext('distance')で、前のウェイポイントからの距離を取得
        distance = fix.findtext('distance', default="0")

        # 必要な項目に合わせて辞書生成
        waypoints.append({
            'ident': ident,
            'latitude': latitude,
            'longitude': longitude,
            'orig_altitude_ft': orig_altitude_ft,
            'altitude_m': str(altitude_m),
            'orig_tas': orig_tas,
            'tas': str(tas),
            'distance': distance
        })

    # 降下率のチェックと調整（各区間について一度だけ適用し、後続の変更に影響されないようにロックします）
    if star_data and len(waypoints) > 0:
        # 最後のウェイポイントは調整不要なのでロック
        waypoints[-1]['locked'] = True
        # 後方から順に各区間を調整
        for i in range(len(waypoints)-2, -1, -1):
            leg_distance = float(waypoints[i+1].get('distance', "0"))
            alt1_ft = float(waypoints[i]['altitude_m']) * 3.28084
            alt2_ft = float(waypoints[i+1]['altitude_m']) * 3.28084
            allowed_drop = leg_distance * 350  # 例：2マイルなら700フィート
            if alt1_ft - alt2_ft > allowed_drop:
                new_alt_ft = alt2_ft + allowed_drop
                waypoints[i]['altitude_m'] = str(new_alt_ft / 3.28084)
            # このウェイポイントは調整済みとしてロック
            waypoints[i]['locked'] = True

    # TOD以降のウェイポイントについてのみ、前のウェイポイントの高度が直後より低くなっている場合、
    # 直後のウェイポイントの高度を前のウェイポイントと同じにする処理
    tod_index = None
    for idx, wp in enumerate(waypoints):
        if wp['ident'] == "TOD":
            tod_index = idx
            break
    if tod_index is not None:
        for i in range(tod_index, len(waypoints)-1):
            alt_prev = float(waypoints[i]['altitude_m'])
            alt_next = float(waypoints[i+1]['altitude_m'])
            if alt_prev < alt_next:
                waypoints[i+1]['altitude_m'] = waypoints[i]['altitude_m']

    # STARのウェイポイント全体から、元の高度・TASの関係に基づいてTASを再計算する処理
    if star_data:
        # TAS再計算：TOD以降のウェイポイントすべてを参照データとして収集し、線形補間でTASを再計算する処理
        tod_index = None
        for idx, wp in enumerate(waypoints):
            if wp['ident'] == "TOD":
                tod_index = idx
                break
        if tod_index is not None:
            changed_refs = []
            # TOD以降のウェイポイントすべてから、(新高度, 元のTAS)のペアを収集
            for i in range(tod_index, len(waypoints)):
                wp = waypoints[i]
                changed_refs.append((wp['orig_altitude_ft'], float(wp['orig_tas'])))
            # 参照データが2点以上あれば、線形補間を行う
            if len(changed_refs) >= 2:
                # 高度が高いほど元のTASが高いと仮定し、降順にソート（高い高度順）
                changed_refs.sort(key=lambda x: x[0], reverse=True)
                for i in range(tod_index, len(waypoints)):
                    wp = waypoints[i]
                    new_alt_ft = float(wp['altitude_m']) * 3.28084
                    if new_alt_ft >= changed_refs[0][0]:
                        new_tas = changed_refs[0][1]
                    elif new_alt_ft <= changed_refs[-1][0]:
                        new_tas = changed_refs[-1][1]
                    else:
                        for j in range(len(changed_refs) - 1):
                            alt_high, tas_high = changed_refs[j]
                            alt_low, tas_low = changed_refs[j+1]
                            if alt_low <= new_alt_ft <= alt_high:
                                fraction = (new_alt_ft - alt_low) / (alt_high - alt_low)
                                new_tas = tas_low + (tas_high - tas_low) * fraction
                                break
                    wp['tas'] = str(new_tas)

    # identが"TOD"のウェイポイントで、調整後の高度が元の高度より下がっている場合、そのウェイポイントを削除
    filtered_waypoints = []
    for wp in waypoints:
        if wp['ident'] == "TOD":
            # 調整後の高度(ft)と元の高度(ft)を比較
            if (float(wp['altitude_m']) * 3.28084) < wp['orig_altitude_ft']:
                continue  # このウェイポイントは削除
        filtered_waypoints.append(wp)
    waypoints = filtered_waypoints


    # === (2) RFS用JSON構造の雛形を作成 ===
    # 下記は一例です。実際にはご提示の長大な JSON をベースに改変してください。

    # フライトプラン部分(J_FlightPlan)は RFS が "JSONを文字列" として持つので二重構造に注意
    # 例として、"selectedIdx" や "fPSingleSerializerList" など最低限の形を作ってみる
    fp_points = []
    for wp in waypoints:
        # RFSの各WPで必須となるキーはシミュレータ仕様に合わせてください
        # ここでは単純化した例
        fp_points.append({
            "Altitude": wp['altitude_m'],   # メートルにしている例
            "Speed": wp['tas'],            # ktなのかm/sなのか要注意(RFS側の仕様)
            "IsProcedure": "False",
            "Airport": "",                 # 出発地/到着地ならICAOを入れる
            "Latitude": wp['latitude'],
            "Longitude": wp['longitude'],
            "ident": wp['ident'],
            "type": "12",
            "isAirport": "False",
            "IconId": "2",
            "Description": "GPS-WP",
        })

    flight_plan_dict = {
        "selectedIdx": 0,
        "fPSingleSerializerList": [
            {
                "J_FPDepartureAirport": origin_icao,
                "J_FPArrivalAirport": dest_icao,
                "J_AssignedTakeoffRunway": origin_runway,
                "J_AssignedLandingRunway": dest_runway,
                "J_Sid": "",
                "J_SidTransition": "",
                "J_Star": "",
                "J_Approach": "",
                "J_ApproachTransition": "",
                "FPPoints": fp_points,
                "J_ArrivalAirportParkingPoint": ""
            }
        ]
    }

    # RFSでは "J_FlightPlan" に JSON文字列 として格納する
    flight_plan_json_str = json.dumps(flight_plan_dict)

    # 大枠の辞書 (実際にはもっと多数のキーが必要ですが省略)
    rfs_data = {
        "Livery": {
            "AircraftID": aircraft,
            "ID": "DEFAULT",
            "Version": 14,
            "Type": 0,
            "By": "Rortos",
            "Date": 1571702400,
            "IsFavorite": False,
            "Fps": 0,
            "Name": "DEFAULT"
        },
        "StartType": 0,
        "LevelConfig": {
            "LevelName": "Simulator",
            "TutorialID": None,
            "TutorialCheckpointStepIndex": 0,
            "TutorialCheckpointPreferences": None
        },
        # 例: タイトルを「機体_出発地_到着地_出発RWY到着RWY」の形にしてみる
        "Title": f"{aircraft}_{origin_icao}_{dest_icao}_{origin_runway}{dest_runway}",
        "Description": f"Reference: Fuel {fuel}kg against Payload {payload}kg",
        "Tags": "",
        "AircraftLoad": {
            "FuelQuantityNormalized": 0.0,  # 0.0 ~ 1.0 等 RFS仕様に合わせる
            "PassengersNumber": 0,
            "CargoLoad": 0,
            "MealsLoad": 0
        },
        "m_livery": {
            "AircraftID": aircraft,
            "ID": "DEFAULT",
            "Version": 14,
            "Type": 0,
            "By": "Rortos",
            "Date": 1571702400,
            "IsFavorite": False,
            "Fps": 0,
            "Name": "DEFAULT"
        },
        "InitialSpeed": 0.0,
        "InitialPosition": None,
        "InitialAltitude": 0.0,
        "InitialHeading": 0.0,
        "InitialWaypointIdent": "",
        "DepartureGate": False,
        "SpawnPoint": {
            "Coordinate": {
                "x": float(origin_long),
                "y": float(origin_lat)
            },
            "Type": 1,
            "ID": "33312",
            "Latitude": float(origin_lat),
            "Longitude": float(origin_long)
        },
        "ProNeeded": False,
        "Seed": 1703580569,
        "J_AircraftID": aircraft,
        "J_StartReferenceAirportID": origin_icao,
        # ★ RFS の仕様上、ここは JSON を「文字列」としてセットする
        "J_FlightPlan": flight_plan_json_str,

        "ActivityType": 0,
        "FlightActivityWeather": 1,
        "UniformWeather": {
            "Wind": 0.0,
            "Coordinate": {
                "x": 0.0,
                "y": 45.0
            },
            "Ident": "",
            "WeatherType": 0,
            "CloudType": 0,
            "CloudsBase": 1499.92078,
            "QNH": 1013,
            "_wind": 0.0,
            "WindDirection": 0.0,
            "TurbulenceNormalized": 0.0,
            "RefAltitude": 0.0,
            "Temperature": 20.0,
            "DevTemperature": 0.0,
            "FogIntensityNormalized": 0.0,
            "SnowCoverage": 0,
            "VisibilityMeters": 9999.0,
            "Latitude": 45.0,
            "Longitude": 0.0
        },
        "ActivityDate": "2025-02-11T03:55:07",
        "DateIsReal": False,
        "ActivityHandlerCheckersManager": {
            "DepartureAirportsCheckersManagers": {
                "EveryCheckPassedInOR": True,
                "EveryCheckPassedInAND": True,
                "NumbersOfCheck": 0,
                "m_Checkers": []
            },
            "ArrivalAirportsCheckersManagers": {
                "EveryCheckPassedInOR": True,
                "EveryCheckPassedInAND": True,
                "NumbersOfCheck": 0,
                "m_Checkers": []
            }
        }
    }

    # === (3) JSONとして .rfsファイル に書き出し ===
    #   Python上では普通のJSONファイル出力と同じ
    filename = "/Users/yzhy/Library/Mobile Documents/com~apple~CloudDocs/Downloads/flightPlan.rfs"
    with open(filename, "w", encoding="utf-8") as f:
        # indent=2 で整形, ensure_ascii=False で日本語などもOK
        json.dump(rfs_data, f, indent=2, ensure_ascii=False)

    print(f"{filename} を生成しました！")

if __name__ == "__main__":
    main()
