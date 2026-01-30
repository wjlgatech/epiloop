/**
 * Canvas Component for Autonomous Coding Progress
 * Shows real-time progress visualization for iOS/macOS Canvas interface
 */

import React, { useEffect, useState } from "react";

interface Story {
  id: string;
  title: string;
  passes: boolean;
  progress?: number;
}

interface ProgressData {
  projectName: string;
  currentStory: string | null;
  totalStories: number;
  completedStories: number;
  progressPercent: number;
  elapsedSeconds: number;
  stories: Story[];
  logs?: string[];
  status: "running" | "completed" | "error" | "paused";
}

interface AutonomousCodingProgressProps {
  sessionId: string;
  onPause?: () => void;
  onResume?: () => void;
  onAbort?: () => void;
}

export const AutonomousCodingProgress: React.FC<
  AutonomousCodingProgressProps
> = ({ sessionId, onPause, onResume, onAbort }) => {
  const [data, setData] = useState<ProgressData | null>(null);
  const [showLogs, setShowLogs] = useState(false);

  useEffect(() => {
    // Mock data - would connect to WebSocket in real implementation
    const mockData: ProgressData = {
      projectName: "autonomous-coding-integration",
      currentStory: "US-010",
      totalStories: 15,
      completedStories: 9,
      progressPercent: 60,
      elapsedSeconds: 3600,
      status: "running",
      stories: [
        { id: "US-001", title: "Extension structure", passes: true },
        { id: "US-002", title: "Claude-loop integration", passes: true },
        { id: "US-003", title: "PRD generator", passes: true },
        { id: "US-004", title: "Loop executor", passes: true },
        { id: "US-005", title: "Progress reporter", passes: true },
        { id: "US-006", title: "Skill integration", passes: true },
        { id: "US-007", title: "Workspace management", passes: true },
        { id: "US-008", title: "Experience store", passes: true },
        { id: "US-009", title: "Quality gates", passes: true },
        { id: "US-010", title: "Canvas visualization", passes: false, progress: 60 },
        { id: "US-011", title: "Parallel coordinator", passes: false },
        { id: "US-012", title: "Logging & metrics", passes: false },
        { id: "US-013", title: "Self-improvement", passes: false },
        { id: "US-014", title: "Documentation", passes: false },
        { id: "US-015", title: "E2E tests", passes: false },
      ],
      logs: [
        "[00:45:23] Starting US-010: Canvas visualization",
        "[00:45:24] Running tests...",
        "[00:45:30] Tests passed (15/15)",
        "[00:45:35] Implementing component...",
      ],
    };

    setData(mockData);
  }, [sessionId]);

  if (!data) {
    return <div className="loading">Loading progress...</div>;
  }

  const formatTime = (seconds: number): string => {
    const hours = Math.floor(seconds / 3600);
    const minutes = Math.floor((seconds % 3600) / 60);
    const secs = seconds % 60;
    return `${hours}h ${minutes}m ${secs}s`;
  };

  const getStatusColor = (status: string) => {
    switch (status) {
      case "running":
        return "#4CAF50";
      case "completed":
        return "#2196F3";
      case "error":
        return "#F44336";
      case "paused":
        return "#FF9800";
      default:
        return "#9E9E9E";
    }
  };

  return (
    <div style={styles.container}>
      {/* Header */}
      <div style={styles.header}>
        <h2 style={styles.title}>{data.projectName}</h2>
        <div
          style={{
            ...styles.statusBadge,
            backgroundColor: getStatusColor(data.status),
          }}
        >
          {data.status.toUpperCase()}
        </div>
      </div>

      {/* Progress Overview */}
      <div style={styles.overview}>
        <div style={styles.metric}>
          <span style={styles.metricLabel}>Progress</span>
          <span style={styles.metricValue}>{data.progressPercent}%</span>
        </div>
        <div style={styles.metric}>
          <span style={styles.metricLabel}>Stories</span>
          <span style={styles.metricValue}>
            {data.completedStories}/{data.totalStories}
          </span>
        </div>
        <div style={styles.metric}>
          <span style={styles.metricLabel}>Elapsed</span>
          <span style={styles.metricValue}>
            {formatTime(data.elapsedSeconds)}
          </span>
        </div>
      </div>

      {/* Progress Bar */}
      <div style={styles.progressBarContainer}>
        <div
          style={{
            ...styles.progressBar,
            width: `${data.progressPercent}%`,
          }}
        />
      </div>

      {/* Story Grid */}
      <div style={styles.storyGrid}>
        {data.stories.map((story) => (
          <div
            key={story.id}
            style={{
              ...styles.storyCard,
              borderColor:
                story.id === data.currentStory
                  ? "#2196F3"
                  : story.passes
                  ? "#4CAF50"
                  : "#E0E0E0",
              backgroundColor:
                story.id === data.currentStory
                  ? "#E3F2FD"
                  : story.passes
                  ? "#E8F5E9"
                  : "#FAFAFA",
            }}
          >
            <div style={styles.storyHeader}>
              <span style={styles.storyId}>{story.id}</span>
              <span style={styles.storyStatus}>
                {story.passes ? "✅" : story.id === data.currentStory ? "⏳" : "⏹"}
              </span>
            </div>
            <div style={styles.storyTitle}>{story.title}</div>
            {story.progress !== undefined && (
              <div style={styles.miniProgressBar}>
                <div
                  style={{
                    ...styles.miniProgress,
                    width: `${story.progress}%`,
                  }}
                />
              </div>
            )}
          </div>
        ))}
      </div>

      {/* Controls */}
      <div style={styles.controls}>
        {data.status === "running" ? (
          <button style={styles.button} onClick={onPause}>
            ⏸ Pause
          </button>
        ) : data.status === "paused" ? (
          <button style={styles.button} onClick={onResume}>
            ▶ Resume
          </button>
        ) : null}
        <button
          style={{ ...styles.button, ...styles.dangerButton }}
          onClick={onAbort}
        >
          ⏹ Abort
        </button>
        <button style={styles.button} onClick={() => setShowLogs(!showLogs)}>
          {showLogs ? "Hide" : "Show"} Logs
        </button>
      </div>

      {/* Logs Panel */}
      {showLogs && (
        <div style={styles.logsPanel}>
          <h3 style={styles.logsTitle}>Execution Logs</h3>
          <div style={styles.logsContent}>
            {data.logs?.map((log, i) => (
              <div key={i} style={styles.logLine}>
                {log}
              </div>
            ))}
          </div>
        </div>
      )}
    </div>
  );
};

