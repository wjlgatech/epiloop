# Progress Indicators (US-001)

Real-time progress indicators for claude-loop showing current story, completion percentage, time tracking, and acceptance criteria checklist with visual progress bars and color coding.

## Overview

The progress indicators feature provides a rich terminal UI that gives you real-time feedback on:
- Current story being implemented
- Overall progress (completed vs total stories)
- Time elapsed and estimated time remaining
- Current action being performed
- Acceptance criteria checklist with visual status indicators

## Features

### Visual Progress Bar

Shows completion percentage with color coding:
- **Green**: On track, making good progress
- **Yellow**: Delayed, taking longer than expected
- **Red**: Blocked or significantly delayed

### Acceptance Criteria Checklist

Each story's acceptance criteria is displayed with status indicators:
- ✅ **Done**: Criterion completed
- ⏳ **In Progress**: Currently working on this criterion
- ○ **Pending**: Not yet started

### Time Tracking

- **Elapsed Time**: Time since claude-loop started
- **Estimated Remaining**: Based on story velocity (average time per story)

### Current Action Display

Shows what claude-loop is currently doing:
- "Preparing iteration prompt..."
- "Running Claude Code iteration..."
- "Writing tests..."
- "Running linter..."

### Terminal Resize Handling

The UI gracefully handles terminal resize events (SIGWINCH) and redraws automatically.

## Usage

### Enable (Default)

Progress indicators are enabled by default:

```bash
./claude-loop.sh
```

### Disable for CI/CD

Use the `--no-progress` flag to disable progress indicators in CI/CD environments or when piping output:

```bash
./claude-loop.sh --no-progress
```

### Non-TTY Behavior

When output is not a TTY (e.g., redirected to a file), progress indicators automatically fall back to simple log messages:

```bash
./claude-loop.sh > output.log  # Automatically uses simple logging
```

## Implementation Details

### Core Module

The progress indicators are implemented in `lib/progress-indicators.sh`, which provides:

- `init_progress(prd_file)` - Initialize progress tracking
- `start_story(story_id, story_title, acceptance_criteria...)` - Start tracking a story
- `set_current_action(action)` - Update the current action
- `mark_criterion_done(index)` - Mark an acceptance criterion as complete
- `mark_criterion_in_progress(index)` - Mark a criterion as in progress
- `complete_story()` - Mark the current story as complete
- `disable_progress()` / `enable_progress()` - Toggle progress indicators

### Integration with claude-loop.sh

The progress indicators are integrated at key points in the execution flow:

1. **Initialization** (line ~2808): Source the library and call `init_progress`
2. **Story Start** (line ~2079): Call `start_story` with acceptance criteria
3. **During Execution** (line ~2125): Update current action
4. **Story Completion** (line ~2161): Call `complete_story`

### Color and Unicode Detection

The module automatically detects terminal capabilities:
- Colors are disabled if output is not a TTY or `tput` is unavailable
- Unicode symbols fall back to ASCII if the locale doesn't support UTF-8

## Configuration

### Environment Variables

- `PROGRESS_ENABLED` - Set to "false" to disable (same as --no-progress flag)

### Customization

You can customize the progress indicators by modifying `lib/progress-indicators.sh`:
- Change color codes (lines 22-34)
- Modify symbols (lines 37-47)
- Adjust progress bar width (default: 40 characters)
- Change time thresholds for color coding (yellow at 5min, red at 10min)

## Examples

### Basic Usage

```bash
$ ./claude-loop.sh
╔════════════════════════════════════════════════════════════════╗
║ Current Story: US-001
║
║ Overall Progress: [████████████████░░░░░░░░] 60% (3/5 stories)
║ Time: 15m 30s elapsed | ~10m 20s remaining
║ Currently: Running Claude Code iteration...
║
║ Acceptance Criteria:
║   ✅ Create lib/progress-indicators.sh with functions
║   ✅ Add real-time acceptance criteria checklist display
║   ⏳ Implement visual progress bar with color coding
║   ○ Add time tracking
║   ○ Integrate with existing claude-loop.sh main loop
╚════════════════════════════════════════════════════════════════╝
```

### CI/CD Mode

```bash
$ ./claude-loop.sh --no-progress
[INFO] Project: my-feature
[INFO] Stories: 5 incomplete out of 5 total
[ITERATION 1/10] Stories remaining: 5
[INFO] Working on: US-001 - Create User Model
[SUCCESS] Story US-001 completed
```

## Performance

The progress indicators are designed to be lightweight:
- UI redraws are debounced to avoid excessive rendering
- Non-TTY detection ensures no overhead when piping output
- Estimated overhead: <1% of total execution time

## Terminal Compatibility

Tested on:
- ✅ iTerm2 (macOS)
- ✅ Terminal.app (macOS)
- ✅ xterm (Linux)
- ✅ VS Code integrated terminal
- ✅ tmux
- ✅ screen

## Troubleshooting

### Colors not showing

Make sure your terminal supports colors and `tput` is available:

```bash
tput colors  # Should output a number >= 8
```

### Unicode symbols not rendering

Check your locale settings:

```bash
echo $LANG  # Should contain "UTF-8"
locale      # Should show UTF-8 encoding
```

If UTF-8 is not available, the progress indicators will automatically fall back to ASCII symbols.

### Progress bar flickering

This can happen on slow terminals or when output is very frequent. The module tries to minimize redraws, but if flickering persists, consider using `--no-progress`.

### Terminal resize not working

The resize handler uses the `WINCH` signal. If it's not working:
1. Check that your terminal supports SIGWINCH
2. Verify that the `trap` command is working: `trap -p WINCH`

## Future Enhancements

Potential improvements for future versions:
- Estimated time remaining per acceptance criterion
- Historical velocity tracking across runs
- Configurable refresh rate
- Mouse interaction support (click to expand/collapse)
- Export progress snapshots for monitoring dashboards

## Related Features

- **Progress Dashboard** (INV-006): Provides a dashboard view of progress
- **Compact Dashboard**: Single-line progress display (`--compact-dashboard`)
- **Session State** (INV-007): Persists progress across runs

## See Also

- [claude-loop.sh Documentation](../README.md)
- [Quality Gates](quality-gates.md)
- [Session State Management](session-state.md)
