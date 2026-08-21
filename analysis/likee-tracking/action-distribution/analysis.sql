SELECT action_name, COUNT(*) AS definition_count, COUNT(DISTINCT event_id) AS event_id_count FROM data GROUP BY action_name ORDER BY definition_count DESC
