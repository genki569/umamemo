-- レース基本情報のインポート用テーブル
CREATE TEMPORARY TABLE temp_race_import (
    race_name VARCHAR(100),
    race_number INT,
    date VARCHAR(20),
    venue_details VARCHAR(100),
    start_time VARCHAR(10),
    race_details TEXT,
    results TEXT
);

-- CSVからの一時テーブルへのデータ読み込み
LOAD DATA INFILE 'netkeiba_2024_race_details_20241116.csv'
INTO TABLE temp_race_import
FIELDS TERMINATED BY ','
ENCLOSED BY '"'
LINES TERMINATED BY '\n'
IGNORE 1 LINES;

-- レース情報の抽出とracesテーブルへの挿入
INSERT INTO races (
    name,
    race_number,
    date,
    venue,
    start_time,
    track_type,
    distance,
    direction,
    weather,
    track_condition
)
SELECT 
    race_name,
    race_number,
    date,
    venue_details,
    start_time,
    CASE 
        WHEN race_details LIKE '%ダ%' THEN 'ダート'
        WHEN race_details LIKE '%芝%' THEN '芝'
    END as track_type,
    CAST(REGEXP_SUBSTR(race_details, '\\d+(?=m)') AS UNSIGNED) as distance,
    CASE 
        WHEN race_details LIKE '%左%' THEN '左'
        WHEN race_details LIKE '%右%' THEN '右'
    END as direction,
    REGEXP_SUBSTR(race_details, '天候 : ([^/]+)', 1, 1, '', 1) as weather,
    REGEXP_SUBSTR(race_details, 'ダート : ([^/]+)|芝 : ([^/]+)', 1, 1, '', 1) as track_condition
FROM temp_race_import
ON DUPLICATE KEY UPDATE
    name = VALUES(name),
    start_time = VALUES(start_time);

-- 結果データの正規化と各テーブルへの挿入
-- 騎手データの抽出と挿入
INSERT INTO jockeys (name)
SELECT DISTINCT 
    JSON_UNQUOTE(JSON_EXTRACT(result.value, '$.騎手')) as jockey_name
FROM temp_race_import,
JSON_TABLE(results, '$[*]' COLUMNS (value JSON PATH '$')) as result
ON DUPLICATE KEY UPDATE name = VALUES(name);

-- 馬データの抽出と挿入
INSERT INTO horses (
    name,
    sex,
    age,
    trainer,
    owner
)
SELECT DISTINCT 
    JSON_UNQUOTE(JSON_EXTRACT(result.value, '$.馬名')),
    LEFT(JSON_UNQUOTE(JSON_EXTRACT(result.value, '$.性齢')), 1),
    CAST(RIGHT(JSON_UNQUOTE(JSON_EXTRACT(result.value, '$.性齢')), 1) AS UNSIGNED),
    JSON_UNQUOTE(JSON_EXTRACT(result.value, '$.調教師')),
    JSON_UNQUOTE(JSON_EXTRACT(result.value, '$.馬主'))
FROM temp_race_import,
JSON_TABLE(results, '$[*]' COLUMNS (value JSON PATH '$')) as result
ON DUPLICATE KEY UPDATE
    trainer = VALUES(trainer),
    owner = VALUES(owner);

-- エントリーデータの挿入
INSERT INTO entries (
    race_id,
    horse_id,
    jockey_id,
    horse_number,
    post_position,
    weight_carried,
    finish_time,
    order_of_finish,
    margin,
    passing_order,
    last_3f,
    odds,
    popularity,
    horse_weight
)
SELECT 
    r.id as race_id,
    h.id as horse_id,
    j.id as jockey_id,
    CAST(JSON_UNQUOTE(JSON_EXTRACT(result.value, '$.馬番')) AS UNSIGNED),
    CAST(JSON_UNQUOTE(JSON_EXTRACT(result.value, '$.枠番')) AS UNSIGNED),
    CAST(JSON_UNQUOTE(JSON_EXTRACT(result.value, '$.斤量')) AS DECIMAL(4,1)),
    JSON_UNQUOTE(JSON_EXTRACT(result.value, '$.タイム')),
    CAST(JSON_UNQUOTE(JSON_EXTRACT(result.value, '$.着順')) AS UNSIGNED),
    JSON_UNQUOTE(JSON_EXTRACT(result.value, '$.着差')),
    JSON_UNQUOTE(JSON_EXTRACT(result.value, '$.通過')),
    CAST(JSON_UNQUOTE(JSON_EXTRACT(result.value, '$.上り')) AS DECIMAL(4,1)),
    CAST(JSON_UNQUOTE(JSON_EXTRACT(result.value, '$.単勝')) AS DECIMAL(6,1)),
    CAST(JSON_UNQUOTE(JSON_EXTRACT(result.value, '$.人気')) AS UNSIGNED),
    REGEXP_SUBSTR(JSON_UNQUOTE(JSON_EXTRACT(result.value, '$.馬体重')), '^\\d+')
FROM temp_race_import t
JOIN races r ON r.name = t.race_name AND r.date = t.date AND r.race_number = t.race_number,
JSON_TABLE(t.results, '$[*]' COLUMNS (value JSON PATH '$')) as result
JOIN horses h ON h.name = JSON_UNQUOTE(JSON_EXTRACT(result.value, '$.馬名'))
JOIN jockeys j ON j.name = JSON_UNQUOTE(JSON_EXTRACT(result.value, '$.騎手'))
ON DUPLICATE KEY UPDATE
    weight_carried = VALUES(weight_carried),
    finish_time = VALUES(finish_time),
    order_of_finish = VALUES(order_of_finish),
    margin = VALUES(margin),
    passing_order = VALUES(passing_order),
    last_3f = VALUES(last_3f),
    odds = VALUES(odds),
    popularity = VALUES(popularity),
    horse_weight = VALUES(horse_weight);

-- 一時テーブルの削除
DROP TEMPORARY TABLE IF EXISTS temp_race_import; 