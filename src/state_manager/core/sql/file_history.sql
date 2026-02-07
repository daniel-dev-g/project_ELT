-- === FILE HISTORY QUERIES ===
-- Schema: {{schema}}

-- name: insert_file
INSERT INTO [{{schema}}].[file_history]
(execution_id, file_path, file_name, file_size_bytes,
 destination_table, deatination_schema,
 status, start_time)
OUTPUT INSERTED.file_id
VALUES (?, ?, ?, ?, ?, ?, 'PROCESSING', GETDATE());

-- name: update_file_success
UPDATE [{{schema}}].[file_history]
SET status = 'SUCCESS',
    rows_inserted = ?,
    duration_seconds = ?,
    end_time = GETDATE()
WHERE file_id = ?;

-- name: update_file_failed
UPDATE [{{schema}}].[file_history]
SET status = 'FAILED',
    error_message = ?,
    end_time = GETDATE()
WHERE file_id = ?;

-- name: select_file_stats
SELECT 
    COUNT(*) as total_files,
    SUM(CASE WHEN status = 'SUCCESS' THEN 1 ELSE 0 END) as successful_files,
    SUM(CASE WHEN status = 'FAILED' THEN 1 ELSE 0 END) as failed_files,
    SUM(ISNULL(rows_inserted, 0)) as total_rows
FROM [{{schema}}].[file_history]
WHERE execution_id = ?;