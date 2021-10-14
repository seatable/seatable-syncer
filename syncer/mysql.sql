CREATE TABLE `sync_jobs` (
  `id` int(11) NOT NULL AUTO_INCREMENT,
  `name` varchar(255) NOT NULL,
  `dtable_uuid` varchar(32) NOT NULL,
  `api_token` varchar(500) NOT NULL DEFAULT '',
  `trigger_detail` varchar(255) NOT NULL DEFAULT '',
  `job_type` varchar(50) NOT NULL DEFAULT '',
  `detail` text NOT NULL DEFAULT '',
  `last_trigger_time` datetime(6) DEFAULT NULL,
  `is_valid` tinyint(1) DEFAULT 1,
  PRIMARY KEY (`id`),
  KEY `dtable_uuid_b3m9h4f7_key` (`dtable_uuid`),
  KEY `is_valid_b4g7k2p9_key` (`is_valid`),
  KEY `job_type_h3l9u7g4_key` (`job_type`)
) ENGINE=InnoDB DEFAULT CHARSET=utf8;