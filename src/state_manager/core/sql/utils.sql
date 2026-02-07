-- === UTILITY QUERIES ===

-- name: get_last_insert_id
SELECT SCOPE_IDENTITY();

-- name: check_table_exists
SELECT 1 
FROM INFORMATION_SCHEMA.TABLES 
WHERE TABLE_SCHEMA = ? 
  AND TABLE_NAME = ?;