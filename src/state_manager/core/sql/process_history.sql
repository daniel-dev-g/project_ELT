-- === PROCESS HISTORY QUERIES ===
-- Schema: {{schema}}

-- name: insert_process
INSERT INTO [{{schema}}].[process_history]
(execution_id, start_time, status)
VALUES (?, GETDATE(), 'RUNNING');

-- name: update_process_complete
UPDATE [{{schema}}].[process_history]
SET status = ?,
    end_time = GETDATE(),
    total_files = ?,
    successful_files = ?,
    failed_files = ?,
    total_rows_inserted = ?
WHERE execution_id = ?;

-- name: select_process_summary
SELECT 
    p.execution_id,
    p.start_time,
    p.end_time,
    p.status,
    p.total_files,
    p.successful_files,
    p.failed_files,
    p.total_rows_inserted,
    p.total_duration_seconds
FROM [{{schema}}].[process_history] p
WHERE p.execution_id = ?;