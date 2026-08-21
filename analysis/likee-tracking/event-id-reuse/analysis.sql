SELECT event_id, COUNT(*) AS definition_count, COUNT(DISTINCT action_name) AS action_name_count FROM data GROUP BY event_id ORDER BY definition_count DESC, event_id LIMIT 20
