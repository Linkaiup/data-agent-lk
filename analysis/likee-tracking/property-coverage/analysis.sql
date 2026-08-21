SELECT action_name, COUNT(*) AS definition_count, ROUND(AVG(LENGTH(map_keys)), 1) AS avg_map_keys_characters FROM data GROUP BY action_name ORDER BY avg_map_keys_characters DESC
