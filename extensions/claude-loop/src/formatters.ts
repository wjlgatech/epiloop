/**
 * Formatting utilities for progress reporter
 */

/**
 * Format duration in seconds to human-readable string
 */
export function formatDuration(seconds: number): string {
  if (seconds < 60) {
    return `${seconds}s`;
  } else if (seconds < 3600) {
    const minutes = Math.floor(seconds / 60);
    const remainingSeconds = seconds % 60;
    return remainingSeconds > 0 ? `${minutes}m ${remainingSeconds}s` : `${minutes}m`;
  } else {
    const hours = Math.floor(seconds / 3600);
    const minutes = Math.floor((seconds % 3600) / 60);
    return minutes > 0 ? `${hours}h ${minutes}m` : `${hours}h`;
  }
}

/**
 * Create a text-based progress bar
 */
export function createProgressBar(percent: number, width: number = 20): string {
  const filled = Math.round((percent / 100) * width);
  const empty = width - filled;
  return "█".repeat(filled) + "░".repeat(empty);
}

/**
 * Truncate text to max length with ellipsis
 */
export function truncate(text: string, maxLength: number): string {
  if (text.length <= maxLength) {
    return text;
  }
  return text.substring(0, maxLength - 3) + "...";
}

/**
 * Format file list for display
 */
export function formatFileList(files: string[], maxFiles: number = 5): string {
  if (files.length <= maxFiles) {
    return files.join(", ");
  }
  const shown = files.slice(0, maxFiles);
  const remaining = files.length - maxFiles;
  return `${shown.join(", ")}, and ${remaining} more`;
}

/**
 * Pluralize a word based on count
 */
export function pluralize(word: string, count: number): string {
  return count === 1 ? word : `${word}s`;
}
