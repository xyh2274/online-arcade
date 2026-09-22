CREATE TABLE IF NOT EXISTS `input_mappings` (
	`user_id` integer PRIMARY KEY NOT NULL,
	`keyboard` text DEFAULT '{}' NOT NULL,
	`gamepad` text DEFAULT '{}' NOT NULL,
	`pad_native_only` integer DEFAULT 1 NOT NULL,
	`updated_at` integer DEFAULT (unixepoch()) NOT NULL,
	FOREIGN KEY (`user_id`) REFERENCES `users`(`id`) ON UPDATE no action ON DELETE cascade
);
--> statement-breakpoint
CREATE INDEX IF NOT EXISTS `idx_input_mappings_user` ON `input_mappings` (`user_id`);
