CREATE DATABASE IF NOT EXISTS log_analysis
  DEFAULT CHARACTER SET utf8mb4
  COLLATE utf8mb4_unicode_ci;

USE log_analysis;

CREATE TABLE IF NOT EXISTS access_logs (
  id BIGINT UNSIGNED NOT NULL AUTO_INCREMENT,
  log_time DATETIME NOT NULL,
  log_date DATE GENERATED ALWAYS AS (DATE(log_time)) STORED,
  client_ip VARCHAR(45) NOT NULL,
  request_method VARCHAR(10) NOT NULL,
  api_path VARCHAR(255) NOT NULL,
  status SMALLINT UNSIGNED NOT NULL,
  response_time_ms INT UNSIGNED NOT NULL,
  user_agent VARCHAR(512) NOT NULL DEFAULT '',
  PRIMARY KEY (id),
  KEY idx_date_status (log_date, status),
  KEY idx_api_path (api_path),
  KEY idx_client_ip (client_ip),
  KEY idx_response_time (response_time_ms)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4;