// Styles
const styles: Record<string, React.CSSProperties> = {
  container: {
    fontFamily: "-apple-system, BlinkMacSystemFont, 'Segoe UI', sans-serif",
    padding: "20px",
    maxWidth: "900px",
    margin: "0 auto",
  },
  header: {
    display: "flex",
    justifyContent: "space-between",
    alignItems: "center",
    marginBottom: "20px",
  },
  title: {
    fontSize: "24px",
    fontWeight: "600",
    margin: 0,
  },
  statusBadge: {
    padding: "6px 12px",
    borderRadius: "12px",
    color: "white",
    fontSize: "12px",
    fontWeight: "600",
  },
  overview: {
    display: "flex",
    gap: "20px",
    marginBottom: "20px",
  },
  metric: {
    flex: 1,
    display: "flex",
    flexDirection: "column",
    padding: "15px",
    backgroundColor: "#F5F5F5",
    borderRadius: "8px",
  },
  metricLabel: {
    fontSize: "12px",
    color: "#757575",
    marginBottom: "5px",
  },
  metricValue: {
    fontSize: "24px",
    fontWeight: "600",
    color: "#212121",
  },
  progressBarContainer: {
    width: "100%",
    height: "8px",
    backgroundColor: "#E0E0E0",
    borderRadius: "4px",
    overflow: "hidden",
    marginBottom: "20px",
  },
  progressBar: {
    height: "100%",
    backgroundColor: "#4CAF50",
    transition: "width 0.3s ease",
  },
  storyGrid: {
    display: "grid",
    gridTemplateColumns: "repeat(auto-fill, minmax(200px, 1fr))",
    gap: "12px",
    marginBottom: "20px",
  },
  storyCard: {
    padding: "12px",
    borderRadius: "8px",
    border: "2px solid",
    transition: "all 0.2s ease",
  },
  storyHeader: {
    display: "flex",
    justifyContent: "space-between",
    alignItems: "center",
    marginBottom: "8px",
  },
  storyId: {
    fontSize: "12px",
    fontWeight: "600",
    color: "#616161",
  },
  storyStatus: {
    fontSize: "16px",
  },
  storyTitle: {
    fontSize: "13px",
    color: "#424242",
    lineHeight: "1.4",
  },
  miniProgressBar: {
    marginTop: "8px",
    height: "4px",
    backgroundColor: "#E0E0E0",
    borderRadius: "2px",
    overflow: "hidden",
  },
  miniProgress: {
    height: "100%",
    backgroundColor: "#2196F3",
    transition: "width 0.3s ease",
  },
  controls: {
    display: "flex",
    gap: "10px",
    marginBottom: "20px",
  },
  button: {
    padding: "10px 20px",
    borderRadius: "6px",
    border: "none",
    backgroundColor: "#2196F3",
    color: "white",
    fontSize: "14px",
    fontWeight: "500",
    cursor: "pointer",
  },
  dangerButton: {
    backgroundColor: "#F44336",
  },
  logsPanel: {
    backgroundColor: "#FAFAFA",
    borderRadius: "8px",
    padding: "15px",
    border: "1px solid #E0E0E0",
  },
  logsTitle: {
    fontSize: "16px",
    fontWeight: "600",
    marginBottom: "10px",
  },
  logsContent: {
    fontFamily: "Monaco, 'Courier New', monospace",
    fontSize: "12px",
    backgroundColor: "#1E1E1E",
    color: "#D4D4D4",
    padding: "12px",
    borderRadius: "4px",
    maxHeight: "200px",
    overflowY: "auto",
  },
  logLine: {
    marginBottom: "4px",
  },
};

export default AutonomousCodingProgress;
