CREATE TABLE `email_sync_jobs` (
  `id` int(11) NOT NULL AUTO_INCREMENT,
  `name` varchar(255) NOT NULL,
  `dtable_uuid` varchar(32) NOT NULL,
  `api_token` varchar(50) NOT NULL,
  `schedule_detail` varchar(255) NOT NULL DEFAULT '',
  `imap_server` varchar(255) NOT NULL,
  `email_user` varchar(255) NOT NULL,
  `email_password` varchar(255) NOT NULL,
  `email_table_name` varchar(255) NOT NULL,
  `link_table_name` varchar(255) NOT NULL,
  `last_trigger_time` datetime(6) DEFAULT NULL,
  `is_valid` tinyint(1) DEFAULT 1,
  PRIMARY KEY (`id`),
  UNIQUE KEY `dtable_uuid_email_table_name_link_table_name_n3j7g5t2_uniq_key` (`dtable_uuid`,`email_table_name`,`link_table_name`),
  KEY `dtable_uuid_b3m9h4f7_key` (`dtable_uuid`),
  KEY `is_valid_b4g7k2p9_key` (`is_valid`)
) ENGINE=InnoDB DEFAULT CHARSET=utf8;